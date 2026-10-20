"""Kill an actual check supervisor and reconcile preserved evidence without stale success."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from darkfactory.domain import CheckSpec, Policy
from darkfactory.execution import bounded_process
from darkfactory.resources import Resources
from darkfactory.services import Factory
from darkfactory.storage import Store
from darkfactory.verification import Verifier
from tests.test_contracts import blueprint


@pytest.mark.docker
def test_killed_check_has_durable_aborted_evidence_and_live_owner_is_protected(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "state")
    source = tmp_path / "source"
    source.mkdir()
    check = CheckSpec(
        id="slow",
        kind="test",
        argv=["python", "-I", "{driver}"],
        driver="import time\ntime.sleep(60)\nprint('completed')\n",
        expected_output="completed",
    )
    proposal = blueprint().model_copy(update={"image": "python:3.12-slim", "checks": [check]})
    project = Factory(store).propose(proposal, Policy(required_check_kinds=["test"]), source)
    digest = json.loads((store.root / "projects" / project / "initial.json").read_text())[
        "source_digest"
    ]
    process = subprocess.Popen(
        [
            sys.executable,
            "-I",
            str(Path(__file__).with_name("check_fixture.py")),
            str(store.root),
            project,
            digest,
        ],
        cwd=Path(__file__).resolve().parents[1],
    )
    try:
        deadline = time.monotonic() + 30
        running = None
        resources = []
        while time.monotonic() < deadline:
            rows = Verifier(store).records(project)
            with store.connection() as connection:
                resources = connection.execute(
                    "SELECT intent FROM operations WHERE project_id=? "
                    "AND kind='docker-resource' AND state='ACTIVE'",
                    (project,),
                ).fetchall()
            if rows and resources:
                name = json.loads(resources[0][0])["name"]
                running = bounded_process(
                    ["docker", "inspect", "--format", "{{.State.Running}}", name],
                    timeout=5,
                    output_bytes=1024,
                )
                if running.exit_code == 0 and running.stdout.strip() == "true":
                    break
            assert process.poll() is None, (
                "check fixture exited before creating its protected intent"
            )
            time.sleep(0.05)
        assert rows and resources and running and running.stdout.strip() == "true"
        assert not rows[0]["passed"]
        assert Verifier(store).reconcile(project) == 0
        os.kill(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
        Resources(store, project).reap()
        assert Verifier(Store(store.root)).reconcile(project) == 1
        assert Verifier(store).reconcile(project) == 0
        result = json.loads(Verifier(store).records(project)[0]["result"])
        assert result["aborted"] and result["exit_code"] == -1
        assert not Verifier(store).gate(project, digest).allowed
        assert store.verify_audit()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        Resources(store, project).reap()
