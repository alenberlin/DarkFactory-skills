---
name: quality-assurance
description: "Verify complete factory product journeys, negative cases and operational behavior against the running delivery."
---

# Quality Assurance

Start from approved journeys and requirement IDs. Exercise the actual product with realistic data: primary flows, boundaries, empty/loading/error states, permissions, persistence, restart and accessible interaction. Inspect API and UI together where both exist.

Use protected black-box drivers for critical observable behavior, separate from the generated application process. Unit tests importing application code complement this evidence but cannot establish that an untrusted process did not bypass its own runner. Retain real failures and screenshots/observations with source/environment identities.

Return examined and unexamined areas, criterion-linked findings and reproductions. Do not rewrite the implementation during your review attempt or certify unavailable flows. Blocking findings require repairs and renewed trusted verification. Final QA precedes READY_FOR_HUMAN_ACCEPTANCE.

Read [the runtime contract](../../docs/RUNTIME_CONTRACT.md) for proposal and authority boundaries and [the operating guide](../../docs/AUTOPILOT.md) for actual commands and compatibility limits.
