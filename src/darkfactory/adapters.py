"""Structured native CLI adapters and an isolated, task-scoped inference broker."""

from __future__ import annotations

import json
import os
import secrets
import time
import uuid
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Annotated, Any, Protocol

from pydantic import Field

from darkfactory.domain import Blueprint, Contract, InferenceSpec, Limits
from darkfactory.execution import BoundaryError, DockerExecutor, bounded_process
from darkfactory.resources import Resources, StorageQuota
from darkfactory.security import redact
from darkfactory.storage import Record, StateError, Store


class FileEdit(Contract):
    """Untrusted proposed source edit, applied only through the execution broker."""

    path: str = Field(min_length=1, max_length=500)
    content: str | None = Field(default=None, max_length=1000000)


class Finding(Contract):
    """Reviewer judgment with scope and a concrete required correction."""

    severity: Annotated[str, Field(pattern=r"^(blocking|warning|info)$")]
    description: str = Field(min_length=1, max_length=16000)
    criterion: str = Field(min_length=1, max_length=4000)


class AgentReply(Contract):
    """Proposal protocol excludes authoritative pass, approval and acceptance fields."""

    status: Annotated[str, Field(pattern=r"^(continue|complete|blocked)$")]
    summary: str = Field(min_length=1, max_length=16000)
    files: list[FileEdit] = Field(default_factory=list, max_length=100)
    commands: list[list[str]] = Field(default_factory=list, max_length=10)
    findings: list[Finding] = Field(default_factory=list, max_length=100)
    examined: list[str] = Field(default_factory=list)
    unexamined: list[str] = Field(default_factory=list)
    resolved_findings: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    proposed_blueprint: Blueprint | None = None


class Adapter(Protocol):
    """A model's proposed work is independent of trusted execution and quality gates."""

    def propose(self, context: str, workspace: Path, limits: Limits) -> AgentReply:
        """Return a validated proposal, or fail without publishing authoritative success.

        Args:
            context: Bounded assignment and observations; embedded project text remains untrusted.
            workspace: Isolated task source directory; never the controller state directory.
            limits: Approved resource ceilings; exceeding them cannot grant additional allowance.

        Returns:
            Validated proposed edits, commands or judgments without workflow authority.
        """
        ...


class AdapterFailure(StateError):
    """A native process/protocol failure with a protected diagnostic identity."""

    def __init__(self, category: str, diagnostic_id: str) -> None:
        """Describe a failure without echoing raw provider output or credentials.

        Args:
            category: Observed failure class, such as timeout, exit or protocol.
            diagnostic_id: Identifier in the controller's adapter-run history.
        """
        self.category, self.diagnostic_id = category, diagnostic_id
        super().__init__(f"native adapter {category}; diagnostic {diagnostic_id}")


class InferenceSession:
    """Own ephemeral private networks and a gateway with no controller API or DB access."""

    def __init__(self, store: Store, project: str, attempt: str, spec: InferenceSpec) -> None:
        """Bind a broker session to persisted approved limits and one usage reservation.

        Args:
            store: Protected transactional state, unavailable to ordinary agent containers.
            project: Controller project identifier in the selected protected state directory.
            attempt: Unique attempt identity used for isolated resources and accounting.
            spec: Approved provider/model/image configuration for this inference attempt.
        """
        self.store, self.project, self.attempt, self.spec = store, project, attempt, spec
        self.name = "df-" + uuid.uuid4().hex
        self.network = self.name + "-private"
        self.capability = secrets.token_urlsafe(32)
        self.directory = store.root / "attempts" / attempt / "gateway"
        self.directory.mkdir(parents=True)
        self.executor = DockerExecutor(spec.gateway_image)
        self.started = False
        self.lease: AbstractContextManager[None] | None = None

    def start(self) -> None:
        """Provision only operator-enrolled provider access, never personal CLI config."""
        credential = self.store.root / "credentials" / self.spec.provider
        if not credential.is_file() or credential.is_symlink():
            raise StateError("operator must enroll a provider credential in protected storage")
        if credential.stat().st_mode & 0o077 or credential.stat().st_uid != os.getuid():
            raise StateError("provider credential must have owner-only permissions")
        config = self.directory / "config.json"
        config.write_text(
            json.dumps(
                {**self.spec.model_dump(), "capability": self.capability, "timeout_seconds": 120}
            )
        )
        config.chmod(0o600)
        ledger = self.directory / "ledger"
        ledger.mkdir()
        script = Path(__file__).with_name("gateway_server.py")
        docker = self.executor.binary
        self.lease = Resources(self.store, self.project).lease(self.name, network=self.network)
        self.lease.__enter__()
        created = bounded_process(
            [docker, "network", "create", "--internal", self.network], timeout=10, output_bytes=4096
        )
        if created.exit_code:
            raise BoundaryError("private inference network unavailable")
        command = [
            docker,
            "run",
            "--detach",
            "--name",
            self.name,
            "--network",
            "bridge",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "32",
            "--memory",
            "256m",
            "--cpus",
            "1",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--mount",
            f"type=bind,source={config},target=/trusted/config,readonly",
            "--mount",
            f"type=bind,source={credential},target=/trusted/credential,readonly",
            "--mount",
            f"type=bind,source={script},target=/trusted/server.py,readonly",
            "--mount",
            f"type=bind,source={ledger},target=/ledger",
            "--entrypoint",
            "python",
            self.executor.image_id,
            "-I",
            "/trusted/server.py",
        ]
        result = bounded_process(command, timeout=15, output_bytes=4096)
        if result.exit_code:
            self.close()
            raise BoundaryError("isolated inference gateway cannot start")
        connected = bounded_process(
            [docker, "network", "connect", "--alias", "inference", self.network, self.name],
            timeout=10,
            output_bytes=4096,
        )
        if connected.exit_code:
            self.close()
            raise BoundaryError("isolated inference network attachment failed")
        self.started = True
        deadline = time.monotonic() + 10
        while not (ledger / "usage.json").exists():
            if time.monotonic() >= deadline:
                self.close()
                raise BoundaryError("inference gateway did not initialize")
            time.sleep(0.05)

    def usage(self) -> Record:
        """Read only the trusted gateway's ledger, never model-reported token/cost claims.

        Returns:
            Trusted gateway usage ledger, preserving unknown usage as reserved capacity.
        """
        path = self.directory / "ledger" / "usage.json"
        if not path.exists():
            return {"tokens": 0, "reserved": self.spec.attempt_tokens, "unknown": True}
        return dict(json.loads(path.read_text()))

    def close(self) -> None:
        """Remove only ephemeral resources created by this session, retaining usage evidence."""
        docker = self.executor.binary
        bounded_process([docker, "rm", "--force", self.name], timeout=10, output_bytes=4096)
        bounded_process([docker, "network", "rm", self.network], timeout=10, output_bytes=4096)
        self.started = False
        if self.lease is not None:
            self.lease.__exit__(None, None, None)
            self.lease = None


class NativeAdapter:
    """Launch native Claude Code or Codex in a contained environment via model-only gateway."""

    def __init__(self, blueprint: Blueprint, session: InferenceSession) -> None:
        """Require an explicit provider/image binding; no host CLI execution fallback.

        Args:
            blueprint: Validated project contract whose exact identity requires human approval.
            session: Isolated inference gateway session; provider credentials stay outside task
                mounts.
        """
        if blueprint.inference is None:
            raise StateError("approved inference configuration required")
        self.name = blueprint.adapter
        self.spec = blueprint.inference
        self.session = session
        self.executor = DockerExecutor(
            self.spec.agent_image, Resources(session.store, session.project)
        )

    def propose(self, context: str, workspace: Path, limits: Limits) -> AgentReply:
        """Run native structured-output inference with broker-mediated edits and commands.

        Args:
            context: Bounded assignment and observations; embedded project text remains untrusted.
            workspace: Isolated task source directory; never the controller state directory.
            limits: Approved resource ceilings; exceeding them cannot grant additional allowance.

        Returns:
            Validated proposed edits, commands or judgments without workflow authority.
        """
        schema = strict_schema(AgentReply.model_json_schema())
        schema_file = self.session.directory / "reply-schema.json"
        schema_file.write_text(json.dumps(schema))
        environment: dict[str, str]
        if self.name == "claude" and self.spec.provider == "anthropic":
            argv = [
                "claude",
                "--bare",
                "--print",
                "--tools",
                "",
                "--output-format",
                "json",
                "--json-schema",
                json.dumps(schema),
                "--model",
                self.spec.model,
                "--system-prompt",
                "Return only the assigned AgentReply JSON proposal.",
            ]
            environment = {
                "ANTHROPIC_BASE_URL": "http://inference:8080",
                "ANTHROPIC_AUTH_TOKEN": self.session.capability,
                "ANTHROPIC_API_KEY": self.session.capability,
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            }
        elif self.name == "codex" and self.spec.provider == "openai":
            provider = 'model_providers.factory={name="Factory",base_url="http://inference:8080/v1",env_key="FACTORY_CAPABILITY",wire_api="responses"}'
            argv = [
                "codex",
                "--ask-for-approval",
                "never",
                "--sandbox",
                "read-only",
                "-c",
                'model_provider="factory"',
                "-c",
                provider,
                "--model",
                self.spec.model,
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--skip-git-repo-check",
                "--json",
                "--output-schema",
                "/trusted/schema",
                "-",
            ]
            environment = {"FACTORY_CAPABILITY": self.session.capability, "CODEX_HOME": "/tmp"}  # noqa: S108 -- isolated container tmpfs
        else:
            raise StateError("unsupported adapter/provider binding")
        identifier = uuid.uuid4().hex
        directory = self.session.directory.parent / "adapter-diagnostics"
        directory.mkdir(exist_ok=True)
        with (directory / (identifier + ".lock")).open("a") as lock:
            import fcntl

            fcntl.flock(lock, fcntl.LOCK_EX)
            self._record(identifier, "RUNNING", {"image_id": self.executor.image_id})
            try:
                result = self.executor.run(
                    workspace,
                    argv,
                    limits,
                    input_text=context,
                    readonly=True,
                    trusted_files={"schema": schema_file},
                    network=self.session.network,
                    environment=environment,
                )
            except (OSError, RuntimeError, ValueError):
                self._record(identifier, "LAUNCH_ERROR", {"image_id": self.executor.image_id})
                raise AdapterFailure("launch", identifier) from None
            diagnostic = result.model_dump(mode="json")
            for field in ("stdout", "stderr"):
                diagnostic[field] = redact(
                    str(diagnostic[field]).replace(self.session.capability, "[REDACTED]")
                )
            category = (
                "TIMEOUT"
                if result.timed_out
                else "OUTPUT_LIMIT"
                if result.output_truncated
                else "EXIT"
                if result.exit_code
                else "COMPLETE"
            )
            if category != "COMPLETE":
                self._record(identifier, category, diagnostic)
                raise AdapterFailure(category.lower(), identifier)
            try:
                reply = self.parse(self.name, result.stdout)
            except (ValueError, StateError, TypeError):
                self._record(identifier, "PROTOCOL", diagnostic)
                raise AdapterFailure("protocol", identifier) from None
            self._record(identifier, "COMPLETE", diagnostic)
            return reply

    def _record(self, identifier: str, state: str, diagnostic: Record) -> None:
        store = self.session.store
        data = json.dumps(diagnostic)
        quota = StorageQuota(
            store.root, store.blueprint(self.session.project).limits.state_storage_mb * 1024 * 1024
        )
        with quota.allocate(len(data.encode()) * 2 + 65536), store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO adapter_runs VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET state=excluded.state,"
                "diagnostic=excluded.diagnostic,finished=excluded.finished",
                (
                    identifier,
                    self.session.project,
                    self.session.attempt,
                    self.name,
                    state,
                    data,
                    time.time(),
                    None if state == "RUNNING" else time.time(),
                ),
            )
            store._event(
                connection,
                self.session.project,
                "adapter." + state.lower(),
                {
                    "diagnostic": identifier,
                    "attempt": self.session.attempt,
                    "adapter": self.name,
                },
            )

    @staticmethod
    def reconcile(store: Store, project: str) -> int:
        """Record abandoned native processes after their supervisor OS locks are released.

        Args:
            store: Protected controller state.
            project: Project being recovered.

        Returns:
            Count of interrupted adapter runs, without inventing provider usage.
        """
        import fcntl

        with store.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM adapter_runs WHERE project_id=? AND state='RUNNING'", (project,)
            ).fetchall()
        count = 0
        for row in rows:
            path = (
                store.root
                / "attempts"
                / row["attempt_id"]
                / "adapter-diagnostics"
                / (row["id"] + ".lock")
            )
            with path.open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                with store.connection() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    updated = connection.execute(
                        "UPDATE adapter_runs SET state='ABORTED',finished=? "
                        "WHERE id=? AND state='RUNNING'",
                        (time.time(), row["id"]),
                    )
                    if updated.rowcount:
                        store._event(
                            connection, project, "adapter.aborted", {"diagnostic": row["id"]}
                        )
                        count += 1
        return count

    @staticmethod
    def parse(name: str, output: str) -> AgentReply:
        """Parse declared CLI envelopes without turning malformed output into success.

        Args:
            name: Explicit native adapter identifier or broker-owned resource name.
            output: Actual native CLI output; malformed or failed envelopes are rejected.

        Returns:
            Validated AgentReply from a successful declared native envelope.
        """
        if name == "claude":
            envelope = json.loads(output)
            if not isinstance(envelope, dict) or envelope.get("is_error"):
                raise StateError("Claude output is not a successful structured result")
            return AgentReply.model_validate(envelope.get("structured_output"))
        if name == "codex":
            answer: Any = None
            for line in output.splitlines():
                event = json.loads(line)
                if not isinstance(event, dict) or event.get("type") in ("error", "turn.failed"):
                    raise StateError("Codex reported a failed or malformed turn")
                item = event.get("item", {})
                if not isinstance(item, dict):
                    raise StateError("Codex reported a malformed item")
                if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                    answer = item.get("text")
            if not isinstance(answer, str):
                raise StateError("Codex output contains no structured agent reply")
            return AgentReply.model_validate_json(answer)
        raise StateError("unsupported native adapter")


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Require all declared properties for native structured-output API compatibility.

    Args:
        schema: JSON schema adjusted for closed native structured-output contracts.

    Returns:
        The schema with all object properties required and undeclared fields refused.
    """
    for value in schema.values():
        if isinstance(value, dict):
            strict_schema(value)
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, dict):
                    strict_schema(child)
    if schema.get("type") == "object" and "properties" in schema:
        schema["required"] = list(schema["properties"])
        schema["additionalProperties"] = False
    return schema
