# Completion work after local validation

The operator authorized completion of the remaining implementation on 2026-10-19.
The approved version-1 blueprint remains immutable. This checklist implements its
existing requirements; it does not grant runtime approval, credentials, live
inference, source commits, service installation, release, or final acceptance.

| Slice | Approved scope | Completion evidence |
| --- | --- | --- |
| C01 Workflow contracts | FR-020, FR-023, FR-034: foreground Advisory/Enforced execution, revision-scoped human finding exceptions, separately recorded corrective tasks | Real service/CLI transitions, no unattended downgrade, stale/forged exception rejection, preserved correction history |
| C02 Failure and resources | FR-014, FR-021, FR-025, FR-027, FR-028: interrupted-check reconciliation, structured adapter diagnostics, bounded/redacted persistence and resource exhaustion | Actual killed processes, failed protocols and concurrent allocation tests; preserved failures and unknown charges |
| C03 Integrity and recovery | FR-019, FR-022, FR-025, FR-029, FR-036: runner/config protection, bypass/injection cases, mixed toolchains and missing capabilities | Actual filesystem, Docker, Git, HTTP and process boundary tests; explicit unsupported configurations |
| C04 Operator delivery | FR-024, FR-030–FR-032: usable configuration examples, dashboard keyboard/error behavior, complete exports and operating instructions | Schema-valid examples, browser/keyboard/accessibility checks, installed-package resources and command smoke |
| C05 Engineering handoff | T18, FR-036: consistent skills/runtime documentation and fresh full validation | Narrow regression tests first, full lint/typecheck/tests/build/install, source-bound evidence and requirement matrix |

The operator will conduct the real-project trial and human acceptance after the
local engineering handoff. Actual vendor authentication, live model quality,
provider charges, OS service installation and real reboot remain separately
identified operator-dependent observations, never simulated passes. Optional
network acquisition routes and platform capabilities must fail closed when not
supported. Resource admission is distinguished from a kernel filesystem quota;
any claim of an OS-enforced quota requires an actual supported, verified volume.

Implementation for C01–C05 is present. Completion is established by a fresh
`evidence/local-validation.json` PASS with unchanged source, passing Python/browser
suites, lint/typechecks and clean wheel installation. Individual coverage and
operator-dependent acceptance are recorded in [EVIDENCE.md](EVIDENCE.md).

| Slice | Implemented regression evidence |
| --- | --- |
| C01 | `test_foreground_modes.py`, `test_corrections_and_exceptions.py`, actual browser correction/acceptance |
| C02 | `test_check_recovery.py`, `test_adapter_diagnostics.py`, `test_adapter_recovery.py`, `test_integrity_matrix.py`, `test_state_volumes.py` |
| C03 | `test_integrity_matrix.py`, `test_required_test_execution.py`, `test_context_rehydration.py`, `test_profiles.py` and existing Git/gateway/recovery suites |
| C04 | `test_operator_setup.py`, browser keyboard/axe/mobile/error checks, installed-wheel resources and CLI smoke |
| C05 | `scripts/verify_local.py`, generated schemas, pack validation, operating/setup/traceability guides and frozen-manifest checks |
