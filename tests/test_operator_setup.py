"""Operator setup writes validated proposals without provider, approval or overwrite effects."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from darkfactory.domain import Blueprint, DeliverySpec, InferenceSpec, Limits, Policy, digest
from darkfactory.execution import SnapshotStore
from darkfactory.profiles import Profile
from darkfactory.setup import initialize
from darkfactory.storage import StateError, Store
from darkfactory.verification import Verifier
from tests.test_contracts import blueprint


@pytest.mark.parametrize("language", ["python", "node", "rust", "node-rust"])
def test_setup_configs_are_valid_unapproved_and_credential_free(
    tmp_path: Path, language: str
) -> None:
    destination = tmp_path / "config"
    report = initialize(destination, "openai", "operator-selected-model", 50000, language)
    assert report["provider_calls"] == 0 and not report["approved"]
    InferenceSpec.model_validate_json((destination / "inference.json").read_text())
    Limits.model_validate_json((destination / "limits.json").read_text())
    Policy.model_validate_json((destination / "policy.json").read_text())
    profile = Profile.model_validate_json((destination / "profile.json").read_text())
    assert profile.name == language
    assert not list(destination.glob("*credential*"))
    with pytest.raises(StateError, match="new"):
        initialize(destination, "openai", "other", 50000, language)


def test_missing_monetary_prices_fail_before_any_config_files_are_created(tmp_path: Path) -> None:
    with pytest.raises(StateError, match="rates"):
        initialize(tmp_path / "config", "openai", "model", 1000, "python", max_cost_microusd=1)
    assert not (tmp_path / "config").exists()


def test_actual_init_cli_creates_only_configuration_proposals(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "darkfactory.cli",
            "--state",
            str(tmp_path / "state"),
            "init",
            str(tmp_path / "config"),
            "--provider",
            "openai",
            "--model",
            "fixture-model",
            "--max-tokens",
            "1000",
            "--profile",
            "python",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["provider_calls"] == 0
    assert not (tmp_path / "state").exists()


def test_delivery_requires_actual_nonempty_readme_and_runbook(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    proposal = blueprint().model_copy(update={"delivery": DeliverySpec()})
    project = store.create_project(proposal, Policy(required_check_kinds=["test"]))
    source = tmp_path / "source"
    source.mkdir()
    snapshots = SnapshotStore(store.root / "snapshots")
    empty = snapshots.capture(source)
    assert not Verifier(store).delivery_gate(project, empty.digest).allowed
    (source / "README.md").write_text(
        "# Setup\n\nRun the approved application command from this directory."
    )
    (source / "RUNBOOK.md").write_text(
        "# Operations\n\nPreserve the data before restart and follow the approved recovery steps."
    )
    documented = snapshots.capture(source)
    assert Verifier(store).delivery_gate(project, documented.digest).allowed
    with pytest.raises(ValueError):
        DeliverySpec(required_files=["../outside.md"])


def test_safe_new_defaults_preserve_exact_legacy_approval_identity(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    proposal = blueprint()
    project = store.create_project(proposal, Policy(required_check_kinds=["test"]))
    legacy = proposal.model_dump(mode="json")
    legacy["limits"].pop("require_filesystem_quota")
    legacy.pop("delivery")
    identity = digest(legacy)
    with store.connection() as connection:
        connection.execute(
            "UPDATE projects SET blueprint=?,blueprint_hash=? WHERE id=?",
            (json.dumps(legacy), identity, project),
        )
    store.approve(project, identity, "human:fixture")
    assert store.current_approval(project)
    assert not store.blueprint(project).limits.require_filesystem_quota
    assert Blueprint.model_validate(legacy).delivery.required_files == ["README.md", "RUNBOOK.md"]
