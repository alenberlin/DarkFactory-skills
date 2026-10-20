"""Bound replacement-session context while preserving read-only access to approved scope."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from darkfactory.adapters import AgentReply, strict_schema
from darkfactory.domain import Role, TaskSpec
from darkfactory.execution import SnapshotStore
from darkfactory.pack import role_context
from darkfactory.resources import StorageQuota
from darkfactory.security import redact_value
from darkfactory.storage import Record, StateError, Store


def context_inputs(store: Store, project: str, source: Path) -> dict[str, Path]:
    """Publish immutable approved scope and source manifests as read-only inspection inputs.

    Args:
        store: Protected controller state.
        project: Approved project identity.
        source: Actual current task source directory.

    Returns:
        Protected files mounted under /trusted for broker-mediated inspection commands.
    """
    root = store.root / "projects" / project / "context"
    root.mkdir(parents=True, exist_ok=True)
    quota = StorageQuota(store.root, store.blueprint(project).limits.state_storage_mb * 1024 * 1024)
    snapshots = SnapshotStore(store.root / "snapshots")
    with store.connection() as connection:
        findings = [
            dict(row)
            for row in connection.execute(
                "SELECT f.*,r.role FROM findings f JOIN reviews r ON r.id=f.review_id "
                "WHERE f.project_id=? AND f.resolved_by IS NULL",
                (project,),
            )
        ]
    values = {
        "blueprint": json.loads(store.project(project)["blueprint"]),
        "manifest": snapshots.manifest(source),
        "findings": findings,
        "workflow": [
            {key: row[key] for key in ("id", "spec", "state", "error")}
            for row in store.tasks(project)
        ],
    }
    files = {}
    for label, value in values.items():
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        path = root / (label + "-" + hashlib.sha256(encoded).hexdigest() + ".json")
        if path.exists():
            if path.read_bytes() != encoded:
                raise StateError("protected context artifact integrity failure")
        else:
            with quota.allocate(len(encoded)):
                temporary = root / ("pending-" + uuid.uuid4().hex)
                temporary.write_bytes(encoded)
                temporary.chmod(0o444)
                temporary.replace(path)
        files[label] = path
    return files


def build_context(
    store: Store,
    project: str,
    task: TaskSpec,
    source: Path,
    diagnosis: str,
    findings: list[Record],
    role: Role | None = None,
) -> str:
    """Pack bounded relevant context with explicit omissions and inspectable approved artifacts.

    Args:
        store: Protected runtime state used for rehydration.
        project: Approved project identity.
        task: Complete current assignment; it is never silently truncated.
        source: Actual contained source directory.
        diagnosis: Prior observed failure, with sensitive values redacted.
        findings: Persistent unresolved findings for this assignment.
        role: Independent review role, or the assignment's implementation role.

    Returns:
        A bounded JSON assignment with protected scope/manifest references. Omitted
        source and criteria remain available through read-only broker commands.

    Raises:
        StateError: Essential assignment data exceeds the approved attempt allowance.
    """
    blueprint = store.blueprint(project)
    configuration = blueprint.agent_configuration(role or task.role)
    budget = 700000
    if configuration:
        spec = configuration.inference
        schema_bytes = len(json.dumps(strict_schema(AgentReply.model_json_schema())).encode())
        budget = min(
            budget,
            max(4096, (spec.attempt_tokens - spec.max_output_tokens) * 2 - schema_bytes - 16384),
        )
    manifest = SnapshotStore(store.root / "snapshots").manifest(source)
    record: Record = {
        "protocol": "AgentReply",
        "role_instructions": role_context(role or task.role),
        "assignment": task.model_dump(mode="json"),
        "approved_blueprint_digest": store.project(project)["blueprint_hash"],
        "approved_scope_path": "/trusted/blueprint",
        "source_manifest_path": "/trusted/manifest",
        "findings_path": "/trusted/findings",
        "workflow_path": "/trusted/workflow",
        "blueprint": {
            "name": blueprint.name,
            "version": blueprint.version,
            "architecture": blueprint.architecture[:4000],
            "requirements": [],
        },
        "source": {},
        "source_manifest": [],
        "omitted_files": [],
        "omitted_source_count": len(manifest),
        "omitted_requirement_count": 0,
        "diagnosis": "",
        "verification": [],
        "open_findings": [],
        "omitted_findings_count": len(findings),
        "rules": (
            "Propose only scoped edits and argv commands; claims never pass gates. "
            "Read-only inspection commands can read /trusted/blueprint and /trusted/manifest "
            "for complete approved scope and omitted files. This JSON is a bounded projection. "
            "Never infer missing criteria from a summary. Reviewers cannot edit source. "
            "Final QA/acceptance must examine every assigned requirement and disclose gaps."
        ),
    }

    def encoded() -> str:
        return json.dumps(record, ensure_ascii=False)

    if len(encoded().encode()) > budget:
        raise StateError(
            "essential assignment exceeds inference context allowance; split or revise it"
        )

    def append(container: list[object], item: object) -> bool:
        container.append(item)
        if len(encoded().encode()) <= budget:
            return True
        container.pop()
        return False

    record["diagnosis"] = redact_value(diagnosis[: min(4000, budget // 8)])
    for finding in findings:
        if not append(record["open_findings"], redact_value(finding)):
            break
        record["omitted_findings_count"] -= 1
    requirements = [item for item in blueprint.requirements if item.id in task.requirement_ids]
    included = 0
    for requirement in requirements:
        if append(record["blueprint"]["requirements"], requirement.model_dump(mode="json")):
            included += 1
    record["omitted_requirement_count"] = len(requirements) - included
    for entry in manifest:
        path = entry["path"]
        if entry["size"] <= min(budget // 3, budget - len(encoded().encode()) - 1024):
            data = (source / path).read_bytes()
            if b"\0" not in data:
                record["source"][path] = data.decode(errors="replace")
                if len(encoded().encode()) <= budget - 1024:
                    record["omitted_source_count"] -= 1
                    continue
                del record["source"][path]
        if len(record["omitted_files"]) < 50:
            append(record["omitted_files"], path)
    for entry in manifest:
        if not append(record["source_manifest"], entry):
            break
    with store.connection() as connection:
        checks = connection.execute(
            "SELECT check_id,passed,source_digest,result FROM checks "
            "WHERE project_id=? AND task_id=? ORDER BY created DESC LIMIT 5",
            (project, task.id),
        ).fetchall()
    for check in checks:
        value = dict(check)
        value["result"] = value["result"][:4000]
        if not append(record["verification"], redact_value(value)):
            break
    if len(encoded().encode()) > budget:
        raise StateError("context allowance exceeded; no scope was silently omitted")
    return encoded()
