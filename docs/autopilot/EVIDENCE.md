# Local verification and remaining coverage

Status: implementation and local engineering evidence; real-project acceptance remains open.
The source-bound validation record below determines whether the current handoff passes.
The operator explicitly requested local validation first and left the live pilot
pending on 2026-10-10. Offline agent fixtures are identified in test classes and
reports. Native CLI protocol tests use actual Claude Code/Codex processes and
canned model responses, not a vendor service or live reasoning.

The generated [local validation record](evidence/local-validation.json) records
the exact tested source scope, commands, exit statuses, image IDs and test counts.
The [JUnit report](evidence/pytest.xml) preserves individual test results.
[Browser results](evidence/browser-tests.json) and [desktop](evidence/dashboard-desktop.png)/
[mobile](evidence/dashboard-mobile.png) captures show a disposable fixture after
approval, execution, a separate correction task and re-verification. The browser
test then records actual human-channel acceptance and verifies the audit chain. This is
not acceptance of the factory upgrade or the pending pilot.

## What local checks exercise

- Schema/DAG/coverage validation, exact approval identity, replay refusal,
  API authentication/Origin/Host controls and safe validation errors.
- Actual non-root Docker processes, read-only system/source checks, no target
  egress, bounded output/time, immutable snapshots and protected drivers.
- Actual Python/Node.js/TypeScript/Rust passing and failing programs, all
  four profile checks, combined Node.js/Rust eight-check execution and missing-tool admission; actual native CLI structured-output protocols offline.
- Real supervisor and worker SIGKILL, orphan resource cleanup, expired leases,
  fresh fencing, checkpoint recovery and independence from an exited CLI client.
- Actual concurrent task execution, three-way Git merges, merge verification,
  unpublished conflicts, initial-repository interruption and interrupted ref
  publication reconciliation.
- Journaled scratch-worktree cleanup refuses active ownership; a real killed
  worktree owner releases its OS lock and recovery cleans only its recorded copy.
- Persistent blocking findings, explicit independent repair verification,
  final-QA correction cycles, protected baseline deletion/weakening refusal,
  unknown usage reconciliation and concurrent resource reservation bounds.
- Transactional discovery questions/stages, existing-source context, bounded
  invalid-reply repair and idempotent proposal recovery without self-approval.
- Current approval/latest review checks at acceptance, separately recorded criterion-linked
  human correction tasks, exact-source finding exceptions/revocation and complete exports.
- Durable interrupted-check/native-adapter records, redaction before persistence,
  actual skipped/empty test refusal and protected runner/config substitution refusal.
- Actual kernel disk exhaustion on a bounded APFS state volume, missing-mount refusal,
  actual container CPU/memory/scratch bounds and alternative-shell host/state denial.
- Credential-free operator setup for four profiles, bounded assignment rehydration,
  full protected input inspection, WAL connection lifecycle and approval compatibility.
- Real browser keyboard/refresh-race/network-error/correction/acceptance flow,
  automated WCAG 2/2.1 A/AA checks at two widths, mobile overflow checks and screenshots.
- Pack registration/frontmatter, public API docstrings, build and clean installed-wheel
  resources/CLI smoke checks.

Visual QA preserved the existing design and inspected desktop/mobile captures.
The static visual detector could not resolve the API-mounted `/assets/style.css`
from the source folder and warned about a default 16px heading hierarchy. That
incomplete detector result is not counted as a pass; actual stylesheet sizes and
rendered browser captures were inspected. Browser/axe checks remain the recorded
automated accessibility evidence, with no real screen-reader session claimed.

## Blueprint acceptance scenarios

“Local pass” means the specifically named offline operation passed. “Partial”
means some required boundaries remain unexercised. Neither means live readiness.

| ID | Local evidence | Remaining boundary |
| --- | --- | --- |
| A01 | Discovery fixture: adaptive question, artifacts, schema, repair and recovery | Actual live intake/planning and product-quality judgments |
| A02 | Local pass: implementation denied before exact approval and permitted afterward | Live pilot execution |
| A03 | Local pass: separate worker finishes after status CLI exits | Installed OS supervisor continuity |
| A04 | Actual native CLI requests a delayed offline provider; supervisor SIGKILL preserves an ABORTED record, live owner is protected, timeout is recorded and recovery is idempotent | Real vendor usage and billing recovery |
| A05 | Local pass: real SIGKILL/restart, ownership and Git recovery | Actual machine reboot/service restoration |
| A06 | Local protocol: a fresh worker uses persisted source/checkpoints; bounded inputs retain full protected references | Actual model context exhaustion/session replacement |
| A07 | Local pass: wrong real programs fail; source repairs and renewed evidence pass | Live agent discovers/repairs the nontrivial pilot defect |
| A08 | Local protocol: blocking security findings persist; explicit re-verification or scoped audited human exception is required | Real pilot vulnerability detection and repair |
| A09 | Local pass: two concurrent Engine tasks, separate ownership, merged checks and actual Git conflict refusal | Live product parallel work and conflict repair |
| A10 | Local pass: a blocked Engine task leaves an independent task running through real verification/integration; its dependent task stays unscheduled | Live blocked dependency demonstration |
| A11 | Partial: path/contract/approval boundaries and material questions stop affected tasks | Independent live semantic scope assessment |
| A12 | Local pass: revision/authentication/check/review/finding acceptance gates and browser correction flow | Actual pilot human acceptance |
| A13 | Local boundary tests: no-egress/host isolation, alternate shell/state/ref/secret-path probes, API/gateway and release-request denial | Native-image direct Git binary is absent; live semantic attacks and kernel compromise are not certified |
| A14 | Local boundary tests: concurrent reservations, unknown-charge block, storage admission, actual APFS ENOSPC, cgroup CPU/memory and scratch bounds | Actual vendor charges/exhaustion; Linux deployment |
| A15 | Partial: bounded attempts, blocked questions/findings and honest reports | Live foundational failure/outage recovery |

## Policy bypass scenarios

| ID | Actual coverage | State |
| --- | --- | --- |
| P01 | Coordinator refuses publication without trusted checks; exit/markers and required tests checked | Local pass |
| P02 | Only trusted check execution writes gate evidence; arbitrary reply success has no authority | Local pass for current fixture boundaries |
| P03 | Policy/approval content hashes and extra-field rejection; workspace is outside authority | Local path/identity denial; trusted-host tampering remains outside the model |
| P04 | Actual protected baseline test deletion/weakening, immutable driver and no-op marker failure | Local pass: common runner/manifest substitution protected; custom project paths still require approval review |
| P05 | Authoritative refs exist only in controller-managed repositories; worker receives source copies | Local filesystem denial through alternate shell; no Git executable in the native fixture image, so no direct-container-Git claim |
| P06 | No release adapter/credentials; permission does not grant deployment | Local pass: unauthorized deployment route returns 404 and creates no operation; deployment remains unsupported |
| P07 | Native gateway fixture: vendor key absent from agent environment and unsupported routes/egress denied | Local cross-project/host-path denial and nested persistence redaction; no host-administrator guarantee |
| P08 | Actual authenticated API rejects fake identity, replay and stale approval; host path absent in container | Local pass for exercised boundaries; no host-administrator guarantee |
| P09 | Real container filesystem/network restrictions and scoped argv/file proposals | Local alternate-shell host/state/ref denial and protected runner cases; native Git binary absent |
| P10 | Source/definition/policy/image identities; stale evidence and interrupted integration tests | Local pass for exercised recovery cases |

## Requirement traceability

The following maps every factory requirement to actual local modules/tests and
its practical limit. It does not convert a partial requirement into a pass.

| Requirements | Evidence | Limit/state |
| --- | --- | --- |
| FR-001, FR-008 | 24 skills, 14 roles, seven commands, pack validation and role bindings | Local pack complete; live role routing pending |
| FR-007 | Approved Engine execution, scope/path guards and material-question blocking test | Local scoped autonomy passed; live semantic judgment pending |
| FR-002–FR-005 | Discovery/domain/contract tests, approved planning documents, DAG/check coverage | Local protocol/profile/required-document gates passed; live generated product artifacts pending |
| FR-006 | Store/API/Engine approval tests and browser approval action | Local pass |
| FR-009 | Engine/remediation tests use real candidates/checks and separate fixture reviews | Live autonomous implementation/reasoning pending |
| FR-010–FR-012 | Store ownership/DAG tests, concurrent Engine, actual Git and killed-worktree cleanup tests | Local pass for exercised cases; live conflict repair pending |
| FR-013–FR-016 | Real killed-process/restart/client-exit tests, checkpoints, resource journal, limits | Bounded context and abandoned-check/native-call reconciliation implemented; actual native context exhaustion/outages and OS reboot unexercised |
| FR-017, FR-018 | Closed domain contracts, protected policies, state phases and evidence hashes | Local pass for exercised transitions; full transition/failure matrix pending |
| FR-019, FR-020 | Docker/native gateway probes, explicit quality modes and fail-closed admission | Attached Advisory/Enforced supported; unattended Strict only. Arbitrary target egress remains refused; no universal Strict certification |
| FR-021, FR-022 | Real check/process records, protected drivers, source/definition/policy/image binding | Abandoned check/adapter intents reconcile to explicit aborted diagnostics under released owner locks; vendor effects can remain unknown |
| FR-023, FR-024 | Separate review attempts, persistent findings, explicit resolution and bounded final-QA repair | Scoped human exception/revocation and preserved adverse history tested; semantic vulnerability detection requires real-project trial |
| FR-025, FR-026 | Protected state/mounts, approvals, audit chain, API identities and latest acceptance review | Trusted host owner outside threat model; audit tail is not externally anchored |
| FR-027 | Conservative model reservations, ledger accounting/unknown reconciliation, storage/process bounds | Optional kernel-bounded filesystem admission and actual macOS APFS exhaustion tested; actual vendor charges and Linux operation pending |
| FR-028 | Actual Claude Code 2.1.179/Codex 0.139.0 offline wire protocols | Structured redacted exit/timeout/output/protocol/aborted diagnostics implemented/tested; actual vendor service/live compatibility pending |
| FR-029 | Actual Python/Node.js/TypeScript/Rust behavior and test/type/lint/build | Combined Node/Rust eight-check fixture and missing-tool admission tested; product frameworks require actual provisioned dependencies/checks |
| FR-030, FR-031 | Shared services, generated OpenAPI, authenticated API and actual dashboard workflow | Loopback only; CLI exports source, API report is not a source ZIP |
| FR-032 | Exported artifacts, preserved planning documents, wheel and operating guide | Nonempty product README/runbook required by default; semantic accuracy requires actual product review |
| FR-033, FR-034 | Human revision acceptance, current approval/latest review, criterion-linked correction/re-review | Human requests create separate scoped TaskSpecs and preserve originals/attempts; renewed real checks/reviews exercised |
| FR-035 | Prepared [pilot intake](../../examples/pilot/GOAL.md) | Pending at operator request; no app or live run is claimed |
| FR-036 | Full local checks and this explicit acceptance/bypass/requirement matrix | Source-bound local engineering run plus explicit live/platform/semantic limits; real-project human acceptance remains open |

| NFR | Evidence | Remaining verification |
| --- | --- | --- |
| NFR-001 Correctness | Transactions, schemas, leases, coordinator gates and real integration tests | Complete failure/transition matrix and live product correctness |
| NFR-002 Security | Actual isolation/gateway/API probes and source/evidence identity | Full adversarial/security review; no container/kernel compromise guarantee |
| NFR-003 Reliability | Real process termination, client exit, checkpoint/Git/discovery reconciliation | OS reboot, provider outages and native session replacement |
| NFR-004 Maintainability | Strict mypy, Ruff, cohesive modules, locked build and public docstrings | Public runtime surfaces have Google-style API docstrings; strict mypy/Ruff and installed-package checks enforce the local contract |
| NFR-005 Accessibility | Semantic labeled dashboard controls and actual browser workflow | Keyboard/axe/mobile/desktop browser checks and visual inspection performed; real assistive-technology session not performed |
| NFR-006 Resources | Reservations, shared bulk-storage admission, container time/output/CPU/memory settings | Actual APFS exhaustion, container CPU/memory/scratch tests; Linux quota provisioning/operation not exercised |
| NFR-007 Privacy | No inherited personal configs; synthetic credential fixtures; safe API validation | Nested JSON/header/URL/key redaction and alternate-shell/host-path probes tested; no claim of exhaustive semantic injection resistance |
| NFR-008 Portability | macOS arm64/Docker Desktop and three language toolchains; supervision templates | Actual Linux service deployment and reboot not performed |

## Remaining work and operational boundaries

The live project-board pilot, live provider credentials/model/limits and real
provider conformance remain pending by explicit operator choice. No real API key
was enrolled, existing personal CLI credentials were not read/copied, and no
live provider call or spending occurred.

Implementation intentionally preserves unrecognized/initialization staging rather than
silently deleting it. Target network allowlists, remote multi-user hosting, release
adapters and unattended non-Strict execution remain unsupported and fail closed.
Whole-state kernel bounds are optional and must be explicitly provisioned/approved;
ordinary storage admission alone is not a kernel quota. The audit chain is local,
not externally anchored. Discovery interrupted by unknown usage requires an explicit
operator accounting observation before inference can continue.

These are documented operating boundaries, not simulated implementations. The local
implementation is ready for a real-project trial only when the fresh validation
record reports PASS for unchanged source. The complete frozen blueprint's live
acceptance scenarios are **not claimed complete or release-certified**. No source
repository commit, remote publication, service installation, reboot or deployment
was performed. The original frozen blueprint and proposed manifest are preserved.
