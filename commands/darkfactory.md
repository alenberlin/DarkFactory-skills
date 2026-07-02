---
description: Engage the full Dark Factory lifecycle for this project — discovery, then an autonomous build → test → fix → review loop — driven by the orchestrator.
---

Engage the Dark Factory workflow for this project, treating the following as initial context for discovery:

$ARGUMENTS

Read the orchestrator at `ORCHESTRATOR.md` in the root of the Dark Factory pack (when installed as a plugin, `${CLAUDE_PLUGIN_ROOT}/ORCHESTRATOR.md`) and follow it end to end.

First, record engagement so the gate will not ask again here: ensure a `.darkfactory` file in the project root contains `engage`. Then start at the orchestrator's **On entry** step — resume from an existing blueprint and progress ledger if one is present, otherwise begin Phase 0 (discovery).

The blueprint is the single approval gate. Once you approve it, the loop runs autonomously under the orchestrator's escalation rules — pausing only when a decision is genuinely required, a milestone that later work depends on fails past its retry budget (independent ones are marked blocked and the loop continues), or an action is irreversible or reaches outside the workspace.
