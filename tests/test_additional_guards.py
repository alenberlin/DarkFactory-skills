"""Approval, role pricing and journal invariants exercised against actual state and Git."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from darkfactory.adapters import AgentReply, strict_schema
from darkfactory.domain import (
    AgentConfiguration,
    InferenceSpec,
    Limits,
    Policy,
    Role,
    RoleConfiguration,
)
from darkfactory.engine import Engine
from darkfactory.gitops import Repository
from darkfactory.storage import StateError, Store
from tests.test_contracts import blueprint
from tests.test_store import prepared_store


def test_role_bindings_are_approved_distinct_and_native_schema_is_closed() -> None:
    default = InferenceSpec(provider="anthropic", model="default-model", agent_image="agent")
    review = RoleConfiguration(
        role=Role.REVIEW,
        adapter="codex",
        inference=InferenceSpec(provider="openai", model="review-model", agent_image="review"),
    )
    proposal = blueprint().model_copy(update={"inference": default, "role_bindings": [review]})
    assert proposal.agent_configuration(Role.BACKEND).inference.model == "default-model"
    assert proposal.agent_configuration(Role.REVIEW).inference.model == "review-model"
    data = proposal.model_dump()
    data["role_bindings"].append(review.model_dump())
    with pytest.raises(ValidationError, match="duplicate role"):
        type(proposal).model_validate(data)
    with pytest.raises(ValidationError, match="binding"):
        AgentConfiguration(adapter="claude", inference=review.inference)
    schema = strict_schema(AgentReply.model_json_schema())

    def check(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(schema)


def test_cost_reservations_cover_expensive_role_and_unknown_usage_blocks(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    spec = InferenceSpec(
        provider="anthropic",
        model="default",
        agent_image="agent",
        input_microusd_per_token=1,
        output_microusd_per_token=2,
    )
    expensive = RoleConfiguration(
        role=Role.SECURITY,
        adapter="claude",
        inference=spec.model_copy(update={"output_microusd_per_token": 10}),
    )
    proposal = blueprint().model_copy(
        update={
            "inference": spec,
            "role_bindings": [expensive],
            "limits": Limits(max_tokens=1000, max_cost_microusd=1000),
        }
    )
    project = store.create_project(proposal, Policy(required_check_kinds=["test"]))
    engine = Engine(store)
    reservation = engine.reserve(project, "expensive-review", 100)
    with pytest.raises(StateError, match="monetary"):
        engine.reserve(project, "another", 1)
    engine._account(project, reservation, {"unknown": True, "tokens": 7})
    assert store.project(project)["state"] == "BLOCKED"
    with store.connection() as connection:
        assert (
            connection.execute("SELECT reserved FROM usage WHERE id=?", (reservation,)).fetchone()[
                0
            ]
            == 100
        )


def test_immutable_environment_requires_revision_and_approval(tmp_path: Path) -> None:
    store, project = prepared_store(tmp_path)
    store.record_environment(project, {"target_image": "sha256:first"})
    store.record_environment(project, {"target_image": "sha256:first"})
    with pytest.raises(StateError, match="environment changed"):
        store.record_environment(project, {"target_image": "sha256:second"})
    assert store.environment(project)["target_image"] == "sha256:first"
    assert store.verify_audit()


def test_storage_allocations_serialize_and_reject_oversubscription(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from darkfactory.resources import StorageQuota

    quota = StorageQuota(tmp_path, 1000)

    def write(name: str) -> bool:
        try:
            with quota.allocate(700):
                (tmp_path / name).write_bytes(b"x" * 700)
            return True
        except StateError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ["one", "two"]))
    assert sorted(results) == [False, True]
    assert sum(path.stat().st_size for path in tmp_path.iterdir()) == 700


def test_abandoned_usage_stays_unknown_until_human_reconciliation(tmp_path: Path) -> None:
    store, project = prepared_store(tmp_path)
    engine = Engine(store)
    reservation = engine.reserve(project, "abandoned-attempt", 100)
    engine.reconcile_usage(project)
    assert store.project(project)["state"] == "BLOCKED"
    with store.connection() as connection:
        record = connection.execute(
            "SELECT state FROM operations WHERE id=?", (reservation,)
        ).fetchone()
    assert record[0] == "UNKNOWN"
    from darkfactory.services import Factory

    factory = Factory(store)
    with pytest.raises(StateError, match="human"):
        factory.reconcile_usage(project, reservation, 0, None, "fixture-receipt", "agent:fake")
    factory.reconcile_usage(project, reservation, 0, None, "fixture-receipt", "human:test")
    assert store.project(project)["state"] == "BLOCKED"
    with pytest.raises(StateError, match="unknown"):
        factory.reconcile_usage(project, reservation, 0, None, "replay", "human:test")
    assert store.verify_audit()


@pytest.mark.docker
def test_git_effect_is_reconciled_after_database_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_engine import FixtureAdapter
    from tests.test_remediation import prepared

    factory, project = prepared(tmp_path, lambda a, b, c, role: FixtureAdapter(role))
    actual_git = Repository.git

    def interrupted(self: Repository, *args: str, **kwargs: object) -> str:
        result = actual_git(self, *args, **kwargs)
        if args[0] == "update-ref":
            raise OSError("injected controller interruption after actual Git effect")
        return result

    monkeypatch.setattr(Repository, "git", interrupted)
    factory.engine.run_one(project, "interrupted")
    reopened = Repository(Store(factory.store.root), project)
    merged = reopened.head()
    assert factory.store.tasks(project)[0]["state"] == "REPAIR_REQUIRED"
    assert factory.store.project(project)["source_digest"] != reopened.current().digest
    reopened.reconcile()
    reopened.reconcile()
    assert factory.store.tasks(project)[0]["state"] == "INTEGRATED"
    assert factory.store.project(project)["source_digest"] == reopened.current().digest
    with factory.store.connection() as connection:
        operations = connection.execute(
            "SELECT state,intent FROM operations WHERE kind='integration'"
        ).fetchall()
    assert len(operations) == 1 and operations[0]["state"] == "APPLIED"
    assert json.loads(operations[0]["intent"])["commit"] == merged
    assert factory.store.verify_audit()
