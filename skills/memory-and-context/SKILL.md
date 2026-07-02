---
name: memory-and-context
description: Preserves and restores working context across sessions, and records decisions that future work depends on. Use at the end of a session to save state, at the start to restore it, and whenever an architectural decision should outlive the conversation. Never persists secrets.
---

# Memory and Context

## Overview

An agent starts every session blank. Without a deliberate handoff, hard-won context — what was built, what was decided, what to do next — is lost, and the next session re-derives or re-breaks it. This skill is the handoff: save the essential state at the end, restore it at the start, and record durable decisions as lightweight ADRs. It also governs what context to *load* so quality doesn't degrade from a cluttered or empty working set.

## Security Boundary

**Never persist secrets.** API keys, tokens, passwords, private keys, cookies, connection strings, auth headers — none of these go into saved memory. If a value is useful but sensitive, store a redacted placeholder (`[REDACTED_API_KEY]`). When unsure, treat it as sensitive and omit it. Run a final scrub pass before writing anything to disk.

## Save — at the end of a session

Capture only what a skilled colleague who knows nothing about today would need to continue. Not a transcript — the essential state. Store memory as **one file per session** under `.memory/` (e.g. `.memory/2026-06-15-auth.md`), and keep a one-line pointer in `.memory/INDEX.md`. Per-file, append-only — never overwrite history into a single clobbered file.

Capture:
- **What was built** — specific files/features, precisely. Not "the auth flow" but "added `app/(auth)/login/page.tsx`, `callback/page.tsx`, `middleware.ts`; OAuth with Google working end to end."
- **Decisions made** — choices future work depends on, and why.
- **Problems solved** — anything that took real effort, so it isn't re-solved. ("Auth callback needs a trailing slash in the redirect URL.")
- **Current state** — what works, what's partial, what's known-broken.
- **Next step** — the specific first action for the next session.
- **Open questions** — unresolved items.

Don't capture what the code/git already shows, or how something was built (only what and why).

```markdown
# Memory — [Feature]  ·  [date]
## Built        …    ## Decisions   …    ## Problems solved  …
## State        …    ## Next         …    ## Open questions   …
```

## Restore — at the start of a session

Read the latest `.memory/` file and `INDEX.md`, plus existing project context files (`CLAUDE.md`, `.cursor/rules/`, `AGENTS.md`, etc.) — only those, don't crawl the repo. Then summarize what was restored and **confirm before continuing**:
```
Restored. Last session: [built]. State: [works now].
Decisions locked: [...]. Next up: [...]. Correct? (yes / fix anything off)
```
In an unattended run under an approved blueprint (see the pack's `ORCHESTRATOR.md`), the summary is informational — state it and continue; the blueprint approval stands in for confirmation. Never surface a raw secret from restored context — summarize in redacted form. If memory is missing or unclear, say exactly what's absent and let the developer decide whether to proceed.

## Record — decisions worth keeping (ADR-lite)

When a decision is architectural, hard to reverse, or future-load-bearing, record it as a short ADR in `docs/adr/` so the *why* survives past the conversation:
```markdown
# ADR-007: Server-side data fetching for the dashboard
Status: accepted · Date: 2026-06-15
Context: client fetching caused loading-state sprawl and leaked query logic.
Decision: fetch on the server; pass data down as props.
Consequences: no client loading states; SSR cost per request; revisit if it becomes interactive.
```

## Load — keep context clean

Right context, right time. Load what the current task needs; don't drag stale, irrelevant context that dilutes attention. If output quality is degrading mid-session, that's the signal to prune and re-anchor on the task.

## Red Flags

- A single `memory.md` overwritten each session (history lost)
- Any secret or credential-like value written to memory
- Restoring and charging ahead without confirming the summary
- Decisions made in chat and never recorded — re-litigated next month
- Loading the whole repo "for context" and drowning the actual task

## Verification

- [ ] Memory saved as a per-session file, not an overwrite
- [ ] A secret-scrub pass ran before writing; nothing sensitive persisted
- [ ] Restore was confirmed with the developer before work continued (in an unattended run: stated, with the approved blueprint standing in)
- [ ] Durable decisions captured as ADRs, not left in the transcript
- [ ] Only relevant context was loaded for the task
