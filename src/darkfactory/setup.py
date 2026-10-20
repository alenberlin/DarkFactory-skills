"""Create credential-free, unapproved operator configuration for an explicit project."""

from __future__ import annotations

from pathlib import Path

from darkfactory.domain import InferenceSpec, Limits, Policy
from darkfactory.profiles import project_profile
from darkfactory.storage import Record, StateError


def initialize(
    destination: Path,
    provider: str,
    model: str,
    max_tokens: int,
    language: str,
    *,
    image: str | None = None,
    max_cost_microusd: int | None = None,
    input_rate: int | None = None,
    output_rate: int | None = None,
    require_filesystem_quota: bool = False,
) -> Record:
    """Write configuration proposals without credentials, approval or inference effects.

    Args:
        destination: New configuration directory, separate from application source.
        provider: Explicit OpenAI or Anthropic provider choice.
        model: Operator-selected model identifier.
        max_tokens: Explicit total planning/run token allowance proposal.
        language: Python, Node, Rust or node-rust toolchain profile.
        image: Optional locally provisioned target image override.
        max_cost_microusd: Optional monetary allowance proposal in exact units.
        input_rate: Conservative input price per token in micro-USD.
        output_rate: Conservative output price per token in micro-USD.
        require_filesystem_quota: Require a kernel-bounded state filesystem at admission.

    Returns:
        Created paths and the adapter to use for planning.

    Raises:
        StateError: Configuration would overwrite files or lacks required monetary rates.
        ValueError: A provider/profile/limit is invalid.
    """
    if destination.exists() or destination.is_symlink() or not destination.parent.is_dir():
        raise StateError("initial configuration directory must be new with an existing parent")
    if provider not in ("openai", "anthropic"):
        raise ValueError("unsupported provider")
    if max_cost_microusd is not None and (input_rate is None or output_rate is None):
        raise StateError("a monetary limit requires explicit conservative input/output rates")
    images = {
        "python": "darkfactory-python-tools:0.3.0",
        "node": "darkfactory-native-adapters:0.3.0",
        "rust": "darkfactory-rust-tools:0.3.0",
        "node-rust": "darkfactory-mixed-tools:0.3.0",
    }
    if language not in images:
        raise ValueError("unsupported language profile")
    profile = project_profile(language, image or images[language])
    inference = InferenceSpec(
        provider=provider,
        model=model,
        agent_image="darkfactory-native-adapters:0.3.0",
        attempt_tokens=min(30000, max_tokens),
        input_microusd_per_token=input_rate,
        output_microusd_per_token=output_rate,
    )
    limits = Limits(
        max_tokens=max_tokens,
        max_cost_microusd=max_cost_microusd,
        require_filesystem_quota=require_filesystem_quota,
    )
    destination.mkdir(mode=0o700)
    for name, data in (
        ("inference.json", inference),
        ("limits.json", limits),
        ("policy.json", Policy()),
        ("profile.json", profile),
    ):
        (destination / name).write_text(data.model_dump_json(indent=2) + "\n")
    (destination / "README.md").write_text(
        "# Proposed operator configuration\n\n"
        "No provider call, blueprint approval, source change or service installation occurred.\n\n"
        "1. Review inference.json and limits.json; prices are conservative operator bounds, "
        "not a provider billing guarantee.\n"
        "2. Provision the selected images and all application dependencies.\n"
        "3. Enroll a dedicated provider credential through the protected operator channel.\n"
        "4. Run factory discover with these inference/limits files, your goal and a separate "
        "application source directory. Pass --profile profile.json for this toolchain.\n"
        "5. Answer material questions and inspect the complete generated blueprint.\n"
        "6. Approve its exact digest, run preflight, then start the Strict worker. "
        "Use factory run for explicitly attached foreground quality modes.\n\n"
        "Policy and profile files are proposals; editing them cannot activate runtime authority. "
        "Do not store credentials in this directory.\n"
    )
    return {
        "directory": str(destination.resolve()),
        "adapter": "codex" if provider == "openai" else "claude",
        "provider_calls": 0,
        "approved": False,
        "files": sorted(path.name for path in destination.iterdir()),
    }
