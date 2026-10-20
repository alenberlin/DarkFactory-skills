"""Use actual source files and container processes to verify execution boundaries."""

import os
from pathlib import Path

import pytest

from darkfactory.domain import Limits
from darkfactory.execution import BoundaryError, DockerExecutor, SnapshotStore


def test_snapshot_is_immutable_and_source_changes_invalidate_identity(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("value = 1\n")
    snapshots = SnapshotStore(tmp_path / "snapshots")
    first = snapshots.capture(source)
    (source / "app.py").write_text("value = 2\n")
    second = snapshots.capture(source)
    assert first.digest != second.digest
    assert (first.path / "app.py").read_text() == "value = 1\n"
    assert snapshots.verify(first)
    (first.path / "app.py").chmod(0o600)
    (first.path / "app.py").write_text("tampered\n")
    assert not snapshots.verify(first)


def test_symlink_escape_and_special_files_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "escape").symlink_to(tmp_path / "outside")
    with pytest.raises(BoundaryError, match="symlink"):
        SnapshotStore(tmp_path / "snapshots").capture(source)


def test_external_hardlink_cannot_import_out_of_scope_contents(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "synthetic-outside"
    outside.write_text("synthetic content outside imported source")
    os.link(outside, source / "innocent-name.txt")
    with pytest.raises(BoundaryError, match="hardlinked"):
        SnapshotStore(tmp_path / "snapshots").capture(source)


@pytest.mark.docker
def test_real_container_cannot_read_host_or_modify_system(tmp_path: Path) -> None:
    workspace = tmp_path / "task"
    workspace.mkdir()
    executor = DockerExecutor("python:3.12-slim")
    result = executor.run(
        workspace,
        [
            "python",
            "-c",
            "import os; print(os.getuid()); print(os.path.exists('/controller')); "
            "open('/blocked','w').write('no')",
        ],
        Limits(command_seconds=20),
    )
    assert result.exit_code != 0
    assert result.stdout.splitlines()[0] != "0"
    assert result.stdout.splitlines()[1] == "False"
    assert "Read-only file system" in result.stderr or "Permission denied" in result.stderr
    assert result.image_id.startswith("sha256:")


@pytest.mark.docker
def test_real_container_egress_is_denied(tmp_path: Path) -> None:
    workspace = tmp_path / "task"
    workspace.mkdir()
    result = DockerExecutor("python:3.12-slim").run(
        workspace,
        [
            "python",
            "-c",
            "import socket; s=socket.socket(); s.settimeout(1); s.connect(('1.1.1.1',443))",
        ],
        Limits(command_seconds=20),
    )
    assert result.exit_code != 0
    assert "Network is unreachable" in result.stderr


@pytest.mark.docker
def test_real_timeout_and_output_limit_terminate_execution(tmp_path: Path) -> None:
    workspace = tmp_path / "task"
    workspace.mkdir()
    executor = DockerExecutor("python:3.12-slim")
    timed = executor.run(
        workspace, ["python", "-c", "import time; time.sleep(30)"], Limits(command_seconds=1)
    )
    assert timed.timed_out
    flooded = executor.run(
        workspace,
        ["python", "-c", "print('x'*100000)"],
        Limits(command_seconds=20, output_bytes=2048),
    )
    assert flooded.output_truncated
    assert len(flooded.stdout.encode()) <= 2048
