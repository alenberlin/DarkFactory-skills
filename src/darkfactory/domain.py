"""Versioned, provider-independent task and authorization contracts."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")]


class Contract(BaseModel):
    """Reject undeclared fields at all factory trust boundaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Mode(StrEnum):
    """Declare the requested enforcement guarantee without automatic downgrade."""

    ADVISORY = "advisory"
    ENFORCED = "enforced"
    STRICT = "strict"


class Role(StrEnum):
    """Roles the trusted scheduler can assign to bounded agent attempts."""

    ORCHESTRATOR = "factory-orchestrator"
    ANALYST = "product-analyst"
    ARCHITECT = "software-architect"
    PLANNER = "implementation-planner"
    BACKEND = "backend-engineer"
    FRONTEND = "frontend-engineer"
    TEST = "test-engineer"
    SECURITY = "security-auditor"
    REVIEW = "code-reviewer"
    PERFORMANCE = "performance-auditor"
    QA = "qa-engineer"
    RELEASE = "release-engineer"
    DOCUMENTATION = "documentation-engineer"
    ACCEPTANCE = "acceptance-auditor"


class ProjectState(StrEnum):
    """Persisted project lifecycle, separate from deployment permission."""

    DRAFT = "DRAFT"
    DISCOVERY = "DISCOVERY"
    AWAITING_APPROVAL = "AWAITING_BLUEPRINT_APPROVAL"
    READY = "READY"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    FINAL_QA = "FINAL_QA"
    AWAITING_ACCEPTANCE = "READY_FOR_HUMAN_ACCEPTANCE"
    ACCEPTED = "ACCEPTED"
    PAUSING = "PAUSING"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskState(StrEnum):
    """Task status never inferred from a model's success message."""

    PENDING = "PENDING"
    READY = "READY"
    IMPLEMENTING = "IMPLEMENTING"
    VERIFYING = "VERIFYING"
    IN_REVIEW = "IN_REVIEW"
    READY_TO_INTEGRATE = "READY_TO_INTEGRATE"
    INTEGRATED = "INTEGRATED"
    REPAIR_REQUIRED = "REPAIR_REQUIRED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Requirement(Contract):
    """A scope item with an observable acceptance criterion."""

    id: Identifier
    description: str = Field(min_length=1, max_length=16000)
    acceptance: str = Field(min_length=1, max_length=16000)


class CheckSpec(Contract):
    """A protected executable definition, independent of agent-written reports."""

    id: Identifier
    argv: list[str] = Field(min_length=1, max_length=100)
    kind: Annotated[
        str, Field(pattern=r"^(test|build|typecheck|lint|security|runtime|performance|qa)$")
    ]
    requirement_ids: list[Identifier] = Field(default_factory=list)
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    required: bool = True
    allow_skipped_tests: bool = False
    expected_output: str | None = Field(default=None, max_length=4000)
    driver: str | None = Field(default=None, max_length=100000)
    service_argv: list[str] | None = Field(default=None, min_length=1, max_length=100)
    toolchain_probe: list[str] | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def valid_arguments(self) -> Self:
        """Reject empty arguments, embedded NULs and implicit shell invocation."""
        if any(not value or "\0" in value for value in self.argv):
            raise ValueError("check arguments must be nonempty and contain no NUL")
        if self.toolchain_probe and any(
            not value or "\0" in value for value in self.toolchain_probe
        ):
            raise ValueError("invalid toolchain probe arguments")
        if self.service_argv is not None:
            if self.driver is None or not self.expected_output:
                raise ValueError("black-box service checks require a protected driver and result")
            if any(not value or "\0" in value for value in self.service_argv):
                raise ValueError("invalid service arguments")
        return self


class TaskSpec(Contract):
    """A requirement-linked assignment and declared component ownership."""

    id: Identifier
    description: str = Field(min_length=1, max_length=20000)
    requirement_ids: list[Identifier] = Field(min_length=1)
    dependencies: list[Identifier] = Field(default_factory=list)
    role: Role = Role.BACKEND
    deliverables: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    check_ids: list[Identifier] = Field(default_factory=list)
    permitted_paths: list[str] = Field(default_factory=lambda: ["**"])
    security_considerations: list[str] = Field(default_factory=list)


class Permissions(Contract):
    """Explicit local effects; external release is separately authorized."""

    local_commits: bool = False
    local_integration: bool = False
    approved_network_hosts: list[str] = Field(default_factory=list)


class Limits(Contract):
    """Run bounds recorded with approval and enforced before dispatch."""

    concurrency: int = Field(default=2, ge=1, le=16)
    max_attempts: int = Field(default=3, ge=1, le=10)
    max_tokens: int = Field(default=100000, ge=1)
    max_cost_microusd: int | None = Field(default=None, ge=1)
    command_seconds: int = Field(default=300, ge=1, le=3600)
    memory_mb: int = Field(default=1024, ge=128, le=32768)
    cpus: int = Field(default=1, ge=1, le=32)
    output_bytes: int = Field(default=1048576, ge=1024, le=16777216)
    state_storage_mb: int = Field(default=4096, ge=16, le=1048576)
    require_filesystem_quota: bool = False


class Policy(Contract):
    """A schema-versioned policy activated only through trusted administration."""

    schema_version: int = Field(default=1, ge=1, le=1)
    id: Identifier = "DF-BASELINE"
    version: int = Field(default=1, ge=1)
    required_check_kinds: list[str] = Field(
        default_factory=lambda: ["test", "build", "lint", "typecheck"]
    )
    required_review_roles: list[Role] = Field(
        default_factory=lambda: [Role.REVIEW, Role.SECURITY, Role.TEST]
    )
    protect_test_paths: list[str] = Field(
        default_factory=lambda: [
            "tests/**",
            "test/**",
            "**/tests/**",
            "**/test/**",
            "conftest.py",
            "**/conftest.py",
            "pytest.ini",
            "**/pytest.ini",
            "pyproject.toml",
            "**/pyproject.toml",
            "setup.cfg",
            "**/setup.cfg",
            "tox.ini",
            "uv.lock",
            "requirements*.txt",
            "**/requirements*.txt",
            "package.json",
            "**/package.json",
            "package-lock.json",
            "**/package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "tsconfig*.json",
            "**/tsconfig*.json",
            "eslint.config.*",
            "**/eslint.config.*",
            ".eslintrc*",
            "**/.eslintrc*",
            "Cargo.toml",
            "**/Cargo.toml",
            "Cargo.lock",
            "**/Cargo.lock",
            "rust-toolchain*",
            ".cargo/**",
            "**/.cargo/**",
            "Makefile",
            "**/Makefile",
        ]
    )
    allowed_images: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def known_rules(self) -> Self:
        """Refuse undeclared check kinds and duplicate required review assignments."""
        if not set(self.required_check_kinds) <= {
            "test",
            "build",
            "lint",
            "typecheck",
            "security",
            "runtime",
            "performance",
            "qa",
        }:
            raise ValueError("unknown policy check kind")
        if len(set(self.required_review_roles)) != len(self.required_review_roles):
            raise ValueError("duplicate required review role")
        return self


class InferenceSpec(Contract):
    """Approved model, isolated CLI image and measurable per-attempt inference limits."""

    provider: Annotated[str, Field(pattern=r"^(anthropic|openai)$")]
    model: str = Field(min_length=1, max_length=200)
    agent_image: str = Field(min_length=1, max_length=300)
    gateway_image: str = "python:3.12-slim"
    attempt_tokens: int = Field(default=30000, ge=100, le=1000000)
    max_output_tokens: int = Field(default=4096, ge=100, le=32768)
    input_microusd_per_token: int | None = Field(default=None, ge=0)
    output_microusd_per_token: int | None = Field(default=None, ge=0)


class AgentConfiguration(Contract):
    """An approved native adapter/provider/model binding for an assigned role."""

    adapter: Annotated[str, Field(pattern=r"^(claude|codex)$")]
    inference: InferenceSpec

    @model_validator(mode="after")
    def compatible_provider(self) -> Self:
        """Deny unsupported provider combinations before an agent is dispatched."""
        if self.inference.provider != {"claude": "anthropic", "codex": "openai"}[self.adapter]:
            raise ValueError("unsupported adapter/provider binding")
        return self


class RoleConfiguration(AgentConfiguration):
    """An explicit model binding with a finite role identity and portable JSON schema."""

    role: Role


class PlanningDocument(Contract):
    """A bounded reviewable artifact whose path cannot overwrite factory authority."""

    name: Annotated[
        str, Field(pattern=r"^(PRD|ARCHITECTURE|DESIGN|PLAN|THREAT_MODEL|DECISIONS)\.md$")
    ]
    content: str = Field(min_length=1, max_length=100000)


class DeliverySpec(Contract):
    """Approved documentation required in the actual integrated source before delivery."""

    required_files: list[Annotated[str, Field(pattern=r"^[A-Za-z0-9_./-]{1,200}$")]] = Field(
        default_factory=lambda: ["README.md", "RUNBOOK.md"],
        max_length=20,
    )

    @model_validator(mode="after")
    def safe_paths(self) -> Self:
        """Reject absolute/traversing documentation paths and duplicate requirements."""
        if len(set(self.required_files)) != len(self.required_files) or any(
            path.startswith("/") or ".." in path.split("/") for path in self.required_files
        ):
            raise ValueError("invalid required delivery paths")
        return self


class Blueprint(Contract):
    """Approved project inputs with complete, acyclic requirement traceability."""

    schema_version: int = Field(default=1, ge=1, le=1)
    version: int = Field(default=1, ge=1)
    name: str = Field(min_length=1, max_length=200)
    architecture: str = Field(min_length=1, max_length=100000)
    requirements: list[Requirement] = Field(min_length=1, max_length=1000)
    tasks: list[TaskSpec] = Field(min_length=1, max_length=2000)
    checks: list[CheckSpec] = Field(min_length=1, max_length=200)
    non_goals: list[str] = Field(default_factory=list)
    mode: Mode = Mode.STRICT
    adapter: str = Field(default="claude", pattern=r"^[a-z][a-z0-9-]{0,63}$")
    image: str = Field(default="python:3.14-slim", min_length=1, max_length=300)
    permissions: Permissions = Field(default_factory=Permissions)
    limits: Limits = Field(default_factory=Limits)
    inference: InferenceSpec | None = None
    role_bindings: list[RoleConfiguration] = Field(default_factory=list, max_length=14)
    documents: list[PlanningDocument] = Field(default_factory=list, max_length=6)
    delivery: DeliverySpec = Field(default_factory=DeliverySpec)

    def agent_configuration(self, role: Role) -> AgentConfiguration | None:
        """Resolve an explicit role binding or the approved project default.

        Args:
            role: Finite assigned role used for instructions and approved model routing.

        Returns:
            Explicit role binding or project default; None if no native binding exists.
        """
        for binding in self.role_bindings:
            if binding.role == role:
                return binding
        if self.inference is None:
            return None
        return AgentConfiguration(adapter=self.adapter, inference=self.inference)

    @model_validator(mode="after")
    def coherent_graph(self) -> Self:
        """Validate identifiers, coverage and prerequisites before approval."""
        if len({item.role for item in self.role_bindings}) != len(self.role_bindings):
            raise ValueError("duplicate role model binding")
        if len({item.name for item in self.documents}) != len(self.documents):
            raise ValueError("duplicate blueprint document")
        requirements = {item.id for item in self.requirements}
        task_ids = {task.id for task in self.tasks}
        check_ids = {check.id for check in self.checks}
        if any(
            len(items) != count
            for items, count in (
                (requirements, len(self.requirements)),
                (task_ids, len(self.tasks)),
                (check_ids, len(self.checks)),
            )
        ):
            raise ValueError("duplicate identifiers")
        covered: set[str] = set()
        for task in self.tasks:
            if not set(task.requirement_ids) <= requirements:
                raise ValueError(f"unknown requirement in {task.id}")
            if not set(task.dependencies) <= task_ids:
                raise ValueError(f"unknown dependency in {task.id}")
            if not set(task.check_ids) <= check_ids:
                raise ValueError(f"unknown check in {task.id}")
            covered.update(task.requirement_ids)
        if covered != requirements:
            raise ValueError(f"unmapped requirements: {sorted(requirements - covered)}")
        verification_coverage: set[str] = set()
        for check in self.checks:
            if not set(check.requirement_ids) <= requirements:
                raise ValueError(f"unknown requirement in check {check.id}")
            if check.required:
                verification_coverage.update(check.requirement_ids or requirements)
        if verification_coverage != requirements:
            raise ValueError("unmapped verification requirements")
        graph = {task.id: task.dependencies for task in self.tasks}
        visited: set[str] = set()
        active: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in active:
                raise ValueError("dependency cycle")
            if task_id in visited:
                return
            active.add(task_id)
            for dependency in graph[task_id]:
                visit(dependency)
            active.remove(task_id)
            visited.add(task_id)

        for task_id in graph:
            visit(task_id)
        return self


class GateDecision(Contract):
    """A trusted evaluator's decision and structured remediation reasons."""

    allowed: bool
    policy_id: str = "DF-QUALITY-001"
    reasons: list[str] = Field(default_factory=list)


def digest(value: Contract | dict[str, object] | list[object]) -> str:
    """Return the SHA-256 of canonical JSON for an immutable factory record.

    Args:
        value: Validated contract or JSON-shaped value to hash canonically.

    Returns:
        Canonical SHA-256 content identity.
    """
    payload = value.model_dump(mode="json") if isinstance(value, Contract) else value
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
