"""Shared authenticated operator actions, evidence reports and delivery exports."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from darkfactory.adapters import NativeAdapter
from darkfactory.domain import Blueprint, Policy, ProjectState, Role, TaskState
from darkfactory.engine import Engine
from darkfactory.execution import Snapshot, SnapshotStore
from darkfactory.gitops import Repository
from darkfactory.resources import Resources, StorageQuota
from darkfactory.storage import Record, StateError, Store
from darkfactory.verification import Verifier, redact


class Factory:
    """Provide the same policy decisions to CLI, HTTP and dashboard callers."""

    def __init__(self, store: Store, engine: Engine | None = None) -> None:
        """Compose services without starting workers or granting execution permissions.

        Args:
            store: Protected transactional state, never exposed to task containers.
            engine: Optional shared execution service; offline fixture engines must be labeled.
        """
        self.store = store
        self.engine = engine or Engine(store)

    def propose(self, blueprint: Blueprint, policy: Policy, source: Path) -> str:
        """Capture an initial source and validated proposal without creating Git effects.

        Args:
            blueprint: Project contract whose exact identity requires separate human approval.
            policy: Versioned quality/execution rules bound into the approval identity.
            source: Real source directory inspected through the validated snapshot boundary.

        Returns:
            Unapproved project identity with its captured source snapshot.
        """
        if (
            source.resolve() == self.store.root
            or self.store.root.is_relative_to(source.resolve())
            or source.resolve().is_relative_to(self.store.root)
        ):
            raise StateError("target source and protected controller state must be separate")
        quota = StorageQuota(self.store.root, blueprint.limits.state_storage_mb * 1024 * 1024)
        snapshot = SnapshotStore(self.store.root / "snapshots").capture(source, quota=quota)
        return self._propose_snapshot(blueprint, policy, snapshot)

    def _propose_snapshot(
        self,
        blueprint: Blueprint,
        policy: Policy,
        snapshot: Snapshot,
        *,
        project_id: str | None = None,
    ) -> str:
        if not SnapshotStore(self.store.root / "snapshots").verify(snapshot):
            raise StateError("proposal source snapshot integrity failure")
        project = self.store.create_project(blueprint, policy, project_id=project_id)
        initial = self.store.root / "projects" / project / "initial.json"
        initial.parent.mkdir(exist_ok=True)
        if initial.exists() and json.loads(initial.read_text())["source_digest"] != snapshot.digest:
            raise StateError("proposed identity cannot replace its initial source")
        temporary = initial.with_suffix(".pending")
        temporary.write_text(json.dumps({"source_digest": snapshot.digest}))
        temporary.replace(initial)
        return project

    def start(self, project: str) -> Record:
        """Admit current capabilities and initialize approved local effects before scheduling.

        Args:
            project: Project identity in the selected protected controller state.

        Returns:
            Admitted capability record; a separate worker performs the work.
        """
        current = self.store.project(project)
        if current["state"] not in (ProjectState.READY, ProjectState.PAUSED, ProjectState.BLOCKED):
            raise StateError("start requires approved blueprint")
        if not self.store.current_approval(project) or not self.store.verify_audit():
            raise StateError("start requires intact approval, policy and audit identities")
        Resources(self.store, project).reap()
        self.engine.verifier.reconcile(project)
        NativeAdapter.reconcile(self.store, project)
        self.engine.reconcile_usage(project)
        with self.store.connection() as connection:
            if connection.execute(
                "SELECT COUNT(*) FROM operations WHERE project_id=? "
                "AND kind='inference-usage' AND state='UNKNOWN'",
                (project,),
            ).fetchone()[0]:
                raise StateError("unknown inference usage requires operator reconciliation")
        admitted = self.engine.admit(project)
        self.store.record_environment(project, admitted)
        record = json.loads((self.store.root / "projects" / project / "initial.json").read_text())
        snapshot = Snapshot(
            record["source_digest"],
            self.store.root / "snapshots" / record["source_digest"] / "source",
        )
        repository = Repository(self.store, project)
        repository.initialize(snapshot.path)
        repository.reconcile()
        self.store.start(project)
        return admitted

    def revise(self, project: str, blueprint: Blueprint, policy: Policy) -> str:
        """Propose a linked material revision without inheriting the old approval.

        Args:
            project: Project identity in the selected protected controller state.
            blueprint: Project contract whose exact identity requires separate human approval.
            policy: Versioned quality/execution rules bound into the approval identity.

        Returns:
            New unapproved project identity; old artifacts and approval remain preserved.
        """
        current = self.store.project(project)
        if current["state"] in (ProjectState.RUNNING, ProjectState.PAUSING, ProjectState.FINAL_QA):
            raise StateError("pause active work before proposing a material revision")
        if blueprint.version <= self.store.blueprint(project).version:
            raise StateError("blueprint revision must increase")
        if (
            policy != self.store.policy(project)
            and policy.version <= self.store.policy(project).version
        ):
            raise StateError("changed policy version must increase")
        source = current["source_digest"]
        if not source:
            initial = json.loads(
                (self.store.root / "projects" / project / "initial.json").read_text()
            )
            source = initial["source_digest"]
        snapshot = Snapshot(source, self.store.root / "snapshots" / source / "source")
        proposed = self._propose_snapshot(blueprint, policy, snapshot)
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.store._event(
                connection,
                proposed,
                "blueprint.revision_proposed",
                {"previous_project": project, "previous_digest": current["blueprint_hash"]},
            )
        return proposed

    def report(self, project: str) -> Record:
        """Return actual status, criterion evidence, failures, reviews, findings and usage.

        Args:
            project: Project identity in the selected protected controller state.

        Returns:
            Actual states, revisions, checks, findings, corrections, exceptions and accounting.
        """
        current = self.store.project(project)
        blueprint = self.store.blueprint(project)
        checks = Verifier(self.store).records(project)
        with self.store.connection() as connection:
            reviews = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM reviews WHERE project_id=?", (project,)
                )
            ]
            findings = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM findings WHERE project_id=?", (project,)
                )
            ]
            usage = [
                dict(row)
                for row in connection.execute("SELECT * FROM usage WHERE project_id=?", (project,))
            ]
            exceptions = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM finding_exceptions WHERE project_id=? ORDER BY created",
                    (project,),
                )
            ]
            adapter_runs = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM adapter_runs WHERE project_id=? ORDER BY created", (project,)
                )
            ]
            events = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM audit WHERE project_id=? ORDER BY seq", (project,)
                )
            ]
        source = current["delivery_digest"] or current["source_digest"]
        matrix = []
        for requirement in blueprint.requirements:
            specs = [
                spec.id
                for spec in blueprint.checks
                if spec.required
                and (not spec.requirement_ids or requirement.id in spec.requirement_ids)
            ]
            evidence = [
                row["id"]
                for row in checks
                if row["source_digest"] == source and row["passed"] and row["check_id"] in specs
            ]
            matrix.append(
                {
                    "requirement": requirement.model_dump(),
                    "required_checks": specs,
                    "evidence": evidence,
                    "gate": Verifier(self.store).gate(project, source or "").model_dump(),
                }
            )
        return {
            "project": current,
            "blueprint": blueprint.model_dump(mode="json"),
            "tasks": self.store.tasks(project),
            "corrections": self.store.corrections(project),
            "finding_exceptions": exceptions,
            "adapter_runs": adapter_runs,
            "checks": checks,
            "reviews": reviews,
            "findings": findings,
            "usage": usage,
            "environment": self.store.environment(project),
            "events": events,
            "acceptance_matrix": matrix,
            "audit_intact": self.store.verify_audit(),
            "release": "Separate authorization required; no release adapter configured",
        }

    def retry(self, project: str, actor: str) -> None:
        """Retry a diagnostic blocker only within its already approved attempt and usage bounds.

        Args:
            project: Project identity in the selected protected controller state.
            actor: Authenticated human identity supplied by the administrative channel.
        """
        if not actor.startswith("human:") or not self.store.current_approval(project):
            raise StateError("retry requires authenticated human and current approval")
        limits = self.store.blueprint(project).limits
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT state FROM projects WHERE id=?", (project,)
            ).fetchone()
            if current is None or current[0] not in (ProjectState.BLOCKED, ProjectState.PAUSED):
                raise StateError("retry requires a blocked or paused project")
            if connection.execute(
                "SELECT COUNT(*) FROM usage WHERE project_id=? AND reserved>0", (project,)
            ).fetchone()[0]:
                raise StateError("outstanding usage reservations require operator reconciliation")
            blocked = connection.execute(
                "SELECT * FROM tasks WHERE project_id=? AND state='BLOCKED'", (project,)
            ).fetchall()
            if any(row["attempts"] >= limits.max_attempts for row in blocked):
                raise StateError("attempt limit exhausted; a newly approved blueprint is required")
            connection.execute(
                "UPDATE tasks SET state='REPAIR_REQUIRED' WHERE project_id=? AND state='BLOCKED'",
                (project,),
            )
            self.store._event(connection, project, "tasks.retry_authorized", {"actor": actor})
        self.start(project)

    def control(self, project: str, action: str, actor: str) -> None:
        """Apply human pause/cancellation and revoke cancelled execution endpoints.

        Args:
            project: Project identity in the selected protected controller state.
            action: Explicit operator control action such as pause or cancel.
            actor: Authenticated human identity supplied by the administrative channel.
        """
        self.store.control(project, action, actor)
        if action == "cancel":
            Resources(self.store, project).revoke()

    def reconcile_usage(
        self,
        project: str,
        usage: str,
        tokens: int,
        cost_microusd: int | None,
        reference: str,
        actor: str,
    ) -> None:
        """Record human reconciliation of unknown charges without granting new allowances.

        Args:
            project: Project identity in the selected protected controller state.
            usage: Persisted unknown usage reservation requiring explicit reconciliation.
            tokens: Capacity reserved before dispatch, distinct from observed provider usage.
            cost_microusd: Observed monetary charge in exact micro-USD units when required.
            reference: Operator accounting reference explaining the observation.
            actor: Authenticated human identity supplied by the administrative channel.
        """
        if not actor.startswith("human:") or not reference.strip() or tokens < 0:
            raise StateError("usage reconciliation requires authenticated human accounting")
        if cost_microusd is not None and cost_microusd < 0:
            raise StateError("invalid observed monetary charge")
        if (
            self.store.blueprint(project).limits.max_cost_microusd is not None
            and cost_microusd is None
        ):
            raise StateError("a monetary cap requires reconciled monetary usage")
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT u.*,o.state FROM usage u JOIN operations o ON o.id=u.id "
                "WHERE u.id=? AND u.project_id=?",
                (usage, project),
            ).fetchone()
            if row is None or row["state"] != "UNKNOWN" or tokens < row["tokens"]:
                raise StateError(
                    "reconciliation must match unknown usage and preserve observed charges"
                )
            connection.execute(
                "UPDATE usage SET tokens=?,reserved=0,cost_microusd=? WHERE id=?",
                (tokens, cost_microusd, usage),
            )
            connection.execute(
                "UPDATE operations SET state='RECONCILED',outcome=? WHERE id=?",
                (
                    json.dumps(
                        {"tokens": tokens, "cost_microusd": cost_microusd, "reference": reference}
                    ),
                    usage,
                ),
            )
            self.store._event(
                connection,
                project,
                "usage.reconciled",
                {
                    "usage": usage,
                    "actor": actor,
                    "reference": reference,
                    "tokens": tokens,
                    "cost_microusd": cost_microusd,
                },
            )

    def review(self, project: str) -> bool:
        """Review integrated source independently without granting delivery approval.

        Args:
            project: Project identity in the selected protected controller state.

        Returns:
            Whether fresh final review permits the actual integrated revision.
        """
        current = self.store.project(project)
        if not self.store.current_approval(project) or current["state"] not in (
            ProjectState.PAUSED,
            ProjectState.BLOCKED,
            ProjectState.AWAITING_ACCEPTANCE,
        ):
            raise StateError("operator review requires approved, inactive source")
        if any(row["owner"] for row in self.store.tasks(project)):
            raise StateError("active tasks must settle before operator review")
        self.engine.admit(project)
        snapshot = Repository(self.store, project).current()
        task = self.store.blueprint(project).tasks[0].model_copy(update={"check_ids": []})
        return self.engine.review(project, task, snapshot, "human-requested-review", final=True)

    def accept(self, project: str, revision: str, actor: str) -> None:
        """Bind real human sign-off to an intact, verified, reviewed delivery revision.

        Args:
            project: Project identity in the selected protected controller state.
            revision: Exact current delivered source digest inspected by the operator.
            actor: Authenticated human identity supplied by the administrative channel.
        """
        if not actor.startswith("human:"):
            raise StateError("acceptance requires authenticated human identity")
        current = self.store.project(project)
        if (
            current["state"] != ProjectState.AWAITING_ACCEPTANCE
            or current["delivery_digest"] != revision
        ):
            raise StateError("acceptance requires the current delivered revision")
        if (
            not self.store.current_approval(project)
            or not self.store.verify_audit()
            or not Verifier(self.store).gate(project, revision).allowed
            or not Verifier(self.store).delivery_gate(project, revision).allowed
        ):
            raise StateError("delivery verification/audit is incomplete")
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT * FROM projects WHERE id=?", (project,)).fetchone()
            if (
                current is None
                or current["state"] != ProjectState.AWAITING_ACCEPTANCE
                or current["delivery_digest"] != revision
            ):
                raise StateError("stale acceptance request")
            if self.store.blocking_findings(project, revision, connection=connection):
                raise StateError("unresolved blocking findings")
            roles = {*self.store.policy(project).required_review_roles, Role.QA, Role.ACCEPTANCE}
            latest: dict[str, str] = {}
            for row in connection.execute(
                "SELECT role,id FROM reviews WHERE project_id=? AND task_id IS NULL "
                "AND source_digest=? ORDER BY created DESC",
                (project, revision),
            ):
                latest.setdefault(row[0], row[1])
            reviewed = {
                role
                for role, review_id in latest.items()
                if self.store.review_satisfied(connection, project, review_id, revision)
            }
            if not roles <= reviewed:
                raise StateError("final independent reviews missing")
            if any(row["state"] != TaskState.INTEGRATED for row in self.store.tasks(project)):
                raise StateError("required tasks incomplete")
            connection.execute(
                "UPDATE projects SET state=?,updated=? WHERE id=?",
                (ProjectState.ACCEPTED, time.time(), project),
            )
            self.store._event(
                connection, project, "delivery.accepted", {"actor": actor, "revision": revision}
            )

    def grant_exception(
        self,
        project: str,
        finding: str,
        revision: str,
        reason: str,
        actor: str,
    ) -> str:
        """Authorize one finding exception for an exact verified source and policy.

        Args:
            project: Approved project identity.
            finding: Persisted unresolved finding in that project.
            revision: Source digest inspected by the human operator.
            reason: Explicit justification, retained in the protected audit.
            actor: Authenticated administrative human identity.

        Returns:
            The exception identity needed for explicit revocation.

        Raises:
            StateError: Authorization, source, finding or current state is invalid.
        """
        if not actor.startswith("human:") or not reason.strip():
            raise StateError("finding exceptions require explicit human justification")
        if not re.fullmatch(r"[a-f0-9]{64}", revision):
            raise StateError("exception requires an exact source digest")
        if not self.store.current_approval(project) or not self.store.verify_audit():
            raise StateError("exception requires intact current approval")
        snapshot = Snapshot(revision, self.store.root / "snapshots" / revision / "source")
        if not SnapshotStore(self.store.root / "snapshots").verify(snapshot):
            raise StateError("exception source integrity failure")
        identifier = uuid.uuid4().hex
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT * FROM projects WHERE id=?", (project,)).fetchone()
            row = connection.execute(
                "SELECT * FROM findings WHERE id=? AND project_id=? AND resolved_by IS NULL",
                (finding, project),
            ).fetchone()
            if current is None or current["state"] in ("ACCEPTED", "CANCELLED") or row is None:
                raise StateError("exception requires an active project and unresolved finding")
            known = revision in (
                current["source_digest"],
                current["delivery_digest"],
                row["source_digest"],
            )
            if (
                not known
                and not connection.execute(
                    "SELECT id FROM checks WHERE project_id=? AND source_digest=? LIMIT 1",
                    (project, revision),
                ).fetchone()
            ):
                raise StateError("exception source does not belong to this project")
            if connection.execute(
                "SELECT id FROM finding_exceptions WHERE project_id=? AND finding_id=? "
                "AND source_digest=? AND revoked IS NULL",
                (project, finding, revision),
            ).fetchone():
                raise StateError("finding already has an active exception for this revision")
            connection.execute(
                "INSERT INTO finding_exceptions VALUES(?,?,?,?,?,?,?,?,?,NULL)",
                (
                    identifier,
                    project,
                    finding,
                    revision,
                    current["blueprint_hash"],
                    current["policy_hash"],
                    actor,
                    redact(reason)[:16000],
                    time.time(),
                ),
            )
            self.store._event(
                connection,
                project,
                "finding.exception_granted",
                {
                    "exception": identifier,
                    "finding": finding,
                    "revision": revision,
                    "actor": actor,
                    "reason": redact(reason)[:16000],
                },
            )
        return identifier

    def revoke_exception(self, project: str, exception: str, actor: str) -> None:
        """Revoke a human exception without erasing its original justification.

        Args:
            project: Project owning the exception.
            exception: Active exception identity from the report.
            actor: Authenticated administrative human identity.

        Raises:
            StateError: Identity, project phase or exception is invalid.
        """
        if not actor.startswith("human:"):
            raise StateError("exception revocation requires authenticated human")
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT state FROM projects WHERE id=?", (project,)
            ).fetchone()
            if current is None or current[0] in ("ACCEPTED", "CANCELLED"):
                raise StateError("exception revocation requires an active project")
            updated = connection.execute(
                "UPDATE finding_exceptions SET revoked=? "
                "WHERE project_id=? AND id=? AND revoked IS NULL",
                (time.time(), project, exception),
            )
            if updated.rowcount != 1:
                raise StateError("unknown or already revoked finding exception")
            if current[0] == ProjectState.AWAITING_ACCEPTANCE:
                connection.execute(
                    "UPDATE projects SET state=?,error=?,updated=? WHERE id=?",
                    (
                        ProjectState.BLOCKED,
                        "finding exception revoked; re-verification required",
                        time.time(),
                        project,
                    ),
                )
            self.store._event(
                connection,
                project,
                "finding.exception_revoked",
                {
                    "exception": exception,
                    "actor": actor,
                },
            )

    def reject(
        self,
        project: str,
        revision: str,
        reason: str,
        actor: str,
        criteria: list[str] | None = None,
    ) -> None:
        """Persist human feedback and reopen existing scoped work without weakening criteria.

        Args:
            project: Project identity in the selected protected controller state.
            revision: Exact current delivered source digest inspected by the operator.
            reason: Concrete diagnostic or feedback preserved with its original criteria.
            actor: Authenticated human identity supplied by the administrative channel.
            criteria: Existing approved requirement identifiers affected by correction.
        """
        if not actor.startswith("human:") or not reason.strip():
            raise StateError("rejection requires authenticated human feedback")
        self.store.request_repairs(
            project,
            redact(reason),
            actor=actor,
            revision=revision,
            criteria=criteria or [item.id for item in self.store.blueprint(project).requirements],
        )

    def export(self, project: str, destination: Path) -> None:
        """Export a new delivery directory with source and truthful requirement-linked reports.

        Args:
            project: Project identity in the selected protected controller state.
            destination: New destination; existing data is never overwritten.
        """
        if destination.exists() or destination.is_symlink():
            raise StateError("delivery destination must be a new directory")
        current = self.store.project(project)
        source = current["delivery_digest"] or current["source_digest"]
        if not source:
            raise StateError("no integrated source available for export")
        snapshot = Snapshot(source, self.store.root / "snapshots" / source / "source")
        SnapshotStore(self.store.root / "snapshots").materialize(snapshot, destination / "source")
        (destination / "REPORT.json").write_text(json.dumps(self.report(project), indent=2) + "\n")
        blueprint = self.store.blueprint(project)
        (destination / "BLUEPRINT.json").write_text(blueprint.model_dump_json(indent=2) + "\n")
        (destination / "PRD.md").write_text(
            "# "
            + blueprint.name
            + "\n\n"
            + "\n\n".join(
                f"## {item.id}\n\n{item.description}\n\nAcceptance: {item.acceptance}"
                for item in blueprint.requirements
            )
        )
        (destination / "ARCHITECTURE.md").write_text(blueprint.architecture + "\n")
        (destination / "PLAN.md").write_text(
            "# Implementation plan\n\n"
            + "\n\n".join(
                f"## {task.id}\n\n{task.description}\n\n"
                f"Dependencies: {', '.join(task.dependencies) or 'None'}\n\n"
                f"Requirements: {', '.join(task.requirement_ids)}"
                for task in (
                    self.store.task_spec(project, record["id"])
                    for record in self.store.tasks(project)
                )
            )
        )
        for document in blueprint.documents:
            (destination / document.name).write_text(document.content + "\n")
        report = self.report(project)
        (destination / "PROGRESS.md").write_text(
            "# Actual task progress\n\n"
            + "\n".join(
                f"- {task['id']}: {task['state']} ({task['attempts']} attempts)"
                for task in report["tasks"]
            )
            + "\n"
        )
        for filename, content in (
            ("TEST_REPORT.json", report["checks"]),
            (
                "SECURITY_REPORT.json",
                {
                    "reviews": [
                        item for item in report["reviews"] if item["role"] == Role.SECURITY
                    ],
                    "findings": report["findings"],
                },
            ),
            ("QA_REPORT.json", [item for item in report["reviews"] if item["role"] == Role.QA]),
            ("ACCEPTANCE_REPORT.json", report["acceptance_matrix"]),
        ):
            (destination / filename).write_text(json.dumps(content, indent=2) + "\n")
        (destination / "DELIVERY.md").write_text(
            "# Delivery identity\n\nSource: " + str(source) + "\n\n"
            "Use the setup and runtime instructions in source/README.md and source/RUNBOOK.md "
            "when provided. Reported task/check history includes failures and prior revisions. "
            "Factory readiness and human acceptance are separate. Release is unsupported.\n"
        )
        (destination / "README.md").write_text(
            "# " + blueprint.name + " — delivery\n\n"
            "Factory state: " + str(current["state"]) + "\n\n"
            "Exact source identity: " + str(source) + "\n\n"
            "Application source and its setup instructions are in source/. "
            "Read source/README.md and source/RUNBOOK.md before running the application. "
            "This export does not deploy it or record human acceptance.\n\n"
            "REPORT.json contains actual checks, review findings, exceptions, corrections "
            "and the requirement-to-evidence matrix. Prior failed attempts remain visible.\n"
        )
        (destination / "RUNBOOK.md").write_text(
            "# Factory delivery operations\n\n"
            "Project: " + project + "\n\n"
            "Application operations: source/RUNBOOK.md. Factory recovery and controls use "
            "the original protected state directory, not this export.\n\n"
            "Use factory report PROJECT_ID to inspect blockers and current delivery identity. "
            "Use factory pause before controller maintenance; preserve the state database, "
            "snapshots and evidence together. A database-only copy cannot restore "
            "source artifacts. "
            "Acceptance and separately authorized release are distinct operations.\n"
        )
