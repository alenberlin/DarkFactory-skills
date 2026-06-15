---
name: git-and-shipping
description: Structures commits and releases — atomic history, then a safe path to production with a pre-launch check and rollback plan. Use when committing, branching, or preparing to deploy. Use when you need quality gates and a way back if a release goes wrong.
---

# Git and Shipping

## Overview

History and releases are both about reversibility. A clean commit history lets you understand, bisect, and revert one change without unpicking ten. A safe launch lets you ship confidently because you can roll back fast. The two halves of this skill share one principle: **make every step easy to undo.** Faster is safer when each step is small and recoverable.

## When to Use

- Committing or branching any change
- Resolving conflicts or organizing parallel work
- Preparing a deploy, setting up gates, or planning a rollout

**When NOT to use:** as a substitute for review/tests — those gate *what* ships; this gates *how* it ships. Run them first.

## Part A — Git Workflow

### Atomic commits
One logical change per commit. A commit should be revertible on its own without dragging unrelated work with it. If the message needs "and," it's probably two commits.

### Messages that explain *why*
Subject in the imperative ("Add retry to upload handler"), body for the reasoning the diff can't show. The code says what changed; the message says why.
```
Fix race in task completion

completeTask read state before the prior write committed, so the
UI showed a stale status. Await the write before reading back.
```

### Branching and history
Short-lived feature branches off the default branch; never commit straight to a protected branch. Keep history readable — small, ordered commits that tell the story of the change. Resolve conflicts by understanding both sides, not by blindly taking one.

### Commit hygiene
Don't commit secrets, generated artifacts, or `.DS_Store`/logs (keep `.gitignore` honest). Commit or push only when asked; if on the default branch, branch first.

## Part B — Shipping and Launch

### Pre-launch checklist
Before deploying: tests green in CI, `code-review` clean, `security-and-hardening` pass for anything sensitive, migrations tested and reversible, config/secrets present in the target environment, and feature flags set as intended.

### Quality gates in CI
Automate the gates so they don't depend on memory: lint, type-check, tests, and build run on every change; a red gate blocks merge. This is the enforcement layer for everything the other skills ask for.

### Staged rollout + rollback
Prefer a staged release (canary / small percentage → full) over a big-bang flip. **Write the rollback plan before deploying**, not during the incident: how to revert (redeploy previous build, flip the flag, run the down-migration) and the symptom that triggers it.

### Watch after you ship
A deploy isn't done at "deployed" — it's done when you've confirmed healthy. Watch error rate, latency, and key metrics for the rollout window. Instrument enough to *know* it's working (structured logs, a few RED metrics, a symptom-based alert), not just hope so. Record any non-obvious decision via `memory-and-context` (ADR-lite).

## Red Flags

- A commit mixing unrelated changes, or a message that only restates the diff
- Committing to a protected branch directly, or committing secrets/artifacts
- Deploying with red or skipped CI gates
- No rollback plan written before the deploy
- A big-bang release of a risky change with no canary
- "Deployed" treated as "done" with no post-deploy watch

## Verification

- [ ] Each commit is atomic and explains why, not just what
- [ ] No secrets/artifacts committed; `.gitignore` covers them
- [ ] CI gates (lint, types, tests, build) are green
- [ ] Migrations are tested and reversible
- [ ] A rollback plan exists, with the trigger symptom named
- [ ] Post-deploy health was confirmed, not assumed
