---
name: factory-control
description: "Operate an existing DarkFactory runtime: inspect, start, pause, resume, cancel and report approved factory projects."
---

# Factory Control

Read actual project state through factory status/report or the authenticated administrative API. Use the recorded blueprint digest, policy version, permissions, limits, task DAG and blockers. A .darkfactory marker opts into skill routing; it does not authorize runtime actions.

Propose with factory propose, present the complete blueprint and exact digest, then have the human invoke protected approval. Start only after approval and successful environment admission. The worker must be run as a separate supervised process for continuity beyond the chat. Do not claim that an interactive session is a daemon.

Use factory init to prepare credential-free configuration proposals. Use factory run for an explicitly attached Advisory or Enforced session; the unattended worker remains Strict-only. A foreground quality warning cannot manufacture final delivery evidence. Check current correction records and adapter/check diagnostics when resuming work.

Pause stops new claims and allows bounded current work to reach a safe checkpoint. Cancellation fences integration; retain diagnostics and work. Resume uses current records, not a new discovery interview. Deployment, publication and messaging are separate operations. Report blockers and measured progress; keep acceptance pending for the human.

Read [the runtime contract](../../docs/RUNTIME_CONTRACT.md) for proposal and authority boundaries and [the operating guide](../../docs/AUTOPILOT.md) for actual commands and compatibility limits.
