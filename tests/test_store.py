"""Exercise durable ownership, approval and protected audit invariants."""

from pathlib import Path

import pytest

from darkfactory.domain import CheckSpec, Permissions, Policy, TaskSpec, TaskState
from darkfactory.storage import StateError, Store
from tests.test_contracts import blueprint


def prepared_store(tmp_path: Path) -> tuple[Store, str]:
    store = Store(tmp_path / "state")
    initial = blueprint().model_copy(
        update={"permissions": Permissions(local_commits=True, local_integration=True)}
    )
    policy = Policy(required_check_kinds=["test"], required_review_roles=[])
    project_id = store.create_project(initial, policy)
    store.approve(project_id, store.project(project_id)["blueprint_hash"], "human:test")
    store.start(project_id)
    return store, project_id


def test_approval_is_revision_bound_and_durable(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    project_id = store.create_project(blueprint(), Policy(required_check_kinds=["test"]))
    with pytest.raises(StateError, match="approval"):
        store.start(project_id)
    with pytest.raises(StateError, match="digest"):
        store.approve(project_id, "different-blueprint", "human:test")
    with pytest.raises(StateError, match="human"):
        store.approve(project_id, store.project(project_id)["blueprint_hash"], "agent:test")
    store.approve(project_id, store.project(project_id)["blueprint_hash"], "human:test")
    reopened = Store(tmp_path / "state")
    assert reopened.project(project_id)["state"] == "READY"
    assert reopened.verify_audit()


def test_stale_worker_cannot_publish_after_reclaim(tmp_path: Path) -> None:
    store, project_id = prepared_store(tmp_path)
    first = store.claim(project_id, "worker-one", now=100.0, lease_seconds=10)
    assert first is not None
    second = store.claim(project_id, "worker-two", now=111.0, lease_seconds=10)
    assert second is not None
    assert second["fence"] > first["fence"]
    with pytest.raises(StateError, match="stale"):
        store.heartbeat(project_id, first["task_id"], first["fence"], now=112.0)
    store.heartbeat(project_id, second["task_id"], second["fence"], now=112.0)


def test_dependencies_and_component_ownership_control_dispatch(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    initial = blueprint().model_copy(
        update={
            "tasks": [
                TaskSpec(
                    id="T01",
                    description="First",
                    requirement_ids=["FR-001"],
                    permitted_paths=["src/**"],
                ),
                TaskSpec(
                    id="T02",
                    description="Overlaps",
                    requirement_ids=["FR-001"],
                    permitted_paths=["src/ui/**"],
                ),
                TaskSpec(
                    id="T03",
                    description="Independent",
                    requirement_ids=["FR-001"],
                    permitted_paths=["docs/**"],
                ),
                TaskSpec(
                    id="T04",
                    description="Depends",
                    requirement_ids=["FR-001"],
                    dependencies=["T01"],
                ),
            ],
            "checks": [CheckSpec(id="unit", argv=["python", "-m", "unittest"], kind="test")],
        }
    )
    project_id = store.create_project(initial, Policy(required_check_kinds=["test"]))
    store.approve(project_id, store.project(project_id)["blueprint_hash"], "human:test")
    store.start(project_id)
    first = store.claim(project_id, "w1", now=100.0)
    second = store.claim(project_id, "w2", now=100.0)
    assert first is not None and first["task_id"] == "T01"
    assert second is not None and second["task_id"] == "T03"
    assert store.claim(project_id, "w3", now=100.0) is None


def test_audit_rewrite_is_detected(tmp_path: Path) -> None:
    store, _ = prepared_store(tmp_path)
    assert store.verify_audit()
    with store.connection() as connection:
        connection.execute("UPDATE audit SET payload='{}' WHERE seq=1")
    assert not store.verify_audit()


def test_illegal_phases_and_cancelled_ownership_are_denied(tmp_path: Path) -> None:
    store, project = prepared_store(tmp_path)
    assignment = store.claim(project, "worker")
    assert assignment
    with pytest.raises(StateError, match="illegal"):
        store.stage(assignment, TaskState.READY_TO_INTEGRATE)
    store.stage(assignment, TaskState.VERIFYING)
    store.stage(assignment, TaskState.IN_REVIEW)
    store.control(project, "cancel", "human:test")
    with pytest.raises(StateError, match="stale"):
        store.stage(assignment, TaskState.READY_TO_INTEGRATE)
    assert store.project(project)["state"] == "CANCELLED"
    assert store.tasks(project)[0]["state"] == "CANCELLED"
    assert store.verify_audit()


def test_pause_drains_dead_worker_without_rescheduling(tmp_path: Path) -> None:
    store, project = prepared_store(tmp_path)
    assignment = store.claim(project, "worker", now=1, lease_seconds=1)
    assert assignment
    store.control(project, "pause", "human:test")
    assert store.project(project)["state"] == "PAUSING"
    store.expire_draining(project)
    assert store.tasks(project)[0]["owner"] is None
    assert store.tasks(project)[0]["state"] == "REPAIR_REQUIRED"
    assert store.claim(project, "replacement") is None
