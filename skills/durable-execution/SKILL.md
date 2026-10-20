---
name: durable-execution
description: "Handle factory attempt checkpoints, fresh sessions, leases, bounded retries and restart recovery."
---

# Durable Execution

Restore from protected state: approved blueprint/policy, task assignment, dependencies, immutable source, attempt history, trusted failures, unresolved findings and remaining capacity. Load only the context needed for the current assignment.

Heartbeat the current lease through trusted supervision. Fencing prevents an abandoned worker publishing after replacement. Preserve completed effects in the operation journal; reconcile before retrying them. A process failure, provider outage and code defect need different diagnoses.

Use bounded alternative repair strategies and fresh sessions rather than indefinite repetition. Preserve failed candidate checkpoints and verification evidence. Exhaustion blocks the affected task; independent eligible work continues. Only the scheduler replaces workers or revises ownership. Never forge a heartbeat, approval or completion record from an agent response.

Read [the runtime contract](../../docs/RUNTIME_CONTRACT.md) for proposal and authority boundaries and [the operating guide](../../docs/AUTOPILOT.md) for actual commands and compatibility limits.
