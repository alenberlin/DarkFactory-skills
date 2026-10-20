"""Use actual contained checks and Git for all declared foreground quality modes."""

from pathlib import Path

import pytest

from darkfactory.cli import worker
from darkfactory.domain import CheckSpec, Mode, Permissions, Policy, TaskState
from darkfactory.engine import Engine
from darkfactory.gitops import Repository
from darkfactory.services import Factory
from darkfactory.storage import StateError, Store
from tests.test_contracts import blueprint
from tests.test_engine import FixtureAdapter


def project_for_mode(tmp_path: Path, mode: Mode, *, failing: bool = False) -> tuple[Factory, str]:
    """Prepare an explicitly approved fixture with real checks and isolated local effects."""
    store = Store(tmp_path / "state")
    engine = Engine(store, lambda a, b, c, role: FixtureAdapter(role), foreground=True)
    factory = Factory(store, engine)
    source = tmp_path / "source"
    source.mkdir()
    spec = CheckSpec(
        id="unit",
        kind="test",
        argv=["python", "-I", "{driver}"],
        driver="from pathlib import Path\n"
        + f"assert Path('value.txt').read_text() == {'incorrect' if failing else 'correct'!r}\n"
        + "print('protected criterion passed')\n",
        expected_output="protected criterion passed",
    )
    proposal = blueprint().model_copy(
        update={
            "mode": mode,
            "image": "python:3.12-slim",
            "checks": [spec],
            "permissions": Permissions(local_commits=True, local_integration=True),
        }
    )
    project = factory.propose(proposal, Policy(required_check_kinds=["test"]), source)
    store.approve(project, store.project(project)["blueprint_hash"], "human:fixture")
    return factory, project


@pytest.mark.docker
@pytest.mark.parametrize("mode", list(Mode))
def test_explicit_foreground_modes_execute_real_verified_work(tmp_path: Path, mode: Mode) -> None:
    factory, project = project_for_mode(tmp_path, mode)
    factory.start(project)
    factory.engine.run_one(project, "foreground-fixture")
    assert factory.store.project(project)["state"] == "READY_FOR_HUMAN_ACCEPTANCE", factory.report(
        project
    )
    assert (
        Repository(factory.store, project).current().path / "value.txt"
    ).read_text() == "correct"
    assert factory.store.verify_audit()


@pytest.mark.docker
@pytest.mark.parametrize("mode", [Mode.ADVISORY, Mode.ENFORCED])
def test_non_strict_modes_cannot_enter_unattended_execution(tmp_path: Path, mode: Mode) -> None:
    factory, project = project_for_mode(tmp_path, mode)
    background = Engine(factory.store)
    with pytest.raises(StateError, match="background scheduling"):
        background.admit(project)
    with pytest.raises(StateError, match="foreground"):
        background.run_one(project, "unattended-bypass")
    with pytest.raises(StateError, match="Strict"):
        worker(factory.store, project, once=True)
    assert factory.store.tasks(project)[0]["attempts"] == 0


@pytest.mark.docker
def test_missing_toolchain_refuses_admission_before_any_agent_attempt(tmp_path: Path) -> None:
    factory, project = project_for_mode(tmp_path, Mode.STRICT)
    proposal = factory.store.blueprint(project)
    proposal = proposal.model_copy(
        update={
            "version": proposal.version + 1,
            "checks": [
                proposal.checks[0].model_copy(update={"toolchain_probe": ["cargo", "--version"]})
            ],
        }
    )
    project = factory.revise(project, proposal, factory.store.policy(project))
    factory.store.approve(
        project, factory.store.project(project)["blueprint_hash"], "human:fixture"
    )
    with pytest.raises(StateError, match="toolchain probe"):
        factory.engine.admit(project)
    assert factory.store.tasks(project)[0]["attempts"] == 0


@pytest.mark.docker
@pytest.mark.parametrize("mode", [Mode.ADVISORY, Mode.ENFORCED])
def test_advisory_reports_failed_quality_but_never_fabricates_delivery(
    tmp_path: Path,
    mode: Mode,
) -> None:
    factory, project = project_for_mode(tmp_path, mode, failing=True)
    factory.start(project)
    factory.engine.run_one(project, "foreground-fixture")
    report = factory.report(project)
    assert any(not check["passed"] for check in report["checks"])
    assert report["project"]["state"] != "READY_FOR_HUMAN_ACCEPTANCE"
    assert factory.store.tasks(project)[0]["state"] == TaskState.REPAIR_REQUIRED
    current = Repository(factory.store, project).current().path / "value.txt"
    assert current.exists() == (mode == Mode.ADVISORY)
    with pytest.raises(StateError, match="revision"):
        factory.accept(project, report["project"]["source_digest"], "human:fixture")
