"""Transactional project state, fenced task ownership and protected audit history."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
import weakref
from _thread import LockType
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

from darkfactory.domain import Blueprint, Policy, ProjectState, TaskSpec, TaskState, digest
from darkfactory.policy import validate_policy
from darkfactory.security import redact_value

Record = dict[str, Any]


def _close_connections(
    anchor: sqlite3.Connection,
    pool: list[sqlite3.Connection],
    lock: LockType,
) -> None:
    with lock:
        for connection in pool:
            connection.close()
        pool.clear()
        anchor.close()


class StateError(RuntimeError):
    """An operation lacked a current approval, lease or legal transition."""


class Store:
    """Own authoritative state outside all agent-writable task mounts.

    This is a trusted internal interface. Administrative callers authenticate
    before invoking it; task adapters are never given this object or database.
    """

    def __init__(self, root: Path) -> None:
        """Initialize protected local storage and fail on an unsafe SQLite version.

        Args:
            root: Dedicated storage root outside imported application source.
        """
        if root.is_symlink():
            raise StateError("state directory must not be a symlink")
        if sqlite3.sqlite_version_info < (3, 51, 3):
            raise StateError("SQLite 3.51.3+ is required for safe WAL concurrency")
        from darkfactory.volumes import require_registered_mount

        require_registered_mount(root)
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        self.database = self.root / "factory.sqlite3"
        self._pool: list[sqlite3.Connection] = []
        self._pool_lock = threading.Lock()
        self._closed = False
        for name in ("projects", "attempts", "snapshots", "evidence"):
            (self.root / name).mkdir(exist_ok=True, mode=0o700)
        self._initialize()
        # An idle anchor prevents SQLite's last-connection WAL cleanup on every status read.
        self._anchor = sqlite3.connect(self.database, timeout=5, check_same_thread=False)
        self._anchor.execute("PRAGMA synchronous=FULL")
        self._finalizer = weakref.finalize(
            self, _close_connections, self._anchor, self._pool, self._pool_lock
        )
        self.database.chmod(0o600)

    def close(self) -> None:
        """Release idle transactional connections and the WAL anchor after clients stop.

        Committed writes remain durable under synchronous=FULL. Active operations
        own separate transactional connections and are never shared across threads.
        Calling close repeatedly is safe; it does not delete persisted state.
        """
        self._closed = True
        self._finalizer()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Commit atomic mutations, rolling back on any exception.

        Yields:
            Ownership of the protected operation for this context lifetime.
        """
        if self._closed:
            raise StateError("controller store is closed")
        with self._pool_lock:
            connection = self._pool.pop() if self._pool else None
        if connection is None:
            connection = sqlite3.connect(self.database, timeout=5, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA synchronous=FULL")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            # Each checkout owns a distinct connection, including nested service reads.
            with self._pool_lock:
                if not self._closed and len(self._pool) < 8:
                    self._pool.append(connection)
                else:
                    connection.close()

    def _initialize(self) -> None:
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
                INSERT INTO schema_version SELECT 1
                    WHERE NOT EXISTS(SELECT 1 FROM schema_version);
                CREATE TABLE IF NOT EXISTS projects(
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, state TEXT NOT NULL,
                    blueprint TEXT NOT NULL, blueprint_hash TEXT NOT NULL,
                    policy TEXT NOT NULL, policy_hash TEXT NOT NULL,
                    source_digest TEXT, delivery_digest TEXT, error TEXT,
                    created REAL NOT NULL, updated REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approvals(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    blueprint_hash TEXT NOT NULL, policy_hash TEXT NOT NULL,
                    actor TEXT NOT NULL, created REAL NOT NULL,
                    UNIQUE(project_id, blueprint_hash, policy_hash)
                );
                CREATE TABLE IF NOT EXISTS tasks(
                    project_id TEXT NOT NULL REFERENCES projects(id), id TEXT NOT NULL,
                    spec TEXT NOT NULL, state TEXT NOT NULL, fence INTEGER NOT NULL DEFAULT 0,
                    owner TEXT, lease_until REAL, attempts INTEGER NOT NULL DEFAULT 0,
                    attempt_id TEXT, source_digest TEXT, error TEXT,
                    PRIMARY KEY(project_id, id)
                );
                CREATE TABLE IF NOT EXISTS attempts(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, task_id TEXT NOT NULL,
                    fence INTEGER NOT NULL, owner TEXT NOT NULL, started REAL NOT NULL,
                    finished REAL, state TEXT NOT NULL, diagnosis TEXT,
                    FOREIGN KEY(project_id, task_id) REFERENCES tasks(project_id,id)
                );
                CREATE TABLE IF NOT EXISTS checks(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    task_id TEXT, attempt_id TEXT, check_id TEXT NOT NULL,
                    source_digest TEXT NOT NULL, definition_hash TEXT NOT NULL,
                    policy_hash TEXT NOT NULL, passed INTEGER NOT NULL,
                    result TEXT NOT NULL, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reviews(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    task_id TEXT, source_digest TEXT NOT NULL, role TEXT NOT NULL,
                    attempt_id TEXT NOT NULL, verdict TEXT NOT NULL,
                    report TEXT NOT NULL, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS findings(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    review_id TEXT NOT NULL REFERENCES reviews(id), task_id TEXT,
                    source_digest TEXT NOT NULL, severity TEXT NOT NULL,
                    description TEXT NOT NULL, resolved_by TEXT, resolution TEXT
                );
                CREATE TABLE IF NOT EXISTS operations(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    kind TEXT NOT NULL, intent TEXT NOT NULL, state TEXT NOT NULL,
                    outcome TEXT, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS usage(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    attempt_id TEXT NOT NULL, tokens INTEGER NOT NULL DEFAULT 0,
                    reserved INTEGER NOT NULL DEFAULT 0, cost_microusd INTEGER,
                    created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS corrections(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    revision TEXT NOT NULL, actor TEXT NOT NULL, criteria TEXT NOT NULL,
                    reason TEXT NOT NULL, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS correction_tasks(
                    correction_id TEXT NOT NULL REFERENCES corrections(id),
                    project_id TEXT NOT NULL, task_id TEXT NOT NULL, parent_task TEXT NOT NULL,
                    PRIMARY KEY(project_id,task_id),
                    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id),
                    FOREIGN KEY(project_id,parent_task) REFERENCES tasks(project_id,id)
                );
                CREATE TABLE IF NOT EXISTS finding_exceptions(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    finding_id TEXT NOT NULL REFERENCES findings(id), source_digest TEXT NOT NULL,
                    blueprint_hash TEXT NOT NULL, policy_hash TEXT NOT NULL,
                    actor TEXT NOT NULL, reason TEXT NOT NULL, created REAL NOT NULL,
                    revoked REAL
                );
                CREATE TABLE IF NOT EXISTS adapter_runs(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    attempt_id TEXT NOT NULL, adapter TEXT NOT NULL, state TEXT NOT NULL,
                    diagnostic TEXT NOT NULL, created REAL NOT NULL, finished REAL
                );
                CREATE TABLE IF NOT EXISTS audit(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT,
                    event TEXT NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL,
                    previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS task_dispatch ON tasks(project_id,state,lease_until);
                CREATE INDEX IF NOT EXISTS check_revision ON checks(project_id,source_digest);
            """)
            versions = [row[0] for row in connection.execute("SELECT version FROM schema_version")]
            if versions not in ([1], [2]):
                raise StateError("unsupported database schema; no automatic destructive migration")
            connection.execute("UPDATE schema_version SET version=2 WHERE version=1")

    def _event(
        self, connection: sqlite3.Connection, project_id: str | None, event: str, payload: Record
    ) -> None:
        encoded = json.dumps(redact_value(payload), sort_keys=True, separators=(",", ":"))
        row = connection.execute(
            "SELECT event_hash FROM audit ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        previous = row[0] if row else "0" * 64
        timestamp = time.time()
        material = json.dumps([project_id, event, encoded, timestamp, previous]).encode()
        event_hash = hashlib.sha256(material).hexdigest()
        connection.execute(
            "INSERT INTO audit(project_id,event,payload,created,previous_hash,event_hash) "
            "VALUES(?,?,?,?,?,?)",
            (project_id, event, encoded, timestamp, previous, event_hash),
        )

    def verify_audit(self) -> bool:
        """Detect altered, missing or reordered records in the protected event chain.

        Returns:
            Whether the protected hash chain is intact; no external tail anchor is implied.
        """
        previous = "0" * 64
        with self.connection() as connection:
            for row in connection.execute("SELECT * FROM audit ORDER BY seq"):
                material = json.dumps(
                    [row["project_id"], row["event"], row["payload"], row["created"], previous]
                ).encode()
                if row["previous_hash"] != previous:
                    return False
                if hashlib.sha256(material).hexdigest() != row["event_hash"]:
                    return False
                previous = row["event_hash"]
        return True

    def create_project(
        self, blueprint: Blueprint, policy: Policy, *, project_id: str | None = None
    ) -> str:
        """Persist a validated proposed blueprint without authorizing implementation.

        Args:
            blueprint: Project contract whose exact identity requires separate human approval.
            policy: Versioned quality/execution rules bound into the approval identity.
            project_id: Project identity in the selected protected controller state.

        Returns:
            Persisted unapproved identity; implementation is not authorized.
        """
        blueprint = Blueprint.model_validate(blueprint.model_dump())
        decision = validate_policy(blueprint, policy)
        if not decision.allowed:
            raise StateError("; ".join(decision.reasons))
        project_id = project_id or uuid.uuid4().hex
        if uuid.UUID(hex=project_id).hex != project_id:
            raise StateError("invalid proposed project identity")
        now = time.time()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT blueprint_hash,policy_hash FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            if existing:
                if tuple(existing) != (digest(blueprint), digest(policy)):
                    raise StateError("proposed identity cannot replace a different blueprint")
                return project_id
            connection.execute(
                "INSERT INTO projects(id,name,state,blueprint,blueprint_hash,policy,policy_hash,"
                "created,updated) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    project_id,
                    blueprint.name,
                    ProjectState.AWAITING_APPROVAL,
                    blueprint.model_dump_json(),
                    digest(blueprint),
                    policy.model_dump_json(),
                    digest(policy),
                    now,
                    now,
                ),
            )
            for task in blueprint.tasks:
                connection.execute(
                    "INSERT INTO tasks(project_id,id,spec,state) VALUES(?,?,?,?)",
                    (project_id, task.id, task.model_dump_json(), TaskState.PENDING),
                )
            self._event(connection, project_id, "blueprint.proposed", {"digest": digest(blueprint)})
        return project_id

    def project(self, project_id: str) -> Record:
        """Return one controller record or a safe not-found error.

        Args:
            project_id: Project identity in the selected protected controller state.

        Returns:
            Protected project record with current state and content identities.
        """
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if row is None:
                raise StateError("unknown project")
            return dict(row)

    def projects(self) -> list[Record]:
        """Return actual persisted project summaries for operational interfaces.

        Returns:
            Actual persisted projects in creation order.
        """
        with self.connection() as connection:
            return [
                dict(row) for row in connection.execute("SELECT * FROM projects ORDER BY created")
            ]

    def blueprint(self, project_id: str) -> Blueprint:
        """Load the authoritative blueprint, never a workspace projection.

        Args:
            project_id: Project identity in the selected protected controller state.

        Returns:
            Validated stored blueprint independent of editable workspace documents.
        """
        return Blueprint.model_validate_json(self.project(project_id)["blueprint"])

    def policy(self, project_id: str) -> Policy:
        """Load the active policy version bound to this project's approval.

        Args:
            project_id: Project identity in the selected protected controller state.

        Returns:
            Protected validated policy bound to this project approval.
        """
        return Policy.model_validate_json(self.project(project_id)["policy"])

    def environment(self, project_id: str) -> Record | None:
        """Return the immutable execution identities established at first approved start.

        Args:
            project_id: Project identity in the selected protected controller state.

        Returns:
            Recorded immutable capabilities, or None before successful admission.
        """
        with self.connection() as connection:
            row = connection.execute(
                "SELECT intent FROM operations WHERE project_id=? AND kind='environment'",
                (project_id,),
            ).fetchone()
            return json.loads(row[0]) if row else None

    def record_environment(self, project_id: str, environment: Record) -> None:
        """Bind images and adapter capabilities; changed execution requires renewed approval.

        Args:
            project_id: Project identity in the selected protected controller state.
            environment: Explicit contained variables or a protected immutable capability record.
        """
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute(
                "SELECT intent FROM operations WHERE project_id=? AND kind='environment'",
                (project_id,),
            ).fetchone()
            if previous:
                if json.loads(previous[0]) != environment:
                    raise StateError(
                        "admitted environment changed; new blueprint approval required"
                    )
                return
            connection.execute(
                "INSERT INTO operations VALUES(?,?,?,?,?,?,?)",
                (
                    uuid.uuid4().hex,
                    project_id,
                    "environment",
                    json.dumps(environment),
                    "APPLIED",
                    digest(environment),
                    time.time(),
                ),
            )
            self._event(connection, project_id, "environment.admitted", environment)

    def approve(self, project_id: str, blueprint_hash: str, actor: str) -> None:
        """Record an authenticated human's approval for an exact blueprint/policy.

        Args:
            project_id: Project identity in the selected protected controller state.
            blueprint_hash: Exact proposed digest presented to the human approval action.
            actor: Authenticated human identity supplied by the administrative channel.
        """
        if not actor.startswith("human:"):
            raise StateError("approval requires an authenticated human identity")
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if row is None or row["blueprint_hash"] != blueprint_hash:
                raise StateError("approval digest mismatch")
            if row["state"] != ProjectState.AWAITING_APPROVAL:
                raise StateError("approval requires a proposed blueprint")
            connection.execute(
                "INSERT INTO approvals VALUES(?,?,?,?,?,?)",
                (
                    uuid.uuid4().hex,
                    project_id,
                    blueprint_hash,
                    row["policy_hash"],
                    actor,
                    time.time(),
                ),
            )
            connection.execute(
                "UPDATE projects SET state=?,updated=? WHERE id=?",
                (ProjectState.READY, time.time(), project_id),
            )
            self._event(
                connection,
                project_id,
                "blueprint.approved",
                {"actor": actor, "digest": blueprint_hash},
            )

    def current_approval(self, project_id: str) -> bool:
        """Verify approved content identities before project effects begin.

        Args:
            project_id: Project identity in the selected protected controller state.

        Returns:
            True only when exact stored identities have a current protected approval.
        """
        project = self.project(project_id)
        self.blueprint(project_id)
        self.policy(project_id)
        if (
            # Safe optional defaults must not rewrite the content identity of an old approval.
            digest(json.loads(project["blueprint"])) != project["blueprint_hash"]
            or digest(json.loads(project["policy"])) != project["policy_hash"]
        ):
            return False
        with self.connection() as connection:
            return (
                connection.execute(
                    "SELECT id FROM approvals WHERE project_id=? "
                    "AND blueprint_hash=? AND policy_hash=?",
                    (project_id, project["blueprint_hash"], project["policy_hash"]),
                ).fetchone()
                is not None
            )

    def start(self, project_id: str) -> None:
        """Activate approved scheduling after the service performs environment admission.

        Args:
            project_id: Project identity in the selected protected controller state.
        """
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if row is None or row["state"] not in (
                ProjectState.READY,
                ProjectState.PAUSED,
                ProjectState.BLOCKED,
            ):
                raise StateError("start requires a current approval and resumable state")
            approval = connection.execute(
                "SELECT id FROM approvals WHERE project_id=? "
                "AND blueprint_hash=? AND policy_hash=?",
                (project_id, row["blueprint_hash"], row["policy_hash"]),
            ).fetchone()
            if approval is None:
                raise StateError("missing current blueprint approval")
            connection.execute(
                "UPDATE projects SET state=?,error=NULL,updated=? WHERE id=?",
                (ProjectState.RUNNING, time.time(), project_id),
            )
            self._event(connection, project_id, "project.started", {})

    def tasks(self, project_id: str) -> list[Record]:
        """Return actual task states, ownership and retained diagnostics.

        Args:
            project_id: Project identity in the selected protected controller state.

        Returns:
            Persisted task states, source identities, ownership and diagnostics.
        """
        with self.connection() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM tasks WHERE project_id=? ORDER BY rowid", (project_id,)
                )
            ]

    def task_spec(self, project_id: str, task_id: str) -> TaskSpec:
        """Load an approved assignment or its human-authorized scoped correction.

        Args:
            project_id: Controller project identity.
            task_id: Original or corrective task identity.

        Returns:
            The persisted task definition, including its protected check selection.

        Raises:
            StateError: The task does not belong to this project.
        """
        with self.connection() as connection:
            row = connection.execute(
                "SELECT spec FROM tasks WHERE project_id=? AND id=?", (project_id, task_id)
            ).fetchone()
        if row is None:
            raise StateError("unknown project task")
        return TaskSpec.model_validate_json(row[0])

    def corrections(self, project_id: str) -> list[Record]:
        """Return immutable correction requests and their separately attributable tasks.

        Args:
            project_id: Controller project identity.

        Returns:
            Requests with original criteria, rejected revision and child-task links.
        """
        with self.connection() as connection:
            result = []
            for row in connection.execute(
                "SELECT * FROM corrections WHERE project_id=? ORDER BY created", (project_id,)
            ):
                record = dict(row)
                record["criteria"] = json.loads(record["criteria"])
                record["tasks"] = [
                    dict(link)
                    for link in connection.execute(
                        "SELECT task_id,parent_task FROM correction_tasks WHERE correction_id=?",
                        (row["id"],),
                    )
                ]
                result.append(record)
            return result

    def blocking_findings(
        self,
        project_id: str,
        source: str,
        task_id: str | None = None,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> list[Record]:
        """Return unresolved blocking findings without a valid exact-revision exception.

        Args:
            project_id: Project whose protected findings are evaluated.
            source: Exact source revision at the gate being evaluated.
            task_id: Optional task scope; project findings always apply.
            connection: Existing transaction when evaluating an atomic mutation.

        Returns:
            Blocking findings that still prevent the requested transition.
        """
        if connection is None:
            with self.connection() as database:
                return self.blocking_findings(project_id, source, task_id, connection=database)
        return [
            dict(row)
            for row in connection.execute(
                "SELECT f.* FROM findings f WHERE f.project_id=? "
                "AND f.severity='blocking' AND f.resolved_by IS NULL "
                "AND (? IS NULL OR f.task_id=? OR f.task_id IS NULL) "
                "AND NOT EXISTS(SELECT 1 FROM finding_exceptions e "
                "JOIN projects p ON p.id=e.project_id "
                "WHERE e.project_id=f.project_id AND e.finding_id=f.id "
                "AND e.source_digest=? AND e.blueprint_hash=p.blueprint_hash "
                "AND e.policy_hash=p.policy_hash AND e.revoked IS NULL)",
                (project_id, task_id, task_id, source),
            )
        ]

    def review_satisfied(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        review_id: str,
        source: str,
    ) -> bool:
        """Evaluate a real review without rewriting its unfavorable historical verdict.

        Args:
            connection: Gate's current database transaction.
            project_id: Owning project identity.
            review_id: Actual independent review identity.
            source: Exact source revision under consideration.

        Returns:
            Whether the review approves, or all its blocking findings have been
            resolved or explicitly excepted for this exact source and policy.
        """
        review = connection.execute(
            "SELECT verdict FROM reviews WHERE id=? AND project_id=? AND source_digest=?",
            (review_id, project_id, source),
        ).fetchone()
        if review is None:
            return False
        if review[0] == "APPROVE":
            return True
        findings = connection.execute(
            "SELECT id FROM findings WHERE review_id=? AND severity='blocking'", (review_id,)
        ).fetchall()
        blockers = {
            row["id"] for row in self.blocking_findings(project_id, source, connection=connection)
        }
        return bool(findings) and not any(row[0] in blockers for row in findings)

    def claim(
        self, project_id: str, owner: str, *, now: float | None = None, lease_seconds: int = 60
    ) -> Record | None:
        """Claim an eligible task atomically, fencing abandoned workers and overlapping paths.

        Args:
            project_id: Project identity in the selected protected controller state.
            owner: Unique worker ownership identity for the current scheduling session.
            now: Optional explicit clock for deterministic ownership boundary tests.
            lease_seconds: Ownership expiry bound for heartbeat and stale-worker fencing.

        Returns:
            Fenced assignment and attempt identity, or None when none is eligible.
        """
        timestamp = time.time() if now is None else now
        blueprint = self.blueprint(project_id)
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = connection.execute(
                "SELECT state FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            if state is None or state[0] != ProjectState.RUNNING:
                return None
            rows = list(
                connection.execute(
                    "SELECT * FROM tasks WHERE project_id=? ORDER BY rowid", (project_id,)
                )
            )
            active = [row for row in rows if row["owner"] and row["lease_until"] > timestamp]
            if len(active) >= blueprint.limits.concurrency:
                return None
            integrated = {row["id"] for row in rows if row["state"] == TaskState.INTEGRATED}
            owned_paths = [
                TaskSpec.model_validate_json(row["spec"]).permitted_paths for row in active
            ]
            for row in rows:
                expired = bool(row["owner"] and row["lease_until"] <= timestamp)
                if (
                    row["state"] not in (TaskState.PENDING, TaskState.REPAIR_REQUIRED)
                    and not expired
                ):
                    continue
                spec = TaskSpec.model_validate_json(row["spec"])
                if not set(spec.dependencies) <= integrated:
                    continue
                if any(_paths_overlap(spec.permitted_paths, paths) for paths in owned_paths):
                    continue
                if row["attempts"] >= blueprint.limits.max_attempts:
                    connection.execute(
                        "UPDATE tasks SET state=?,owner=NULL,lease_until=NULL,error=? "
                        "WHERE project_id=? AND id=?",
                        (TaskState.BLOCKED, "recovery strategies exhausted", project_id, row["id"]),
                    )
                    self._event(connection, project_id, "task.blocked", {"task": row["id"]})
                    continue
                if expired:
                    connection.execute(
                        "UPDATE attempts SET state='ABANDONED',finished=? WHERE id=?",
                        (timestamp, row["attempt_id"]),
                    )
                fence = int(row["fence"]) + 1
                attempt_id = uuid.uuid4().hex
                connection.execute(
                    "UPDATE tasks SET state=?,owner=?,lease_until=?,fence=?,"
                    "attempts=attempts+1,attempt_id=? WHERE project_id=? AND id=?",
                    (
                        TaskState.IMPLEMENTING,
                        owner,
                        timestamp + lease_seconds,
                        fence,
                        attempt_id,
                        project_id,
                        row["id"],
                    ),
                )
                connection.execute(
                    "INSERT INTO attempts(id,project_id,task_id,fence,owner,started,state) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (attempt_id, project_id, row["id"], fence, owner, timestamp, "RUNNING"),
                )
                self._event(
                    connection,
                    project_id,
                    "task.claimed",
                    {"task": row["id"], "fence": fence, "attempt": attempt_id},
                )
                return {
                    "project_id": project_id,
                    "task_id": row["id"],
                    "fence": fence,
                    "attempt_id": attempt_id,
                    "spec": spec.model_dump(mode="json"),
                    "owner": owner,
                }
            return None

    def _lease(
        self, connection: sqlite3.Connection, project_id: str, task_id: str, fence: int, now: float
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM tasks WHERE project_id=? AND id=?", (project_id, task_id)
        ).fetchone()
        if row is None or row["fence"] != fence or not row["owner"] or row["lease_until"] <= now:
            raise StateError("stale worker lease")
        return cast(sqlite3.Row, row)

    def heartbeat(
        self,
        project_id: str,
        task_id: str,
        fence: int,
        *,
        now: float | None = None,
        lease_seconds: int = 60,
    ) -> None:
        """Extend only the current unexpired ownership lease.

        Args:
            project_id: Project identity in the selected protected controller state.
            task_id: Original or human-authorized corrective task identifier.
            fence: Current ownership generation; expired or superseded values are rejected.
            now: Optional explicit clock for deterministic ownership boundary tests.
            lease_seconds: Ownership expiry bound for heartbeat and stale-worker fencing.
        """
        timestamp = time.time() if now is None else now
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._lease(connection, project_id, task_id, fence, timestamp)
            connection.execute(
                "UPDATE tasks SET lease_until=? WHERE project_id=? AND id=?",
                (timestamp + lease_seconds, project_id, task_id),
            )

    def finish_attempt(
        self,
        assignment: Record,
        state: TaskState,
        *,
        source_digest: str | None = None,
        error: str | None = None,
    ) -> None:
        """Publish a trusted attempt outcome only while its fencing token remains current.

        Args:
            assignment: Persisted task ownership, attempt and fencing identity.
            state: Trusted attempt outcome, not an agent completion claim.
            source_digest: Exact immutable source identity associated with the result.
            error: Observed failure diagnostic with credentials excluded.
        """
        if state not in (TaskState.INTEGRATED, TaskState.REPAIR_REQUIRED, TaskState.BLOCKED):
            raise StateError("invalid attempt outcome")
        project_id, task_id, fence = (
            assignment["project_id"],
            assignment["task_id"],
            assignment["fence"],
        )
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._lease(connection, project_id, task_id, fence, time.time())
            connection.execute(
                "UPDATE tasks SET state=?,source_digest=?,error=?,owner=NULL,lease_until=NULL "
                "WHERE project_id=? AND id=?",
                (state, source_digest, error, project_id, task_id),
            )
            connection.execute(
                "UPDATE attempts SET state=?,finished=?,diagnosis=? WHERE id=?",
                (state, time.time(), error, assignment["attempt_id"]),
            )
            self._event(
                connection,
                project_id,
                "task.attempt_finished",
                {"task": task_id, "state": state, "source": source_digest, "error": error},
            )

    def checkpoint(self, assignment: Record, source_digest: str) -> None:
        """Retain source progress under the current fence without certifying its quality.

        Args:
            assignment: Persisted task ownership, attempt and fencing identity.
            source_digest: Exact immutable source identity associated with the result.
        """
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._lease(
                connection,
                assignment["project_id"],
                assignment["task_id"],
                assignment["fence"],
                time.time(),
            )
            connection.execute(
                "UPDATE tasks SET source_digest=? WHERE project_id=? AND id=?",
                (source_digest, assignment["project_id"], assignment["task_id"]),
            )
            self._event(
                connection,
                assignment["project_id"],
                "task.checkpointed",
                {
                    "task": assignment["task_id"],
                    "source": source_digest,
                    "fence": assignment["fence"],
                },
            )

    def stage(self, assignment: Record, target: TaskState) -> None:
        """Persist a legal phase under current ownership without granting quality approval.

        Args:
            assignment: Persisted task ownership, attempt and fencing identity.
            target: Requested legal task phase under the current ownership fence.
        """
        transitions = {
            TaskState.IMPLEMENTING: {TaskState.VERIFYING},
            TaskState.VERIFYING: {TaskState.IN_REVIEW},
            TaskState.IN_REVIEW: {TaskState.READY_TO_INTEGRATE},
            TaskState.READY_TO_INTEGRATE: {TaskState.VERIFYING},
        }
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._lease(
                connection,
                assignment["project_id"],
                assignment["task_id"],
                assignment["fence"],
                time.time(),
            )
            if target not in transitions.get(current["state"], set()):
                raise StateError("illegal task phase transition")
            connection.execute(
                "UPDATE tasks SET state=? WHERE project_id=? AND id=?",
                (target, assignment["project_id"], assignment["task_id"]),
            )
            self._event(
                connection,
                assignment["project_id"],
                "task.stage",
                {"task": assignment["task_id"], "state": target, "fence": assignment["fence"]},
            )

    def request_repairs(
        self,
        project_id: str,
        reason: str,
        *,
        criteria: list[str],
        actor: str = "trusted:final-verifier",
        revision: str | None = None,
    ) -> None:
        """Create scoped human correction tasks or retry automatic QA within existing bounds.

        Args:
            project_id: Approved project whose delivered work needs repair.
            reason: Concrete failed behavior or criterion.
            criteria: Existing approved requirement identifiers.
            actor: Authenticated human or the trusted final verifier.
            revision: Exact rejected delivery identity for a human request.

        Raises:
            StateError: Scope, human identity, revision or project phase is invalid.
        """
        if not reason.strip():
            raise StateError("correction requires concrete feedback")
        blueprint = self.blueprint(project_id)
        known = {item.id for item in blueprint.requirements}
        if not criteria or not set(criteria) <= known:
            raise StateError("correction criteria must reference approved requirements")
        selected = {
            task.id for task in blueprint.tasks if set(task.requirement_ids) & set(criteria)
        }
        changed = True
        while changed:
            prior = set(selected)
            selected.update(
                task.id for task in blueprint.tasks if set(task.dependencies) & selected
            )
            changed = prior != selected
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if row is None or row["state"] not in (
                ProjectState.FINAL_QA,
                ProjectState.AWAITING_ACCEPTANCE,
            ):
                raise StateError("correction requires final QA or current human delivery")
            human = actor.startswith("human:")
            if row["state"] == ProjectState.AWAITING_ACCEPTANCE and not human:
                raise StateError("delivered revision requires human correction authorization")
            if human and row["delivery_digest"] != revision:
                raise StateError("correction revision/state mismatch")
            connection.execute(
                "UPDATE projects SET state=?,delivery_digest=NULL,error=?,updated=? WHERE id=?",
                (
                    ProjectState.PAUSED if human else ProjectState.RUNNING,
                    reason,
                    time.time(),
                    project_id,
                ),
            )
            latest = {task.id: task.id for task in blueprint.tasks}
            for link in connection.execute(
                "SELECT t.task_id,t.parent_task FROM correction_tasks t "
                "JOIN corrections c ON c.id=t.correction_id "
                "WHERE t.project_id=? ORDER BY c.created,t.rowid",
                (project_id,),
            ):
                latest[link["parent_task"]] = link["task_id"]
            correction_id = None
            if human:
                correction_id = uuid.uuid4().hex
                connection.execute(
                    "INSERT INTO corrections VALUES(?,?,?,?,?,?,?)",
                    (
                        correction_id,
                        project_id,
                        revision,
                        actor,
                        json.dumps(criteria),
                        reason,
                        time.time(),
                    ),
                )
                children = {parent: "COR" + uuid.uuid4().hex for parent in selected}
                for original in blueprint.tasks:
                    if original.id not in selected:
                        continue
                    child = original.model_copy(
                        update={
                            "id": children[original.id],
                            "description": original.description[:10000]
                            + "\nHuman correction: "
                            + reason[:9000],
                            "dependencies": [
                                children.get(dep, latest[dep]) for dep in original.dependencies
                            ],
                        }
                    )
                    connection.execute(
                        "INSERT INTO tasks(project_id,id,spec,state,error) VALUES(?,?,?,?,?)",
                        (
                            project_id,
                            child.id,
                            child.model_dump_json(),
                            TaskState.REPAIR_REQUIRED,
                            reason,
                        ),
                    )
                for parent, child_id in children.items():
                    connection.execute(
                        "INSERT INTO correction_tasks VALUES(?,?,?,?)",
                        (correction_id, project_id, child_id, parent),
                    )
                affected = list(children.values())
            else:
                affected = [latest[parent] for parent in selected]
                for task in affected:
                    connection.execute(
                        "UPDATE tasks SET state=?,source_digest=NULL,error=? "
                        "WHERE project_id=? AND id=?",
                        (TaskState.REPAIR_REQUIRED, reason, project_id, task),
                    )
            self._event(
                connection,
                project_id,
                "delivery.corrections_requested",
                {
                    "actor": actor,
                    "criteria": criteria,
                    "tasks": sorted(affected),
                    "correction": correction_id,
                    "revision": row["delivery_digest"] or row["source_digest"],
                    "reason": reason,
                },
            )

    def control(self, project_id: str, action: str, actor: str) -> None:
        """Pause, resume or cancel through an authenticated human control channel.

        Args:
            project_id: Project identity in the selected protected controller state.
            action: Explicit operator control action such as pause or cancel.
            actor: Authenticated human identity supplied by the administrative channel.
        """
        if not actor.startswith("human:"):
            raise StateError("control requires human authorization")
        if action == "resume":
            self.start(project_id)
            return
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            project = connection.execute(
                "SELECT state FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            if project is None or project[0] in (ProjectState.ACCEPTED, ProjectState.CANCELLED):
                raise StateError("project is not controllable")
            if action == "pause":
                if project[0] in (ProjectState.DISCOVERY, ProjectState.AWAITING_APPROVAL):
                    raise StateError("planning/unapproved projects cannot be paused as execution")
                running = connection.execute(
                    "SELECT COUNT(*) FROM tasks WHERE project_id=? AND owner IS NOT NULL",
                    (project_id,),
                ).fetchone()[0]
                target = ProjectState.PAUSING if running else ProjectState.PAUSED
            elif action == "cancel":
                target = ProjectState.CANCELLED
                connection.execute(
                    "UPDATE attempts SET state='CANCELLED',finished=? "
                    "WHERE project_id=? AND state='RUNNING'",
                    (time.time(), project_id),
                )
                connection.execute(
                    "UPDATE tasks SET state=?,fence=fence+1,owner=NULL,lease_until=NULL "
                    "WHERE project_id=? AND state!=?",
                    (TaskState.CANCELLED, project_id, TaskState.INTEGRATED),
                )
            else:
                raise StateError("unknown control action")
            connection.execute(
                "UPDATE projects SET state=?,updated=? WHERE id=?",
                (target, time.time(), project_id),
            )
            self._event(connection, project_id, f"project.{action}", {"actor": actor})

    def expire_draining(self, project: str) -> None:
        """Quiesce abandoned ownership when a paused project cannot dispatch replacements.

        Args:
            project: Project identity in the selected protected controller state.
        """
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = connection.execute(
                "SELECT state FROM projects WHERE id=?", (project,)
            ).fetchone()
            if state is None or state[0] != ProjectState.PAUSING:
                return
            rows = connection.execute(
                "SELECT * FROM tasks WHERE project_id=? AND owner IS NOT NULL AND lease_until<=?",
                (project, time.time()),
            ).fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE tasks SET state='REPAIR_REQUIRED',owner=NULL,lease_until=NULL,"
                    "fence=fence+1 WHERE project_id=? AND id=?",
                    (project, row["id"]),
                )
                connection.execute(
                    "UPDATE attempts SET state='ABANDONED',finished=? WHERE id=?",
                    (time.time(), row["attempt_id"]),
                )
                self._event(
                    connection,
                    project,
                    "task.drain_abandoned",
                    {"task": row["id"], "attempt": row["attempt_id"]},
                )

    def block(self, project_id: str, reason: str) -> None:
        """Preserve work and record a diagnostic blocker without fabricating success.

        Args:
            project_id: Project identity in the selected protected controller state.
            reason: Concrete diagnostic or feedback preserved with its original criteria.
        """
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE projects SET state=?,error=?,updated=? WHERE id=? "
                "AND state NOT IN ('ACCEPTED','CANCELLED','PAUSED')",
                (ProjectState.BLOCKED, reason, time.time(), project_id),
            )
            self._event(connection, project_id, "project.blocked", {"reason": reason})

    def backup(self, destination: Path) -> None:
        """Create a consistent backup using SQLite's backup API, including committed WAL state.

        Args:
            destination: New destination; existing data is never overwritten.
        """
        if destination.exists():
            raise StateError("backup destination must be new")
        with self.connection() as connection, sqlite3.connect(destination) as backup:
            connection.backup(backup)
        os.chmod(destination, 0o600)


def _paths_overlap(left: list[str], right: list[str]) -> bool:
    def prefix(pattern: str) -> str:
        return pattern.split("*", 1)[0].split("?", 1)[0].split("[", 1)[0]

    return any(
        prefix(a).startswith(prefix(b)) or prefix(b).startswith(prefix(a))
        for a in left
        for b in right
    )
