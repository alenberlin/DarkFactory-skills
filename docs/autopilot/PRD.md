# DarkFactory Autopilot product requirements

Blueprint version: 1 · Status: proposed

## Product and users

An individual developer or small engineering team describes a product, agrees on
its blueprint, and entrusts implementation to a locally operable factory. The
operator reviews accurate progress and accepts the delivered application.
Developers can also use the upgraded skills independently in their coding tool.

Success requires executable engineering, independently produced evidence, safe
recovery, and honest failure reporting. Generated documents, role prompts,
provider availability, and coverage percentages alone do not establish success.

## Requirements and acceptance criteria

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| FR-001 | Preserve and upgrade the existing pack | All 15 existing skills and six commands remain available with consistent factory contracts; manifests and references validate |
| FR-002 | Adaptive requirements discovery | A short natural-language request produces focused questions, documented defaults, explicit unresolved decisions, and a versioned requirements artifact |
| FR-003 | Complete PRD and traceability | Functional/nonfunctional requirements have unique IDs, non-goals and measurable criteria; every in-scope ID maps to tasks and verification |
| FR-004 | Architecture and design | Produce architecture, interfaces, data model, trust boundaries, threat model, operational design, and applicable UI design artifacts |
| FR-005 | Executable implementation plan | Schema-valid tasks form an acyclic graph and define roles, dependencies, deliverables, affected components, security concerns, and required evidence |
| FR-006 | Protected blueprint approval | Implementation is denied without authenticated approval of the exact blueprint digest, policy version, execution scope, and resource limits |
| FR-007 | Scoped autonomy | Approved routine engineering proceeds without extra prompts; scope expansion and privileged exceptions require separate authorization |
| FR-008 | Role-based agents | All 14 roles can be assigned through structured tasks and bounded context; model/provider selection is configurable by role |
| FR-009 | Real implementation and repair | An agent changes actual source, meaningful tests execute, failures trigger recorded repairs, and configured retry strategies are bounded |
| FR-010 | Dependency scheduling | Only eligible tasks are claimed; overlapping ownership is serialized, concurrency limits are respected, and independent work continues around blockers |
| FR-011 | Workspace and Git isolation | Active tasks use independent branches/worktrees or contained source copies backed by managed worktrees; ordinary agents cannot update the authoritative integration branch |
| FR-012 | Controlled integration | Merge a verified candidate only through the integration coordinator; verify the actual merged revision and preserve conflicts for diagnosis |
| FR-013 | Durable state | Projects, approvals, tasks, attempts, findings, snapshots, checks, usage, audit events, and acceptance status survive controller restart |
| FR-014 | Safe ownership and recovery | Leases, fencing tokens, heartbeats, operation IDs, and checkpoints reject stale workers and reconcile interrupted operations without duplicate irreversible effects |
| FR-015 | Context rehydration | Replacement sessions retrieve approved requirements, current task, architecture, prior failures, and source/evidence identities without depending on chat history |
| FR-016 | Background operation | Closing the interactive client does not stop the supervised worker; safe pause/resume/cancel and operator-installable restart definitions are provided |
| FR-017 | Versioned policy-as-code | Validate policy documents against a schema; only separately authorized administration activates a policy revision |
| FR-018 | Enforced state transitions | Required prerequisites are evaluated in trusted code; missing, failed, ambiguous, or stale mandatory evidence blocks advancement |
| FR-019 | Controlled privileged execution | Shell, files, Git, network, credentials, CI and release requests pass through declared authorization boundaries; protected paths are inaccessible to ordinary agents |
| FR-020 | Three enforcement modes | Advisory/Enforced/Strict have explicit guarantees; unattended defaults to Strict and fails closed when mandatory capabilities are missing |
| FR-021 | Independent verification | Trusted executors capture real check definitions, source and environment identity, results, timestamps and evidence; agent assertions cannot create passing check records |
| FR-022 | Protected test integrity | Acceptance checks and required runner definitions are protected; removed/weakened tests or a no-op runner cannot silently satisfy gates |
| FR-023 | Independent review lifecycle | Fresh-context review covers code, security, tests and applicable performance; blocking findings persist until verified remediation or authenticated scoped exception |
| FR-024 | Full application QA | Execute approved primary workflows, relevant negative paths, accessibility and browser/runtime checks; missing required observations block readiness |
| FR-025 | Factory security | Restrict agent processes, credentials, network and resources; redact logs; treat project text and tool output as untrusted; adversarial tests exercise actual boundaries |
| FR-026 | Protected audit and approvals | Authoritative records remain outside agent-writable storage; audit history preserves failures, decisions and identities; agent impersonation is denied |
| FR-027 | Resource accounting | Record available usage accurately, label estimates/unknowns, reserve capacity for concurrent work, and safely pause before permitted limits are exceeded |
| FR-028 | Tested provider adapters | Claude Code and Codex expose declared capabilities, sanitized configuration, structured logs and supervision; unverified security modes remain unavailable |
| FR-029 | Language-agnostic projects | Execute actual configured Node.js/TypeScript, Rust and Python checks through the same task/evidence interfaces; profiles do not hardcode one framework |
| FR-030 | Unified CLI and API | Intake, plan, approve, start, status, pause, resume, cancel, retry, report, review, accept and reject call the same application services with appropriate authentication |
| FR-031 | Optional local dashboard | Show real pipeline/task/dependency/evidence states and supported controls; no invented metrics or independent dashboard-only gate logic |
| FR-032 | Reproducible documentation and delivery | Export PRD, architecture, plan, progress, decisions, test/security/QA/acceptance reports, README and runbook matching actual implementation |
| FR-033 | Distinct final states | Only passing required gates yields READY_FOR_HUMAN_ACCEPTANCE; only authenticated human action yields ACCEPTED; release requires its own authorization |
| FR-034 | Acceptance corrections | Human rejection creates criterion-linked corrective tasks; relevant checks and reviews rerun before a new acceptance request |
| FR-035 | Real pilot | Build and run the approved project-board pilot with real agent work, persistence, API/UI, protected functionality, dependent and parallel tasks, and final evidence |
| FR-036 | Honest operations and validation | Exercise the original 15 acceptance scenarios, policy bypass tests and recovery cases; report every unexercised configuration, blocker and known limitation |

## Nonfunctional requirements

- NFR-001 — Correctness: authoritative mutations are transactional and validated;
  completion cannot be obtained by editing a Markdown file or agent response.
- NFR-002 — Security: fail closed on invalid permissions, unknown required
  capabilities, malformed policies, stale evidence, and approval mismatch.
- NFR-003 — Reliability: process termination and client disconnect are tested;
  ambiguous operations are reconciled before retry, with preserved source work.
- NFR-004 — Maintainability: typed boundaries, small cohesive modules, documented
  exported APIs, meaningful tests, and no speculative distributed infrastructure.
- NFR-005 — Accessibility: dashboard controls support keyboard interaction,
  semantic labels, visible focus and understandable loading/error/empty states.
- NFR-006 — Resource limits: dispatch and running jobs respect approved model,
  concurrency, CPU, memory, disk, output, command and token/monetary limits.
- NFR-007 — Privacy: logs/artifacts omit credentials; unrelated project content
  is isolated; outbound code/model transmission uses approved destinations.
- NFR-008 — Portability: documented workstation/server installation without a
  mandatory cloud; tested language profiles and explicit platform support.

All NFRs require implementation evidence. Judgment-based quality and semantic
scope checks require recorded review and escalation rather than an absolute
mechanical guarantee.

## Pilot scope

The proposed pilot is a local project board with persistent accounts, protected
sessions, projects and tasks, a browser UI, ownership checks, task state updates,
and an activity record. It includes setup/migration instructions, automated
tests and security/QA reports. Backend task endpoints and the frontend task board
can be developed independently after their common contract is approved.

Pilot criteria: PB-001 account/session access; PB-002 persistent owned projects;
PB-003 task creation and updates; PB-004 browser primary workflows; PB-005
cross-user denial; PB-006 meaningful automated and security checks; PB-007 safe
parallel integration and restart recovery; PB-008 reproducible delivery with
traceability. Billing, production email, external notifications, public hosting
and purchases are outside pilot scope. Pilot human acceptance remains a real
operator action even after this factory blueprint is approved.

## Constraints and dependencies

The current folder has no Git checkout or executable runtime. Implementation must
retain original assets and attribution. Operator-approved provider access,
resource limits, container images/toolchains, and a continuously available host
are dependencies for a live unattended run. Initial host targets are macOS and
Linux. Credentials, paid infrastructure, publication and production deployment
are not implicitly authorized by this document.
