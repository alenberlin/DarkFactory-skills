"""Real contained behavior proves the factory executes different project languages."""

import json
from pathlib import Path

import pytest

from darkfactory.domain import Limits
from darkfactory.execution import DockerExecutor
from darkfactory.profiles import project_profile


@pytest.mark.docker
@pytest.mark.parametrize(
    ("image", "filename", "code", "argv"),
    [
        (
            "python:3.12-slim",
            "case.py",
            "assert sum([2,3]) == 5\nprint('behavior passed')\n",
            ["python", "-I", "case.py"],
        ),
        (
            "darkfactory-native-adapters:0.3.0",
            "case.js",
            "require('node:assert/strict').equal(2+3,5);console.log('behavior passed');\n",
            ["node", "case.js"],
        ),
        (
            "darkfactory-native-adapters:0.3.0",
            "case.ts",
            "const sum=(a:number,b:number):number=>a+b; "
            "if(sum(2,3)!==5)throw Error('bad'); console.log('behavior passed');\n",
            [
                "sh",
                "-c",
                "tsc case.ts --outDir /tmp/typescript --target ES2022 --module commonjs "
                "&& node /tmp/typescript/case.js",
            ],
        ),
        (
            "rust:1.98.1-slim-bookworm",
            "case.rs",
            'fn main() { assert_eq!(2+3,5); println!("behavior passed"); }\n',
            ["sh", "-c", "rustc case.rs -o /tmp/case && /tmp/case"],
        ),
    ],
)
def test_real_language_execution(
    image: str, filename: str, code: str, argv: list[str], tmp_path: Path
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / filename).write_text(code)
    executor = DockerExecutor(image)
    result = executor.run(source, argv, Limits(command_seconds=30), readonly=True)
    assert result.exit_code == 0, result.stderr
    assert "behavior passed" in result.stdout
    (source / filename).write_text(
        code.replace("== 5", "== 6")
        .replace("equal(2+3,5)", "equal(2+3,6)")
        .replace("assert_eq!(2+3,5)", "assert_eq!(2+3,6)")
        .replace("sum(2,3)!==5", "sum(2,3)!==6")
    )
    failed = executor.run(source, argv, Limits(command_seconds=30), readonly=True)
    assert failed.exit_code != 0


def test_profiles_choose_real_commands_and_require_explicit_toolchain_images() -> None:
    for name in ("python", "node", "rust", "node-rust"):
        profile = project_profile(name, "operator-approved-image")
        assert {check.kind for check in profile.checks} == {"test", "typecheck", "lint", "build"}
        assert profile.image == "operator-approved-image"
    with pytest.raises(ValueError):
        project_profile("unknown", "image")


@pytest.mark.docker
def test_real_rust_profile_test_typecheck_lint_and_build(tmp_path: Path) -> None:
    source = tmp_path / "crate"
    source.mkdir()
    (source / "src").mkdir()
    (source / "Cargo.toml").write_text(
        '[package]\nname="factory_fixture"\nversion="0.1.0"\nedition="2024"\n'
    )
    (source / "Cargo.lock").write_text(
        'version = 4\n[[package]]\nname = "factory_fixture"\nversion = "0.1.0"\n'
    )
    (source / "src/lib.rs").write_text(
        "pub fn sum(a:u32,b:u32)->u32 { a+b }\n#[test] fn adds() {assert_eq!(sum(2,3),5);}\n"
    )
    profile = project_profile("rust", "darkfactory-rust-tools:0.3.0")
    executor = DockerExecutor(profile.image)
    for check in profile.checks:
        result = executor.run(source, check.argv, Limits(command_seconds=60), readonly=True)
        assert result.exit_code == 0, (check.kind, result.stderr)
    (source / "src/lib.rs").write_text(
        "pub fn sum(a:u32,b:u32)->u32 { a-b }\n#[test] fn adds() {assert_eq!(sum(2,3),5);}\n"
    )
    result = executor.run(source, profile.checks[0].argv, Limits(command_seconds=60), readonly=True)
    assert result.exit_code != 0 and "FAILED" in result.stdout


@pytest.mark.docker
def test_real_python_profile_test_typecheck_lint_and_build(tmp_path: Path) -> None:
    source = tmp_path / "package"
    source.mkdir()
    (source / "src/counter").mkdir(parents=True)
    (source / "tests").mkdir()
    (source / "pyproject.toml").write_text(
        '[build-system]\nrequires=["hatchling"]\nbuild-backend="hatchling.build"\n'
        '[project]\nname="counter"\nversion="0.1.0"\n'
        '[tool.pytest.ini_options]\npythonpath=["src"]\n'
    )
    (source / "src/counter/__init__.py").write_text(
        "def sum_values(a: int, b: int) -> int:\n    return a + b\n"
    )
    (source / "tests/test_counter.py").write_text(
        "from counter import sum_values\n\n\ndef test_adds() -> None:\n"
        "    assert sum_values(2, 3) == 5\n"
    )
    profile = project_profile("python", "darkfactory-python-tools:0.3.0")
    executor = DockerExecutor(profile.image)
    for check in profile.checks:
        result = executor.run(source, check.argv, Limits(command_seconds=60), readonly=True)
        assert result.exit_code == 0, (check.kind, result.stdout, result.stderr)
    (source / "src/counter/__init__.py").write_text(
        "def sum_values(a: int, b: int) -> int:\n    return a - b\n"
    )
    failed = executor.run(source, profile.checks[0].argv, Limits(command_seconds=60), readonly=True)
    assert failed.exit_code != 0 and "FAILED" in failed.stdout


@pytest.mark.docker
def test_real_node_typescript_profile_test_typecheck_lint_and_build(tmp_path: Path) -> None:
    source = tmp_path / "node-package"
    source.mkdir()
    (source / "src").mkdir()
    (source / "tests").mkdir()
    compiler = "tsc --target ES2022 --module NodeNext --moduleResolution NodeNext src/sum.ts"
    (source / "package.json").write_text(
        json.dumps(
            {
                "name": "factory-node-fixture",
                "version": "0.1.0",
                "type": "module",
                "private": True,
                "scripts": {
                    "test": "node --experimental-strip-types --test tests/sum.test.mjs",
                    "typecheck": compiler + " --noEmit --strict",
                    "lint": "node --check tests/sum.test.mjs && "
                    + compiler
                    + " --noEmit --noUnusedLocals --noUnusedParameters",
                    "build": compiler + " --outDir /tmp/node-dist",
                },
            }
        )
    )
    (source / "src/sum.ts").write_text(
        "export function sum(a:number,b:number):number { return a+b; }\n"
    )
    (source / "tests/sum.test.mjs").write_text(
        'import assert from "node:assert/strict";\nimport test from "node:test";\n'
        'import {sum} from "../src/sum.ts";\ntest("adds",()=>assert.equal(sum(2,3),5));\n'
    )
    profile = project_profile("node", "darkfactory-native-adapters:0.3.0")
    executor = DockerExecutor(profile.image)
    for check in profile.checks:
        result = executor.run(source, check.argv, Limits(command_seconds=60), readonly=True)
        assert result.exit_code == 0, (check.kind, result.stdout, result.stderr)
    (source / "src/sum.ts").write_text(
        "export function sum(a:number,b:number):number { return a-b; }\n"
    )
    failed = executor.run(source, profile.checks[0].argv, Limits(command_seconds=60), readonly=True)
    assert failed.exit_code != 0 and "fail 1" in failed.stdout


@pytest.mark.docker
def test_real_mixed_profile_runs_both_toolchains_and_detects_each_failure(tmp_path: Path) -> None:
    source = tmp_path / "mixed"
    for folder in ("node/src", "node/tests", "rust/src"):
        (source / folder).mkdir(parents=True)
    compiler = "tsc --target ES2022 --module NodeNext --moduleResolution NodeNext src/sum.ts"
    (source / "node/package.json").write_text(
        json.dumps(
            {
                "type": "module",
                "private": True,
                "scripts": {
                    "test": "node --experimental-strip-types --test tests/sum.test.mjs",
                    "typecheck": compiler + " --noEmit --strict",
                    "lint": compiler + " --noEmit --noUnusedLocals --noUnusedParameters",
                    "build": compiler + " --outDir /tmp/node-dist",
                },
            }
        )
    )
    node_source = source / "node/src/sum.ts"
    node_source.write_text("export function sum(a:number,b:number):number { return a+b; }\n")
    (source / "node/tests/sum.test.mjs").write_text(
        'import assert from "node:assert/strict";\nimport test from "node:test";\n'
        'import {sum} from "../src/sum.ts";\ntest("adds",()=>assert.equal(sum(2,3),5));\n'
    )
    (source / "rust/Cargo.toml").write_text(
        '[package]\nname="mixed_fixture"\nversion="0.1.0"\nedition="2024"\n'
    )
    (source / "rust/Cargo.lock").write_text(
        'version = 4\n[[package]]\nname = "mixed_fixture"\nversion = "0.1.0"\n'
    )
    rust_source = source / "rust/src/lib.rs"
    rust_source.write_text(
        "pub fn sum(a:u32,b:u32)->u32 { a+b }\n#[test] fn adds() {assert_eq!(sum(2,3),5);}\n"
    )
    profile = project_profile("node-rust", "darkfactory-mixed-tools:0.3.0")
    executor = DockerExecutor(profile.image)
    assert len(profile.checks) == 8
    for check in profile.checks:
        result = executor.run(source, check.argv, Limits(command_seconds=60), readonly=True)
        assert result.exit_code == 0, (check.id, result.stdout, result.stderr)
    node_source.write_text(node_source.read_text().replace("a+b", "a-b"))
    rust_source.write_text(rust_source.read_text().replace("a+b", "a-b"))
    for check in (spec for spec in profile.checks if spec.kind == "test"):
        failed = executor.run(source, check.argv, Limits(command_seconds=60), readonly=True)
        assert failed.exit_code != 0, check.id
