---
name: architect
description: Aligns on what to build before any code is written — clarifies intent, agrees on vocabulary, settles the decisions that change the implementation, and produces a short spec and ordered plan. Use when starting a new feature or change. Use when a request is underspecified, ambiguous, or only exists as a rough idea.
---

# Architect

## Overview

This is the thinking session that happens before the building session. A senior engineer does not start coding the moment a task arrives — they make sure both people are building the same thing in their heads first. This skill surfaces the decisions that matter, aligns on language, and produces a lightweight spec and ordered plan you confirm before anything gets built.

It scales to the work. A one-line change gets one round of alignment; a new feature gets the full pass. It is a thinking session, not an interrogation, and not a 20-page PRD.

## When to Use

- Starting a new feature, system, or significant change
- A request is vague, ambiguous, or only a rough idea ("build me a dashboard")
- The work touches more than a couple of files or has non-obvious decisions
- You catch yourself about to silently fill in an ambiguous requirement

**When NOT to use:** mechanical changes with obvious correctness (rename, formatting, a clear one-line fix), or when the user has given an unambiguous, complete instruction. Don't manufacture decisions that aren't there.

## Process

### Step 1 — Understand what already exists
Before asking anything, do your homework: read the request, any context files (`CLAUDE.md`, specs, ADRs), and the relevant existing code. Never ask about something the existing material already answers. A good senior engineer walks into the meeting prepared.

### Step 2 — Align on language
Every project has its own vocabulary. Pick the 3–5 terms in the request that could be read more than one way, state how you're interpreting each, and confirm:
```
Before we go further, let me make sure we mean the same things:
- "user" — I'm treating this as an authenticated account holder, not a visitor. Right?
- "archive" — I read this as soft-delete (hidden, recoverable), not permanent removal. Match?
Correct anything that's off before we continue.
```
Update immediately on correction. Do not proceed until the language is shared.

### Step 3 — Surface the decisions that matter
Raise only the decisions that change the implementation direction — not every possible question. For each one, **share your recommendation and reasoning** so the developer has something to react to, not a blank page. One at a time, highest-impact first.
```
Decision: Where does data fetching live?
My take: server-side fetching — avoids client loading states and keeps query logic off the client.
Does that work for you, or do you see it differently?
```
If an answer makes a later decision irrelevant, drop it.

> **Designing an interface or API as part of this?** Hand the contract details (shapes, endpoints, versioning, error model) to `api-and-interface-design` rather than settling them here.

### Step 4 — Know when you're done
Stop when every decision that would change the implementation is settled — not when every possible question is answered. Don't ask questions for the sake of thoroughness. When the plan is solid enough to start, say:
```
Blueprint ready.
```

### Step 5 — Produce the spec and plan
Write a short, concrete plan from what was discussed:
```
## Plan — [Feature Name]

### What we're building
[One clear paragraph: exactly what will be built, and the acceptance criteria that mean it's done.]

### Language we agreed on
- [Term]: [agreed definition]

### Decisions made
- [Decision]: [what was decided and why]

### Assumptions
- [Anything assumed but not explicitly confirmed]

### Build order
1. [Thin first slice that proves the core works end to end]
2. [Next slice]
3. ...
```
Order the build so the riskiest, most foundational slice comes first — fail early, not late. Present the plan and **wait for explicit confirmation.** Only then does implementation begin (hand off to `incremental-implementation`).

## Red Flags

- Writing code before the plan is confirmed
- Asking questions whose answers are already in the context files
- A blank-page question with no recommendation attached
- A "plan" that's really a full spec document for a two-file change
- Decisions left implicit that will force a rewrite when discovered later

## Verification

- [ ] Ambiguous terms were defined and confirmed
- [ ] Every decision that changes the implementation is resolved
- [ ] The plan states acceptance criteria, not just a feature description
- [ ] Build order starts with the riskiest/most foundational slice
- [ ] The developer explicitly confirmed before any code was written

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "It's obvious what they want, I'll just build it" | The most expensive bugs are wrong assumptions built confidently. One alignment pass is cheaper than a rebuild. |
| "Planning slows us down" | It slows the first hour and saves the next ten. Unplanned work is where rework comes from. |
| "I'll figure out the structure as I go" | Structure decided mid-build is structure you'll fight later. Decide the load-bearing parts first. |
