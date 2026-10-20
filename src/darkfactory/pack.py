"""Load shipped role prompts and skills consistently from source or installed wheels."""

from pathlib import Path

from darkfactory.domain import Role

ROLE_SKILLS: dict[Role, list[str]] = {
    Role.ORCHESTRATOR: ["factory-control", "durable-execution", "parallel-integration"],
    Role.ANALYST: ["product-discovery"],
    Role.ARCHITECT: ["architect", "api-and-interface-design"],
    Role.PLANNER: ["implementation-planning"],
    Role.BACKEND: ["incremental-implementation", "test-driven-development"],
    Role.FRONTEND: ["ui-engineering", "incremental-implementation"],
    Role.TEST: ["test-driven-development"],
    Role.SECURITY: ["security-and-hardening"],
    Role.REVIEW: ["code-review"],
    Role.PERFORMANCE: ["performance-optimization"],
    Role.QA: ["quality-assurance"],
    Role.RELEASE: ["git-and-shipping"],
    Role.DOCUMENTATION: ["documentation-delivery"],
    Role.ACCEPTANCE: ["acceptance-validation"],
}


def role_context(role: Role) -> str:
    """Read only the shipped instructions relevant to one scheduled responsibility.

    Args:
        role: Finite assigned role used for instructions and approved model routing.

    Returns:
        Registered role instructions including the shared authority contract.
    """
    root = Path(__file__).parent / "pack"
    if not root.exists():
        root = Path(__file__).resolve().parents[2]
    documents = [
        (root / "docs" / "RUNTIME_CONTRACT.md").read_text(),
        (root / "agents" / (role.value + ".md")).read_text(),
    ]
    documents.extend(
        (root / "skills" / name / "SKILL.md").read_text() for name in ROLE_SKILLS[role]
    )
    return "\n\n".join(documents)
