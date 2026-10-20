"""Real three-way Git integration preserves parallel work and rejects conflicts."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from darkfactory.execution import SnapshotStore
from darkfactory.gitops import Repository
from darkfactory.storage import StateError
from tests.test_store import prepared_store


def test_real_parallel_candidates_merge_and_conflicts_remain_unpublished(tmp_path: Path) -> None:
    store, project = prepared_store(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "value").write_text("initial\n")
    repository = Repository(store, project)
    repository.initialize(source)
    base = repository.head()
    snapshots = SnapshotStore(store.root / "snapshots")
    (source / "a").write_text("one\n")
    first = repository.candidate(base, snapshots.capture(source))
    (source / "a").unlink()
    (source / "b").write_text("two\n")
    second = repository.candidate(base, snapshots.capture(source))
    repository.git("update-ref", "refs/heads/integration", first, base)
    parent, merged, snapshot = repository.merged(second)
    assert parent == first and merged != first
    assert (snapshot.path / "a").read_text() == "one\n"
    assert (snapshot.path / "b").read_text() == "two\n"
    (source / "value").write_text("left\n")
    left = repository.candidate(base, snapshots.capture(source))
    (source / "value").write_text("right\n")
    right = repository.candidate(base, snapshots.capture(source))
    repository.git("update-ref", "refs/heads/integration", left, first)
    with pytest.raises(StateError, match="Git operation failed"):
        repository.merged(right)
    assert repository.head() == left


@pytest.mark.parametrize("interruption", ["before-commit", "after-publish"])
def test_initialization_recovers_before_and_after_authoritative_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interruption: str
) -> None:
    store, project = prepared_store(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "initial.txt").write_text("approved initial content")
    repository = Repository(store, project)
    if interruption == "before-commit":
        actual = Repository.git

        def fail_commit(self: Repository, *args: str, **kwargs: object) -> str:
            if args[0] == "commit":
                raise OSError("injected interruption before initial commit")
            return actual(self, *args, **kwargs)

        monkeypatch.setattr(Repository, "git", fail_commit)
    else:
        actual_rename = Path.rename

        def fail_after_rename(self: Path, target: Path) -> Path:
            result = actual_rename(self, target)
            if target == repository.path:
                raise OSError("injected interruption after authoritative rename")
            return result

        monkeypatch.setattr(Path, "rename", fail_after_rename)
    with pytest.raises(OSError, match="injected"):
        repository.initialize(source)
    assert store.project(project)["source_digest"] is None
    monkeypatch.undo()
    reopened = Repository(store, project)
    snapshot = reopened.initialize(source)
    assert (snapshot.path / "initial.txt").read_text() == "approved initial content"
    assert reopened.current().digest == snapshot.digest
    assert store.project(project)["source_digest"] == snapshot.digest
    assert reopened.git("rev-list", "--count", "HEAD") == "1"
    assert store.verify_audit()


def test_direct_coordinator_publish_requires_trusted_checks(tmp_path: Path) -> None:
    store, project = prepared_store(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    repository = Repository(store, project)
    snapshot = repository.initialize(source)
    assignment = store.claim(project, "attempt")
    assert assignment
    head = repository.head()
    with pytest.raises(StateError, match="trusted checks"):
        repository.publish(assignment, head, head, snapshot)
    assert repository.head() == head
    assert store.tasks(project)[0]["state"] == "IMPLEMENTING"


def test_recovery_cleans_only_abandoned_journaled_git_worktree(tmp_path: Path) -> None:
    store, project = prepared_store(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "initial.txt").write_text("preserved initial source")
    repository = Repository(store, project)
    snapshot = repository.initialize(source)
    marker = tmp_path / "worktree-ready"
    script = (
        "from pathlib import Path\nimport time\n"
        "from darkfactory.storage import Store\n"
        "from darkfactory.gitops import Repository\n"
        f"r=Repository(Store(Path({str(store.root)!r})),{project!r})\n"
        "with r.working_copy(r.head()) as worktree:\n"
        f" Path({str(marker)!r}).write_text(str(worktree))\n"
        " time.sleep(120)\n"
    )
    process = subprocess.Popen([sys.executable, "-c", script], start_new_session=True)
    try:
        deadline = time.monotonic() + 10
        while not marker.exists():
            assert process.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.05)
        worktree = Path(marker.read_text())
        repository.reconcile()
        assert worktree.exists(), "live ownership must prevent cleanup"
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
        repository.reconcile()
        assert not worktree.exists()
        assert repository.current().digest == snapshot.digest
        assert store.verify_audit()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        repository.reconcile()
