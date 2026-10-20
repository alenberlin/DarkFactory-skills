"""Controller-only Git worktrees, three-way integration and crash journals."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from darkfactory.domain import Mode
from darkfactory.execution import BoundaryError, Snapshot, SnapshotStore, bounded_process
from darkfactory.policy import quality_decision
from darkfactory.resources import StorageQuota
from darkfactory.storage import Record, StateError, Store
from darkfactory.verification import Verifier


class Repository:
    """Keep authoritative Git references out of all worker mounts."""

    def __init__(self, store: Store, project_id: str) -> None:
        """Bind a managed repository to one persisted project.

        Args:
            store: Protected transactional state, never exposed to task containers.
            project_id: Project identity in the selected protected controller state.
        """
        self.store = store
        self.project_id = project_id
        self.root = store.root / "projects" / project_id
        self.path = self.root / "repository"
        self.snapshots = SnapshotStore(store.root / "snapshots")
        self.quota = StorageQuota(
            store.root, store.blueprint(project_id).limits.state_storage_mb * 1024 * 1024
        )
        self.root.mkdir(exist_ok=True)
        self.binary = shutil.which("git")
        if self.binary is None:
            raise BoundaryError("Git unavailable")

    def git(self, *arguments: str, cwd: Path | None = None) -> str:
        """Run an isolated, local-only trusted Git argument vector without user hooks.

        Args:
            cwd: Optional controller-owned working directory for trusted Git execution.
            arguments: Trusted Git arguments; repository hooks and configuration remain isolated.

        Returns:
            Actual Git stdout; failed commands raise instead of fabricating results.
        """
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "DarkFactory",
            "GIT_AUTHOR_EMAIL": "factory@localhost",
            "GIT_COMMITTER_NAME": "DarkFactory",
            "GIT_COMMITTER_EMAIL": "factory@localhost",
            "GIT_TERMINAL_PROMPT": "0",
        }
        result = bounded_process(
            [
                str(self.binary),
                "-c",
                f"core.hooksPath={os.devnull}",
                "-c",
                "commit.gpgSign=false",
                "-c",
                "protocol.file.allow=never",
                *arguments,
            ],
            cwd=cwd or self.path,
            env=environment,
            timeout=30,
            output_bytes=1024 * 1024,
        )
        if result.exit_code or result.timed_out or result.output_truncated:
            raise StateError("Git operation failed: " + result.stderr[:4000])
        return result.stdout.strip()

    @contextmanager
    def lock(self) -> Iterator[None]:
        """Serialize integration across independent supervised worker processes.

        Yields:
            Ownership of the protected operation for this context lifetime.
        """
        with (self.root / "integration.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def initialize(self, source: Path) -> Snapshot:
        """Create local history only when the approved blueprint permits commits.

        Args:
            source: Real source directory inspected through the validated snapshot boundary.

        Returns:
            Actual integration commit after safe initialization or recovery.
        """
        if not self.store.blueprint(self.project_id).permissions.local_commits:
            raise StateError("local commits require explicit blueprint permission")
        snapshot = self.snapshots.capture(source, quota=self.quota)
        with self.lock():
            if self.path.exists():
                current = self.current()
                if self.store.project(self.project_id)["source_digest"]:
                    return current
                if current.digest != snapshot.digest:
                    raise StateError("interrupted initialization source requires reconciliation")
            else:
                operation = uuid.uuid4().hex
                staging = self.root / ("initialization-" + operation)
                with self.store.connection() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        "INSERT INTO operations VALUES(?,?,?,?,?,?,?)",
                        (
                            operation,
                            self.project_id,
                            "repository-initialization",
                            json.dumps({"source": snapshot.digest, "staging": staging.name}),
                            "PREPARED",
                            None,
                            time.time(),
                        ),
                    )
                self.snapshots.materialize(snapshot, staging, quota=self.quota)
                size = sum(item["size"] for item in self.snapshots.manifest(snapshot.path))
                with self.quota.allocate(size + 1024 * 1024):
                    self.git("init", "--initial-branch=integration", cwd=staging)
                    self.git("add", "--all", cwd=staging)
                    self.git(
                        "commit", "--allow-empty", "-m", "Approved initial source", cwd=staging
                    )
                # Only a complete repository becomes authoritative; interrupted staging is retained.
                staging.rename(self.path)
                descriptor = os.open(self.root, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            with self.store.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                pending = connection.execute(
                    "SELECT id FROM operations WHERE project_id=? "
                    "AND kind='repository-initialization' AND state='PREPARED' ORDER BY created",
                    (self.project_id,),
                ).fetchall()
                for i, item in enumerate(pending):
                    connection.execute(
                        "UPDATE operations SET state=?,outcome=? WHERE id=?",
                        (
                            "APPLIED" if i == len(pending) - 1 else "SUPERSEDED",
                            snapshot.digest,
                            item[0],
                        ),
                    )
                connection.execute(
                    "UPDATE projects SET source_digest=? WHERE id=?",
                    (snapshot.digest, self.project_id),
                )
                self.store._event(
                    connection,
                    self.project_id,
                    "source.initialized",
                    {"source": snapshot.digest, "commit": self.head()},
                )
        return snapshot

    def head(self) -> str:
        """Read the protected integration reference, never a task's claimed commit.

        Returns:
            Actual authoritative integration commit identifier.
        """
        return self.git("rev-parse", "refs/heads/integration")

    def checkout(self, commit: str, name: str | None = None) -> Path:
        """Create a detached controller-managed worktree; workers receive only source copies.

        Args:
            commit: Actual managed Git commit, never an agent-reported completion label.
            name: Broker-owned resource or unique managed worktree name.

        Returns:
            New managed worktree path owned by this controller.
        """
        name = name or uuid.uuid4().hex
        if uuid.UUID(hex=name).hex != name:
            raise StateError("invalid managed worktree identity")
        path = self.root / "worktrees" / name
        path.parent.mkdir(exist_ok=True)
        with self.quota.allocate(self._tree_size(commit) + 1024 * 1024):
            self.git("worktree", "add", "--detach", str(path), commit)
        return path

    @contextmanager
    def working_copy(self, commit: str) -> Iterator[Path]:
        """Lease recorded scratch work until source/commit preservation permits cleanup.

        Args:
            commit: Protected commit to materialize in a fresh managed worktree.

        Yields:
            Controller-only detached worktree; agents receive separate source copies.

        Raises:
            StateError: Git creation or confirmed cleanup fails.
        """
        operation = uuid.uuid4().hex
        locks = self.root / "worktree-locks"
        locks.mkdir(exist_ok=True)
        with (locks / (operation + ".lock")).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with self.store.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO operations VALUES(?,?,?,?,?,?,?)",
                    (
                        operation,
                        self.project_id,
                        "git-worktree",
                        json.dumps({"commit": commit}),
                        "ACTIVE",
                        None,
                        time.time(),
                    ),
                )
                self.store._event(
                    connection, self.project_id, "worktree.leased", {"operation": operation}
                )
            try:
                yield self.checkout(commit, operation)
            finally:
                self._remove_worktree(operation)
                self._closed_worktree(operation, "CLOSED")

    def _remove_worktree(self, operation: str) -> None:
        if uuid.UUID(hex=operation).hex != operation:
            raise StateError("invalid journaled worktree identity")
        path = self.root / "worktrees" / operation
        if path.is_symlink():
            raise StateError("managed worktree symlink requires operator reconciliation")
        registered = (
            "worktree " + str(path) in self.git("worktree", "list", "--porcelain").splitlines()
        )
        if registered:
            self.git("worktree", "remove", "--force", str(path))
        elif path.exists():
            raise StateError("unregistered scratch files preserved for operator reconciliation")
        if path.exists():
            raise StateError("managed worktree cleanup not confirmed")

    def _closed_worktree(self, operation: str, state: str) -> None:
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE operations SET state=? WHERE id=? AND kind='git-worktree'",
                (state, operation),
            )
            self.store._event(
                connection,
                self.project_id,
                "worktree.cleaned",
                {"operation": operation, "state": state},
            )

    def reap_worktrees(self) -> None:
        """Remove only journaled scratch worktrees whose owner OS lock has been released."""
        with self.store.connection() as connection:
            operations = connection.execute(
                "SELECT id FROM operations WHERE project_id=? "
                "AND kind='git-worktree' AND state='ACTIVE'",
                (self.project_id,),
            ).fetchall()
        for row in operations:
            operation = row[0]
            with (self.root / "worktree-locks" / (operation + ".lock")).open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                self._remove_worktree(operation)
                self._closed_worktree(operation, "REAPED")

    def capture_commit(self, commit: str) -> Snapshot:
        """Preserve a protected commit as a snapshot before cleaning its managed scratch copy.

        Args:
            commit: Actual managed Git commit, never an agent-reported completion label.

        Returns:
            Immutable source snapshot of the actual managed commit.
        """
        with self.working_copy(commit) as worktree:
            return self.snapshots.capture(worktree, quota=self.quota)

    def _tree_size(self, commit: str) -> int:
        sizes = self.git("ls-tree", "-r", "--format=%(objectsize)", commit)
        return sum(int(value) for value in sizes.splitlines())

    def current(self) -> Snapshot:
        """Capture the actual integration tree, including after controller restart.

        Returns:
            Snapshot of the current authoritative integrated source.
        """
        return self.capture_commit(self.head())

    def candidate(self, base: str, snapshot: Snapshot) -> str:
        """Commit a validated candidate inside an isolated managed worktree.

        Args:
            base: Managed base commit for the isolated source candidate.
            snapshot: Immutable source identity and its controller-owned files.

        Returns:
            Isolated candidate commit without publishing the integration branch.
        """
        if not self.store.blueprint(self.project_id).permissions.local_commits:
            raise StateError("local commits not authorized")
        size = sum(item["size"] for item in self.snapshots.manifest(snapshot.path))
        with self.working_copy(base) as worktree, self.quota.allocate(2 * size + 1024 * 1024):
            for entry in self.snapshots.manifest(worktree):
                (worktree / str(entry["path"])).unlink()
            for entry in self.snapshots.manifest(snapshot.path):
                relative = str(entry["path"])
                destination = worktree / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(snapshot.path / relative, destination)
                destination.chmod(0o755 if entry["executable"] else 0o644)
            self.git("add", "--all", cwd=worktree)
            self.git("commit", "--allow-empty", "-m", "Verified task candidate", cwd=worktree)
            return self.git("rev-parse", "HEAD", cwd=worktree)

    def merged(self, candidate: str) -> tuple[str, str, Snapshot]:
        """Build a three-way merged candidate without changing authoritative refs.

        Args:
            candidate: Actual candidate commit for three-way merge verification.

        Returns:
            Current parent, merged commit and the immutable merged source snapshot.
        """
        parent = self.head()
        with self.quota.allocate(
            self._tree_size(parent) + self._tree_size(candidate) + 1024 * 1024
        ):
            tree = self.git("merge-tree", "--write-tree", parent, candidate).splitlines()[0]
            commit = self.git(
                "commit-tree",
                tree,
                "-p",
                parent,
                "-p",
                candidate,
                "-m",
                "Verified factory integration",
            )
        return parent, commit, self.capture_commit(commit)

    def publish(self, assignment: Record, parent: str, commit: str, snapshot: Snapshot) -> None:
        """Journal and compare-and-swap an already verified integration under a valid lease.

        Args:
            assignment: Persisted task ownership, attempt and fencing identity.
            parent: Expected authoritative parent for compare-and-swap publication.
            commit: Actual managed Git commit, never an agent-reported completion label.
            snapshot: Immutable source identity and its controller-owned files.
        """
        if not self.store.blueprint(self.project_id).permissions.local_integration:
            raise StateError("local integration not authorized")
        if (
            not self.store.current_approval(self.project_id)
            or not self.store.verify_audit()
            or not self.snapshots.verify(snapshot)
            or not quality_decision(
                Verifier(self.store).gate(
                    self.project_id, snapshot.digest, task_id=assignment["task_id"]
                ),
                self.store.blueprint(self.project_id).mode,
            ).allowed
        ):
            raise StateError("integration requires current approval, source and trusted checks")
        with self.store.connection() as connection:
            roles = self.store.policy(self.project_id).required_review_roles
            for role in roles:
                reviewed = connection.execute(
                    "SELECT id,verdict,attempt_id FROM reviews WHERE project_id=? AND task_id=? "
                    "AND source_digest=? AND role=? ORDER BY created DESC LIMIT 1",
                    (self.project_id, assignment["task_id"], snapshot.digest, role),
                ).fetchone()
                if (
                    reviewed is None
                    or (
                        self.store.blueprint(self.project_id).mode != Mode.ADVISORY
                        and not self.store.review_satisfied(
                            connection, self.project_id, reviewed["id"], snapshot.digest
                        )
                    )
                    or reviewed["attempt_id"] == assignment["attempt_id"]
                ):
                    raise StateError("integration requires independent current reviews")
            if self.store.blueprint(
                self.project_id
            ).mode != Mode.ADVISORY and self.store.blocking_findings(
                self.project_id, snapshot.digest, assignment["task_id"], connection=connection
            ):
                raise StateError("integration has unresolved blocking findings")
        operation = uuid.uuid4().hex
        intent = {
            "parent": parent,
            "commit": commit,
            "source": snapshot.digest,
            "assignment": assignment,
        }
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            owned = self.store._lease(
                connection, self.project_id, assignment["task_id"], assignment["fence"], time.time()
            )
            if owned["state"] != "READY_TO_INTEGRATE":
                raise StateError("integration requires completed verification/review phases")
            if self.store.project(self.project_id)["state"] not in ("RUNNING", "PAUSING"):
                raise StateError("integration is not active")
            connection.execute(
                "INSERT INTO operations VALUES(?,?,?,?,?,?,?)",
                (
                    operation,
                    self.project_id,
                    "integration",
                    json.dumps(intent),
                    "PREPARED",
                    None,
                    time.time(),
                ),
            )
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.store._lease(
                connection, self.project_id, assignment["task_id"], assignment["fence"], time.time()
            )
            self.git("update-ref", "refs/heads/integration", commit, parent)
            connection.execute(
                "UPDATE projects SET source_digest=? WHERE id=?", (snapshot.digest, self.project_id)
            )
            connection.execute(
                "UPDATE operations SET state='APPLIED',outcome=? WHERE id=?",
                (snapshot.digest, operation),
            )
            self._complete(connection, assignment, snapshot.digest)
            self.store._event(connection, self.project_id, "integration.applied", intent)

    def _complete(self, database: sqlite3.Connection, assignment: Record, source: str) -> None:
        database.execute(
            "UPDATE tasks SET state='INTEGRATED',source_digest=?,error=NULL,owner=NULL,"
            "lease_until=NULL WHERE project_id=? AND id=? AND fence=?",
            (source, self.project_id, assignment["task_id"], assignment["fence"]),
        )
        database.execute(
            "UPDATE attempts SET state='INTEGRATED',finished=? WHERE id=?",
            (time.time(), assignment["attempt_id"]),
        )

    def reconcile(self) -> None:
        """Recover journaled ref updates without replaying an already applied Git mutation."""
        with self.lock():
            self.reap_worktrees()
            self._reconcile_integrations()

    def _reconcile_integrations(self) -> None:
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT * FROM operations WHERE project_id=? "
                "AND kind='integration' AND state='PREPARED'",
                (self.project_id,),
            ).fetchall()
            for row in rows:
                intent = json.loads(row["intent"])
                head = self.head()
                state = "ABORTED"
                if head == intent["commit"]:
                    connection.execute(
                        "UPDATE projects SET source_digest=? WHERE id=?",
                        (intent["source"], self.project_id),
                    )
                    state = "APPLIED"
                    self._complete(connection, intent["assignment"], intent["source"])
                elif head != intent["parent"]:
                    raise StateError("integration journal needs operator reconciliation")
                connection.execute("UPDATE operations SET state=? WHERE id=?", (state, row["id"]))
                self.store._event(
                    connection,
                    self.project_id,
                    "integration.reconciled",
                    {"operation": row["id"], "state": state},
                )
