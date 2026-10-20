"""Durable bounded attempts, independent reviews and trusted integration gates."""

from __future__ import annotations

import fcntl
import fnmatch
import json
import os
import shutil
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from darkfactory.adapters import Adapter, AgentReply, InferenceSession, NativeAdapter
from darkfactory.context import build_context, context_inputs
from darkfactory.domain import Blueprint, Mode, ProjectState, Role, TaskSpec, TaskState
from darkfactory.execution import BoundaryError, DockerExecutor, Snapshot, SnapshotStore
from darkfactory.gitops import Repository
from darkfactory.policy import quality_decision
from darkfactory.resources import Resources, StorageQuota
from darkfactory.storage import Record, StateError, Store
from darkfactory.verification import Verifier, redact

AdapterFactory = Callable[[str, str, Blueprint, Role], Adapter]


class HumanInputRequired(StateError):
    """A material decision stops the affected task until the operator resolves its scope."""


def apply_reply(workspace: Path, reply: AgentReply, task: TaskSpec) -> None:
    """Apply only validated in-scope regular file proposals, refusing control files and links.

    Args:
        workspace: Isolated task source directory, separate from controller state.
        reply: Untrusted proposal; it cannot certify checks or grant authority.
        task: Approved task definition or task identity, as declared by the parameter type.
    """
    for edit in reply.files:
        relative = PurePosixPath(edit.path)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or relative.parts[0] in (".git", ".factory", ".darkfactory")
            or any(part.startswith(".env") for part in relative.parts)
        ):
            raise BoundaryError("unsafe proposed file path")
        if not any(fnmatch.fnmatchcase(edit.path, pattern) for pattern in task.permitted_paths):
            raise BoundaryError("proposed edit exceeds assigned component ownership")
        destination = workspace / relative
        if any(path.is_symlink() for path in (destination, *destination.parents)):
            raise BoundaryError("symlink edit rejected")
        if edit.content is None:
            if destination.is_file():
                destination.unlink()
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(edit.content)


class Engine:
    """Schedule real effects through protected services; models supply proposals only."""

    def __init__(
        self,
        store: Store,
        adapter_factory: AdapterFactory | None = None,
        *,
        lease_seconds: int = 60,
        foreground: bool = False,
    ) -> None:
        """Bind shared storage and optionally inject an explicitly labeled test fixture adapter.

        Args:
            store: Protected transactional state, never exposed to task containers.
            adapter_factory: Optional explicit offline fixture; ordinary operation uses native
                adapters.
            lease_seconds: Ownership expiry bound for heartbeat and stale-worker fencing.
            foreground: Explicit operator-attached execution; unattended scheduling stays
                Strict-only.
        """
        self.store = store
        self.snapshots = SnapshotStore(store.root / "snapshots")
        self.verifier = Verifier(store)
        self.adapter_factory = adapter_factory
        self.lease_seconds = lease_seconds
        self.foreground = foreground

    def admit(self, project_id: str) -> Record:
        """Check actual toolchain/adapter availability and refuse unsupported unattended modes.

        Args:
            project_id: Project identity in the selected protected controller state.

        Returns:
            Observed toolchain, image and adapter capabilities for this approved configuration.
        """
        blueprint = self.store.blueprint(project_id)
        if blueprint.limits.require_filesystem_quota:
            from darkfactory.volumes import inspect_volume

            inspect_volume(self.store.root, blueprint.limits.state_storage_mb * 1024 * 1024)
        if blueprint.mode != Mode.STRICT and not self.foreground:
            raise StateError(
                "background scheduling requires Strict; use other modes for diagnostics"
            )
        if blueprint.mode == Mode.STRICT and not {Role.REVIEW, Role.SECURITY, Role.TEST} <= set(
            self.store.policy(project_id).required_review_roles
        ):
            raise StateError("Strict requires independent code, security and test reviews")
        protected = {
            requirement
            for check in blueprint.checks
            if check.required and check.kind == "test" and check.driver and check.expected_output
            for requirement in (
                check.requirement_ids or [item.id for item in blueprint.requirements]
            )
        }
        if blueprint.mode == Mode.STRICT and protected != {
            item.id for item in blueprint.requirements
        }:
            raise StateError(
                "Strict requires protected acceptance verification for every requirement"
            )
        if not blueprint.permissions.local_commits or not blueprint.permissions.local_integration:
            raise StateError(
                "this managed runtime requires approved local commit/integration permissions"
            )
        if blueprint.permissions.approved_network_hosts:
            raise StateError(
                "target egress grants are unsupported; provision dependencies in images"
            )
        target = DockerExecutor(blueprint.image)
        with self.quota(project_id).allocate(0):
            pass
        probe = self.store.root / "projects" / project_id / "probe"
        probe.mkdir(parents=True, exist_ok=True)
        tools = []
        for check in blueprint.checks:
            if check.toolchain_probe:
                result = target.run(probe, check.toolchain_probe, blueprint.limits, readonly=True)
                if result.exit_code or result.timed_out or result.output_truncated:
                    raise StateError("required toolchain probe failed: " + check.id)
                tools.append(
                    {
                        "check": check.id,
                        "argv": check.toolchain_probe,
                        "version": redact(result.stdout + result.stderr).strip(),
                    }
                )
        if self.adapter_factory is not None:
            return self._environment(
                project_id,
                {
                    "target_image": target.image_id,
                    "tools": tools,
                    "adapter": "test-fixture",
                    "live": False,
                },
            )
        probe = self.store.root / "projects" / project_id / "probe"
        probe.mkdir(exist_ok=True)
        bindings: dict[str, Record] = {}
        probes: dict[tuple[str, str], bool] = {}
        for role in Role:
            configuration = blueprint.agent_configuration(role)
            if configuration is None:
                raise StateError("Strict requires an approved native configuration for " + role)
            spec, adapter = configuration.inference, configuration.adapter
            if blueprint.limits.max_cost_microusd is not None and (
                spec.input_microusd_per_token is None or spec.output_microusd_per_token is None
            ):
                raise StateError("monetary limits require conservative pricing for every role")
            credential = self.store.root / "credentials" / spec.provider
            if (
                not credential.is_file()
                or credential.is_symlink()
                or credential.stat().st_mode & 0o077
                or credential.stat().st_uid != os.getuid()
            ):
                raise StateError("operator-owned provider access must be enrolled privately")
            agent = DockerExecutor(spec.agent_image)
            gateway = DockerExecutor(spec.gateway_image)
            key = (adapter, agent.image_id)
            if key not in probes:
                result = agent.run(probe, [adapter, "--help"], blueprint.limits, readonly=True)
                required = (
                    ["--bare", "--json-schema", "--tools"]
                    if adapter == "claude"
                    else ["--sandbox", "--ask-for-approval"]
                )
                if result.exit_code or any(flag not in result.stdout for flag in required):
                    raise StateError("native CLI capability probe failed; no Strict downgrade")
                probes[key] = True
            bindings[role] = {
                "agent_image": agent.image_id,
                "gateway_image": gateway.image_id,
                "adapter": adapter,
                "model": spec.model,
                "provider": spec.provider,
            }
        return self._environment(
            project_id,
            {
                "target_image": target.image_id,
                "tools": tools,
                "roles": bindings,
                "protocol": "live conformance pending until actual run",
                "live": True,
            },
        )

    def _environment(self, project: str, current: Record) -> Record:
        previous = self.store.environment(project)
        if previous is not None and previous != current:
            raise StateError("admitted environment changed; new blueprint approval required")
        return current

    def quota(self, project: str) -> StorageQuota:
        """Apply the approved conservative bound to the complete shared state directory.

        Args:
            project: Project identity in the selected protected controller state.

        Returns:
            Serialized allocation guard for the approved project allowance.
        """
        return StorageQuota(
            self.store.root, self.store.blueprint(project).limits.state_storage_mb * 1024 * 1024
        )

    def reserve(self, project_id: str, attempt_id: str, tokens: int) -> str:
        """Reserve capacity transactionally so concurrent workers cannot oversubscribe limits.

        Args:
            project_id: Project identity in the selected protected controller state.
            attempt_id: Unique persisted attempt identity for attribution and ownership.
            tokens: Capacity reserved before dispatch, distinct from observed provider usage.

        Returns:
            Persisted reservation identity that prevents concurrent oversubscription.
        """
        limits = self.store.blueprint(project_id).limits
        blueprint = self.store.blueprint(project_id)
        configurations = [blueprint.agent_configuration(role) for role in Role]
        rate = max(
            (
                max(
                    item.inference.input_microusd_per_token or 0,
                    item.inference.output_microusd_per_token or 0,
                )
                for item in configurations
                if item is not None
            ),
            default=0,
        )
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            consumed = connection.execute(
                "SELECT COALESCE(SUM(tokens+reserved),0),COALESCE(SUM(cost_microusd),0) "
                "FROM usage WHERE project_id=?",
                (project_id,),
            ).fetchone()
            if consumed[0] + tokens > limits.max_tokens:
                raise StateError("token budget exhausted; increase requires renewed approval")
            worst_cost = tokens * rate
            if limits.max_cost_microusd is not None:
                reservations = connection.execute(
                    "SELECT COALESCE(SUM(reserved),0) FROM usage WHERE project_id=?",
                    (project_id,),
                ).fetchone()[0]
                if consumed[1] + reservations * rate + worst_cost > limits.max_cost_microusd:
                    raise StateError("monetary budget exhausted")
            usage_id = uuid.uuid4().hex
            connection.execute(
                "INSERT INTO usage VALUES(?,?,?,?,?,?,?)",
                (usage_id, project_id, attempt_id, 0, tokens, None, time.time()),
            )
            connection.execute(
                "INSERT INTO operations VALUES(?,?,?,?,?,?,?)",
                (
                    usage_id,
                    project_id,
                    "inference-usage",
                    json.dumps({"attempt": attempt_id}),
                    "RESERVED",
                    None,
                    time.time(),
                ),
            )
            self.store._event(
                connection, project_id, "usage.reserved", {"usage": usage_id, "tokens": tokens}
            )
            return usage_id

    def _account(self, project_id: str, usage_id: str, usage: Record) -> None:
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if usage.get("unknown"):
                connection.execute(
                    "UPDATE usage SET tokens=? WHERE id=?", (usage.get("tokens", 0), usage_id)
                )
            else:
                connection.execute(
                    "UPDATE usage SET tokens=?,reserved=0,cost_microusd=? WHERE id=?",
                    (usage.get("tokens", 0), usage.get("cost_microusd"), usage_id),
                )
            self.store._event(
                connection, project_id, "usage.observed", {"usage": usage_id, **usage}
            )
            connection.execute(
                "UPDATE operations SET state=?,outcome=? WHERE id=?",
                ("UNKNOWN" if usage.get("unknown") else "ACCOUNTED", json.dumps(usage), usage_id),
            )
        if usage.get("unknown"):
            self.store.block(
                project_id, "provider usage is unknown; operator reconciliation required"
            )

    def _with_agent(
        self, project: str, attempt: str, role: Role, callback: Callable[[Adapter], AgentReply]
    ) -> AgentReply:
        blueprint = self.store.blueprint(project)
        if self.adapter_factory is not None:
            return callback(self.adapter_factory(project, attempt, blueprint, role))
        configuration = blueprint.agent_configuration(role)
        if configuration is None:
            raise StateError("no approved inference binding for assigned role")
        spec = configuration.inference
        environment = self.store.environment(project)
        if environment and "roles" in environment:
            identities = environment["roles"][role]
            spec = spec.model_copy(
                update={
                    "agent_image": identities["agent_image"],
                    "gateway_image": identities["gateway_image"],
                }
            )
        selected = blueprint.model_copy(
            update={"adapter": configuration.adapter, "inference": spec}
        )
        if self.store.project(project)["state"] not in (
            ProjectState.DISCOVERY,
            ProjectState.RUNNING,
            ProjectState.FINAL_QA,
            ProjectState.PAUSED,
            ProjectState.AWAITING_ACCEPTANCE,
        ):
            raise StateError("inference is blocked by current project control")
        directory = self.store.root / "attempts" / attempt
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "inference.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            reservation = self.reserve(project, attempt, spec.attempt_tokens)
            session = InferenceSession(self.store, project, attempt, spec)
            try:
                session.start()
                return callback(NativeAdapter(selected, session))
            finally:
                try:
                    session.close()
                finally:
                    usage = session.usage()
                    usage["unknown"] = bool(usage.get("unknown") or usage.get("reserved"))
                    self._account(project, reservation, usage)
                    if usage["unknown"]:
                        raise StateError(
                            "provider usage is unknown; operator reconciliation required"
                        )
                    if usage.get("requests", 0) < 1 or usage.get("tokens", 0) < 1:
                        raise StateError("native adapter produced no observed provider inference")

    def reconcile_usage(self, project: str) -> None:
        """Recover abandoned inference charges from protected ledgers or retain an unknown bound.

        Args:
            project: Project identity in the selected protected controller state.
        """
        with self.store.connection() as connection:
            pending = connection.execute(
                "SELECT u.* FROM usage u JOIN operations o ON o.id=u.id "
                "WHERE u.project_id=? AND o.kind='inference-usage' AND o.state='RESERVED'",
                (project,),
            ).fetchall()
        for row in pending:
            directory = self.store.root / "attempts" / row["attempt_id"]
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / "inference.lock").open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                ledger = directory / "gateway" / "ledger" / "usage.json"
                observed = (
                    json.loads(ledger.read_text())
                    if ledger.is_file()
                    else {"tokens": row["tokens"], "unknown": True}
                )
                observed["unknown"] = bool(observed.get("unknown") or observed.get("reserved"))
                self._account(project, row["id"], observed)

    def _context(
        self,
        project: str,
        task: TaskSpec,
        source: Path,
        diagnosis: str = "",
        role: Role | None = None,
    ) -> str:
        return build_context(
            self.store, project, task, source, diagnosis, self.open_findings(project, task.id), role
        )

    def open_findings(self, project: str, task: str | None = None) -> list[Record]:
        """Retrieve unresolved judgments for rehydration and independent re-verification.

        Args:
            project: Project identity in the selected protected controller state.
            task: Approved task definition or task identity, as declared by the parameter type.

        Returns:
            Unresolved findings with original source and reviewer attribution.
        """
        with self.store.connection() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT f.*,r.role FROM findings f JOIN reviews r ON r.id=f.review_id "
                    "WHERE f.project_id=? AND f.resolved_by IS NULL "
                    "AND (? IS NULL OR f.task_id=? OR f.task_id IS NULL)",
                    (project, task, task),
                )
            ]

    def _protected(self, project: str, base: Snapshot, candidate: Snapshot) -> None:
        patterns = self.store.policy(project).protect_test_paths
        previous = {str(entry["path"]): entry for entry in self.snapshots.manifest(base.path)}
        current = {str(entry["path"]): entry for entry in self.snapshots.manifest(candidate.path)}
        for path, entry in previous.items():
            if any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns):
                if current.get(path) != entry:
                    raise StateError("protected baseline test/runner changed: " + path)

    def review(
        self,
        project: str,
        task: TaskSpec,
        snapshot: Snapshot,
        implementation: str,
        *,
        final: bool = False,
    ) -> bool:
        """Assign separate read-only reviewer sessions and persist blocking judgments.

        Args:
            project: Project identity in the selected protected controller state.
            task: Approved task definition or task identity, as declared by the parameter type.
            snapshot: Immutable source identity and its controller-owned files.
            implementation: Implementation attempt identity that cannot certify its own independent
                review.
            final: Require complete application QA and acceptance scope from fresh reviewers.

        Returns:
            Whether independent review and current findings permit advancement.
        """
        passed = True
        roles = list(
            dict.fromkeys(
                [
                    *self.store.policy(project).required_review_roles,
                    *(
                        Role(row["role"])
                        for row in self.open_findings(project, task.id)
                        if row["task_id"] is None and row["severity"] == "blocking"
                    ),
                ]
            )
        )
        if final:
            roles = list(dict.fromkeys([*roles, Role.QA, Role.ACCEPTANCE]))
        for role in roles:
            attempt = uuid.uuid4().hex
            assert attempt != implementation
            workspace = self.store.root / "attempts" / attempt / "review-source"
            self.snapshots.materialize(snapshot, workspace, quota=self.quota(project))
            context = self._context(project, task, workspace, role=role)
            context += "\nIndependent review role: " + role.value
            with self.store.connection() as connection:
                unresolved = [
                    dict(row)
                    for row in connection.execute(
                        "SELECT f.* FROM findings f JOIN reviews r ON r.id=f.review_id "
                        "WHERE f.project_id=? "
                        "AND (? OR f.task_id=? OR f.task_id IS NULL) "
                        "AND f.resolved_by IS NULL AND r.role=?",
                        (project, final, task.id, role),
                    )
                ]
            preview: list[Record] = []
            for prior_finding in unresolved:
                if len(json.dumps([*preview, prior_finding]).encode()) > 8000:
                    break
                preview.append(prior_finding)
            context += "\nPrior findings requiring explicit re-verification: " + json.dumps(preview)

            def propose_review(
                adapter: Adapter, context: str = context, workspace: Path = workspace
            ) -> AgentReply:
                limits = self.store.blueprint(project).limits
                image = (self.store.environment(project) or {}).get(
                    "target_image", self.store.blueprint(project).image
                )
                executor = DockerExecutor(image, Resources(self.store, project))
                observations = ""
                for _ in range(10):
                    reply = adapter.propose(context + observations, workspace, limits)
                    if reply.files or reply.questions or reply.proposed_blueprint:
                        raise StateError("review cannot edit source or change approved scope")
                    if reply.commands:
                        results = [
                            executor.run(
                                workspace,
                                argv,
                                limits,
                                readonly=True,
                                trusted_files=context_inputs(self.store, project, workspace),
                            ).model_dump(mode="json")
                            for argv in reply.commands
                        ]
                        observations = (
                            "\nRead-only observations: " + redact(json.dumps(results))[:8000]
                        )
                    if reply.status == "complete":
                        return reply
                    if reply.status == "blocked":
                        raise StateError("review blocked: " + reply.summary)
                raise StateError("review inspection round limit exhausted")

            reply = self._with_agent(
                project,
                attempt,
                role,
                propose_review,
            )
            if reply.files or not reply.examined or reply.status != "complete":
                raise StateError("review must be read-only with declared examined scope")
            if final and role in (Role.QA, Role.ACCEPTANCE):
                required = {item.id for item in self.store.blueprint(project).requirements}
                if not required <= set(reply.examined) or reply.unexamined:
                    raise StateError("final QA/acceptance has unexamined mandatory scope")
            blocking = any(finding.severity == "blocking" for finding in reply.findings)
            allowed_findings = {row["id"]: row for row in unresolved}
            if any(finding not in allowed_findings for finding in reply.resolved_findings):
                raise StateError("review attempted to resolve another role's findings")
            passed = passed and not blocking
            review_id = uuid.uuid4().hex
            with (
                self.quota(project).allocate(len(reply.model_dump_json().encode()) * 3 + 65536),
                self.store.connection() as connection,
            ):
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        review_id,
                        project,
                        None if final else task.id,
                        snapshot.digest,
                        role,
                        attempt,
                        "BLOCK" if blocking else "APPROVE",
                        reply.model_dump_json(),
                        time.time(),
                    ),
                )
                for finding in reply.findings:
                    connection.execute(
                        "INSERT INTO findings VALUES(?,?,?,?,?,?,?,?,?)",
                        (
                            uuid.uuid4().hex,
                            project,
                            review_id,
                            None if final else task.id,
                            snapshot.digest,
                            finding.severity,
                            finding.model_dump_json(),
                            None,
                            None,
                        ),
                    )
                gate_task = (
                    None if final or any(row["task_id"] is None for row in unresolved) else task.id
                )
                if self.verifier.gate(project, snapshot.digest, task_id=gate_task).allowed:
                    for finding_id in reply.resolved_findings:
                        if allowed_findings[finding_id]["source_digest"] == snapshot.digest:
                            raise StateError(
                                "unchanged source cannot mechanically resolve a finding"
                            )
                        connection.execute(
                            "UPDATE findings SET resolved_by=?,resolution=? WHERE id=?",
                            (
                                review_id,
                                "Renewed independent review and protected checks: "
                                + snapshot.digest,
                                finding_id,
                            ),
                        )
                self.store._event(
                    connection,
                    project,
                    "review.finished",
                    {
                        "review": review_id,
                        "role": role,
                        "source": snapshot.digest,
                        "blocking": blocking,
                        "attempt": attempt,
                    },
                )
        return passed and not self.store.blocking_findings(
            project, snapshot.digest, None if final else task.id
        )

    def run_one(self, project: str, owner: str) -> bool:
        """Claim, verify and independently review a task before integrating its actual merge.

        Args:
            project: Project identity in the selected protected controller state.
            owner: Unique worker ownership identity for the current scheduling session.

        Returns:
            True if a task was attempted, False when no eligible task was claimed.
        """
        if not self.store.current_approval(project) or not self.store.verify_audit():
            raise StateError("approved blueprint/policy/audit integrity failure")
        if self.store.blueprint(project).mode != Mode.STRICT and not self.foreground:
            raise StateError("non-Strict execution requires an explicit foreground operator run")
        Repository(self.store, project).reconcile()
        self.store.expire_draining(project)
        assignment = self.store.claim(project, owner, lease_seconds=self.lease_seconds)
        if assignment is None:
            self.settle(project)
            return False
        stopped = threading.Event()
        stale = threading.Event()

        def heartbeat() -> None:
            while not stopped.wait(min(10, self.lease_seconds / 3)):
                try:
                    self.store.heartbeat(
                        project,
                        assignment["task_id"],
                        assignment["fence"],
                        lease_seconds=self.lease_seconds,
                    )
                except StateError:
                    stale.set()
                    return

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        task = TaskSpec.model_validate(assignment["spec"])
        repository = Repository(self.store, project)
        candidate: Snapshot | None = None
        try:
            base_commit = repository.head()
            base = repository.capture_commit(base_commit)
            current_task = next(row for row in self.store.tasks(project) if row["id"] == task.id)
            resumed = current_task["source_digest"]
            workspace = self.store.root / "attempts" / assignment["attempt_id"] / "workspace"
            self.snapshots.materialize(base, workspace, quota=self.quota(project))
            if resumed:
                checkpoint = Snapshot(resumed, self.store.root / "snapshots" / resumed / "source")
                if not self.snapshots.verify(checkpoint):
                    raise StateError("checkpoint integrity failure")
                before = {str(item["path"]): item for item in self.snapshots.manifest(base.path)}
                saved = {
                    str(item["path"]): item for item in self.snapshots.manifest(checkpoint.path)
                }
                for path in before.keys() | saved.keys():
                    if any(fnmatch.fnmatchcase(path, pattern) for pattern in task.permitted_paths):
                        if before.get(path) != saved.get(path):
                            destination = workspace / path
                            if path in saved:
                                with self.quota(project).allocate(saved[path]["size"]):
                                    destination.parent.mkdir(parents=True, exist_ok=True)
                                    shutil.copyfile(checkpoint.path / path, destination)
                                    destination.chmod(0o755 if saved[path]["executable"] else 0o644)
                            elif destination.is_file():
                                destination.unlink()
            executor = DockerExecutor(
                (self.store.environment(project) or {}).get(
                    "target_image", self.store.blueprint(project).image
                ),
                Resources(self.store, project),
            )
            diagnosis = next(
                (row["error"] or "" for row in self.store.tasks(project) if row["id"] == task.id),
                "",
            )

            def implement(adapter: Adapter) -> AgentReply:
                nonlocal diagnosis, candidate
                for _ in range(10):
                    if stale.is_set():
                        raise StateError("stale worker fenced during execution")
                    reply = adapter.propose(
                        self._context(project, task, workspace, diagnosis),
                        workspace,
                        self.store.blueprint(project).limits,
                    )
                    if reply.questions or reply.proposed_blueprint is not None:
                        raise HumanInputRequired(
                            "material decision needs human input: " + "; ".join(reply.questions)
                        )
                    size = sum(
                        len(edit.content.encode())
                        for edit in reply.files
                        if edit.content is not None
                    )
                    with self.quota(project).allocate(size):
                        apply_reply(workspace, reply, task)
                    candidate = self.snapshots.capture(workspace, quota=self.quota(project))
                    self._protected(project, base, candidate)
                    self.store.checkpoint(assignment, candidate.digest)
                    outputs = []
                    for argv in reply.commands:
                        result = executor.run(
                            workspace,
                            argv,
                            self.store.blueprint(project).limits,
                            readonly=True,
                            trusted_files=context_inputs(self.store, project, workspace),
                        )
                        outputs.append(result.model_dump(mode="json"))
                    diagnosis = json.dumps(outputs)
                    if reply.status == "blocked":
                        raise StateError(reply.summary)
                    if reply.status == "complete":
                        return reply
                raise StateError("proposal round limit exhausted")

            self._with_agent(project, assignment["attempt_id"], task.role, implement)
            candidate = self.snapshots.capture(workspace, quota=self.quota(project))
            before = {str(entry["path"]): entry for entry in self.snapshots.manifest(base.path)}
            after = {str(entry["path"]): entry for entry in self.snapshots.manifest(candidate.path)}
            for path in before.keys() | after.keys():
                if before.get(path) != after.get(path) and not any(
                    fnmatch.fnmatchcase(path, pattern) for pattern in task.permitted_paths
                ):
                    raise BoundaryError("command changed an unowned component: " + path)
            self._protected(project, base, candidate)
            self.store.stage(assignment, TaskState.VERIFYING)
            verification_task = (
                None
                if any(row["task_id"] is None for row in self.open_findings(project, task.id))
                else task.id
            )
            checked = self.verifier.run(
                project, candidate, task_id=verification_task, attempt_id=assignment["attempt_id"]
            )
            if not quality_decision(checked, self.store.blueprint(project).mode).allowed:
                raise StateError("; ".join(checked.reasons))
            self.store.stage(assignment, TaskState.IN_REVIEW)
            reviewed = self.review(project, task, candidate, assignment["attempt_id"])
            if not reviewed and self.store.blueprint(project).mode != Mode.ADVISORY:
                raise StateError("independent review has blocking findings")
            self.store.stage(assignment, TaskState.READY_TO_INTEGRATE)
            commit = repository.candidate(base_commit, candidate)
            with repository.lock():
                parent, merged_commit, merged = repository.merged(commit)
                self.store.stage(assignment, TaskState.VERIFYING)
                checked = self.verifier.run(
                    project, merged, task_id=task.id, attempt_id=assignment["attempt_id"]
                )
                if not quality_decision(checked, self.store.blueprint(project).mode).allowed:
                    raise StateError("merged candidate failed: " + "; ".join(checked.reasons))
                self.store.stage(assignment, TaskState.IN_REVIEW)
                if merged.digest != candidate.digest:
                    reviewed = self.review(project, task, merged, assignment["attempt_id"])
                    if not reviewed and self.store.blueprint(project).mode != Mode.ADVISORY:
                        raise StateError("merged candidate has blocking review findings")
                self.store.stage(assignment, TaskState.READY_TO_INTEGRATE)
                repository.publish(assignment, parent, merged_commit, merged)
        except (StateError, BoundaryError, ValueError, OSError) as error:
            try:
                self.store.finish_attempt(
                    assignment,
                    TaskState.BLOCKED
                    if isinstance(error, HumanInputRequired)
                    else TaskState.REPAIR_REQUIRED,
                    source_digest=candidate.digest if candidate else None,
                    error=redact(str(error)),
                )
            except StateError:
                pass
        finally:
            stopped.set()
            thread.join(timeout=2)
        self.settle(project)
        return True

    def settle(self, project: str) -> None:
        """Serialize final verification and reconcile its state after worker interruption.

        Args:
            project: Project identity in the selected protected controller state.
        """
        with Repository(self.store, project).lock():
            self._settle(project)

    def _settle(self, project: str) -> None:
        """Derive paused/blocked/delivery eligibility from actual task and evidence records."""
        tasks = self.store.tasks(project)
        current = self.store.project(project)
        if current["state"] == ProjectState.PAUSING and not any(row["owner"] for row in tasks):
            self._state(project, ProjectState.PAUSED)
        elif current["state"] in (ProjectState.RUNNING, ProjectState.FINAL_QA):
            if all(row["state"] == TaskState.INTEGRATED for row in tasks):
                if current["state"] == ProjectState.RUNNING:
                    self._state(project, ProjectState.FINAL_QA)
                snapshot = Repository(self.store, project).current()
                decision = self.verifier.run(project, snapshot)
                documentation = self.verifier.delivery_gate(project, snapshot.digest)
                if not documentation.allowed:
                    decision = decision.model_copy(
                        update={
                            "allowed": False,
                            "reasons": [*decision.reasons, *documentation.reasons],
                        }
                    )
                task = (
                    self.store.blueprint(project)
                    .tasks[0]
                    .model_copy(
                        update={
                            "description": (
                                "Review all approved requirements, runtime QA and delivery evidence"
                            ),
                            "requirement_ids": [
                                item.id for item in self.store.blueprint(project).requirements
                            ],
                            "check_ids": [],
                        }
                    )
                )
                reviewed = decision.allowed and self.review(
                    project, task, snapshot, "final-verifier", final=True
                )
                unresolved = self.store.blocking_findings(project, snapshot.digest)
                if decision.allowed and reviewed and not unresolved:
                    self._state(project, ProjectState.AWAITING_ACCEPTANCE, snapshot.digest)
                else:
                    findings = [
                        row for row in self.open_findings(project) if row["severity"] == "blocking"
                    ]
                    reason = "final verification/findings: " + "; ".join(decision.reasons)
                    if findings:
                        reason += "\n" + json.dumps(findings)
                    self.store.request_repairs(
                        project,
                        reason,
                        criteria=[item.id for item in self.store.blueprint(project).requirements],
                    )
            elif any(row["state"] == TaskState.BLOCKED for row in tasks) and not any(
                row["owner"] for row in tasks
            ):
                integrated = {row["id"] for row in tasks if row["state"] == TaskState.INTEGRATED}
                attempt_limit = self.store.blueprint(project).limits.max_attempts
                eligible = any(
                    row["state"] in (TaskState.PENDING, TaskState.REPAIR_REQUIRED)
                    and row["attempts"] < attempt_limit
                    and set(TaskSpec.model_validate_json(row["spec"]).dependencies) <= integrated
                    for row in tasks
                )
                if not eligible:
                    self.store.block(project, "tasks blocked; independent work preserved")

    def _state(self, project: str, state: ProjectState, delivery: str | None = None) -> None:
        expected = {
            ProjectState.FINAL_QA: ProjectState.RUNNING,
            ProjectState.AWAITING_ACCEPTANCE: ProjectState.FINAL_QA,
            ProjectState.PAUSED: ProjectState.PAUSING,
        }[state]
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                "UPDATE projects SET state=?,delivery_digest=?,updated=? WHERE id=? AND state=?",
                (state, delivery, time.time(), project, expected),
            ).rowcount
            if changed != 1:
                raise StateError("project control changed during finalization")
            self.store._event(
                connection, project, "project.transition", {"state": state, "delivery": delivery}
            )
