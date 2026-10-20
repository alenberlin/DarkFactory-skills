"""Kill a real supervisor process and reconcile its actual orphaned Docker resource."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from darkfactory.resources import Resources
from darkfactory.storage import Store
from tests.test_engine import FixtureAdapter
from tests.test_remediation import prepared
from tests.test_store import prepared_store


@pytest.mark.docker
def test_actual_supervisor_kill_reaps_only_its_journaled_container(tmp_path: Path) -> None:
    store, project = prepared_store(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    marker = tmp_path / "started.json"
    script = (
        "from pathlib import Path\nimport json,time\n"
        "from darkfactory.execution import DockerExecutor\n"
        "from darkfactory.domain import Limits\n"
        "from darkfactory.resources import Resources\n"
        "from darkfactory.storage import Store\n"
        f"store=Store(Path({str(store.root)!r}))\n"
        f"resources=Resources(store,{project!r})\n"
        f"Path({str(marker)!r}).write_text(json.dumps({{'pid':__import__('os').getpid()}}))\n"
        f"DockerExecutor('python:3.12-slim',resources).run(Path({str(source)!r}),"
        "['python','-c','import time; time.sleep(120)'],"
        "Limits(command_seconds=120),readonly=True)\n"
    )
    process = subprocess.Popen([sys.executable, "-c", script], start_new_session=True)
    name = None
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with store.connection() as connection:
                row = connection.execute(
                    "SELECT intent FROM operations WHERE kind='docker-resource' AND state='ACTIVE'"
                ).fetchone()
            if row:
                name = json.loads(row[0])["name"]
                probe = subprocess.run(
                    ["docker", "inspect", "--format", "{{.State.Running}}", name],
                    capture_output=True,
                    text=True,
                )
                if probe.returncode == 0 and probe.stdout.strip() == "true":
                    break
            time.sleep(0.05)
        assert name is not None
        assert process.poll() is None
        assert Resources(store, project).reap() == 0
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
        assert Resources(Store(store.root), project).reap() == 1
        probe = subprocess.run(["docker", "inspect", name], capture_output=True, text=True)
        assert probe.returncode != 0
        assert store.verify_audit()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        Resources(store, project).reap()


@pytest.mark.docker
def test_actual_factory_worker_restart_rehydrates_checkpoint_and_fences_old_owner(
    tmp_path: Path,
) -> None:
    factory, project = prepared(tmp_path, lambda a, b, c, role: FixtureAdapter(role))
    command = [sys.executable, "-m", "tests.worker_fixture", str(factory.store.root), project]
    process = subprocess.Popen([*command, "interrupt"], start_new_session=True)
    try:
        deadline = time.monotonic() + 20
        ready = False
        while time.monotonic() < deadline:
            with factory.store.connection() as connection:
                resource = connection.execute(
                    "SELECT intent FROM operations WHERE kind='docker-resource' AND state='ACTIVE'"
                ).fetchone()
            task = factory.store.tasks(project)[0]
            if resource and task["source_digest"]:
                name = json.loads(resource[0])["name"]
                running = subprocess.run(
                    ["docker", "inspect", "--format", "{{.State.Running}}", name],
                    capture_output=True,
                    text=True,
                )
                if running.returncode == 0 and running.stdout.strip() == "true":
                    ready = True
                    break
            assert process.poll() is None
            time.sleep(0.05)
        assert ready, "first worker did not reach its durable, contained interruption point"
        old = factory.store.tasks(project)[0]
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
        assert Resources(factory.store, project).reap() == 1
        while time.time() <= old["lease_until"]:
            time.sleep(0.05)
        replacement = subprocess.run(
            [*command, "recover"], capture_output=True, text=True, timeout=30
        )
        assert replacement.returncode == 0, replacement.stderr
        task = Store(factory.store.root).tasks(project)[0]
        assert task["fence"] == old["fence"] + 1
        assert task["attempts"] == 2
        assert task["state"] == "INTEGRATED"
        assert factory.store.project(project)["state"] == "READY_FOR_HUMAN_ACCEPTANCE", (
            factory.report(project)
        )
        with factory.store.connection() as connection:
            attempts = connection.execute(
                "SELECT state FROM attempts WHERE project_id=? ORDER BY started", (project,)
            ).fetchall()
        assert [row[0] for row in attempts] == ["ABANDONED", "INTEGRATED"]
        assert factory.store.verify_audit()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        Resources(factory.store, project).reap()


@pytest.mark.docker
def test_separate_worker_continues_when_status_client_exits(tmp_path: Path) -> None:
    factory, project = prepared(tmp_path, lambda a, b, c, role: FixtureAdapter(role))
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tests.worker_fixture",
            str(factory.store.root),
            project,
            "disconnect",
        ],
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 20
        while not factory.store.tasks(project)[0]["source_digest"]:
            assert process.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.05)
        client = subprocess.run(
            [
                sys.executable,
                "-m",
                "darkfactory.cli",
                "--state",
                str(factory.store.root),
                "status",
                project,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert client.returncode == 0
        assert json.loads(client.stdout)["state"] == "RUNNING"
        assert process.poll() is None
        (factory.store.root / "continue.marker").write_text("client has exited")
        process.wait(timeout=30)
        assert process.returncode == 0
        assert factory.store.project(project)["state"] == "READY_FOR_HUMAN_ACCEPTANCE"
        assert factory.store.verify_audit()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        Resources(factory.store, project).reap()
