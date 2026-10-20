---
name: code-simplification
description: "Reduces unnecessary complexity while preserving behavior exactly. Use when code works but is harder to read, maintain, or extend than it should be. Use when reviewing code that has accumulated incidental complexity. Quality only — it does not change what the code does."
---

## Autopilot handoff

Simplify only assigned components while preserving the approved behavior and criterion coverage. Submit a new candidate revision; previous passing evidence does not apply to changed source. Do not remove functionality to satisfy a check.

For assigned factory work, read [the shared runtime contract](../../docs/RUNTIME_CONTRACT.md). It defines authority, proposal fields, approval scope and evidence identity. These skills remain language agnostic; the approved profile selects actual commands.


# Code Simplification

## Overview

Working code and good code are not the same. Code accretes incidental complexity — premature abstractions, defensive cruft, clever one-liners, dead branches — and each layer makes the next change harder. This skill removes that complexity *without changing behavior*. The bar: would a staff engineer look at this and say "why didn't you just…"? If yes, simplify to the boring, obvious version.

## When to Use

- Code works but is hard to read, follow, or extend
- After a feature lands, as a deliberate cleanup pass
- Reviewing code that has grown tangled over several changes

**When NOT to use:** when you can't confirm behavior is preserved (no tests, can't verify) — add a characterization test first via `test-driven-development`. This is not the skill for finding bugs (use `code-review`) — it's quality-only, behavior-preserving.

## Process

### 1. Lock behavior first
Simplification is only safe if you can prove behavior didn't change. Ensure tests cover the code; if they don't, write characterization tests that capture current behavior before touching anything.

### 2. Apply the simplifications that earn their keep
- **Delete dead code** — unused branches, unreachable paths, commented-out blocks, unused params. The best simplification is removal.
- **Collapse needless indirection** — a one-call wrapper, a single-implementation interface, an abstraction with one user. Inline it.
- **Flatten control flow** — early returns over nested `if`; guard clauses over arrow-shaped code.
- **Replace cleverness with clarity** — a dense ternary chain or bit-trick that needs a comment to read is more expensive than the plain version.
- **Name for intent** — a well-named function/variable removes the need for an explanatory comment.
- **Reduce state** — fewer mutable variables, narrower scope, less shared state.

```typescript
// Before: nested, mutable, hard to scan
function classify(u) {
  let r;
  if (u) { if (u.active) { if (u.admin) { r = 'admin'; } else { r = 'user'; } } else { r = 'inactive'; } }
  return r;
}
// After: flat, obvious, same behavior
function classify(u: User | null): Role {
  if (!u) return 'unknown';
  if (!u.active) return 'inactive';
  return u.admin ? 'admin' : 'user';
}
```

### 3. Stay surgical and behavior-preserving
Change structure, not semantics. Don't "improve" outputs, don't fix bugs you spot along the way (note them for `code-review` instead), don't expand scope. Run the tests after each simplification — green means behavior held.

### 4. Resist over-abstraction, both ways
Don't replace duplication with the wrong abstraction. Two similar blocks are often clearer than one parameterized abstraction serving two masters. Simpler sometimes means *more* lines, not fewer.

## Red Flags

- Simplifying code with no tests and no way to confirm behavior held
- A refactor commit that also changes outputs or fixes a bug
- Replacing clear duplication with a tortured shared abstraction
- "Cleaning up" code unrelated to the task
- Clever code that needs a comment to be readable, left in place

## Verification

- [ ] Behavior is provably unchanged (tests green before and after)
- [ ] No outputs, semantics, or bugs were changed under cover of "cleanup"
- [ ] Each change made the code measurably easier to read or extend
- [ ] Scope stayed within the targeted code
- [ ] Any bugs noticed were noted for review, not silently fixed
