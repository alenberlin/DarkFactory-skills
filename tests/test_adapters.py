"""Native protocol parsing and actual private gateway denial boundaries."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from darkfactory.adapters import AgentReply, InferenceSession, NativeAdapter, strict_schema
from darkfactory.domain import InferenceSpec, Limits, Policy
from darkfactory.execution import DockerExecutor
from darkfactory.storage import StateError, Store
from tests.test_contracts import blueprint


def test_native_envelopes_reject_forged_authority_and_malformed_results() -> None:
    reply = AgentReply(status="complete", summary="Proposed candidate")
    assert (
        NativeAdapter.parse("claude", json.dumps({"structured_output": reply.model_dump()}))
        == reply
    )
    event = {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": reply.model_dump_json()},
    }
    assert NativeAdapter.parse("codex", json.dumps(event)) == reply
    with pytest.raises(ValidationError):
        NativeAdapter.parse(
            "claude", json.dumps({"structured_output": {**reply.model_dump(), "approved": True}})
        )
    with pytest.raises(StateError):
        NativeAdapter.parse("codex", '{"type":"turn.completed"}')
    schema = strict_schema(AgentReply.model_json_schema())
    assert set(schema["required"]) == set(schema["properties"])


@pytest.mark.docker
def test_real_gateway_denies_arbitrary_routes_and_hides_vendor_credential(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    project = store.create_project(blueprint(), Policy(required_check_kinds=["test"]))
    credentials = store.root / "credentials"
    credentials.mkdir()
    credential = credentials / "anthropic"
    credential.write_text("invalid-fixture-provider-credential-never-sent")
    credential.chmod(0o600)
    spec = InferenceSpec(
        provider="anthropic", model="fixture-model", agent_image="python:3.12-slim"
    )
    session = InferenceSession(store, project, "fixture-session", spec)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    try:
        session.start()
        code = (
            "import urllib.request,urllib.error,os,pathlib,socket\n"
            "assert not pathlib.Path('/trusted/credential').exists()\n"
            "request=urllib.request.Request('http://inference:8080/admin/approve',data=b'{}',"
            "headers={'Authorization':'Bearer '+os.environ['CAPABILITY']})\n"
            "try:\n urllib.request.urlopen(request,timeout=5)\n"
            " raise AssertionError('route escaped')\n"
            "except urllib.error.HTTPError as error:\n assert error.code==403\n"
            "try:\n socket.create_connection(('1.1.1.1',443),timeout=2)\n"
            " raise AssertionError('egress escaped')\n"
            "except OSError:\n pass\n"
            "print('private gateway boundary passed')\n"
        )
        result = DockerExecutor("python:3.12-slim").run(
            workspace,
            ["python", "-I", "-c", code],
            Limits(command_seconds=15),
            network=session.network,
            environment={"CAPABILITY": session.capability},
            readonly=True,
        )
        assert result.exit_code == 0, result.stderr
        assert "private gateway boundary passed" in result.stdout
        assert session.usage()["tokens"] == 0
        assert session.usage()["requests"] == 0
    finally:
        session.close()
