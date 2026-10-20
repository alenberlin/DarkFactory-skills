"""Exercise actual defects, persistent findings, scoped checkpoints and renewed evidence."""

import json
from pathlib import Path

import pytest

from darkfactory.adapters import AgentReply, FileEdit, Finding
from darkfactory.domain import CheckSpec, Limits, Permissions, Policy, Role, TaskSpec
from darkfactory.engine import AdapterFactory, Engine
from darkfactory.gitops import Repository
from darkfactory.services import Factory
from darkfactory.storage import Store
from tests.test_contracts import blueprint
from tests.test_engine import FixtureAdapter


def prepared(tmp_path: Path, factory_adapter: AdapterFactory) -> tuple[Factory, str]:
    """Build an isolated, explicitly approved offline fixture with protected checks."""
    store = Store(tmp_path / "state")
    engine = Engine(store, factory_adapter)
    factory = Factory(store, engine)
    source = tmp_path / "source"
    source.mkdir()
    proposal = blueprint().model_copy(
        update={
            "image": "python:3.12-slim",
            "permissions": Permissions(local_commits=True, local_integration=True),
            "checks": [
                CheckSpec(
                    id="unit",
                    kind="test",
                    argv=["python", "-I", "{driver}"],
                    driver=(
                        "from pathlib import Path\n"
                        "assert Path('value.txt').read_text().startswith('correct')\n"
                        "print('checked')\n"
                    ),
                    expected_output="checked",
                )
            ],
        }
    )
    project = factory.propose(proposal, Policy(required_check_kinds=["test"]), source)
    store.approve(project, store.project(project)["blueprint_hash"], "human:test")
    factory.start(project)
    return factory, project


@pytest.mark.docker
def test_finding_survives_reopen_and_cannot_be_ignored(tmp_path: Path) -> None:
    class Reviewer(FixtureAdapter):
        def propose(self, context: str, workspace: Path, limits: Limits) -> AgentReply:
            if self.role == Role.SECURITY:
                prior = json.loads(
                    context.split("Prior findings requiring explicit re-verification: ")[1]
                )
                if (workspace / "value.txt").read_text() == "correct":
                    return AgentReply(
                        status="complete",
                        summary="Observed defect",
                        examined=["value.txt"],
                        findings=[
                            Finding(
                                severity="blocking",
                                description="Repair criterion",
                                criterion="FR-001",
                            )
                        ],
                    )
                return AgentReply(
                    status="complete",
                    summary="Reverified repair",
                    examined=["value.txt"],
                    resolved_findings=[row["id"] for row in prior],
                )
            if self.role == Role.BACKEND:
                known = json.loads(context)["open_findings"]
                return AgentReply(
                    status="complete",
                    summary="Proposed correction",
                    files=[
                        FileEdit(path="value.txt", content="correct-fixed" if known else "correct")
                    ],
                )
            return super().propose(context, workspace, limits)

    factory, project = prepared(tmp_path, lambda a, b, c, role: Reviewer(role))
    assert factory.engine.run_one(project, "first")
    assert factory.store.tasks(project)[0]["state"] == "REPAIR_REQUIRED"
    assert Repository(factory.store, project).current().path.joinpath("value.txt").exists() is False
    assert len(factory.engine.open_findings(project)) == 1
    restarted = Factory(
        Store(factory.store.root),
        Engine(Store(factory.store.root), lambda a, b, c, role: Reviewer(role)),
    )
    assert restarted.engine.run_one(project, "replacement")
    report = restarted.report(project)
    assert report["project"]["state"] == "READY_FOR_HUMAN_ACCEPTANCE", report
    assert not restarted.engine.open_findings(project)
    assert all(row["resolved_by"] for row in report["findings"])
    assert len({row["source_digest"] for row in report["checks"]}) == 2


@pytest.mark.docker
def test_final_qa_finding_creates_bounded_correction_cycle(tmp_path: Path) -> None:
    class Reviewer(FixtureAdapter):
        def propose(self, context: str, workspace: Path, limits: Limits) -> AgentReply:
            if self.role == Role.QA:
                prior = json.loads(
                    context.split("Prior findings requiring explicit re-verification: ")[1]
                )
                if (workspace / "value.txt").read_text() == "correct":
                    return AgentReply(
                        status="complete",
                        summary="Final workflow defect",
                        examined=["FR-001"],
                        findings=[
                            Finding(
                                severity="blocking",
                                description="Final criterion defect",
                                criterion="FR-001",
                            )
                        ],
                    )
                return AgentReply(
                    status="complete",
                    summary="Final repair verified",
                    examined=["FR-001"],
                    resolved_findings=[row["id"] for row in prior],
                )
            if self.role == Role.BACKEND and json.loads(context)["open_findings"]:
                return AgentReply(
                    status="complete",
                    summary="Corrected final defect",
                    files=[FileEdit(path="value.txt", content="correct-final")],
                )
            return super().propose(context, workspace, limits)

    factory, project = prepared(tmp_path, lambda a, b, c, role: Reviewer(role))
    factory.engine.run_one(project, "first")
    assert factory.store.project(project)["state"] == "RUNNING"
    assert factory.store.tasks(project)[0]["attempts"] == 1
    assert factory.store.tasks(project)[0]["state"] == "REPAIR_REQUIRED"
    factory.engine.run_one(project, "repair")
    assert factory.store.project(project)["state"] == "READY_FOR_HUMAN_ACCEPTANCE", factory.report(
        project
    )
    assert factory.store.tasks(project)[0]["attempts"] == 2
    assert not factory.engine.open_findings(project)


@pytest.mark.docker
def test_old_checkpoint_preserves_new_unowned_integration(tmp_path: Path) -> None:
    factory, project = prepared(tmp_path, lambda a, b, c, role: FixtureAdapter(role))
    repository = Repository(factory.store, project)
    old = repository.current()
    checkpoint = tmp_path / "checkpoint"
    factory.engine.snapshots.materialize(old, checkpoint)
    (checkpoint / "value.txt").write_text("incorrect")
    saved = factory.engine.snapshots.capture(checkpoint)
    updated = tmp_path / "other-task"
    factory.engine.snapshots.materialize(old, updated)
    (updated / "other.txt").write_text("independent new work")
    integrated = factory.engine.snapshots.capture(updated)
    commit = repository.candidate(repository.head(), integrated)
    repository.git("update-ref", "refs/heads/integration", commit, repository.head())
    task = TaskSpec(
        id="T01",
        description="Scoped correction",
        requirement_ids=["FR-001"],
        permitted_paths=["value.txt"],
    )
    with factory.store.connection() as connection:
        connection.execute(
            "UPDATE tasks SET spec=?,source_digest=?,state='REPAIR_REQUIRED' WHERE project_id=?",
            (task.model_dump_json(), saved.digest, project),
        )
    factory.engine.run_one(project, "recover")
    current = repository.current()
    assert (current.path / "other.txt").read_text() == "independent new work"
    assert (current.path / "value.txt").read_text() == "correct"
    assert factory.store.project(project)["state"] == "READY_FOR_HUMAN_ACCEPTANCE", factory.report(
        project
    )
