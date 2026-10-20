# Autopilot implementation progress

Blueprint v1 was explicitly approved in this chat, including local commits
inside isolated test-fixture and pilot repositories. The approved document
digest is `7b2db21dbf8b6dd49fd0c2e9180006c3e919f6c743e84085dd82bebe11116407`.
The frozen blueprint documents and original proposed manifest remain unchanged;
this progress note is not a runtime approval credential.

The requested workflow/architecture diagram is in [TAM.md](TAM.md).

| Task | State | Evidence |
| --- | --- | --- |
| T01 Foundation | Locally verified | Locked Python/Node tooling, lint/typecheck/test/build and installed-wheel smoke |
| T02 Contracts and policy transitions | Implemented; local checks recorded | Closed schemas, coverage/DAG/mode and phase tests; unattended modes are explicitly limited |
| T03 Protected state/approval/audit | Implemented; local checks recorded | Real database reopen, authenticated exact approval/replay checks, audit tampering and usage reconciliation |
| T04 Execution/gateway boundary | Implemented; live certification separate | Real isolation, alternate-shell/resource/API/gateway probes; vendor service and kernel-compromise certification not claimed |
| T05 Immutable verification | Implemented; local checks recorded | Actual failing/passing/marker/read-only/separate-driver checks, baseline protection and stale-evidence denial |
| T06 Native adapters | Implemented; live conformance separate | Actual Claude Code/Codex offline protocols, bounded/redacted diagnostics and abandoned-call reconciliation; vendor sessions pending |
| T07 Scheduler/recovery/budgets | Locally verified; operational cases open | Actual worker kill/restart/client exit, leases, checkpoints, orphan cleanup and conservative reservations |
| T08 Skills/roles/commands | Locally verified | 24 validated skills, 14 registered roles, seven commands, preserved attribution and hook opt-in tests |
| T09 Discovery/planning | Locally verified with fixture agents | Questions/artifacts/source context, invalid-reply repair and interrupted proposal recovery; live planning pending |
| T10 End-to-end slice | Locally verified with fixture agents | Exact approval → real source/checks/reviews/Git → delivery → human acceptance |
| T11 Review/remediation | Implemented; semantic trial separate | Separate reviews, persistent findings, scoped human exceptions/revocation and bounded re-verification; real vulnerability judgment pending |
| T12 Parallel integration | Locally verified; live cases open | Actual concurrent scoped tasks, merged checks, conflicts, interrupted Git and killed-worktree cleanup |
| T13 Language profiles | Implemented; local checks recorded | Python, Node.js/TypeScript, Rust and combined Node/Rust test/type/lint/build, negative behavior and missing-tool admission |
| T14 CLI/API/dashboard | Implemented; local checks recorded | Shared services/OpenAPI, keyboard/axe/mobile/browser correction/acceptance and error recovery; real assistive-technology/Linux operation untested |
| T15 Delivery/acceptance/corrections | Implemented; product acceptance separate | Exact revision/review/check gates, separate correction tasks, complete exports and required source setup/runbook; real product documentation accuracy needs human review |
| T16 Adversarial/recovery matrix | Local matrix expanded | Actual process, container, disk, Git, redaction, runner protection and API probes; exact A01–A15/P01–P10 boundaries in EVIDENCE.md |
| T17 Live project-board pilot | Pending by operator choice | Prepared pilot intake; no app or provider run substituted with a fixture |
| T18 Reproducible delivery | Local package verified; final acceptance open | Operating guide, bundled resources, clean install and validation evidence; depends on mandatory open cases and T17 |

The operator selected **build and validate locally first; leave the live pilot
pending** on 2026-10-10. [EVIDENCE.md](EVIDENCE.md) maps every factory requirement,
NFR, acceptance scenario and bypass scenario to its actual local evidence and
remaining boundary. Generated evidence records the tested source and commands.

The implementation handoff is determined by the fresh source-bound PASS record.
The frozen blueprint’s real-project/live acceptance remains open. “Locally verified” names
the tested local behavior and does not claim full Strict certification, actual
vendor compatibility, live product quality, OS reboot or final human acceptance.

## Completion after the operator's request

[COMPLETION_PLAN.md](COMPLETION_PLAN.md) records the implementation slices.
The local implementation now includes all-mode attached execution, separate human
correction tasks, scoped finding exceptions, durable aborted-operation diagnostics,
bounded context, strengthened runner/redaction boundaries, optional kernel-bounded
state volumes, operator setup generation and required delivery documents.
[Getting started](../GETTING_STARTED.md) gives the operator path from local checks
to their first real-project trial. Actual check outcomes, exact source identity
and host/toolchain metadata are in [local-validation.json](evidence/local-validation.json).
No global install/service, real provider access, source commit or deployment occurred.
