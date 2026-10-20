"""Adaptive planning persists questions and produces an unapproved complete proposal."""

import json
from pathlib import Path

import pytest

from darkfactory.adapters import AgentReply
from darkfactory.discovery import Discovery
from darkfactory.domain import CheckSpec, InferenceSpec, Limits, Role
from darkfactory.engine import Engine
from darkfactory.services import Factory
from darkfactory.storage import Store
from tests.test_contracts import blueprint


class PlanningFixture:
    """Offline discovery protocol fixture with one material question."""

    def __init__(self, role: Role) -> None:
        self.role = role

    def propose(self, context: str, workspace: Path, limits: Limits) -> AgentReply:
        interview = json.loads(context)["interview"]
        if self.role == Role.ANALYST and not interview["answers"]:
            return AgentReply(
                status="continue", summary="Resolve owner", questions=["Who owns each task?"]
            )
        if self.role == Role.PLANNER:
            checks = [
                CheckSpec(id=kind, kind=kind, argv=["python", "-c", "print('configured check')"])
                for kind in ("test", "build", "lint", "typecheck")
            ]
            return AgentReply(
                status="complete",
                summary="Fixture planning proposal",
                proposed_blueprint=blueprint().model_copy(update={"checks": checks}),
            )
        return AgentReply(status="complete", summary="Fixture planning artifacts")


def test_interview_reopens_without_self_approval(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    engine = Engine(store, lambda project, attempt, proposal, role: PlanningFixture(role))
    discovery = Discovery(store, engine)
    source = tmp_path / "source"
    source.mkdir()
    project = discovery.begin(
        "Build task ownership",
        InferenceSpec(provider="anthropic", model="fixture", agent_image="fixture"),
        Limits(),
        source,
        "claude",
    )
    first = discovery.advance(project)
    assert first["questions"] == ["Who owns each task?"]
    resumed = Discovery(Store(store.root), engine).advance(project, ["The authenticated account"])
    assert resumed["stage"] == 3
    assert store.project(resumed["proposal"])["state"] == "AWAITING_BLUEPRINT_APPROVAL"
    with store.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 0


def test_invalid_plan_is_repaired_and_proposal_survives_interrupted_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []

    class RepairFixture(PlanningFixture):
        def propose(self, context: str, workspace: Path, limits: Limits) -> AgentReply:
            data = json.loads(context)
            assert data["source"]["existing.txt"] == "existing project context"
            if self.role == Role.PLANNER:
                seen.append(data["validation_failure"])
                if len(seen) == 1:
                    raise ValueError("cyclic/incomplete proposed plan rejected")
            return super().propose(context, workspace, limits)

    store = Store(tmp_path / "state")
    engine = Engine(store, lambda a, b, c, role: RepairFixture(role))
    discovery = Discovery(store, engine)
    source = tmp_path / "source"
    source.mkdir()
    (source / "existing.txt").write_text("existing project context")
    project = discovery.begin(
        "Extend this project",
        InferenceSpec(provider="anthropic", model="fixture", agent_image="fixture"),
        Limits(),
        source,
        "claude",
    )
    discovery.advance(project)
    actual = Factory._propose_snapshot

    def crash_after_creation(self: Factory, *args: object, **kwargs: object) -> str:
        actual(self, *args, **kwargs)
        raise OSError("injected failure after durable proposal creation")

    monkeypatch.setattr(Factory, "_propose_snapshot", crash_after_creation)
    with pytest.raises(OSError, match="injected"):
        discovery.advance(project, ["Authenticated owner"])
    assert len(store.projects()) == 2
    monkeypatch.undo()
    result = Discovery(Store(store.root), engine).advance(project)
    assert result["stage"] == 3
    assert len(store.projects()) == 2
    assert len(seen) == 2 and "rejected" in seen[1]
    assert store.project(result["proposal"])["state"] == "AWAITING_BLUEPRINT_APPROVAL"
    assert store.verify_audit()
