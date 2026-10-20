"""Exercise runner protection, real denied effects and container resource enforcement."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from darkfactory.api import create_app
from darkfactory.domain import Limits
from darkfactory.engine import Engine
from darkfactory.execution import DockerExecutor, SnapshotStore
from darkfactory.security import redact, redact_value
from darkfactory.storage import StateError
from tests.test_store import prepared_store


@pytest.mark.parametrize(
    "filename",
    ["package.json", "pyproject.toml", "Cargo.toml", "pytest.ini", "conftest.py", "Makefile"],
)
def test_default_policy_protects_actual_runner_substitution(tmp_path: Path, filename: str) -> None:
    store, project = prepared_store(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    runner = source / filename
    runner.write_text("original mandatory checks")
    snapshots = SnapshotStore(store.root / "snapshots")
    before = snapshots.capture(source)
    runner.write_text("exit successfully without executing required tests")
    after = snapshots.capture(source)
    with pytest.raises(StateError, match="protected baseline"):
        Engine(store)._protected(project, before, after)


def test_nested_json_redaction_preserves_valid_audit_and_accounting(tmp_path: Path) -> None:
    store, project = prepared_store(tmp_path)
    payload = {
        "password": "synthetic-do-not-retain",
        "tokens": 123,
        "diagnostic": 'password="synthetic-two" Authorization: Bearer synthetic-three',
    }
    with store.connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        store._event(connection, project, "fixture.redaction", payload)
    with store.connection() as connection:
        text = connection.execute("SELECT payload FROM audit ORDER BY seq DESC LIMIT 1").fetchone()[
            0
        ]
    decoded = json.loads(text)
    assert decoded["tokens"] == 123 and decoded["password"] == "[REDACTED]"
    assert "synthetic" not in text and store.verify_audit()
    assert redact_value({"nested": [{"api_key": "synthetic"}]}) == {
        "nested": [{"api_key": "[REDACTED]"}]
    }
    assert "synthetic" not in redact("https://user:synthetic@example.test/path")


@pytest.mark.docker
def test_alternative_shell_paths_cannot_reach_controller_git_or_other_projects(
    tmp_path: Path,
) -> None:
    state, project = prepared_store(tmp_path)
    workspace = tmp_path / "candidate"
    workspace.mkdir()
    secret = tmp_path / "synthetic-secret"
    secret.write_text("synthetic-host-only-value")
    checks = [
        str(secret),
        str(state.database),
        "/controller",
        "/var/run/docker.sock",
        "/root/.codex/auth.json",
        "/controller/repository/.git/refs/heads/integration",
    ]
    script = (
        "import pathlib,os,socket\n"
        + f"paths={checks!r}\n"
        + "for name in paths:\n"
        + " try:\n  exists=pathlib.Path(name).exists()\n"
        + " except PermissionError:\n  exists=False\n"
        + " assert not exists,name\n"
        + " try:\n  pathlib.Path(name).write_text('unauthorized')\n"
        + " except OSError:\n  pass\n else:\n  raise AssertionError(name)\n"
        + "assert not os.environ.get('HTTP_PROXY')\n"
        + "print('alternative paths denied')\n"
    )
    (workspace / "probe.py").write_text(script)
    result = DockerExecutor("python:3.12-slim").run(
        workspace,
        ["sh", "-c", "exec python -I /workspace/probe.py"],
        Limits(command_seconds=20),
        readonly=True,
    )
    assert result.exit_code == 0, result.stderr
    assert "alternative paths denied" in result.stdout
    assert secret.read_text() == "synthetic-host-only-value"
    assert state.current_approval(project)


@pytest.mark.docker
def test_kernel_memory_cpu_and_scratch_limits_are_real(tmp_path: Path) -> None:
    executor = DockerExecutor("python:3.12-slim")
    result = executor.run(
        tmp_path,
        [
            "python",
            "-I",
            "-c",
            "from pathlib import Path\n"
            "assert int(Path('/sys/fs/cgroup/memory.max').read_text()) == 128*1024*1024\n"
            "quota,period=map(int,Path('/sys/fs/cgroup/cpu.max').read_text().split())\n"
            "assert quota <= period\n"
            "try:\n"
            " with open('/tmp/oversized','wb') as file:\n"
            "  for _ in range(80):\n   file.write(b'x'*(1024*1024))\n"
            "except OSError:\n print('kernel bounds observed')\n"
            "else:\n raise AssertionError('scratch bound escaped')\n",
        ],
        Limits(memory_mb=128, cpus=1, command_seconds=20),
        readonly=True,
    )
    assert result.exit_code == 0 and "kernel bounds observed" in result.stdout, result.stderr
    exhausted = executor.run(
        tmp_path,
        [
            "python",
            "-I",
            "-c",
            "value=bytearray(512*1024*1024)\n"
            "for offset in range(0,len(value),4096): value[offset]=1\nprint(len(value))",
        ],
        Limits(memory_mb=128, command_seconds=20),
        readonly=True,
    )
    assert exhausted.exit_code == 137 and not exhausted.timed_out


def test_actual_unauthorized_release_request_has_no_effect(tmp_path: Path) -> None:
    store, project = prepared_store(tmp_path)
    token = "synthetic-administrative-test-only-credential"
    client = TestClient(create_app(store, token), base_url="http://127.0.0.1")
    response = client.post(
        f"/v1/projects/{project}/deploy", headers={"Authorization": "Bearer " + token}, json={}
    )
    assert response.status_code == 404
    with store.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 0
    assert store.verify_audit()
