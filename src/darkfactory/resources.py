"""Journal ephemeral Docker effects and reap only abandoned controller-owned resources."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import time
import uuid
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from darkfactory.storage import StateError, Store


class StorageQuota:
    """Serialize bulk allocations; a dedicated bounded volume also caps all metadata writes."""

    def __init__(self, root: Path, max_bytes: int) -> None:
        """Bind the approved shared-state admission bound without inspecting file contents.

        Args:
            root: Dedicated storage root outside imported application source.
            max_bytes: Maximum source or protected storage bytes allowed by this store.
        """
        self.root, self.max_bytes = root.resolve(), max_bytes

    @contextmanager
    def allocate(self, requested: int) -> Iterator[None]:
        """Reject a bulk write before its effect and hold ownership through its completion.

        Args:
            requested: Conservative maximum new file bytes for this operation.

        Yields:
            Permission for the trusted caller's bounded write.

        Raises:
            StateError: Shared storage or available disk cannot accommodate it.
        """
        if requested < 0:
            raise StateError("invalid storage allocation")
        with (self.root / "storage.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            allocated = 0
            for directory, names, files in os.walk(self.root, followlinks=False):
                for name in (*names, *files):
                    path = Path(directory) / name
                    if path.is_symlink():
                        raise StateError("protected state contains an unexpected symlink")
                for name in files:
                    try:
                        allocated += (Path(directory) / name).stat().st_size
                    except FileNotFoundError:
                        # SQLite removes transient WAL/SHM files independently of bulk writers.
                        continue
            if allocated + requested > self.max_bytes:
                raise StateError(
                    "protected state storage limit reached; preserve work and revise limits"
                )
            if shutil.disk_usage(self.root).free < requested + 16 * 1024 * 1024:
                raise StateError("insufficient available disk; preserve work before allocating")
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


class Resources:
    """OS-held locks distinguish live supervision from a killed or abandoned process."""

    def __init__(self, store: Store, project: str) -> None:
        """Record resource intents outside all task mounts.

        Args:
            store: Protected transactional state, never exposed to task containers.
            project: Project identity in the selected protected controller state.
        """
        self.store, self.project = store, project
        self.root = store.root / "resources"
        self.root.mkdir(exist_ok=True)

    @contextmanager
    def lease(self, name: str, *, network: str | None = None) -> Iterator[None]:
        """Journal resource names before effects and hold an OS lock through cleanup.

        Args:
            name: Broker-owned resource or unique managed worktree name.
            network: Broker-owned private network or none for ordinary target commands.

        Yields:
            Ownership of the protected operation for this context lifetime.
        """
        if not name.startswith(("df-", "darkfactory-")) or not name.replace("-", "").isalnum():
            raise StateError("invalid factory resource identity")
        identifier = uuid.uuid4().hex
        with (self.root / (identifier + ".lock")).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with self.store.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO operations VALUES(?,?,?,?,?,?,?)",
                    (
                        identifier,
                        self.project,
                        "docker-resource",
                        json.dumps({"name": name, "network": network}),
                        "ACTIVE",
                        None,
                        time.time(),
                    ),
                )
                self.store._event(
                    connection, self.project, "resource.leased", {"resource": identifier}
                )
            try:
                yield
            finally:
                self._remove(name)
                if network:
                    self._remove(network, network=True)
                with self.store.connection() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        "UPDATE operations SET state='CLOSED' WHERE id=?", (identifier,)
                    )
                    self.store._event(
                        connection, self.project, "resource.closed", {"resource": identifier}
                    )

    def reap(self) -> int:
        """Stop known abandoned containers after an actual process death, preserving diagnostics.

        Returns:
            Count of journaled abandoned Docker resources reconciled.
        """
        with self.store.connection() as connection:
            records = connection.execute(
                "SELECT * FROM operations WHERE kind='docker-resource' AND state='ACTIVE'"
            ).fetchall()
        abandoned = []
        with ExitStack() as locks:
            for record in records:
                lock = locks.enter_context((self.root / (record["id"] + ".lock")).open("a"))
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                abandoned.append((record, json.loads(record["intent"])))
            for _, intent in abandoned:
                self._remove(intent["name"])
            # Remove all abandoned endpoints before their private networks.
            for record, intent in abandoned:
                if intent.get("network"):
                    self._remove(intent["network"], network=True)
                with self.store.connection() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        "UPDATE operations SET state='REAPED' WHERE id=? AND state='ACTIVE'",
                        (record["id"],),
                    )
                    self.store._event(
                        connection,
                        record["project_id"],
                        "resource.reaped",
                        {"resource": record["id"]},
                    )
        return len(abandoned)

    def _remove(self, name: str, *, network: bool = False) -> None:
        from darkfactory.execution import bounded_process

        if not name.startswith(("df-", "darkfactory-")) or not name.replace("-", "").isalnum():
            raise StateError("invalid journaled resource; refusing cleanup")
        docker = shutil.which("docker")
        if docker is None:
            raise StateError("Docker unavailable for recovery")
        prefix = [docker, "network"] if network else [docker]
        remove = [*prefix, "rm", name] if network else [*prefix, "rm", "--force", name]
        bounded_process(remove, timeout=10, output_bytes=4096)
        inspected = bounded_process([*prefix, "inspect", name], timeout=10, output_bytes=4096)
        missing = "no such" in inspected.stderr.lower() or (
            network and f"network {name} not found" in inspected.stderr
        )
        if inspected.exit_code == 0 or not missing:
            raise StateError("resource cleanup not confirmed; recovery journal retained")

    def revoke(self) -> None:
        """Stop active project endpoints after explicit cancellation, retaining cleanup journals."""
        with self.store.connection() as connection:
            records = connection.execute(
                "SELECT intent FROM operations WHERE project_id=? "
                "AND kind='docker-resource' AND state='ACTIVE'",
                (self.project,),
            ).fetchall()
        for record in records:
            self._remove(json.loads(record[0])["name"])
