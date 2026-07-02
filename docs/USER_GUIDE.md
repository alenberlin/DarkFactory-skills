# Dark Factory Skills — User Guide

A practical, example-driven guide to using the pack day to day. If you read two things, read **§4 (your first 10 minutes)** — it shows the whole loop on a real feature — and **§5 (the autonomous workflow)**, which shows how to run that loop hands-off.

---

## Contents

1. [What this is, in 30 seconds](#1-what-this-is-in-30-seconds)
2. [Install](#2-install)
3. [How it works (the mental model)](#3-how-it-works-the-mental-model)
4. [Your first 10 minutes — a full walkthrough](#4-your-first-10-minutes--a-full-walkthrough)
5. [The autonomous workflow](#5-the-autonomous-workflow)
6. [The 15 skills, with examples](#6-the-15-skills-with-examples)
7. [Commands cheat sheet](#7-commands-cheat-sheet)
8. [Personas and the `/ship` fan-out](#8-personas-and-the-ship-fan-out)
9. [Recipes — common workflows](#9-recipes--common-workflows)
10. [Files the pack creates](#10-files-the-pack-creates)
11. [Tips, FAQ & troubleshooting](#11-tips-faq--troubleshooting)
12. [Customizing & extending](#12-customizing--extending)

---

## 1. What this is, in 30 seconds

Dark Factory is a set of **engineering workflows** your AI coding agent follows so it behaves like a senior engineer instead of an eager intern. It contains:

- **15 skills** — step-by-step processes for each phase of building software (plan, build, test, review, ship).
- **6 commands** — `/architect` `/build` `/test` `/review` `/ship` `/darkfactory` — shortcuts that kick off a phase, or the whole lifecycle.
- **4 personas** — fresh-context reviewers (`code-reviewer`, `security-auditor`, `test-engineer`, `performance-auditor`).
- **1 autonomous workflow** — an opt-in orchestrator (`/darkfactory`) that runs the entire lifecycle end to end from a single planning checkpoint.
- **1 hook** — loads the skill index and the always-on behaviors at the start of every session.

The whole pack maps to one lifecycle:

```
 DEFINE        BUILD              VERIFY          REVIEW           SHIP
 /architect →  /build         →   /test       →  /review      →   /ship
 align &       thin slices,       prove it        five-axis        gate, then
 plan          test-driven        works           quality check    deploy safely
```

You can drive that lifecycle one step at a time, or hand the whole thing to **`/darkfactory`** and let it run (see §5). Either way, you don't have to memorize the skills — they **activate themselves** when the task matches. Commands are there for when you want to start a phase deliberately.

---

## 2. Install

### Claude Code (recommended)

```
/plugin marketplace add alenberlin/DarkFactory-skills
/plugin install darkfactory@darkfactory-skills
```

Or run it from a local clone while developing:

```bash
git clone https://github.com/alenberlin/DarkFactory-skills.git
claude --plugin-dir /path/to/DarkFactory-skills
```

### Other tools

The skills are plain `SKILL.md` files, so they work anywhere that reads the format:

- **Cursor** — copy a `SKILL.md` into `.cursor/rules/`, or point at the `skills/` folder.
- **Windsurf / Copilot / Gemini / OpenCode** — add skill contents to that tool's rules/instructions file. Personas in `agents/` double as custom personas.
- **The autonomous workflow travels too** — any tool that reads an instruction file can run it; point it at `ORCHESTRATOR.md` via the gate in [`docs/WORKFLOW.md`](WORKFLOW.md).

### Verify it loaded

Start a new session. If the hook is working you'll see the `using-skills` meta-skill injected at session start (the discovery flowchart + operating behaviors). If it isn't there, check the plugin is installed and enabled (`/plugin`), then start a fresh session.

---

## 3. How it works (the mental model)

There are five moving parts. You mostly interact with the first two.

**Skills (automatic).** Each skill has a description like *"…Use when fixing any bug. Use when changing behavior."* The agent reads those triggers and loads the matching skill on its own. Ask it to fix a bug and `debugging-and-recovery` + `test-driven-development` engage without you naming them.

**Commands (deliberate).** When you want to *start* a phase on purpose, type a command. `/review` is just a saved, reliable way of saying "do a proper five-axis review in a clean context."

**Personas (for review).** A persona is a sub-agent with a fresh context window — useful for review, because it isn't biased by the conversation that wrote the code. `/review` and `/ship` invoke them. **Personas never call other personas** — only you or a command orchestrates them.

**The workflow (opt-in).** For bigger jobs you can run the entire lifecycle as one process instead of step by step. Type `/darkfactory` (or answer its engagement gate) and it takes the project from blueprint to reviewed build on its own, pausing only for the one approval that matters and for anything that genuinely needs you. It's off by default — §5 covers it in full.

**The hook (always-on).** At session start it injects the meta-skill, which carries six **operating behaviors that apply to everything**:

1. **Surface assumptions** before non-trivial work.
2. **Manage confusion** — stop and ask instead of guessing.
3. **Push back** when an approach is flawed (no sycophancy).
4. **Enforce simplicity** — prefer the boring, obvious solution.
5. **Scope discipline** — touch only what the task asks for.
6. **Verify, don't assume** — finish with evidence, not "seems right."

> These six are the backbone. Even when no specific skill is active, the agent should be doing these.

---

## 4. Your first 10 minutes — a full walkthrough

Let's build a small feature end to end: **"Add a `GET /tasks` endpoint that returns the current user's tasks, and a list view for it."** This shows the core loop.

### Step 1 — `/architect` (align before coding)

```
You:  /architect add a GET /tasks endpoint returning the current user's
      tasks, plus a list view on the dashboard

Agent: Before we build, let me align on a few terms:
       - "current user's tasks" — I'm assuming tasks the user owns,
         not tasks assigned to them. Correct?
       - "list view" — read-only for now, no inline edit/delete?

       Decision: pagination. My take — paginate from day one (limit 20,
       cursor-based) so the endpoint doesn't degrade as task counts grow.
       Work for you?

You:  Owned tasks, yes. Read-only is fine. Pagination yes, cursor-based.

Agent: Blueprint ready.

       ## Plan — GET /tasks + list view
       What we're building: an authenticated, paginated endpoint returning
       the caller's owned tasks, and a read-only dashboard list that renders
       loading / empty / error states.
       Acceptance: 200 with {tasks, nextCursor}; 401 unauthenticated;
       empty array renders the empty state; list matches existing card style.
       Build order:
       1. Endpoint + auth + pagination (riskiest) — with tests
       2. Data fetching on the dashboard
       3. List UI with loading/empty/error states
       Confirm and I'll start.

You:  Confirmed.
```

Notice what happened: ambiguous terms got pinned, the one decision that mattered (pagination) was surfaced *with a recommendation*, and you got a risk-ordered plan **before** any code. That's the `architect` skill.

### Step 2 — `/build` (thin, test-driven slices)

```
You:  /build

Agent: Slice 1 — endpoint. Writing the failing test first:

       it('returns only the caller's tasks, newest first', …)   // RED ✗

       Implementing the handler with auth + cursor pagination… test passes. ✓
       Full suite green. Committing: "Add GET /tasks endpoint with pagination"

       Slice 2 — dashboard data fetching… [continues one slice at a time]
```

Each slice is: failing test → minimum code → green → its own commit. If something breaks, the agent switches to `debugging-and-recovery` instead of piling on. (Want it to run all slices without stopping between them? Use `/build auto` — it still tests and commits each slice, just doesn't pause for you between them.)

### Step 3 — `/review` (is it correct, not just working?)

```
You:  /review

Agent: ## Review — GET /tasks + list view
       Verdict: REQUEST CHANGES
       Critical:
       - api/tasks.ts:34 — cursor isn't validated; a malformed cursor
         throws a 500 instead of 400. Fix: validate and return 400.
       Important:
       - DashboardList.tsx:20 — no error state; a failed fetch renders blank.
       Suggestions:
       - tasks.ts:12 — name `q` → `query` for readability.
       Done well: pagination is cursor-based and tested.
```

The reviewer **reports and stops** — it doesn't silently fix. You decide what to act on.

### Step 4 — fix, then `/ship`

After you have the agent fix the two findings, gate the release:

```
You:  /ship

Agent: Fanning out: code-reviewer · security-auditor · test-engineer …
       Merged result: GO — no Critical findings.
       Rollback plan: revert deploy to previous build; trigger = error
       rate on /tasks > 2% for 5 min. CI gates green, migration n/a.
```

That's the loop: **align → build → verify → review → ship.** You can run it tightly for a big feature or lean on auto-activation for small ones. And when you'd rather run that entire loop hands-off, that's exactly what `/darkfactory` does — the next section.

---

## 5. The autonomous workflow

Sections 3 and 4 showed the lifecycle as separate steps you drive — `/architect`, then `/build`, then `/review`, and so on. The **`/darkfactory`** workflow runs that same lifecycle for you, start to finish, with **one approval up front** and almost nothing to babysit after it.

It's the difference between conducting the orchestra yourself and handing the conductor a score. The score is a blueprint you approve; after that, the agent plays it.

### When to use it (and when not to)

- **Use it** for a feature or a whole app — anything multi-step where you'd rather set the direction once and let the agent work through it.
- **Skip it** for a quick edit, a one-line fix, or exploring an idea. For those, just ask, or use a single command. The workflow is opt-in precisely so it stays out of the way of small jobs.

### The one rule that makes it safe

Hands-off does not mean uncontrolled. The workflow rests on two guarantees:

1. **One human checkpoint — the blueprint.** Before any code, the `architect` skill interviews you to crystal clarity and writes a blueprint (a PRD plus a phased plan with acceptance criteria). **You approve it.** That single approval is what earns the autonomy that follows.
2. **A defined finish line.** Every milestone, and the project as a whole, carries written acceptance criteria. The loop runs *toward* those criteria and stops when they pass — it never decides it's "done" by feeling, and it never weakens a test to make the loop go green.

### Turning it on

**The easy way — `/darkfactory` (Claude Code).** Just type it, with what you want:

```
/darkfactory build a tasks module: a GET /tasks endpoint plus a dashboard list
```

It starts the discovery interview immediately.

**The portable way — the engagement gate (any tool).** To have it available in every project and in any agent tool (Codex, Cursor, …), add a short block to your **global** instruction file once. From then on it asks, the first time you open each project, whether to engage — and remembers your answer, so you're asked at most once per project. Full setup is in [`docs/WORKFLOW.md`](WORKFLOW.md).

Either way, it stays **off until you opt in**, per project.

### What actually happens

```
You:  /darkfactory build a tasks module: GET /tasks + a dashboard list

Agent: [Discovery] A few things to pin down before I plan…
       - "tasks" — owned by the user, or assigned to them?
       - Stack — I'd use your existing Next.js + Postgres. Good?
       … writes docs/darkfactory/PRD.md and docs/darkfactory/PLAN.md …
       Blueprint ready — 3 milestones, riskiest first. Approve to start.

You:  Approved.

Agent: [Milestone 1/3] endpoint + auth + pagination
         failing test → code → green → committed ✓
       [Milestone 2/3] dashboard data fetching
         failing test → code → green → committed ✓
       [Milestone 3/3] list UI with loading/empty/error states
         fix needed: empty state renders blank → diagnosed → fixed → green ✓
       [Integration] full suite green; five-axis review clean.
       Done — all acceptance criteria pass. 3 commits on the branch.
       Report: docs/darkfactory/REPORT.md — evidence per criterion.
```

You approved once, at "Blueprint ready." Everything after it ran on its own.

### When it pauses for you (the escape hatch)

"No babysitting" includes knowing when *to* stop. The workflow comes back to you only when it genuinely should:

- a decision is needed that the blueprint didn't settle (it won't silently guess something load-bearing);
- a milestone that later work depends on keeps failing past its retry budget — a sign the approach may be wrong, so it surfaces the diagnosis instead of thrashing (an independent milestone is marked blocked and the run continues, reporting it at the end);
- an action is **irreversible or reaches outside your workspace** — deploying, deleting data, touching secrets, sending external requests (these always ask first);
- it's missing access, a credential, or a tool it needs.

When it pauses, it writes a handoff note (via `memory-and-context`) so you — or a different tool tomorrow — can pick up exactly where it stopped.

### Stopping, resuming, and where things live

- **Resume:** run `/darkfactory` again (or re-open the project) and it reads its progress ledger and continues from the first unfinished milestone — it won't restart from scratch.
- **Files it creates** live in *your* project: the blueprint and plan under `docs/darkfactory/`, a `PROGRESS.md` ledger you can watch, and handoff notes under `.memory/`. See §10.
- **Deployment is deliberately separate** — the workflow gets you to a reviewed, production-ready build; actually shipping is its own step (`/ship`) and always asks first.

### It still uses the same skills

The workflow doesn't replace anything in §6 — it **sequences** those skills: `architect` for discovery, `incremental-implementation` + `test-driven-development` + `runtime-verification` for each milestone, `debugging-and-recovery` when something breaks, `code-review` and the personas for the final pass. You get the same discipline as the §4 walkthrough, run automatically.

---

## 6. The 15 skills, with examples

You rarely call these directly — they fire on their triggers. Here's what each does and a one-line example of what sets it off.

### Define

**`architect`** — Aligns on intent and produces a short spec + risk-ordered plan before coding.
*Fires when:* "build me a dashboard for…" → you get questions and a plan, not instant code.

**`api-and-interface-design`** — Designs stable, hard-to-misuse contracts (endpoints, types, module boundaries).
*Fires when:* "design the REST API for comments" → consistent error envelope, illegal states made unrepresentable, versioning considered.

### Build

**`incremental-implementation`** — Delivers in thin vertical slices, one verified commit at a time.
*Fires when:* a change spans several files → it builds the riskiest slice first instead of one big drop.

**`ui-engineering`** — Builds accessible, production-quality components **and** records their style in `ui-registry.md` so the next component matches.
*Fires when:* "add a settings card" → it checks the registry, matches the existing card, handles empty/loading/error, then imprints the pattern.

**`source-driven-development`** — Verifies external API usage against official docs for your installed version instead of from memory.
*Fires when:* using a framework API it's unsure about → it confirms the signature and leaves a source cite, avoiding outdated patterns.

### Verify

**`test-driven-development`** ⭐ — Failing test first; reproduction test before any bug fix. (Polyglot: TS + Python.)
*Fires when:* implementing or fixing anything → RED → GREEN → REFACTOR.

**`runtime-verification`** — Confirms behavior against real runtime data (DOM, console, network, screenshots) via a browser/DevTools MCP.
*Fires when:* "the dropdown doesn't open" → it reproduces in the browser, checks the console, and fixes from evidence.

**`debugging-and-recovery`** — Diagnoses the *type* of failure before fixing: targeted fix / hard reset (polluted session) / rethink (wrong foundation).
*Fires when:* "I've tried fixing this 4 times and it's worse" → it may call a hard reset instead of patching again.

### Review

**`code-review`** — Five-axis review (correctness, readability, architecture, security, performance); reports by severity, doesn't auto-fix.

**`code-simplification`** — Removes unnecessary complexity **without changing behavior** (tests stay green).
*Fires when:* "this function is a mess" → it flattens it and proves behavior held.

**`security-and-hardening`** — Hardens against injection, broken auth/access control, secret leaks, SSRF. (Polyglot, checklist-backed.)
*Fires when:* handling user input, auth, or storage → parameterized queries, per-object authz, no secrets in logs.

**`performance-optimization`** — Measure first, optimize only what the profiler implicates, re-measure.
*Fires when:* "the dashboard is slow" → it finds the N+1 query rather than guessing.

### Ship & sustain

**`git-and-shipping`** — Atomic commits that explain *why*, plus a pre-launch checklist and a rollback plan written **before** deploy.

**`memory-and-context`** — Saves session state to `.memory/` and restores it next time; records big decisions as ADRs. Never persists secrets.
*Fires when:* end/start of a session, or a decision worth keeping.

**`using-skills`** (meta) — Routes tasks to the right skill and enforces the six operating behaviors. Loaded by the hook every session.

---

## 7. Commands cheat sheet

| Command | Use it to… | Backed by |
|---|---|---|
| `/architect <feature>` | Plan before building — align, decide, get a spec | `architect` |
| `/build` | Implement the plan in test-driven slices | `incremental-implementation` + `test-driven-development` |
| `/build auto` | Same, but run all slices without pausing between them | ↑ (autonomous pass) |
| `/test` | Write/run tests; reproduction-test a bug | `test-driven-development` |
| `/review` | Five-axis review in a fresh context | `code-reviewer` persona |
| `/ship` | Pre-ship gate (parallel audit) → go/no-go → deploy | all 4 personas + `git-and-shipping` |
| `/darkfactory <what you want>` | Run the **whole lifecycle** end to end — blueprint, then autonomous build/test/fix/review | the orchestrator (sequences every skill) |

**Examples**

```
/architect add CSV export to the reports page
/build auto
/test the date parser rejects timezones it can't resolve
/review
/ship staged rollout to 10% first
/darkfactory build a small CRUD admin page for managing coupons
```

Anything after the command is passed straight in as context (e.g. `/ship staged rollout to 10% first`).

---

## 8. Personas and the `/ship` fan-out

Personas are fresh-context reviewers ([reference](PERSONAS.md)). The power move is `/ship`, which runs them **in parallel** and merges the results:

```
                    ┌─→ code-reviewer      ─┐
/ship  ── fan out ──┼─→ security-auditor   ─┤──→ merge ──→ GO / NO-GO
                    ├─→ test-engineer      ─┤            + rollback plan
                    └─→ performance-auditor ┘  (only if user-facing)
```

- **GO** only if no persona reports a **Critical** finding.
- **NO-GO** lists the blockers and stops.

You can also invoke a single perspective directly: *"Have the security-auditor look at `auth.ts`"* runs just that one. Because personas never delegate to each other, there are no hidden call chains — if the security-auditor thinks you also need a performance pass, it *says so in its report* and you decide.

A particularly useful pattern is the **test-engineer for bugs**: it writes a reproduction test *without seeing the fix*, so the test checks intended behavior rather than what the code happens to do.

---

## 9. Recipes — common workflows

**Build a feature hands-off (the workflow)**
```
/darkfactory <what you want>
→ architect interviews you and writes the blueprint; you approve once.
  Then it builds, tests, fixes, and reviews each milestone on its own,
  pausing only if it hits a real decision or something irreversible.
```

**Build a new feature (driving each step yourself)**
```
/architect <what you want>     → confirm the plan
/build                         → or /build auto
/review                        → fix Critical/Important findings
/ship                          → gate, then deploy
```

**Quick bug fix**
```
"Fix: completing a task doesn't update completedAt."
→ test-driven-development writes a reproduction test that FAILS,
  the fix lands, the test PASSES, full suite confirms no regressions.
```

**It's broken and getting worse**
```
"I've tried fixing this 4 times and each fix breaks something new."
→ debugging-and-recovery diagnoses the failure MODE first. If the
  session is polluted, it calls a hard reset: saves a reset note via
  memory-and-context, and you restart clean instead of patching deeper.
```

**Pre-merge review only**
```
/review
→ five-axis report with severities and file:line fixes. Nothing is
  changed until you say so.
```

**Pick up where you left off (new session)**
```
End of day:    "Save where we are."        → writes .memory/<date>-<feature>.md
Next morning:  "Restore context."          → summarizes + asks you to confirm
                                              BEFORE continuing.
```

**Inherited a messy UI**
```
"Audit the UI for consistency."
→ ui-engineering audit mode lists every conflicting radius/color/spacing,
  recommends a baseline, and (after you confirm) writes ui-registry.md +
  a list of components to fix.
```

---

## 10. Files the pack creates

These appear in *your* project, not in the pack. Commit them or add them to `.gitignore` as you prefer.

| Path | Created by | What it holds |
|---|---|---|
| `.darkfactory` | the `/darkfactory` workflow | Your per-project engage/ignore choice for the workflow. One line. |
| `docs/darkfactory/PRD.md` + `PLAN.md` + `PROGRESS.md` + `REPORT.md` | the `/darkfactory` workflow | The approved blueprint, the phased plan, the live milestone ledger, and the completion report. |
| `.memory/<date>-<feature>.md` + `.memory/INDEX.md` | `memory-and-context` | Per-session handoff notes (one file per session, never overwritten). **Secrets are never written here.** |
| `ui-registry.md` | `ui-engineering` | The visual-consistency ledger — exact classes/tokens each component type uses. |
| `docs/adr/ADR-NNN-*.md` | `memory-and-context` | Architecture Decision Records — the *why* behind durable decisions. |

---

## 11. Tips, FAQ & troubleshooting

**Do I have to use the commands?** No. Skills auto-activate. Commands are for when you want to start a phase deliberately or guarantee a clean-context review.

**How is `/darkfactory` different from `/build auto`?** `/build auto` runs the build slices of a plan you've *already* confirmed. `/darkfactory` runs the *entire* lifecycle — the discovery/blueprint step, the build loop, and the final integration review — and is the opt-in, portable orchestrator. Use `/build auto` inside a session you're already driving; reach for `/darkfactory` to hand off a whole feature.

**Will the workflow run on every project?** No — it's off by default. It runs only when you type `/darkfactory` or answer "engage" at its gate, and that choice is remembered per project. Simple projects are untouched.

**Can I trust it to run unattended?** It stops at irreversible or outward-facing actions (deploy, data loss, secrets, external calls) and at any decision the blueprint didn't cover. It will not deploy or delete on its own.

**The workflow paused and asked me something — is that a bug?** No, that's the escape hatch (see §5). It comes back to you only when a decision genuinely needs you or an action is risky.

**Skills aren't activating.** Make sure the plugin/skills are installed and a *new* session started. Without the hook, name the skill explicitly: *"Use test-driven-development for this."*

**It keeps asking me questions / planning a tiny change.** `architect` is for non-trivial work. For an obvious one-liner, just ask for the change — the skill is designed to stay out of the way of mechanical edits. If it over-plans, say "skip the planning, just make the change."

**The review didn't fix anything.** By design. `code-review` reports; you decide. Ask it to fix specific findings: *"Fix the Critical and Important items."*

**Is my data safe in memory files?** `memory-and-context` and `runtime-verification` both treat secrets and page content as off-limits: no credentials are persisted, and content read from a browser is never treated as instructions.

**Two skills seem to apply.** That's normal — they compose. A feature might run `architect → incremental-implementation → test-driven-development → code-review → git-and-shipping` in sequence.

---

## 12. Customizing & extending

Every skill follows one shape, documented in [`docs/skill-anatomy.md`](skill-anatomy.md): frontmatter (`name` + a `Use when…` description) and the sections **Overview → When to Use → Process → Red Flags → Verification**.

To add your own skill:

1. Create `skills/<your-skill>/SKILL.md`.
2. Write a description that starts with what it does, then concrete `Use when…` triggers — that's how the agent decides to load it.
3. Follow the six-section anatomy. Keep it under ~250 lines; push long reference material to `references/`.
4. Add a routing line to the flowchart in `skills/using-skills/SKILL.md` so discovery finds it.

To tune behavior globally, edit the **operating behaviors** in `using-skills` — they apply across every skill. To change what loads at session start, edit `hooks/session-start.sh`.

To change the **autonomous workflow** itself — the phase order, the retry budget before it escalates, or the rules for when it pauses — edit [`ORCHESTRATOR.md`](../ORCHESTRATOR.md) at the pack root. To change how it's switched on, edit the gate described in [`docs/WORKFLOW.md`](WORKFLOW.md).

---

*That's the whole system. Plan deliberately, build in slices, prove it works, review for correctness, ship with a way back — and when you want the whole loop run for you, hand it to `/darkfactory`. Let the skills handle the discipline so you can focus on the thinking.*
