"""Native failure diagnostics and malformed protocol turns never certify successful work."""

import json
from pathlib import Path

import pytest

from darkfactory.adapters import AdapterFailure, AgentReply, InferenceSession, NativeAdapter
from darkfactory.domain import InferenceSpec, Limits, Policy
from darkfactory.storage import StateError, Store
from tests.test_contracts import blueprint


@pytest.mark.parametrize(
    "name,output",
    [
        ("claude", "[]"),
        ("claude", "null"),
        ("claude", json.dumps({"is_error": True, "structured_output": {}})),
        ("codex", "[]"),
        ("codex", '{"type":"item.completed","item":null}'),
    ],
)
def test_invalid_native_envelopes_have_explicit_failure(name: str, output: str) -> None:
    with pytest.raises(StateError):
        NativeAdapter.parse(name, output)


def test_failed_turn_after_a_plausible_reply_is_rejected() -> None:
    reply = AgentReply(status="complete", summary="Untrusted proposal")
    output = (
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": reply.model_dump_json(),
                },
            }
        )
        + '\n{"type":"turn.failed","error":{"message":"fixture outage"}}'
    )
    with pytest.raises(StateError, match="failed"):
        NativeAdapter.parse("codex", output)


@pytest.mark.docker
def test_actual_failed_process_has_redacted_structured_diagnostics(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    project = store.create_project(blueprint(), Policy(required_check_kinds=["test"]))
    spec = InferenceSpec(
        provider="anthropic", model="fixture-model", agent_image="python:3.12-slim"
    )
    session = InferenceSession(store, project, "diagnostic-fixture", spec)
    session.network = "none"
    adapter = NativeAdapter(blueprint().model_copy(update={"inference": spec}), session)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(AdapterFailure) as error:
        adapter.propose(
            "No provider request is possible in this fixture", workspace, Limits(command_seconds=20)
        )
    with store.connection() as connection:
        row = connection.execute("SELECT * FROM adapter_runs").fetchone()
        assert connection.execute("SELECT COUNT(*) FROM checks").fetchone()[0] == 0
    assert row["id"] == error.value.diagnostic_id and row["state"] == "EXIT"
    diagnostic = json.loads(row["diagnostic"])
    assert diagnostic["exit_code"] != 0 and diagnostic["image_id"].startswith("sha256:")
    assert session.capability not in row["diagnostic"]
    assert store.verify_audit()
