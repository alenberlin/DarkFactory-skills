# Shared Autopilot contract

Skills define engineering behavior. The executable runtime controls approvals,
task ownership, effects, evidence and state. A hook, prompt, role file, Markdown
report or agent assertion cannot replace those controls.

## Inputs and proposals

The approved Blueprint contains requirement IDs and observable criteria,
architecture, non-goals, an acyclic task DAG, roles, component ownership,
protected check definitions, toolchain/inference configuration, permissions and
limits. Policy defines required check kinds, reviews and protected baseline
paths. Unknown fields and missing requirement coverage are rejected.

Agents receive a bounded assignment, source, failed check history, unresolved
findings and remaining permissions. AgentReply contains status, summary, files,
commands, findings, examined, unexamined and resolved_findings. File edits use
relative paths and content; null proposes deletion. Commands are argv vectors
executed in the target container. Completion means the proposal is ready for
evaluation, never that a gate passed.

Reviewers use separate sessions and cannot submit edits. Bounded inspection
commands run through the broker with read-only source and no external network.
Final QA and acceptance must enumerate all approved requirement IDs in their
examined scope and disclose any missing mandatory coverage.
Findings include severity, description and criterion. Blocking findings persist;
resolution requires explicit independent re-review of a changed revision with
renewed trusted checks. An authenticated human may grant a justified exception
for one finding at one exact source/blueprint/policy identity. Exceptions retain
the adverse finding and verdict, appear in reports, can be revoked, and never
waive mandatory checks, approval, ownership or final human acceptance.

## Authority and identity

The controller owns SQLite state, approvals, policies, snapshots, evidence,
audit history, Git references and protected drivers. Agents receive source
copies and short-lived inference capabilities. Provider keys, controller APIs,
other project state and the Docker socket are outside their mounts.

Only the operator CLI or authenticated loopback API approves exact blueprint
digests or accepts exact delivery digests. Approval separately records local
commit/integration permission. Release, external publication, messages,
production data changes and increased resource allowances are separate actions.
The current runtime provides no deployment adapter.

## Evidence and state

Trusted checks record actual process status, bounded output, immutable source,
definition/policy hashes, executor image, timing and expected output. Failures
remain visible. Unit tests importing generated code have weaker guarantees than
protected drivers observing a separate application container. Use separate
black-box drivers for critical behavior.

Task claims have leases and increasing fencing tokens. Dependencies must be
integrated and overlapping components serialize. The coordinator verifies the
actual merged candidate before a journaled compare-and-swap ref update.
Markdown projections never override these records.

The lifecycle is discovery → proposed blueprint → human approval → admitted
execution → implementation/verification/review/repair/integration → final QA →
ready for human acceptance → human acceptance. Paused, blocked and cancelled
are real states. Final acceptance does not deploy.

Human rejection preserves the original integrated tasks and creates separate
criterion-linked corrective tasks with inherited scope, checks and dependencies.
Automatic final-QA retries remain bounded on the current assigned tasks. Source
README/runbook requirements are part of the blueprint delivery contract.

## Language and capability boundaries

Contracts and skills do not assume the project language. Profiles choose images
and actual build/test/lint/type commands for Python, Node.js/TypeScript, Rust or
mixed projects. Missing tools remain blockers. No fake successful substitute is
valid for an unavailable command.

Advisory reports quality violations; Enforced blocks quality gates; Strict also
requires effect isolation. Background runs require Strict and refuse downgrade.
Explicit `factory run` supports attached foreground execution in all three modes
through the same isolated backend. Advisory never makes failed final evidence
pass or grants human acceptance. `factory init` creates configuration proposals
without credentials, inference, approval or implementation effects.
Current runtime support and incomplete conformance are documented in
[AUTOPILOT.md](AUTOPILOT.md). Never advertise a proposed adapter as tested support.
