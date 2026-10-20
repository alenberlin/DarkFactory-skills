"""Durable adaptive planning sessions, separate from blueprint implementation approval."""

from __future__ import annotations

import fcntl
import json
import time
import uuid
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from darkfactory.adapters import Adapter, AgentReply
from darkfactory.domain import (
    Blueprint,
    CheckSpec,
    InferenceSpec,
    Limits,
    PlanningDocument,
    Policy,
    Requirement,
    Role,
    TaskSpec,
)
from darkfactory.engine import Engine
from darkfactory.execution import Snapshot, SnapshotStore
from darkfactory.pack import role_context
from darkfactory.profiles import Profile
from darkfactory.services import Factory
from darkfactory.storage import Record, StateError, Store
from darkfactory.verification import redact


class Discovery:
    """Persist an authorized interview and planning pipeline without authorizing implementation."""

    def __init__(self, store: Store, engine: Engine | None = None) -> None:
        """Use the same bounded inference broker and authoritative storage as task execution.

        Args:
            store: Protected transactional state, unavailable to ordinary agent containers.
            engine: Optional shared execution service; a fixture engine must be labeled explicitly.
        """
        self.store = store
        self.engine = engine or Engine(store)

    def begin(
        self,
        goal: str,
        inference: InferenceSpec,
        limits: Limits,
        source: Path,
        adapter: str,
        *,
        profile: Profile | None = None,
    ) -> str:
        """Record explicit operator planning scope/resources and the initial source snapshot.

        Args:
            goal: Operator product goal, without permission to implement before blueprint approval.
            inference: Explicit provider, model and isolated adapter image selection.
            limits: Approved resource ceilings; exceeding them cannot grant additional allowance.
            source: Real source directory to inspect or snapshot; links and secret environment files
                are excluded.
            adapter: Explicit Claude or Codex adapter; no personal configuration is imported.
            profile: Optional approved toolchain proposal supplied to the planning context.

        Returns:
            Durable discovery identity; implementation remains unapproved.
        """
        if not goal.strip():
            raise StateError("discovery requires a product goal")
        if (
            source.resolve() == self.store.root
            or self.store.root.is_relative_to(source.resolve())
            or source.resolve().is_relative_to(self.store.root)
        ):
            raise StateError("planning source and controller state must be separate")
        scope = Blueprint(
            name="Discovery: " + goal[:150],
            architecture="Planning only; no implementation authorization.",
            requirements=[
                Requirement(
                    id="DISCOVERY", description=goal, acceptance="Complete reviewable blueprint"
                )
            ],
            tasks=[
                TaskSpec(
                    id="DISCOVERY",
                    description=goal,
                    requirement_ids=["DISCOVERY"],
                    role=Role.ANALYST,
                )
            ],
            checks=[CheckSpec(id="proposal", kind="test", argv=["false"])],
            adapter=adapter,
            inference=inference,
            limits=limits,
            image=inference.agent_image,
        )
        project = self.store.create_project(
            scope, Policy(required_check_kinds=["test"], required_review_roles=[])
        )
        snapshot = SnapshotStore(self.store.root / "snapshots").capture(
            source, quota=self.engine.quota(project)
        )
        directory = self.store.root / "projects" / project
        directory.mkdir(exist_ok=True)
        record = {
            "goal": goal,
            "source": snapshot.digest,
            "stage": 0,
            "answers": [],
            "artifacts": [],
            "questions": [],
            "proposal": None,
            "planned_blueprint": None,
            "proposal_identity": None,
            "diagnosis": "",
            "profile": profile.model_dump(mode="json") if profile else None,
        }
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO operations VALUES(?,?,?,?,?,?,?)",
                (project, project, "discovery", "{}", "ACTIVE", json.dumps(record), time.time()),
            )
            connection.execute("UPDATE projects SET state='DISCOVERY' WHERE id=?", (project,))
            self.store._event(
                connection,
                project,
                "discovery.authorized",
                {"limits": limits.model_dump(), "implementation_approved": False},
            )
        return project

    def advance(self, project: str, answers: list[str] | None = None) -> Record:
        """Ask consequential questions or advance the validated planning pipeline.

        Args:
            project: Controller project identifier in the selected protected state directory.
            answers: One human answer for each pending discovery question, in question order.

        Returns:
            Persisted questions, planning artifacts and any separate unapproved proposal.
        """
        directory = self.store.root / "projects" / project
        with (directory / "discovery.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return self._advance(project, answers)

    def _persist(self, project: str, record: Record, event: str) -> None:
        with (
            self.engine.quota(project).allocate(len(json.dumps(record).encode()) * 3 + 65536),
            self.store.connection() as connection,
        ):
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE operations SET outcome=?,state=? WHERE id=? AND kind='discovery'",
                (json.dumps(record), "DONE" if record["proposal"] else "ACTIVE", project),
            )
            self.store._event(
                connection,
                project,
                event,
                {"stage": record["stage"], "proposal": record["proposal"]},
            )

    def _advance(self, project: str, answers: list[str] | None) -> Record:
        if self.store.project(project)["state"] != "DISCOVERY":
            raise StateError("project is not an active discovery")
        with self.store.connection() as connection:
            stored = connection.execute(
                "SELECT outcome FROM operations WHERE id=? AND kind='discovery'", (project,)
            ).fetchone()
        if stored is None:
            raise StateError("missing durable discovery record")
        record: Record = json.loads(stored[0])
        if record["proposal"]:
            return record
        if record["questions"] and not answers:
            return record
        if answers:
            if not record["questions"] or len(answers) != len(record["questions"]):
                raise StateError("answers must correspond to every pending question")
            record["answers"].append({"questions": record["questions"], "answers": answers})
            record["questions"] = []
            self._persist(project, record, "discovery.answers_recorded")
        stages = [Role.ANALYST, Role.ARCHITECT, Role.PLANNER]
        source = Snapshot(
            record["source"], self.store.root / "snapshots" / record["source"] / "source"
        )
        if not SnapshotStore(self.store.root / "snapshots").verify(source):
            raise StateError("discovery source integrity failure")
        inspected = json.loads(
            self.engine._context(project, self.store.blueprint(project).tasks[0], source.path)
        )
        while record["stage"] < len(stages):
            role = stages[record["stage"]]
            attempt = uuid.uuid4().hex
            workspace = self.store.root / "attempts" / attempt / "planning-source"
            SnapshotStore(self.store.root / "snapshots").materialize(
                source, workspace, quota=self.engine.quota(project)
            )
            context = json.dumps(
                {
                    "interview": record,
                    "role": role_context(role),
                    "blueprint_schema": Blueprint.model_json_schema(),
                    "source": inspected["source"],
                    "source_manifest": inspected["source_manifest"],
                    "omitted_files": inspected["omitted_files"],
                    "rules": (
                        "Planning only. No commands or implementation edits. Ask only material "
                        "unresolved questions. Propose PRD/architecture/design/plan files. "
                        "The final planner returns a complete proposed_blueprint with real "
                        "requirement/check/task coverage. No approval is granted by this reply."
                    ),
                }
            )

            def repair_invalid(
                adapter: Adapter, context: str = context, workspace: Path = workspace
            ) -> AgentReply:
                for _ in range(min(3, self.store.blueprint(project).limits.max_attempts)):
                    try:
                        instructions = json.loads(context)
                        instructions["validation_failure"] = record["diagnosis"]
                        return adapter.propose(
                            json.dumps(instructions),
                            workspace,
                            self.store.blueprint(project).limits,
                        )
                    except (ValidationError, ValueError) as error:
                        details = (
                            json.dumps(error.errors(include_input=False, include_url=False))
                            if isinstance(error, ValidationError)
                            else str(error)
                        )
                        record["diagnosis"] = redact(details)[:10000]
                        self._persist(project, record, "discovery.invalid_reply")
                raise StateError("discovery validation repair limit exhausted")

            reply = self.engine._with_agent(project, attempt, role, repair_invalid)
            if reply.commands or reply.findings:
                raise StateError("discovery attempted execution or authoritative review")
            for artifact in reply.files:
                relative = PurePosixPath(artifact.path)
                if relative.is_absolute() or ".." in relative.parts or len(relative.parts) > 2:
                    raise StateError("invalid planning artifact path")
                PlanningDocument(name=relative.name, content=artifact.content or "")
            record["artifacts"].append(reply.model_dump(mode="json"))
            record["questions"] = reply.questions
            if reply.questions:
                self._persist(project, record, "discovery.questions_pending")
                return record
            if reply.status != "complete":
                raise StateError("discovery session blocked: " + reply.summary)
            if role == Role.PLANNER:
                if reply.proposed_blueprint is None:
                    raise StateError("planner returned no valid proposed blueprint")
                proposal = reply.proposed_blueprint
                original = self.store.blueprint(project)
                documents = {item.name: item for item in proposal.documents}
                for artifact in record["artifacts"]:
                    for file in artifact["files"]:
                        item = PlanningDocument(
                            name=PurePosixPath(file["path"]).name, content=file["content"]
                        )
                        documents[item.name] = item
                proposal = Blueprint.model_validate(
                    proposal.model_copy(
                        update={
                            "inference": original.inference,
                            "limits": original.limits,
                            "adapter": original.adapter,
                            "role_bindings": original.role_bindings,
                            "documents": list(documents.values()),
                            **(
                                {"image": record["profile"]["image"]}
                                if record.get("profile")
                                else {}
                            ),
                        }
                    ).model_dump()
                )
                record["planned_blueprint"] = proposal.model_dump(mode="json")
                record["proposal_identity"] = uuid.uuid4().hex
            record["stage"] += 1
            record["diagnosis"] = ""
            self._persist(project, record, "discovery.stage_finished")
        if record["planned_blueprint"]:
            record["proposal"] = Factory(self.store)._propose_snapshot(
                Blueprint.model_validate(record["planned_blueprint"]),
                Policy(),
                source,
                project_id=record["proposal_identity"],
            )
            self._persist(project, record, "discovery.proposal_created")
        return record
