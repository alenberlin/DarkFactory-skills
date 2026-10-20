"""Real concurrent factory tasks retain merged evidence and independent source ownership."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from darkfactory.adapters import AgentReply, FileEdit
from darkfactory.domain import CheckSpec, Limits, Permissions, Policy, Role, TaskSpec
from darkfactory.engine import Engine
from darkfactory.gitops import Repository
from darkfactory.services import Factory
from darkfactory.storage import Store
from tests.test_contracts import blueprint
from tests.test_engine import FixtureAdapter


@pytest.mark.docker
def test_concurrent_scoped_tasks_reverify_actual_merged_source(tmp_path: Path) -> None:
    barrier = threading.Barrier(2)

    class ParallelFixture(FixtureAdapter):
        def propose(self, context: str, workspace: Path, limits: Limits) -> AgentReply:
            if self.role == Role.BACKEND:
                task = json.loads(context)["assignment"]["id"]
                barrier.wait(timeout=20)
                name = "a" if task == "T01" else "b"
                return AgentReply(
                    status="complete",
                    summary="Independent scoped fixture",
                    files=[FileEdit(path=name + ".txt", content=name)],
                )
            return super().propose(context, workspace, limits)

    store = Store(tmp_path / "state")
    engine = Engine(store, lambda a, b, c, role: ParallelFixture(role))
    factory = Factory(store, engine)
    source = tmp_path / "source"
    source.mkdir()
    checks = [
        CheckSpec(
            id=name,
            kind="test",
            argv=["python", "-I", "{driver}"],
            driver=(
                "from pathlib import Path\n"
                f"assert Path('{name}.txt').read_text() == '{name}'\n"
                f"print('checked {name}')\n"
            ),
            expected_output="checked " + name,
        )
        for name in ("a", "b")
    ]
    tasks = [
        TaskSpec(
            id="T0" + str(i + 1),
            description="Independent " + name,
            requirement_ids=["FR-001"],
            permitted_paths=[name + ".txt"],
            check_ids=[name],
        )
        for i, name in enumerate(("a", "b"))
    ]
    proposal = blueprint().model_copy(
        update={
            "tasks": tasks,
            "checks": checks,
            "image": "python:3.12-slim",
            "permissions": Permissions(local_commits=True, local_integration=True),
        }
    )
    project = factory.propose(proposal, Policy(required_check_kinds=["test"]), source)
    store.approve(project, store.project(project)["blueprint_hash"], "human:test")
    factory.start(project)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(engine.run_one, project, "parallel-" + name) for name in ("a", "b")]
        assert all(future.result(timeout=30) for future in futures)
    snapshot = Repository(store, project).current()
    assert (snapshot.path / "a.txt").read_text() == "a"
    assert (snapshot.path / "b.txt").read_text() == "b"
    report = factory.report(project)
    assert report["project"]["state"] == "READY_FOR_HUMAN_ACCEPTANCE", report
    assert all(item["gate"]["allowed"] for item in report["acceptance_matrix"])
    assert {
        row["check_id"]
        for row in report["checks"]
        if row["source_digest"] == snapshot.digest and row["passed"]
    } == {"a", "b"}
    assert len({row["source_digest"] for row in report["checks"]}) == 3
    assert report["audit_intact"]
