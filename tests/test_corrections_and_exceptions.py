"""Exercise human correction history and exact-revision finding exception authority."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from darkfactory.api import create_app
from darkfactory.domain import Policy, TaskSpec
from darkfactory.execution import SnapshotStore
from darkfactory.services import Factory
from darkfactory.storage import StateError, Store
from tests.test_contracts import blueprint


def delivered(tmp_path: Path) -> tuple[Factory, str, str]:
    """Create protected fixture records without representing an actual completed app."""
    store = Store(tmp_path / "state")
    source = tmp_path / "source"
    source.mkdir()
    (source / "value.txt").write_text("fixture")
    factory = Factory(store)
    proposal = blueprint().model_copy(
        update={
            "tasks": [
                TaskSpec(
                    id="T01",
                    description="Base",
                    requirement_ids=["FR-001"],
                    permitted_paths=["value.txt"],
                    check_ids=["unit"],
                ),
                TaskSpec(
                    id="T02",
                    description="Dependent",
                    requirement_ids=["FR-001"],
                    dependencies=["T01"],
                    permitted_paths=["other.txt"],
                ),
            ]
        }
    )
    project = factory.propose(proposal, Policy(required_check_kinds=["test"]), source)
    store.approve(project, store.project(project)["blueprint_hash"], "human:fixture")
    revision = SnapshotStore(store.root / "snapshots").capture(source).digest
    with store.connection() as connection:
        connection.execute(
            "UPDATE projects SET state='READY_FOR_HUMAN_ACCEPTANCE',"
            "source_digest=?,delivery_digest=? WHERE id=?",
            (revision, revision, project),
        )
        connection.execute(
            "UPDATE tasks SET state='INTEGRATED',attempts=2,source_digest=? WHERE project_id=?",
            (revision, project),
        )
    return factory, project, revision


def test_correction_tasks_preserve_originals_and_inherit_scope(tmp_path: Path) -> None:
    factory, project, revision = delivered(tmp_path)
    originals = factory.store.tasks(project)
    factory.reject(project, revision, "Fix the count", "human:fixture", ["FR-001"])
    rows = factory.store.tasks(project)
    assert rows[:2] == originals
    assert len(rows) == 4
    correction = factory.store.corrections(project)[0]
    assert correction["revision"] == revision and correction["criteria"] == ["FR-001"]
    links = {row["parent_task"]: row["task_id"] for row in correction["tasks"]}
    first = factory.store.task_spec(project, links["T01"])
    second = factory.store.task_spec(project, links["T02"])
    assert first.permitted_paths == ["value.txt"] and first.check_ids == ["unit"]
    assert second.dependencies == [first.id]
    assert all(row["attempts"] == 0 and row["state"] == "REPAIR_REQUIRED" for row in rows[2:])
    assert factory.store.current_approval(project)
    assert factory.store.project(project)["state"] == "PAUSED"
    with pytest.raises(StateError, match="correction"):
        factory.reject(project, revision, "Duplicate replay", "human:fixture")
    reopened = Store(factory.store.root)
    assert reopened.corrections(project) == factory.store.corrections(project)
    assert reopened.verify_audit()
    destination = tmp_path / "delivery"
    factory.export(project, destination)
    plan = (destination / "PLAN.md").read_text()
    assert first.id in plan and second.id in plan and "Fix the count" in plan


def test_new_human_correction_does_not_reset_previous_attempts(tmp_path: Path) -> None:
    factory, project, revision = delivered(tmp_path)
    factory.reject(project, revision, "First correction", "human:fixture")
    with factory.store.connection() as connection:
        connection.execute("UPDATE tasks SET state='INTEGRATED',attempts=2")
        connection.execute(
            "UPDATE projects SET state='READY_FOR_HUMAN_ACCEPTANCE',delivery_digest=?", (revision,)
        )
    previous = factory.store.tasks(project)
    factory.reject(project, revision, "Second correction", "human:fixture")
    assert factory.store.tasks(project)[:4] == previous
    assert len(factory.store.corrections(project)) == 2
    assert len(factory.store.tasks(project)) == 6


def finding(factory: Factory, project: str, revision: str) -> None:
    """Insert an explicitly labeled adverse review fixture in protected storage."""
    with factory.store.connection() as connection:
        connection.execute(
            "INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "review",
                project,
                None,
                revision,
                "security-auditor",
                "independent",
                "BLOCK",
                json.dumps({"fixture": True}),
                1,
            ),
        )
        connection.execute(
            "INSERT INTO findings VALUES(?,?,?,?,?,?,?,?,?)",
            ("finding", project, "review", None, revision, "blocking", "Fixture issue", None, None),
        )


def test_exception_is_scoped_audited_revocable_and_never_resolves_finding(tmp_path: Path) -> None:
    factory, project, revision = delivered(tmp_path)
    finding(factory, project, revision)
    with pytest.raises(StateError, match="human"):
        factory.grant_exception(project, "finding", revision, "Self approve", "agent:fixture")
    identifier = factory.grant_exception(
        project, "finding", revision, "Reviewed temporary exception", "human:fixture"
    )
    assert not factory.store.blocking_findings(project, revision)
    assert factory.store.blocking_findings(project, "a" * 64)
    with factory.store.connection() as connection:
        assert factory.store.review_satisfied(connection, project, "review", revision)
        assert connection.execute("SELECT resolved_by FROM findings").fetchone()[0] is None
        assert connection.execute("SELECT verdict FROM reviews").fetchone()[0] == "BLOCK"
    with pytest.raises(StateError, match="already"):
        factory.grant_exception(project, "finding", revision, "Replay", "human:fixture")
    factory.revoke_exception(project, identifier, "human:fixture")
    assert factory.store.blocking_findings(project, revision)
    assert factory.store.project(project)["state"] == "BLOCKED"
    assert factory.store.verify_audit()


def test_exception_cannot_cross_projects_or_forge_operator_through_api(tmp_path: Path) -> None:
    factory, project, revision = delivered(tmp_path)
    finding(factory, project, revision)
    other = factory.store.create_project(blueprint(), Policy(required_check_kinds=["test"]))
    factory.store.approve(other, factory.store.project(other)["blueprint_hash"], "human:fixture")
    with pytest.raises(StateError, match="unresolved finding"):
        factory.grant_exception(other, "finding", revision, "Cross-project", "human:fixture")
    token = "fixture-administrative-token-is-not-a-real-secret"
    client = TestClient(create_app(factory.store, token, factory), base_url="http://127.0.0.1")
    path = f"/v1/projects/{project}/findings/finding/exception"
    body = {"revision": revision, "reason": "Explicit fixture decision"}
    assert client.post(path, json=body, headers={"X-Actor": "human:forged"}).status_code == 401
    headers = {"Authorization": "Bearer " + token}
    assert (
        client.post(path, json={**body, "actor": "human:forged"}, headers=headers).status_code
        == 422
    )
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 201
    exception = response.json()["id"]
    assert (
        client.post(
            f"/v1/projects/{project}/exceptions/{exception}/revoke", headers=headers
        ).status_code
        == 200
    )


def test_existing_schema_migrates_additively_without_losing_state(tmp_path: Path) -> None:
    factory, project, _ = delivered(tmp_path)
    original = factory.store.project(project)
    with factory.store.connection() as connection:
        connection.execute("UPDATE schema_version SET version=1")
    reopened = Store(factory.store.root)
    assert reopened.project(project) == original
    with reopened.connection() as connection:
        assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 2


@pytest.mark.docker
def test_exception_allows_exact_reviewed_delivery_without_waiving_checks(tmp_path: Path) -> None:
    from darkfactory.adapters import AgentReply, Finding
    from darkfactory.domain import Role
    from tests.test_engine import FixtureAdapter
    from tests.test_remediation import prepared

    adverse = False

    class Reviewer(FixtureAdapter):
        def propose(self, context: str, workspace: Path, limits: object) -> AgentReply:
            if adverse and self.role == Role.SECURITY:
                return AgentReply(
                    status="complete",
                    summary="Independent adverse fixture review",
                    examined=["FR-001"],
                    findings=[
                        Finding(
                            severity="blocking",
                            description="Explicit fixture issue",
                            criterion="FR-001",
                        )
                    ],
                )
            return super().propose(context, workspace, limits)

    factory, project = prepared(tmp_path, lambda a, b, c, role: Reviewer(role))
    factory.engine.run_one(project, "implementation")
    revision = factory.store.project(project)["delivery_digest"]
    adverse = True
    assert not factory.review(project)
    with pytest.raises(StateError, match="blocking"):
        factory.accept(project, revision, "human:fixture")
    issue = factory.engine.open_findings(project)[0]["id"]
    factory.grant_exception(
        project, issue, revision, "Reviewed exact fixture issue", "human:fixture"
    )
    factory.accept(project, revision, "human:fixture")
    assert factory.store.project(project)["state"] == "ACCEPTED"
    assert factory.engine.open_findings(project)[0]["resolved_by"] is None
    assert all(check["passed"] for check in factory.report(project)["checks"])
    assert factory.store.verify_audit()
