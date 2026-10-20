"""Kill a real native CLI supervisor during an actual offline request and recover its record."""

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

from darkfactory.adapters import AdapterFailure, AgentReply, InferenceSession, NativeAdapter
from darkfactory.domain import InferenceSpec, Limits, Policy
from darkfactory.execution import DockerExecutor, bounded_process
from darkfactory.resources import Resources
from darkfactory.storage import Store
from tests.test_contracts import blueprint


@pytest.mark.docker
def test_actual_native_interruption_and_timeout_preserve_diagnostics(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    project = store.create_project(blueprint(), Policy(required_check_kinds=["test"]))
    provider = tmp_path / "provider"
    provider.mkdir()
    shutil.copyfile(Path(__file__).with_name("provider_fixture.py"), provider / "server.py")
    (provider / "reply.json").write_text(
        AgentReply(status="complete", summary="Offline fixture").model_dump_json()
    )
    (provider / "delay-seconds").write_text("60")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executor = DockerExecutor("python:3.12-slim")
    network = "df-interruption-" + uuid.uuid4().hex
    container = network + "-server"
    created = bounded_process(
        [executor.binary, "network", "create", "--internal", network], timeout=10, output_bytes=4096
    )
    assert created.exit_code == 0
    server = threading.Thread(
        target=lambda: executor.run(
            provider,
            ["python", "-I", "server.py"],
            Limits(command_seconds=90),
            readonly=True,
            network=network,
            network_alias="inference",
            container_name=container,
        ),
        daemon=True,
    )
    server.start()
    process = None
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            ready = bounded_process(
                [executor.binary, "inspect", "--format", "{{.State.Running}}", container],
                timeout=5,
                output_bytes=1024,
            )
            if ready.exit_code == 0 and ready.stdout.strip() == "true":
                break
            time.sleep(0.05)
        assert ready.exit_code == 0 and ready.stdout.strip() == "true"
        process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                str(Path(__file__).with_name("adapter_fixture.py")),
                str(store.root),
                project,
                network,
                str(workspace),
            ],
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            received = bounded_process(
                [executor.binary, "logs", container], timeout=5, output_bytes=4096
            )
            if "offline-fixture-request-received" in received.stdout:
                break
            assert process.poll() is None
            time.sleep(0.05)
        assert "offline-fixture-request-received" in received.stdout
        assert NativeAdapter.reconcile(store, project) == 0
        os.kill(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
        Resources(store, project).reap()
        assert NativeAdapter.reconcile(Store(store.root), project) == 1
        assert NativeAdapter.reconcile(store, project) == 0
        with store.connection() as connection:
            assert connection.execute("SELECT state FROM adapter_runs").fetchone()[0] == "ABORTED"
            assert connection.execute("SELECT COUNT(*) FROM checks").fetchone()[0] == 0
        spec = InferenceSpec(
            provider="anthropic",
            model="fixture-model",
            agent_image="darkfactory-native-adapters:0.3.0",
        )
        session = InferenceSession(store, project, "timeout-native", spec)
        session.network = network
        adapter = NativeAdapter(blueprint().model_copy(update={"inference": spec}), session)
        with pytest.raises(AdapterFailure) as failure:
            adapter.propose("Offline timeout fixture", workspace, Limits(command_seconds=1))
        assert failure.value.category == "timeout"
        with store.connection() as connection:
            assert (
                connection.execute(
                    "SELECT state FROM adapter_runs WHERE id=?", (failure.value.diagnostic_id,)
                ).fetchone()[0]
                == "TIMEOUT"
            )
        assert store.verify_audit()
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        Resources(store, project).reap()
        bounded_process(
            [executor.binary, "rm", "--force", container], timeout=10, output_bytes=4096
        )
        server.join(timeout=5)
        bounded_process([executor.binary, "network", "rm", network], timeout=10, output_bytes=4096)
