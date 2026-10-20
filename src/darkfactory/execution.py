"""Immutable source collection and effect-based isolated command execution."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import threading
import time
import uuid
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from darkfactory.domain import Contract, Limits
from darkfactory.resources import Resources, StorageQuota

IGNORED = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "target",
        "dist",
        "build",
        ".factory-dev",
        ".factory",
        ".darkfactory",
    }
)


class BoundaryError(RuntimeError):
    """A filesystem or execution request violates the configured trust boundary."""


class SourceEntry(TypedDict):
    """A validated regular file's content identity and reproducible permission metadata."""

    path: str
    sha256: str
    size: int
    executable: bool


@dataclass(frozen=True)
class Snapshot:
    """An immutable source identity and its controller-owned read-only files."""

    digest: str
    path: Path


class SnapshotStore:
    """Capture source with traversal, symlink, special-file and size validation."""

    def __init__(self, root: Path, max_bytes: int = 100 * 1024 * 1024) -> None:
        """Create snapshot storage outside task mounts with a bounded source size.

        Args:
            root: Dedicated storage root outside imported application source.
            max_bytes: Maximum source or protected storage bytes allowed by this store.
        """
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.max_bytes = max_bytes

    def manifest(self, source: Path) -> list[SourceEntry]:
        """Hash regular source files without following links or reading environment secrets.

        Args:
            source: Real source directory inspected through the validated snapshot boundary.

        Returns:
            Sorted file paths, sizes, executable permissions and content hashes.
        """
        if source.is_symlink() or not source.is_dir():
            raise BoundaryError("source must be a real directory, not a symlink")
        entries: list[SourceEntry] = []
        total = 0
        for directory, names, files in os.walk(source, followlinks=False):
            names[:] = sorted(
                name for name in names if name not in IGNORED and not name.startswith(".env")
            )
            for name in names:
                if (Path(directory) / name).is_symlink():
                    raise BoundaryError("source directory symlink rejected")
            for name in sorted(files):
                if name in IGNORED or name.startswith(".env"):
                    continue
                path = Path(directory) / name
                metadata = path.lstat()
                if stat.S_ISLNK(metadata.st_mode):
                    raise BoundaryError("source file symlink rejected")
                if not stat.S_ISREG(metadata.st_mode):
                    raise BoundaryError("special source file rejected")
                if metadata.st_nlink != 1:
                    raise BoundaryError("hardlinked source file rejected")
                total += metadata.st_size
                if total > self.max_bytes or len(entries) >= 10000:
                    raise BoundaryError("source size/file limit exceeded")
                relative = path.relative_to(source).as_posix()
                if any(character in relative for character in ("\n", "\0")):
                    raise BoundaryError("invalid source filename")
                entries.append(
                    {
                        "path": relative,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "size": metadata.st_size,
                        "executable": bool(metadata.st_mode & 0o111),
                    }
                )
        return sorted(entries, key=lambda item: str(item["path"]))

    def capture(self, source: Path, *, quota: StorageQuota | None = None) -> Snapshot:
        """Copy a validated source manifest, checking for mutation during capture.

        Args:
            source: Real source directory inspected through the validated snapshot boundary.
            quota: Optional serialized storage admission guard for protected writes.

        Returns:
            Read-only source snapshot and its content identity.
        """
        manifest = self.manifest(source)
        encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        identity = hashlib.sha256(encoded).hexdigest()
        destination = self.root / identity / "source"
        if destination.exists():
            snapshot = Snapshot(identity, destination)
            if not self.verify(snapshot):
                raise BoundaryError("existing snapshot was tampered with")
            return snapshot
        staging = self.root / f"staging-{uuid.uuid4().hex}"
        staging_source = staging / "source"
        allocation = (
            quota.allocate(sum(int(item["size"]) for item in manifest) + len(encoded))
            if quota
            else nullcontext()
        )
        with allocation:
            return self._capture(
                source, manifest, encoded, identity, destination, staging, staging_source
            )

    def _capture(
        self,
        source: Path,
        manifest: list[SourceEntry],
        encoded: bytes,
        identity: str,
        destination: Path,
        staging: Path,
        staging_source: Path,
    ) -> Snapshot:
        staging_source.mkdir(parents=True)
        try:
            for item in manifest:
                relative = str(item["path"])
                target = staging_source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / relative, target, follow_symlinks=False)
                target.chmod(0o555 if item["executable"] else 0o444)
            if self.manifest(staging_source) != manifest or self.manifest(source) != manifest:
                raise BoundaryError("source changed during snapshot capture")
            (staging / "manifest.json").write_bytes(encoded)
            try:
                staging.rename(destination.parent)
            except FileExistsError:
                if not self.verify(Snapshot(identity, destination)):
                    raise BoundaryError("concurrent snapshot integrity mismatch") from None
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return Snapshot(identity, destination)

    def verify(self, snapshot: Snapshot) -> bool:
        """Compare actual immutable source files with the claimed content identity.

        Args:
            snapshot: Immutable source identity and its controller-owned files.

        Returns:
            True only when actual source matches the claimed snapshot identity.
        """
        try:
            encoded = json.dumps(
                self.manifest(snapshot.path), sort_keys=True, separators=(",", ":")
            ).encode()
            return hashlib.sha256(encoded).hexdigest() == snapshot.digest
        except (OSError, BoundaryError):
            return False

    def materialize(
        self, snapshot: Snapshot, destination: Path, *, quota: StorageQuota | None = None
    ) -> None:
        """Create a new isolated writable working copy of a verified snapshot.

        Args:
            snapshot: Immutable source identity and its controller-owned files.
            destination: New destination; existing data is never overwritten.
            quota: Optional serialized storage admission guard for protected writes.
        """
        if destination.exists() or not self.verify(snapshot):
            raise BoundaryError("materialization requires new destination and intact snapshot")
        size = sum(int(item["size"]) for item in self.manifest(snapshot.path))
        with quota.allocate(size) if quota else nullcontext():
            shutil.copytree(snapshot.path, destination)
            for path in destination.rglob("*"):
                if path.is_file():
                    path.chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)


class ProcessResult(Contract):
    """Actual bounded process outcome; no agent-supplied success boolean."""

    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str
    started: float
    finished: float
    timed_out: bool = False
    output_truncated: bool = False
    image_id: str = ""


def bounded_process(
    argv: list[str],
    *,
    timeout: int,
    output_bytes: int,
    cwd: Path | None = None,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> ProcessResult:
    """Supervise a trusted launcher with bounded output, input and execution time.

    Args:
        argv: Argument vector for a trusted launcher, never a shell expression.
        timeout: Maximum process lifetime in seconds.
        output_bytes: Combined stdout/stderr budget.
        cwd: Explicit working directory.
        input_text: Optional bounded task context sent over stdin.
        env: Explicit environment for adapter/configuration isolation.

    Returns:
        Actual exit status, bounded streams and termination diagnostics.

    Raises:
        BoundaryError: Arguments or input violate execution limits.
        OSError: The trusted launcher cannot start.
    """
    if not argv or any("\0" in argument for argument in argv):
        raise BoundaryError("invalid command arguments")
    if input_text is not None and len(input_text.encode()) > 1024 * 1024:
        raise BoundaryError("input context limit exceeded")
    started = time.time()
    process = subprocess.Popen(  # noqa: S603 -- trusted launchers use argument vectors
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    streams = [bytearray(), bytearray()]
    lock = threading.Lock()
    truncated = threading.Event()

    def terminate_group() -> None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def read_stream(index: int) -> None:
        stream = process.stdout if index == 0 else process.stderr
        assert stream is not None
        while chunk := stream.read(4096):
            with lock:
                remaining = output_bytes - sum(map(len, streams))
                streams[index].extend(chunk[: max(0, remaining)])
                if len(chunk) > remaining:
                    truncated.set()
                    terminate_group()
                    break
        stream.close()

    def write_input() -> None:
        assert process.stdin is not None
        try:
            if input_text is not None:
                process.stdin.write(input_text.encode())
                process.stdin.flush()
        except BrokenPipeError:
            pass
        finally:
            process.stdin.close()

    threads = [threading.Thread(target=read_stream, args=(i,), daemon=True) for i in range(2)]
    threads.append(threading.Thread(target=write_input, daemon=True))
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        terminate_group()
        process.wait()
    for thread in threads:
        thread.join(timeout=2)
    if any(thread.is_alive() for thread in threads):
        truncated.set()
        terminate_group()
        for thread in threads:
            thread.join(timeout=2)
    return ProcessResult(
        argv=argv,
        exit_code=process.returncode,
        stdout=streams[0].decode(errors="replace"),
        stderr=streams[1].decode(errors="replace"),
        started=started,
        finished=time.time(),
        timed_out=timed_out,
        output_truncated=truncated.is_set(),
    )


class DockerExecutor:
    """Run only contained task effects, without host credentials or administrative mounts."""

    def __init__(self, image: str, resources: Resources | None = None) -> None:
        """Resolve a local operator-selected image to its immutable Docker identity.

        Args:
            image: Approved local image resolved to its actual immutable Docker identity.
            resources: Optional protected resource journal used for interruption recovery.
        """
        binary = shutil.which("docker")
        if binary is None:
            raise BoundaryError("Docker is required; no host execution fallback")
        self.binary = binary
        self.resources = resources
        inspected = bounded_process(
            [binary, "image", "inspect", "--format", "{{.Id}}", image],
            timeout=10,
            output_bytes=4096,
        )
        if inspected.exit_code != 0:
            raise BoundaryError("approved image unavailable; operator must provision it")
        self.image_id = inspected.stdout.strip()
        if not self.image_id.startswith("sha256:") or len(self.image_id) != 71:
            raise BoundaryError("invalid image identity")

    def run(
        self,
        workspace: Path,
        argv: list[str],
        limits: Limits,
        *,
        input_text: str | None = None,
        readonly: bool = False,
        trusted_files: dict[str, Path] | None = None,
        network: str = "none",
        environment: dict[str, str] | None = None,
        container_name: str | None = None,
        network_alias: str | None = None,
    ) -> ProcessResult:
        """Execute a real command in a non-root, resource-limited, network-denied container.

        Args:
            workspace: Isolated task source directory, separate from controller state.
            argv: Exact contained argument vector, never an implicit host shell command.
            limits: Approved resource ceilings; exhaustion does not grant additional allowance.
            input_text: Bounded context sent through process stdin.
            readonly: Mount source read-only for protected verification and inspection.
            trusted_files: Separate protected driver/schema files mounted read-only under /trusted.
            network: Broker-owned private network or none for ordinary target commands.
            environment: Explicit contained variables or a protected immutable capability record.
            container_name: Optional broker-owned unique container name for supervised cleanup.
            network_alias: Optional service alias on an isolated verification network.

        Returns:
            Actual bounded process status, image identity and termination diagnostics.
        """
        if workspace.is_symlink() or not workspace.is_dir():
            raise BoundaryError("workspace must be a real directory")
        path = str(workspace.resolve())
        if any(character in path for character in (",", "\n", "\0")):
            raise BoundaryError("workspace path cannot be represented safely as a mount")
        if os.getuid() == 0:
            raise BoundaryError("controller must run as a non-root host user")
        if not argv or not argv[0] or any("\0" in value for value in argv):
            raise BoundaryError("invalid container command")
        name = container_name or f"darkfactory-{uuid.uuid4().hex}"
        if not name.replace("-", "").isalnum():
            raise BoundaryError("invalid container identity")
        mount = f"type=bind,source={path},target=/workspace"
        if readonly:
            mount += ",readonly"
        command = [
            self.binary,
            "run",
            "--rm",
            "--name",
            name,
            "--network",
            network,
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "128",
            "--memory",
            f"{limits.memory_mb}m",
            "--memory-swap",
            f"{limits.memory_mb}m",
            "--cpus",
            str(limits.cpus),
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--tmpfs",
            "/tmp:rw,exec,nosuid,nodev,size=64m",  # noqa: S108 -- compiled target programs execute only inside the bounded container
            "--mount",
            mount,
            "--workdir",
            "/workspace",
            "--env",
            "HOME=/tmp",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            "HTTP_PROXY=",
            "--env",
            "HTTPS_PROXY=",
            "--env",
            "ALL_PROXY=",
            "--env",
            "NO_PROXY=",
            "--env",
            "http_proxy=",
            "--env",
            "https_proxy=",
            "--env",
            "all_proxy=",
            "--env",
            "no_proxy=",
            "--interactive",
            "--entrypoint",
            argv[0],
            self.image_id,
            *argv[1:],
        ]
        for label, file in (trusted_files or {}).items():
            if (
                not label.isalnum()
                or not file.is_file()
                or file.is_symlink()
                or any(value in str(file.resolve()) for value in (",", "\n", "\0"))
            ):
                raise BoundaryError("invalid trusted verification input")
            command[command.index("--workdir") : command.index("--workdir")] = [
                "--mount",
                f"type=bind,source={file.resolve()},target=/trusted/{label},readonly",
            ]
        for key, value in (environment or {}).items():
            if not key.replace("_", "").isalnum() or "\0" in value:
                raise BoundaryError("invalid contained environment")
            command[command.index("--workdir") : command.index("--workdir")] = [
                "--env",
                f"{key}={value}",
            ]
        if network_alias is not None:
            if not network_alias.isalnum():
                raise BoundaryError("invalid isolated service alias")
            command[command.index("--workdir") : command.index("--workdir")] = [
                "--network-alias",
                network_alias,
            ]
        lease = self.resources.lease(name) if self.resources else nullcontext()
        with lease:
            try:
                result = bounded_process(
                    command,
                    timeout=limits.command_seconds,
                    output_bytes=limits.output_bytes,
                    input_text=input_text,
                )
                return result.model_copy(update={"argv": argv, "image_id": self.image_id})
            finally:
                bounded_process([self.binary, "rm", "--force", name], timeout=10, output_bytes=4096)
