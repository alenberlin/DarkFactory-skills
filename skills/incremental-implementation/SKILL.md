---
name: incremental-implementation
description: "Delivers changes in thin, verifiable vertical slices instead of one large drop. Use when implementing any feature or change that touches more than one file. Use when a task feels too big to land in a single step, or when you're tempted to write a lot of code at once."
---

## Autopilot handoff

Implement only the assigned requirement-linked task in its isolated workspace. Respect permitted paths and dependencies. Return candidate edits and bounded argv commands through AgentReply. The controller verifies, assigns independent reviews, and integrates the actual merge; a complete model reply is only a proposal.

For assigned factory work, read [the shared runtime contract](../../docs/RUNTIME_CONTRACT.md). It defines authority, proposal fields, approval scope and evidence identity. These skills remain language agnostic; the approved profile selects actual commands.


# Incremental Implementation

## Overview

Big-bang changes are where bugs hide and reviews stall. Build in thin vertical slices — each slice is the smallest change that is independently correct, testable, and shippable. One slice lands and is verified before the next begins. This keeps the blast radius small, the feedback loop tight, and every step reversible.

## When to Use

- Implementing any feature or change spanning more than one or two files
- A task that feels too large to start, or where you'd otherwise write hundreds of lines before running anything
- Following a plan from `architect`, executing it slice by slice

**When NOT to use:** genuine one-liners and isolated single-file edits, or mechanical changes (rename, move) where slicing adds ceremony with no safety gain.

## Process

### 1. Slice vertically, not horizontally
A vertical slice cuts through every layer for one small capability (e.g. "create a task end to end: route → handler → persistence → response"). A horizontal slice builds one whole layer for everything (all routes, then all handlers) — and nothing works until the last layer lands. Prefer vertical: the first slice proves the path through the whole system works.

### 2. Order by risk
Build the riskiest, most foundational slice first. If the core assumption is wrong, you want to find out in slice one, not slice nine.

### 3. One slice at a time
For each slice:
- Implement the minimum for that capability
- Verify it (test pass, build clean, runtime check) — see `test-driven-development`
- Submit it for trusted integration; commit only under explicit permission — see `git-and-shipping`
- Only then start the next slice

### 4. Keep scope surgical
Touch only what the current slice needs. Don't refactor adjacent code, "clean up" unrelated files, or pull in the next slice's work early. Drift here is how a focused change becomes an unreviewable one.

### 5. Stop at the slice boundary on failure
If a slice won't go green, stop — don't pile the next slice on top of a broken one. Diagnose with `debugging-and-recovery` before continuing.

## Red Flags

- Hundreds of lines written before anything was run
- A single commit that touches many unrelated concerns
- Layer-by-layer building where nothing works until the end
- "I'll verify it all once it's finished"
- Scope creep: files changed that the task never mentioned

## Verification

- [ ] Each slice was independently verified before the next began
- [ ] Each slice has verified source evidence; any commit was explicitly authorized
- [ ] No slice left the build or test suite broken
- [ ] Only files relevant to the task were touched
- [ ] The first slice exercised the riskiest part of the design
