---
name: debugging-and-recovery
description: Diagnoses what kind of failure you're facing before responding, then fixes by root cause. Use when tests fail, builds break, behavior is wrong, or repeated fix attempts are making things worse. Use when you need a systematic path instead of guessing.
---

# Debugging and Recovery

## Overview

When something breaks, the instinct is to keep prompting for fixes — and each broken fix pollutes the context and makes the next one worse. The first job is not to fix; it's to **diagnose what type of failure this is.** Not every problem is a bug, and not every bug should be debugged. Three failure modes need three different responses, and choosing the wrong response is most of the wasted effort.

## When to Use

- A test fails, a build breaks, or behavior doesn't match expectations
- You've tried to fix something and it's getting worse, not better
- You're not sure whether to fix, restart, or rethink

**When NOT to use:** a clear, one-step error with an obvious fix you can verify immediately (just fix it). This skill is for when the path isn't obvious or the session is drifting.

## Step 1 — Describe the failure precisely

Before touching anything, establish: what was expected, what happened instead, and **how many times it's already been "fixed."** That attempt count is the key signal — a fresh problem and a session that's gone three rounds deep need opposite responses.

## Step 2 — Identify the failure mode

| | **Mode 1 — A specific thing is broken** | **Mode 2 — The session has gone wrong** | **Mode 3 — The foundation is wrong** |
|---|---|---|---|
| Signs | Isolated to one unit; rest works; 1st–2nd attempt; clear error | Multiple fixes made it worse; fixes patching fixes; unclear what the original bug even was | Code runs but is fundamentally wrong; built on a misunderstood requirement, API, or pattern |
| Meaning | A normal bug with a findable root cause | Context is polluted; more prompting compounds damage | Not a bug — the approach itself is wrong |
| Response | **Targeted fix** (3A) | **Hard reset** (3B) | **Rethink** (3C) |

State the mode and why before proceeding: *"This is Mode 2 — three fix attempts have each introduced a new problem and the original symptom is now unclear."*

## Step 3A — Targeted fix (Mode 1)

1. **Reproduce.** Get a reliable repro — ideally a failing test (`test-driven-development`). A bug you can't reproduce isn't diagnosed.
2. **Localize.** Read only the directly relevant code. Binary-search the problem space; don't read the whole codebase.
3. **Find the root cause, and state it** — distinct from the symptom:
   ```
   Root cause: the callback runs before state is committed, so it reads the stale value.
   Symptom (not the cause): the counter displays one behind.
   ```
4. **Fix the cause, not the symptom.** No workarounds layered on broken code. Confirm with the repro test, then run the full suite for regressions.
5. **If the fix fails, stop.** A failed fix usually means a wrong root cause. Re-diagnose from scratch. If two root-cause diagnoses are both wrong, this is probably Mode 2 or 3 — re-evaluate.

## Step 3B — Hard reset (Mode 2)

The honest move is a clean start, not another patch. This is not failure — it's the correct response to a polluted context.

Before ending the session, extract what's worth keeping:
```
## Reset Note — [Feature]
- What we were building: …
- What went wrong: [how the session drifted]
- What to avoid next time: [specific approaches that didn't work]
- Starting point: [what to keep, what to discard]
```
Then: save the note via `memory-and-context`, end this session, start fresh, restore, and re-approach with the note as context. Do not keep patching here. (In an unattended orchestrator run, where ending the session isn't an option, hand the milestone back as failed past budget with the reset note attached — see the pack's `ORCHESTRATOR.md`.)

## Step 3C — Rethink (Mode 3)

Find the wrong assumption — the foundation is wrong because something was assumed that isn't true.
```
Assumed: the API returns results sorted by date.
Reality: order is unspecified; it only appeared sorted in dev.
```
Then propose the correct approach: what changes, what must be discarded, what can be kept. **Present the analysis and wait for agreement before rebuilding** — more code in the wrong direction is harder to untangle later.

## Red Flags

- Trying a second fix before understanding why the first failed
- Fixes that patch previous fixes
- "Fixing" by adding workarounds around the broken code
- Treating a polluted session as a thing to push through
- Rebuilding on a rethink before the developer has agreed to the new approach

## Verification

- [ ] The failure mode was named before any fix was attempted
- [ ] (Mode 1) Root cause stated and distinguished from the symptom
- [ ] (Mode 1) Fix confirmed by a reproduction test + clean full suite
- [ ] (Mode 2) Reset note saved; session restarted rather than patched
- [ ] (Mode 3) New approach agreed with the developer before rebuilding
