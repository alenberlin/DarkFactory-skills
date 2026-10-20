"""Verify blueprint validity and deterministic completion prerequisites."""

import pytest
from pydantic import ValidationError

from darkfactory.domain import (
    Blueprint,
    CheckSpec,
    DeliverySpec,
    GateDecision,
    Mode,
    Policy,
    Requirement,
    TaskSpec,
)
from darkfactory.policy import evaluate_checks, quality_decision


def blueprint() -> Blueprint:
    return Blueprint(
        name="Task counter",
        requirements=[
            Requirement(id="FR-001", description="Count tasks", acceptance="Count is exact")
        ],
        tasks=[TaskSpec(id="T01", description="Count tasks", requirement_ids=["FR-001"])],
        checks=[CheckSpec(id="unit", argv=["python", "-m", "unittest"], kind="test")],
        architecture="A local task counter with deterministic behavior.",
        delivery=DeliverySpec(required_files=[]),
    )


def test_blueprint_rejects_unmapped_requirements() -> None:
    data = blueprint().model_dump()
    data["requirements"].append(
        {"id": "FR-002", "description": "Archive", "acceptance": "Archives are restored"}
    )
    with pytest.raises(ValidationError, match="unmapped"):
        Blueprint.model_validate(data)


def test_blueprint_rejects_dependency_cycles() -> None:
    data = blueprint().model_dump()
    data["tasks"][0]["dependencies"] = ["T02"]
    data["tasks"].append(
        {
            "id": "T02",
            "description": "Second",
            "requirement_ids": ["FR-001"],
            "dependencies": ["T01"],
        }
    )
    with pytest.raises(ValidationError, match="cycle"):
        Blueprint.model_validate(data)


def test_unknown_fields_and_host_shell_are_not_contracts() -> None:
    data = blueprint().model_dump()
    data["approved"] = True
    with pytest.raises(ValidationError):
        Blueprint.model_validate(data)
    with pytest.raises(ValidationError):
        CheckSpec(id="fake", argv=[], kind="test")


def test_missing_failed_and_stale_checks_block_completion() -> None:
    expected = ["test", "build"]
    assert not evaluate_checks(expected, {}, "source-a").allowed
    assert not evaluate_checks(
        expected, {"test": (True, "source-a"), "build": (False, "source-a")}, "source-a"
    ).allowed
    assert not evaluate_checks(
        expected, {"test": (True, "source-old"), "build": (True, "source-a")}, "source-a"
    ).allowed
    assert evaluate_checks(
        expected, {"test": (True, "source-a"), "build": (True, "source-a")}, "source-a"
    ).allowed


def test_modes_report_or_block_quality_without_granting_authorization() -> None:
    failed = GateDecision(allowed=False, reasons=["required test failed"])
    assert quality_decision(failed, Mode.ADVISORY).allowed
    assert quality_decision(failed, Mode.ADVISORY).reasons == failed.reasons
    assert not quality_decision(failed, Mode.ENFORCED).allowed
    assert not quality_decision(failed, Mode.STRICT).allowed
    with pytest.raises(ValidationError, match="unknown"):
        Policy(required_check_kinds=["invented"])
