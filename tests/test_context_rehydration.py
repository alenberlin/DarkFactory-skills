"""Bound inference input without silently losing scope or source inspection capability."""

import json
from pathlib import Path

import pytest

from darkfactory.context import build_context, context_inputs
from darkfactory.domain import InferenceSpec, Policy
from darkfactory.execution import DockerExecutor
from darkfactory.storage import StateError, Store
from tests.test_contracts import blueprint


def test_large_source_context_is_bounded_and_omissions_are_explicit(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    spec = InferenceSpec(
        provider="anthropic", model="fixture", agent_image="fixture", attempt_tokens=30000
    )
    proposal = blueprint().model_copy(update={"inference": spec})
    project = store.create_project(proposal, Policy(required_check_kinds=["test"]))
    source = tmp_path / "source"
    source.mkdir()
    for index in range(100):
        (source / f"module_{index}.py").write_text("value = 1\n" * 2000)
    context = build_context(store, project, proposal.tasks[0], source, "observed failure", [])
    record = json.loads(context)
    assert len(context.encode()) < spec.attempt_tokens * 2
    assert record["omitted_source_count"] > 0
    assert record["source_manifest_path"] == "/trusted/manifest"
    assert record["approved_scope_path"] == "/trusted/blueprint"
    assert record["assignment"] == proposal.tasks[0].model_dump(mode="json")


@pytest.mark.docker
def test_actual_contained_inspection_can_read_protected_scope_and_manifest(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    proposal = blueprint()
    project = store.create_project(proposal, Policy(required_check_kinds=["test"]))
    source = tmp_path / "source"
    source.mkdir()
    (source / "example.txt").write_text("actual source")
    files = context_inputs(store, project, source)
    result = DockerExecutor("python:3.12-slim").run(
        source,
        [
            "python",
            "-I",
            "-c",
            "import json,pathlib\n"
            "approved=json.loads(pathlib.Path('/trusted/blueprint').read_text())\n"
            "assert approved['name']=='Task counter'\n"
            "manifest=json.loads(pathlib.Path('/trusted/manifest').read_text())\n"
            "assert manifest[0]['path']=='example.txt'\n"
            "try:\n pathlib.Path('/trusted/blueprint').write_text('forged')\n"
            "except OSError:\n print('protected inspection passed')\n"
            "else:\n raise AssertionError('protected scope was writable')\n",
        ],
        proposal.limits,
        readonly=True,
        trusted_files=files,
    )
    assert result.exit_code == 0 and "protected inspection passed" in result.stdout
    assert store.blueprint(project) == proposal


def test_context_artifact_tampering_is_rejected(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    project = store.create_project(blueprint(), Policy(required_check_kinds=["test"]))
    source = tmp_path / "source"
    source.mkdir()
    path = context_inputs(store, project, source)["blueprint"]
    path.chmod(0o600)
    path.write_text("forged")
    with pytest.raises(StateError, match="integrity"):
        context_inputs(store, project, source)


def test_idle_wal_anchor_preserves_state_without_last_reader_checkpoint(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    project = store.create_project(blueprint(), Policy(required_check_kinds=["test"]))
    for _ in range(5):
        assert store.project(project)["state"] == "AWAITING_BLUEPRINT_APPROVAL"
        assert Path(str(store.database) + "-wal").exists()
    store.close()
    reopened = Store(store.root)
    assert reopened.project(project)["state"] == "AWAITING_BLUEPRINT_APPROVAL"
    assert reopened.verify_audit()
    reopened.close()
