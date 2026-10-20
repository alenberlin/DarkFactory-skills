"""Deterministic quality gates; model confidence grants no workflow authority."""

from collections.abc import Mapping, Sequence

from darkfactory.domain import Blueprint, GateDecision, Mode, Policy


def evaluate_checks(
    required: Sequence[str], results: Mapping[str, tuple[bool, str]], source_digest: str
) -> GateDecision:
    """Require successful trusted check results for exactly the candidate source.

    Args:
        required: Check identifiers from the protected approved blueprint.
        results: Results obtained by the controller's trusted check executor.
        source_digest: Immutable candidate being evaluated.

    Returns:
        A decision with every missing, failed or stale prerequisite identified.
    """
    reasons = []
    for check_id in required:
        result = results.get(check_id)
        if result is None:
            reasons.append(f"{check_id}: missing trusted evidence")
        elif result[1] != source_digest:
            reasons.append(f"{check_id}: stale source evidence")
        elif not result[0]:
            reasons.append(f"{check_id}: required verification failed")
    if not required:
        reasons.append("no mandatory verification configured")
    return GateDecision(allowed=not reasons, reasons=reasons)


def validate_policy(blueprint: Blueprint, policy: Policy) -> GateDecision:
    """Check a proposed blueprint against authoritative baseline policy.

    Args:
        blueprint: Project contract whose exact identity requires separate human approval.
        policy: Versioned quality/execution rules bound into the approval identity.

    Returns:
        Structured policy decision naming missing prerequisites or prohibited images.
    """
    configured = {check.kind for check in blueprint.checks if check.required}
    missing = set(policy.required_check_kinds) - configured
    reasons = [f"missing required check kind: {kind}" for kind in sorted(missing)]
    images = {blueprint.image}
    for binding in blueprint.role_bindings:
        spec = binding.inference
        images.update((spec.agent_image, spec.gateway_image))
    if blueprint.inference:
        images.update((blueprint.inference.agent_image, blueprint.inference.gateway_image))
    if policy.allowed_images and not images <= set(policy.allowed_images):
        reasons.append("container image is outside administrative policy")
        return GateDecision(allowed=False, policy_id=policy.id, reasons=reasons)
    return GateDecision(
        allowed=not reasons or blueprint.mode == Mode.ADVISORY, policy_id=policy.id, reasons=reasons
    )


def quality_decision(decision: GateDecision, mode: Mode) -> GateDecision:
    """Advisory reports quality failures; authorization and execution admission stay separate.

    Args:
        decision: Observed prerequisite decision; authorization is a separate gate.
        mode: Explicit quality mode; Advisory cannot forge final acceptance or permissions.

    Returns:
        Mode-specific quality decision retaining the original observed reasons.
    """
    if mode == Mode.ADVISORY:
        return decision.model_copy(update={"allowed": True})
    return decision
