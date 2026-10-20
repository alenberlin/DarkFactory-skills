"""Actual native CLI processes against an offline canned inference server."""

import shutil
import threading
import time
import uuid
from pathlib import Path

import pytest

from darkfactory.adapters import AgentReply, InferenceSession, NativeAdapter
from darkfactory.domain import InferenceSpec, Limits, Policy
from darkfactory.execution import DockerExecutor, bounded_process
from darkfactory.storage import Store
from tests.test_contracts import blueprint


@pytest.mark.docker
@pytest.mark.parametrize(("name", "provider"), [("claude", "anthropic"), ("codex", "openai")])
def test_actual_cli_protocol_with_offline_model_fixture(
    name: str, provider: str, tmp_path: Path
) -> None:
    store = Store(tmp_path / "state")
    project = store.create_project(blueprint(), Policy(required_check_kinds=["test"]))
    spec = InferenceSpec(
        provider=provider, model="fixture-model", agent_image="darkfactory-native-adapters:0.3.0"
    )
    session = InferenceSession(store, project, "fixture-native", spec)
    proposal = blueprint().model_copy(update={"adapter": name, "inference": spec})
    expected = AgentReply(status="complete", summary="Offline protocol fixture")
    source = tmp_path / "provider"
    source.mkdir()
    shutil.copyfile(Path(__file__).with_name("provider_fixture.py"), source / "server.py")
    (source / "reply.json").write_text(expected.model_dump_json())
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executor = DockerExecutor("python:3.12-slim")
    network = "df-protocol-" + uuid.uuid4().hex
    container = network + "-server"
    session.network = network
    created = bounded_process(
        [executor.binary, "network", "create", "--internal", network], timeout=10, output_bytes=4096
    )
    assert created.exit_code == 0
    server = threading.Thread(
        target=lambda: executor.run(
            source,
            ["python", "-I", "server.py"],
            Limits(command_seconds=60),
            readonly=True,
            network=network,
            network_alias="inference",
            container_name=container,
        ),
        daemon=True,
    )
    server.start()
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            probe = bounded_process(
                [executor.binary, "inspect", "--format", "{{.State.Running}}", container],
                timeout=5,
                output_bytes=4096,
            )
            if probe.exit_code == 0 and probe.stdout.strip() == "true":
                break
            time.sleep(0.05)
        assert (
            NativeAdapter(proposal, session).propose(
                "Return the offline fixture proposal.", workspace, Limits(command_seconds=30)
            )
            == expected
        )
    finally:
        bounded_process(
            [executor.binary, "rm", "--force", container], timeout=10, output_bytes=4096
        )
        server.join(timeout=5)
        bounded_process([executor.binary, "network", "rm", network], timeout=10, output_bytes=4096)
