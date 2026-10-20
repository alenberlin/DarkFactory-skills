"""Execute protected checks against immutable source and retain authentic outcomes."""

from __future__ import annotations

import fcntl
import json
import re
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from darkfactory.domain import CheckSpec, GateDecision, Limits, digest
from darkfactory.execution import (
    DockerExecutor,
    ProcessResult,
    Snapshot,
    SnapshotStore,
    bounded_process,
)
from darkfactory.policy import evaluate_checks
from darkfactory.resources import Resources, StorageQuota
from darkfactory.security import redact as redact
from darkfactory.storage import Record, Store


class Verifier:
    """Own real check execution; agent statements never enter the passing-result path."""

    def __init__(self, store: Store) -> None:
        """Use controller-owned definitions and immutable snapshots for all checks.

        Args:
            store: Protected transactional state, never exposed to task containers.
        """
        self.store = store
        self.snapshots = SnapshotStore(store.root / "snapshots")

    def specifications(self, project_id: str, task_id: str | None = None) -> list[CheckSpec]:
        """Select required definitions from the authoritative approved blueprint.

        Args:
            project_id: Project identity in the selected protected controller state.
            task_id: Original or human-authorized corrective task identifier.

        Returns:
            Required protected definitions selected for this approved task.
        """
        blueprint = self.store.blueprint(project_id)
        check_ids: list[str] = []
        if task_id:
            task = self.store.task_spec(project_id, task_id)
            check_ids = task.check_ids
        return [
            spec
            for spec in blueprint.checks
            if spec.required and (not check_ids or spec.id in check_ids)
        ]

    @contextmanager
    def _check_execution(
        self,
        project: str,
        identifier: str,
        snapshot: Snapshot,
        spec: CheckSpec,
        task: str | None,
        attempt: str | None,
        image: str,
    ) -> Iterator[None]:
        directory = self.store.root / "evidence" / identifier
        directory.mkdir()
        with (directory / "owner.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            started = time.time()
            intent = {
                "source": snapshot.digest,
                "definition": spec.model_dump(mode="json"),
                "image_id": image,
                "started": started,
            }
            with self.store.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                policy_hash = self.store.project(project)["policy_hash"]
                connection.execute(
                    "INSERT INTO checks VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        identifier,
                        project,
                        task,
                        attempt,
                        spec.id,
                        snapshot.digest,
                        digest(spec),
                        policy_hash,
                        0,
                        json.dumps({"status": "RUNNING", "image_id": image}),
                        started,
                    ),
                )
                connection.execute(
                    "INSERT INTO operations VALUES(?,?,?,?,?,?,?)",
                    (identifier, project, "check-run", json.dumps(intent), "ACTIVE", None, started),
                )
                self.store._event(
                    connection,
                    project,
                    "check.started",
                    {
                        "evidence": identifier,
                        "check": spec.id,
                        "source": snapshot.digest,
                    },
                )
            try:
                yield
            finally:
                self._close_check(project, identifier, intent)

    def _close_check(self, project: str, identifier: str, intent: Record) -> None:
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            check = connection.execute(
                "SELECT result FROM checks WHERE id=?", (identifier,)
            ).fetchone()
            if check is None:
                raise RuntimeError("interrupted verification lost its protected start record")
            pending = json.loads(check[0]).get("status") == "RUNNING"
            if pending:
                report = ProcessResult(
                    argv=intent["definition"]["argv"],
                    exit_code=-1,
                    stdout="",
                    stderr="Check aborted: supervising process ended before evidence commit",
                    started=intent["started"],
                    finished=time.time(),
                    image_id=intent["image_id"],
                ).model_dump(mode="json")
                report.update({"aborted": True, "definition": intent["definition"]})
                connection.execute(
                    "UPDATE checks SET passed=0,result=?,created=? WHERE id=?",
                    (json.dumps(report), time.time(), identifier),
                )
                (self.store.root / "evidence" / identifier / "result.json").write_text(
                    json.dumps(report, indent=2) + "\n"
                )
                self.store._event(connection, project, "check.aborted", {"evidence": identifier})
            connection.execute(
                "UPDATE operations SET state=? WHERE id=? AND kind='check-run'",
                ("ABORTED" if pending else "CLOSED", identifier),
            )

    def reconcile(self, project: str) -> int:
        """Finalize interrupted check evidence only after its supervisor OS lock is released.

        Args:
            project: Project being recovered by the controller or worker.

        Returns:
            Number of abandoned checks reconciled without promoting any result to success.
        """
        with self.store.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM operations WHERE project_id=? "
                "AND kind='check-run' AND state='ACTIVE'",
                (project,),
            ).fetchall()
        reconciled = 0
        for row in rows:
            directory = self.store.root / "evidence" / row["id"]
            if directory.is_symlink() or not directory.is_dir():
                raise RuntimeError("check recovery evidence directory is unavailable")
            with (directory / "owner.lock").open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                with self.store.connection() as connection:
                    active = connection.execute(
                        "SELECT state FROM operations WHERE id=?", (row["id"],)
                    ).fetchone()
                if active and active[0] == "ACTIVE":
                    self._close_check(project, row["id"], json.loads(row["intent"]))
                    reconciled += 1
        return reconciled

    def run(
        self,
        project_id: str,
        snapshot: Snapshot,
        *,
        task_id: str | None = None,
        attempt_id: str | None = None,
    ) -> GateDecision:
        """Run actual configured checks and capture failed, aborted and successful evidence.

        Args:
            project_id: Project identity in the selected protected controller state.
            snapshot: Immutable source identity and its controller-owned files.
            task_id: Original or human-authorized corrective task identifier.
            attempt_id: Unique persisted attempt identity for attribution and ownership.

        Returns:
            Trusted gate decision based on actual current-source execution.
        """
        blueprint = self.store.blueprint(project_id)
        environment = self.store.environment(project_id) or {}
        executor = DockerExecutor(
            environment.get("target_image", blueprint.image), Resources(self.store, project_id)
        )
        if not self.snapshots.verify(snapshot):
            return GateDecision(allowed=False, reasons=["immutable snapshot integrity failure"])
        for spec in self.specifications(project_id, task_id):
            check_run_id = uuid.uuid4().hex
            with self._check_execution(
                project_id, check_run_id, snapshot, spec, task_id, attempt_id, executor.image_id
            ):
                container_source = self.store.root / "evidence" / check_run_id / "workspace"
                quota = StorageQuota(
                    self.store.root, blueprint.limits.state_storage_mb * 1024 * 1024
                )
                self.snapshots.materialize(snapshot, container_source, quota=quota)
                trusted_files: dict[str, Path] = {}
                argv = list(spec.argv)
                if spec.driver is not None:
                    driver = container_source.parent / "driver"
                    driver.write_text(spec.driver)
                    driver.chmod(0o444)
                    trusted_files["driver"] = driver
                    argv = [argument.replace("{driver}", "/trusted/driver") for argument in argv]
                limits = blueprint.limits.model_copy(
                    update={
                        "command_seconds": min(
                            spec.timeout_seconds, blueprint.limits.command_seconds
                        )
                    }
                )
                started = time.time()
                aborted = False
                target_results: list[ProcessResult] = []
                try:
                    if spec.service_argv is None:
                        result = executor.run(
                            container_source,
                            argv,
                            limits,
                            readonly=True,
                            trusted_files=trusted_files,
                        )
                    else:
                        network = "df-check-" + check_run_id
                        server_name = network + "-target"
                        with Resources(self.store, project_id).lease(
                            network + "-scope", network=network
                        ):
                            created = bounded_process(
                                [executor.binary, "network", "create", "--internal", network],
                                timeout=10,
                                output_bytes=4096,
                            )
                            if created.exit_code:
                                raise RuntimeError("isolated black-box check network unavailable")
                            target_errors: list[BaseException] = []

                            def serve(
                                target_results: list[ProcessResult] = target_results,
                                target_errors: list[BaseException] = target_errors,
                                container_source: Path = container_source,
                                spec: CheckSpec = spec,
                                limits: Limits = limits,
                                network: str = network,
                                server_name: str = server_name,
                            ) -> None:
                                try:
                                    target_results.append(
                                        executor.run(
                                            container_source,
                                            list(spec.service_argv or []),
                                            limits,
                                            readonly=True,
                                            network=network,
                                            container_name=server_name,
                                            network_alias="target",
                                        )
                                    )
                                except BaseException as error:
                                    target_errors.append(error)

                            target = threading.Thread(target=serve, daemon=True)
                            target.start()
                            driver_workspace = container_source.parent / "driver-workspace"
                            driver_workspace.mkdir()
                            try:
                                result = executor.run(
                                    driver_workspace,
                                    argv,
                                    limits,
                                    readonly=True,
                                    trusted_files=trusted_files,
                                    network=network,
                                    environment={"FACTORY_TARGET": "http://target:8080"},
                                )
                            finally:
                                bounded_process(
                                    [executor.binary, "rm", "--force", server_name],
                                    timeout=10,
                                    output_bytes=4096,
                                )
                                target.join(timeout=limits.command_seconds + 15)
                                bounded_process(
                                    [executor.binary, "network", "rm", network],
                                    timeout=10,
                                    output_bytes=4096,
                                )
                            if target_errors or target.is_alive():
                                raise RuntimeError(
                                    "isolated target service could not be supervised"
                                )
                except (OSError, RuntimeError, ValueError) as error:
                    aborted = True
                    result = ProcessResult(
                        argv=argv,
                        exit_code=-1,
                        stdout="",
                        stderr="Check aborted: " + redact(str(error)),
                        started=started,
                        finished=time.time(),
                        image_id=executor.image_id,
                    )
                current_manifest = self.snapshots.manifest(container_source)
                unchanged = current_manifest == self.snapshots.manifest(snapshot.path)
                output_ok = True
                if spec.expected_output:
                    output_ok = (
                        spec.expected_output in result.stdout
                        or spec.expected_output in result.stderr
                    )
                elif spec.kind == "test" and spec.driver is None:
                    output_ok = bool(
                        re.search(
                            r"(?:[1-9]\d* passed|Ran [1-9]\d* tests?|#\s*pass\s+[1-9]\d*)",
                            result.stdout + result.stderr,
                        )
                    )
                passed = (
                    result.exit_code == 0 and not result.timed_out and not result.output_truncated
                )
                skipped = (
                    spec.kind == "test"
                    and not spec.allow_skipped_tests
                    and bool(
                        re.search(
                            r"(?:\b[1-9]\d*\s+(?:skipped|deselected|xfailed|xpassed)\b"
                            r"|#\s*(?:skip|todo)\s+[1-9]\d*|Ran 0 tests|# tests 0"
                            r"|collected 0 items|no tests ran)",
                            result.stdout + result.stderr,
                            re.IGNORECASE,
                        )
                    )
                )
                passed = passed and not skipped
                passed = passed and unchanged and output_ok and self.snapshots.verify(snapshot)
                report = result.model_dump(mode="json")
                report.update(
                    {
                        "stdout": redact(result.stdout),
                        "stderr": redact(result.stderr),
                        "source_unchanged": unchanged,
                        "expected_output_observed": output_ok,
                        "definition": spec.model_dump(mode="json"),
                        "aborted": aborted,
                        "unapproved_skipped_tests": skipped,
                        "target_service": [
                            {
                                **item.model_dump(mode="json"),
                                "stdout": redact(item.stdout),
                                "stderr": redact(item.stderr),
                            }
                            for item in target_results
                        ],
                    }
                )
                with quota.allocate(len(json.dumps(report).encode()) * 3 + 65536):
                    (container_source.parent / "result.json").write_text(
                        json.dumps(report, indent=2) + "\n"
                    )
                    with self.store.connection() as connection:
                        connection.execute("BEGIN IMMEDIATE")
                        policy_hash = self.store.project(project_id)["policy_hash"]
                        connection.execute(
                            "INSERT OR REPLACE INTO checks VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                check_run_id,
                                project_id,
                                task_id,
                                attempt_id,
                                spec.id,
                                snapshot.digest,
                                digest(spec),
                                policy_hash,
                                int(passed),
                                json.dumps(report),
                                result.finished,
                            ),
                        )
                        self.store._event(
                            connection,
                            project_id,
                            "check.finished",
                            {
                                "check": spec.id,
                                "source": snapshot.digest,
                                "passed": passed,
                                "evidence": check_run_id,
                            },
                        )
        return self.gate(project_id, snapshot.digest, task_id=task_id)

    def gate(
        self, project_id: str, source_digest: str, *, task_id: str | None = None
    ) -> GateDecision:
        """Accept only current source, policy and check-definition identities.

        Args:
            project_id: Project identity in the selected protected controller state.
            source_digest: Exact immutable source identity associated with the result.
            task_id: Original or human-authorized corrective task identifier.

        Returns:
            Strict evidence decision; Advisory applies only to intermediate transitions.
        """
        project = self.store.project(project_id)
        specs = self.specifications(project_id, task_id)
        results: dict[str, tuple[bool, str]] = {}
        with self.store.connection() as connection:
            for spec in specs:
                row = connection.execute(
                    "SELECT * FROM checks WHERE project_id=? AND source_digest=? "
                    "AND definition_hash=? AND policy_hash=? ORDER BY created DESC LIMIT 1",
                    (project_id, source_digest, digest(spec), project["policy_hash"]),
                ).fetchone()
                if row:
                    environment = self.store.environment(project_id)
                    result = json.loads(row["result"])
                    matched = (
                        not environment or result.get("image_id") == environment["target_image"]
                    )
                    results[spec.id] = (bool(row["passed"]) and matched, row["source_digest"])
        return evaluate_checks([spec.id for spec in specs], results, source_digest)

    def delivery_gate(self, project_id: str, source_digest: str) -> GateDecision:
        """Require approved run/setup documentation in the exact integrated source.

        Args:
            project_id: Approved project whose delivery is under consideration.
            source_digest: Exact immutable source revision to inspect.

        Returns:
            A failure for missing/empty required documents or altered source.
            Semantic accuracy and runnable instructions still require final QA.
        """
        snapshot = Snapshot(source_digest, self.store.root / "snapshots" / source_digest / "source")
        if not self.snapshots.verify(snapshot):
            return GateDecision(allowed=False, reasons=["delivery source integrity failure"])
        missing = [
            path
            for path in self.store.blueprint(project_id).delivery.required_files
            if not (snapshot.path / path).is_file()
            or len((snapshot.path / path).read_text(errors="replace").strip()) < 20
        ]
        return GateDecision(
            allowed=not missing,
            reasons=["missing or empty required delivery document: " + path for path in missing],
        )

    def records(self, project_id: str) -> list[Record]:
        """Return retained check history, including failures and old revisions.

        Args:
            project_id: Project identity in the selected protected controller state.

        Returns:
            Retained check history, including failed and interrupted executions.
        """
        with self.store.connection() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM checks WHERE project_id=? ORDER BY created", (project_id,)
                )
            ]
