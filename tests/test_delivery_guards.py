"""Protected baseline and the latest adverse judgment remain mandatory delivery gates."""

import time
import uuid
from pathlib import Path

import pytest

from darkfactory.engine import Engine
from darkfactory.execution import SnapshotStore
from darkfactory.services import Factory
from darkfactory.storage import StateError
from tests.test_engine import FixtureAdapter
from tests.test_remediation import prepared
from tests.test_store import prepared_store


def test_deleted_or_weakened_baseline_test_is_rejected(tmp_path: Path) -> None:
    store, project = prepared_store(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    tests = source / "tests"
    tests.mkdir()
    test = tests / "test_required.py"
    test.write_text("def test_required():\n    assert 1 == 2\n")
    snapshots = SnapshotStore(store.root / "snapshots")
    baseline = snapshots.capture(source)
    for weakened in ("def test_required():\n    pass\n", None):
        if weakened is None:
            test.unlink()
        else:
            test.write_text(weakened)
        candidate = snapshots.capture(source)
        with pytest.raises(StateError, match="protected baseline"):
            Engine(store)._protected(project, baseline, candidate)


@pytest.mark.docker
def test_acceptance_uses_latest_review_and_current_approval(tmp_path: Path) -> None:
    factory, project = prepared(tmp_path, lambda a, b, c, role: FixtureAdapter(role))
    factory.engine.run_one(project, "fixture")
    delivery = factory.store.project(project)["delivery_digest"]
    with factory.store.connection() as connection:
        connection.execute(
            "INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?)",
            (
                uuid.uuid4().hex,
                project,
                None,
                delivery,
                "security-auditor",
                "adverse-independent-review",
                "BLOCK",
                "{}",
                time.time(),
            ),
        )
    with pytest.raises(StateError, match="final independent reviews"):
        factory.accept(project, delivery, "human:test")
    assert factory.store.project(project)["state"] == "READY_FOR_HUMAN_ACCEPTANCE"
    with factory.store.connection() as connection:
        connection.execute("DELETE FROM approvals WHERE project_id=?", (project,))
    with pytest.raises(StateError, match="verification/audit"):
        Factory(factory.store).accept(project, delivery, "human:test")
