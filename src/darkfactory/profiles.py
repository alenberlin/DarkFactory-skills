"""Language-neutral verification profiles select actual project/toolchain commands."""

from darkfactory.domain import CheckSpec, Contract

TARGET_OUTPUT = "/tmp/target"  # noqa: S108 -- bounded isolated container tmpfs
BUILD_OUTPUT = "/tmp/dist"  # noqa: S108 -- bounded isolated container tmpfs


class Profile(Contract):
    """Operator-selected local image and project-owned real verification commands."""

    name: str
    image: str
    probe: list[str]
    checks: list[CheckSpec]
    notes: str


def project_profile(language: str, image: str) -> Profile:
    """Return a starting profile; the operator must approve actual commands for the target project.

    Args:
        language: Python, Node.js/TypeScript, Rust or node-rust profile name.
        image: Explicit locally provisioned toolchain image.

    Returns:
        A profile proposal with real verification argument vectors.

    Raises:
        ValueError: The requested language profile is unsupported.
    """
    commands = {
        "python": (
            "python",
            [
                ("test", ["python", "-m", "pytest", "-p", "no:cacheprovider"]),
                ("typecheck", ["mypy", "--cache-dir=/tmp/mypy", "."]),
                ("lint", ["ruff", "check", "--no-cache", "."]),
                ("build", ["python", "-m", "build", "--no-isolation", "--outdir", BUILD_OUTPUT]),
            ],
        ),
        "node": (
            "node",
            [
                ("test", ["npm", "test"]),
                ("typecheck", ["npm", "run", "typecheck"]),
                ("lint", ["npm", "run", "lint"]),
                ("build", ["npm", "run", "build"]),
            ],
        ),
        "rust": (
            "cargo",
            [
                ("test", ["cargo", "test", "--locked", "--offline", "--target-dir", TARGET_OUTPUT]),
                (
                    "typecheck",
                    ["cargo", "check", "--locked", "--offline", "--target-dir", TARGET_OUTPUT],
                ),
                (
                    "lint",
                    [
                        "cargo",
                        "clippy",
                        "--locked",
                        "--offline",
                        "--target-dir",
                        TARGET_OUTPUT,
                        "--",
                        "-D",
                        "warnings",
                    ],
                ),
                (
                    "build",
                    ["cargo", "build", "--locked", "--offline", "--target-dir", TARGET_OUTPUT],
                ),
            ],
        ),
    }
    if language == "node-rust":
        node = project_profile("node", image)
        rust = project_profile("rust", image)
        mixed_checks = [
            spec.model_copy(
                update={
                    "id": "node-" + spec.id,
                    "argv": ["npm", "--prefix", "node", *spec.argv[1:]],
                }
            )
            for spec in node.checks
        ]
        mixed_checks.extend(
            spec.model_copy(
                update={
                    "id": "rust-" + spec.id,
                    "argv": [*spec.argv[:2], "--manifest-path", "rust/Cargo.toml", *spec.argv[2:]],
                }
            )
            for spec in rust.checks
        )
        return Profile(
            name=language,
            image=image,
            probe=["node", "--version"],
            checks=mixed_checks,
            notes="Mixed node/ and rust/ workspace. Both toolchains and all eight checks "
            "must be provisioned and approved; add independent acceptance drivers.",
        )
    if language not in commands:
        raise ValueError("unknown language profile")
    probe, checks = commands[language]
    tool_probes = {
        "python": {
            "test": ["python", "-m", "pytest", "--version"],
            "typecheck": ["mypy", "--version"],
            "lint": ["ruff", "--version"],
            "build": ["python", "-m", "build", "--version"],
        },
        "node": {kind: ["npm", "--version"] for kind, _ in checks},
        "rust": {
            kind: ["cargo", "clippy", "--version"] if kind == "lint" else ["cargo", "--version"]
            for kind, _ in checks
        },
    }
    return Profile(
        name=language,
        image=image,
        probe=[probe, "--version"],
        checks=[
            CheckSpec(id=kind, kind=kind, argv=argv, toolchain_probe=tool_probes[language][kind])
            for kind, argv in checks
        ],
        notes=(
            "Proposal only. Provision dependencies in the immutable image. Use /tmp for "
            "bounded build outputs, configure project scripts accordingly, and add protected "
            "acceptance drivers with positive result markers. Mixed projects compose mapped "
            "checks from several profiles."
        ),
    )
