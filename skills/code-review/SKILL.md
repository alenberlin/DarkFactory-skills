---
name: code-review
description: Reviews a change across five axes — correctness, readability, architecture, security, performance — and reports findings by severity without auto-fixing. Use before merging any change, whether written by you, another agent, or a human.
---

# Code Review

## Overview

Building is done when the code is *correct*, not when it runs. Code that runs can still drift from the architecture, bypass the design system, or miss the edge case that matters. This skill reviews across five axes and reports honestly by severity. It **does not fix** — fixing without the developer's decision buries problems instead of surfacing them.

## When to Use

- Before merging any change to a shared branch
- Reviewing code from yourself, another agent, or a teammate
- After a feature is built, before moving to the next one

**When NOT to use:** as a substitute for tests (it complements `test-driven-development`, doesn't replace it). Don't review code you're mid-way through writing — review at a natural stopping point.

## Step 1 — Establish the benchmark

You can't verify correctness without knowing what correct is. Read, in order: the plan from `architect` (if any), the task/feature description, and relevant context (architecture boundaries, code standards, design rules). If there's no stated intent, ask for it before reviewing.

## Step 2 — Review the five axes

Read the tests first — they reveal intent and coverage.

1. **Correctness** — Does it do what the task says? Edge cases handled (null, empty, boundary, error paths)? Do the tests actually verify the behavior? Any race conditions or off-by-ones?
2. **Readability** — Could another engineer understand this without explanation? Descriptive, convention-matching names? Straightforward control flow?
3. **Architecture** — Follows existing patterns, or introduces a new one without justification? Boundaries respected (no DB calls in components, no UI logic in API routes)? Right abstraction level — not over-engineered, not too coupled? Dependencies flowing the right way?
4. **Security** — Untrusted input validated at boundaries? Secrets out of code/logs? Authz checked where needed? Queries parameterized, output encoded? (Deep dive: `security-and-hardening`.)
5. **Performance** — N+1 queries? Unbounded loops or fetches? Sync work that should be async? Missing pagination? (Deep dive: `performance-optimization`.)

## Step 3 — Report by severity

Categorize every finding. Cite `file:line` and give a concrete fix recommendation for anything Critical or Important.

- **Critical — fix before merge:** security holes, data-loss risk, broken functionality, architecture violations that will break future work, silent-failure error handling, planned functionality missing.
- **Important — fix soon:** missing tests, wrong abstraction, design-system drift, edge cases a real user will hit, standards violations that compound.
- **Suggestion — when convenient:** naming, optional optimizations, style that doesn't affect behavior.

```markdown
## Review — [Feature]
**Verdict:** APPROVE | REQUEST CHANGES
**Overview:** [1–2 sentences]

### Critical
- [file:line] [problem → recommended fix]
### Important
- [file:line] [problem → recommended fix]
### Suggestions
- [file:line] [note]
### Done well
- [at least one specific positive]
```

## Step 4 — Let the developer decide

Stop after the report. Don't start fixing, and don't suggest fixes beyond the recommendations unless asked. Wait for the developer to fix, to mark something intentional, or to confirm it's ready. The developer owns the quality decision; the review informs it. (For thorough or pre-merge reviews, this skill is also embodied by the `code-reviewer` persona, which `/review` and `/ship` invoke in a fresh context.) In an unattended orchestrator run there is no developer mid-loop: the orchestrator acts on Critical and Important findings itself and records Suggestions — see the pack's `ORCHESTRATOR.md`.

## Red Flags

- "It works" treated as "it's correct"
- Reviewing without knowing what the change was supposed to do
- Findings with no severity and no `file:line`
- Auto-fixing during review instead of reporting
- A review with zero positives (specific praise reinforces good patterns)
- Approving a change that carries a Critical finding

## Verification

- [ ] Intent/benchmark established before reviewing
- [ ] All five axes covered
- [ ] Tests reviewed first, for intent and coverage
- [ ] Every finding has a severity; Critical/Important have a fix recommendation
- [ ] No fixes were applied — the developer decides
