"""Run reproducible local engineering checks and preserve their actual outcomes."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "autopilot" / "evidence"


def _run(name: str, argv: list[str], *, cwd: Path = ROOT) -> dict[str, object]:
    binary = shutil.which(argv[0])
    if binary is None:
        raise RuntimeError("Required local check executable missing: " + argv[0])
    argv = [binary, *argv[1:]]
    try:
        result = subprocess.run(  # noqa: S603 -- fixed trusted local engineering commands
            argv, cwd=cwd, capture_output=True, text=True, timeout=600, check=False
        )
        output = result.stdout + result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.stdout or b"", error.stderr or b""
        output = (stdout.decode(errors="replace") if isinstance(stdout, bytes) else stdout) + (
            stderr.decode(errors="replace") if isinstance(stderr, bytes) else stderr
        )
        output += "\nValidation command exceeded its 600-second bound.\n"
        exit_code = 124
    log = EVIDENCE / (name + ".log")
    log.write_text(output)
    print(f"{name}: {'PASS' if exit_code == 0 else 'FAIL'}", flush=True)
    return {
        "name": name,
        "argv": argv,
        "exit_code": exit_code,
        "log": log.relative_to(ROOT).as_posix(),
    }


def _source_identity() -> dict[str, object]:
    directories = (
        "src",
        "tests",
        "scripts",
        "skills",
        "agents",
        "commands",
        "hooks",
        "references",
        "schemas",
        "containers",
        "examples",
        ".claude-plugin",
    )
    files = [
        path
        for name in directories
        for path in (ROOT / name).rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    files.extend(
        ROOT / name
        for name in (
            "pyproject.toml",
            "uv.lock",
            "package.json",
            "package-lock.json",
            "eslint.config.mjs",
            "playwright.config.mjs",
            "README.md",
            "ORCHESTRATOR.md",
            "AGENTS.md",
            "CLAUDE.md",
            "LICENSE",
            "NOTICE",
            "docs/AUTOPILOT.md",
            "docs/RUNTIME_CONTRACT.md",
            "docs/WORKFLOW.md",
            "docs/USER_GUIDE.md",
            "docs/PERSONAS.md",
        )
        if (ROOT / name).is_file()
    )
    files.extend(path for path in (ROOT / "docs").rglob("*.md") if path not in files)
    manifest = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(files)
    }
    return {
        "sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
        "files": manifest,
        "excluded": "Generated evidence, build outputs and development state",
    }


def _hook_checks() -> None:
    with tempfile.TemporaryDirectory(prefix="hook-", dir=ROOT / ".factory-dev") as directory:
        folder = Path(directory)
        for marker in (None, "ignore", "engage", "invalid"):
            if marker is not None:
                (folder / ".darkfactory").write_text(marker)
            result = subprocess.run(  # noqa: S603 -- pack-owned hook with disposable markers
                ["/bin/bash", str(ROOT / "hooks" / "session-start.sh")],
                cwd=folder,
                capture_output=True,
                text=True,
                check=True,
            )
            expected = {
                None: "Ask once",
                "ignore": "",
                "engage": "routing engaged",
                "invalid": "marker is invalid",
            }[marker]
            assert expected in result.stdout
            if marker == "ignore":
                assert result.stdout == ""


def main() -> None:
    """Record checks for exact local source without invoking live models or installing services.

    Raises:
        SystemExit: Any check fails or the tested source changes during verification.
    """
    EVIDENCE.mkdir(exist_ok=True)
    private = ROOT / ".factory-dev"
    private.mkdir(exist_ok=True)
    before = _source_identity()
    (EVIDENCE / "local-validation.json").write_text(
        json.dumps({"status": "RUNNING", "source": before}, indent=2) + "\n"
    )
    commands = [
        ("ruff", ["uv", "run", "ruff", "check", "src", "tests", "scripts"]),
        ("format", ["uv", "run", "ruff", "format", "--check", "src", "tests", "scripts"]),
        ("mypy", ["uv", "run", "mypy"]),
        ("dashboard-lint", ["npm", "run", "lint"]),
        ("dashboard-typecheck", ["npm", "run", "typecheck"]),
        ("dashboard-format", ["npm", "exec", "--", "prettier", "--check", "src/darkfactory/web"]),
        ("pack", ["uv", "run", "python", "scripts/validate_pack.py"]),
        ("pytest", ["uv", "run", "pytest", "-q", "--junitxml=" + str(EVIDENCE / "pytest.xml")]),
        ("browser", ["npm", "run", "test:browser"]),
        ("build", ["uv", "build"]),
    ]
    checks = [_run(name, argv) for name, argv in commands]
    _hook_checks()
    manifest = json.loads((ROOT / "docs/autopilot/BLUEPRINT_MANIFEST.json").read_text())
    for item in manifest["documents"]:
        assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    assert manifest["blueprint_sha256"] == (
        "7b2db21dbf8b6dd49fd0c2e9180006c3e919f6c743e84085dd82bebe11116407"
    )
    installation = private / ("wheel-install-" + uuid.uuid4().hex)
    constraints = private / "wheel-constraints.txt"
    checks.append(
        _run(
            "wheel-constraints",
            [
                "uv",
                "export",
                "--quiet",
                "--no-dev",
                "--no-emit-project",
                "--format",
                "requirements-txt",
                "--output-file",
                str(constraints),
            ],
        )
    )
    checks.append(
        _run("wheel-environment", ["uv", "venv", "--python", sys.executable, str(installation)])
    )
    python = installation / "bin/python"
    checks.append(
        _run(
            "wheel-install",
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--constraint",
                str(constraints),
                str(ROOT / "dist/darkfactory_autopilot-0.3.0-py3-none-any.whl"),
            ],
        )
    )
    smoke = """
from pathlib import Path
import json
import darkfactory
from darkfactory.domain import Role
from darkfactory.pack import role_context
from darkfactory.api import create_app
from darkfactory.storage import Store
root = Path(darkfactory.__file__).parent
assert "wheel-install-" in str(root), root
for role in Role:
    assert "Shared Autopilot contract" in role_context(role)
pack = root / "pack"
assert len(list((pack / "skills").glob("*/SKILL.md"))) == 24
assert len(list((pack / "agents").glob("*.md"))) == 14
assert len(list((pack / "commands").glob("*.md"))) == 7
assert (pack / "LICENSE").is_file() and (pack / "NOTICE").is_file()
assert (pack / "examples/supervision/README.md").is_file()
assert (root / "web/app.js").is_file()
app = create_app(Store(Path("api-smoke-state")), "wheel-install-validation-fixture-only")
assert "/v1/projects/{project}/approve" in app.openapi()["paths"]
print(json.dumps({"roles": 14, "skills": 24, "commands": 7, "resources": "present"}))
"""
    checks.append(_run("wheel-resources", [str(python), "-I", "-c", smoke], cwd=installation))
    checks.append(
        _run(
            "installed-cli",
            [
                str(installation / "bin/factory"),
                "--state",
                str(installation / "cli-smoke-state"),
                "status",
            ],
            cwd=installation,
        )
    )
    images = [
        "python:3.12-slim",
        "rust:1.98.1-slim-bookworm",
        "darkfactory-native-adapters:0.3.0",
        "darkfactory-python-tools:0.3.0",
        "darkfactory-rust-tools:0.3.0",
        "darkfactory-mixed-tools:0.3.0",
    ]
    image_ids = subprocess.run(  # noqa: S603 -- read-only declared local image metadata
        [
            str(shutil.which("docker")),
            "image",
            "inspect",
            *images,
            "--format",
            "{{.RepoTags}} {{.Id}}",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    unchanged = before == _source_identity()
    passed = unchanged and all(item["exit_code"] == 0 for item in checks)
    report = {
        "status": "PASS" if passed else "FAIL",
        "completed_at": datetime.now(UTC).isoformat(),
        "source": before,
        "checks": checks,
        "source_unchanged": unchanged,
        "hook_states": "missing/ignore/engage/invalid passed",
        "frozen_blueprint": "unchanged",
        "images": image_ids.splitlines(),
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "sqlite": sqlite3.sqlite_version,
        },
        "live_provider": "Not exercised; explicitly pending at operator request",
        "full_acceptance": "OPEN; real-project/live acceptance remains operator-dependent",
        "browser": json.loads((EVIDENCE / "browser-tests.json").read_text())["stats"],
        "pytest": {
            key: int(value)
            for key, value in re.findall(
                r'(tests|errors|failures|skipped)="(\d+)"',
                (EVIDENCE / "pytest.xml").read_text()[:1000],
            )
        },
    }
    (EVIDENCE / "local-validation.json").write_text(json.dumps(report, indent=2) + "\n")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
