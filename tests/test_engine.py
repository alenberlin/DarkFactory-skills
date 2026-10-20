"""Exercise contained source generation through protected verification and human delivery."""

import json
from pathlib import Path

import pytest

from darkfactory.adapters import AgentReply, FileEdit
from darkfactory.domain import CheckSpec, Limits, Permissions, Policy, Role, TaskSpec
from darkfactory.engine import Engine, apply_reply
from darkfactory.execution import BoundaryError
from darkfactory.services import Factory
from darkfactory.storage import StateError, Store
from tests.test_contracts import blueprint


class FixtureAdapter:
    """Explicit offline fixture; never presented as a live model result."""

    def __init__(self, role: Role) -> None:
        self.role = role

    def propose(self, context: str, workspace: Path, limits: Limits) -> AgentReply:
        if self.role in (Role.QA, Role.ACCEPTANCE, Role.REVIEW, Role.TEST, Role.SECURITY):
            return AgentReply(
                status="complete", summary="Fixture scope reviewed", examined=["FR-001"]
            )
        return AgentReply(
            status="complete",
            summary="Fixture source proposed",
            files=[FileEdit(path="value.txt", content="correct")],
        )


@pytest.mark.docker
def test_approval_to_real_verification_integration_and_acceptance(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    engine = Engine(store, lambda project, attempt, proposal, role: FixtureAdapter(role))
    factory = Factory(store, engine)
    source = tmp_path / "source"
    source.mkdir()
    spec = CheckSpec(
        id="unit",
        argv=["python", "-I", "{driver}"],
        kind="test",
        driver=(
            "from pathlib import Path\n"
            "assert Path('value.txt').read_text() == 'correct'\n"
            "print('criterion passed')\n"
        ),
        expected_output="criterion passed",
    )
    proposal = blueprint().model_copy(
        update={
            "checks": [spec],
            "image": "python:3.12-slim",
            "permissions": Permissions(local_commits=True, local_integration=True),
        }
    )
    project = factory.propose(proposal, Policy(required_check_kinds=["test"]), source)
    with pytest.raises(StateError, match="approved"):
        factory.start(project)
    store.approve(project, store.project(project)["blueprint_hash"], "human:test")
    factory.start(project)
    assert engine.run_one(project, "fixture-worker")
    current = Store(store.root).project(project)
    assert current["state"] == "READY_FOR_HUMAN_ACCEPTANCE", factory.report(project)
    with pytest.raises(StateError, match="human"):
        factory.accept(project, current["delivery_digest"], "agent:fake")
    with pytest.raises(StateError, match="revision"):
        factory.accept(project, "stale", "human:test")
    factory.export(project, tmp_path / "delivery")
    assert (tmp_path / "delivery/source/value.txt").read_text() == "correct"
    factory.accept(project, current["delivery_digest"], "human:test")
    assert store.project(project)["state"] == "ACCEPTED"
    assert store.verify_audit()


def test_proposed_path_traversal_and_unowned_files_are_denied(tmp_path: Path) -> None:
    task = blueprint().tasks[0].model_copy(update={"permitted_paths": ["src/**"]})
    for path in ("../escape", "/host-file", ".git/config", "other.py"):
        with pytest.raises(BoundaryError):
            apply_reply(
                tmp_path,
                AgentReply(
                    status="complete", summary="bad", files=[FileEdit(path=path, content="x")]
                ),
                task,
            )


def test_concurrent_reservations_do_not_oversubscribe(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    project = store.create_project(
        blueprint().model_copy(update={"limits": Limits(max_tokens=1000)}),
        Policy(required_check_kinds=["test"]),
    )
    engine = Engine(store)
    engine.reserve(project, "a", 600)
    with pytest.raises(StateError, match="budget"):
        engine.reserve(project, "b", 600)


@pytest.mark.docker
def test_material_question_blocks_task_without_spending_repair_attempts(tmp_path: Path) -> None:
    from tests.test_remediation import prepared

    class QuestionFixture(FixtureAdapter):
        def propose(self, context: str, workspace: Path, limits: Limits) -> AgentReply:
            return AgentReply(
                status="blocked",
                summary="Unresolved material decision",
                questions=["Approve a different account access model?"],
            )

    factory, project = prepared(tmp_path, lambda a, b, c, role: QuestionFixture(role))
    factory.engine.run_one(project, "first")
    factory.engine.run_one(project, "must-not-retry")
    task = factory.store.tasks(project)[0]
    assert task["state"] == "BLOCKED" and task["attempts"] == 1
    assert "different account access model" in task["error"]
    assert factory.store.project(project)["state"] == "BLOCKED"


@pytest.mark.docker
def test_blocked_dependency_does_not_stop_eligible_independent_work(tmp_path: Path) -> None:
    class BlockedFixture(FixtureAdapter):
        def propose(self, context: str, workspace: Path, limits: Limits) -> AgentReply:
            if self.role == Role.BACKEND:
                task = json.loads(context)["assignment"]["id"]
                if task == "T01":
                    return AgentReply(
                        status="blocked",
                        summary="Material choice",
                        questions=["Resolve the account model?"],
                    )
                assert task != "T03", "dependent work must remain unscheduled"
            return super().propose(context, workspace, limits)

    store = Store(tmp_path / "state")
    factory = Factory(store, Engine(store, lambda a, b, c, role: BlockedFixture(role)))
    source = tmp_path / "source"
    source.mkdir()
    tasks = [
        TaskSpec(
            id="T01",
            description="Blocked",
            requirement_ids=["FR-001"],
            permitted_paths=["blocked.txt"],
        ),
        TaskSpec(
            id="T02",
            description="Independent",
            requirement_ids=["FR-001"],
            permitted_paths=["value.txt"],
        ),
        TaskSpec(
            id="T03",
            description="Dependent",
            requirement_ids=["FR-001"],
            dependencies=["T01"],
            permitted_paths=["dependent.txt"],
        ),
    ]
    check = CheckSpec(
        id="unit",
        kind="test",
        argv=["python", "-I", "{driver}"],
        driver="from pathlib import Path\nassert Path('value.txt').read_text() == 'correct'\n"
        "print('independent verified')\n",
        expected_output="independent verified",
    )
    proposal = blueprint().model_copy(
        update={
            "tasks": tasks,
            "checks": [check],
            "image": "python:3.12-slim",
            "permissions": Permissions(local_commits=True, local_integration=True),
        }
    )
    project = factory.propose(proposal, Policy(required_check_kinds=["test"]), source)
    store.approve(project, store.project(project)["blueprint_hash"], "human:test")
    factory.start(project)
    factory.engine.run_one(project, "blocked")
    assert store.project(project)["state"] == "RUNNING"
    factory.engine.run_one(project, "independent")
    states = {row["id"]: row["state"] for row in store.tasks(project)}
    assert states == {"T01": "BLOCKED", "T02": "INTEGRATED", "T03": "PENDING"}
    assert store.project(project)["state"] == "BLOCKED"
    assert not factory.engine.run_one(project, "must-not-run-dependent")
    assert store.verify_audit()
