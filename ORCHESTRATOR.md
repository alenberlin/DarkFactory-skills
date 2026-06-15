# Dark Factory Orchestrator

The master workflow. It takes a project through the full software-development lifecycle — discovery, build, verification, and review — the way a disciplined engineering team would: one planning checkpoint up front, then autonomous execution after it.

This document is the conductor. It does not reimplement anything; it sequences the skills already in this pack. It is loaded on demand — by the engagement gate in your global agent file, or by the `/darkfactory` command — never automatically.

## Operating contract

- **One human checkpoint.** The only required approval is the blueprint at the end of discovery. Nothing is built before you approve it; little interrupts you after.
- **Autonomous after approval.** Once the blueprint is approved, the build–test–fix loop runs unattended until the work meets its acceptance criteria or hits a condition that genuinely requires you (see *Autonomy & escalation*).
- **Done is defined, not felt.** Every milestone, and the project as a whole, carries written and verifiable acceptance criteria. The loop runs toward those criteria and stops when they pass — it never declares done by feel.
- **The always-on operating behaviors still apply** (`skills/using-skills/SKILL.md`): surface assumptions, manage confusion, push back on flawed approaches, prefer the simplest solution, hold scope, and verify with evidence.

## Artifacts

The workflow reads and writes these in the **target project** — not in this pack:

| Path | Purpose |
|---|---|
| `.darkfactory` | Engagement marker — `engage` or `ignore`. Set once per project. |
| `docs/darkfactory/PRD.md` | The blueprint: what is being built, acceptance criteria, explicit non-goals. |
| `docs/darkfactory/PLAN.md` | Phased milestones in build order, each with its own acceptance criteria. |
| `docs/darkfactory/PROGRESS.md` | The ledger — milestone status, so the loop is resumable and visible. |
| `.memory/<date>-<feature>.md` | Session handoff and pickup, via `memory-and-context`. |

## On entry

1. If `docs/darkfactory/PROGRESS.md` and a recent `.memory/` entry exist, **resume**: run the `memory-and-context` pickup, summarize where the work stands, and continue from the first unfinished milestone. Do not restart from scratch.
2. Otherwise, begin at Phase 0.

## Phase 0 — Discovery & blueprint  *(the human checkpoint)*

Apply `architect` (`skills/architect/SKILL.md`). Reach absolute clarity before any code:

- **Intent** — the problem, the users, and what "production-ready" means for this app.
- **Technical** — language, framework, platform, data. Propose a stack if the developer is non-technical; co-design it if they are.
- **Functional** — features, fields, screens, capabilities.
- **Non-goals** — what this explicitly will *not* do, and the constraints it must respect.

If the work involves API or interface contracts, apply `api-and-interface-design` (`skills/api-and-interface-design/SKILL.md`).

Write the blueprint to `docs/darkfactory/PRD.md` and `docs/darkfactory/PLAN.md`:

- The PRD states the acceptance criteria for the whole app and the explicit non-goals.
- The plan breaks the work into milestones in the most logical order — **riskiest and most foundational first** — each with acceptance criteria that a test or an observable behavior can confirm.

Present the blueprint and **wait for explicit approval.** This is the single gate. Only after approval does Phase 1 begin.

## Phase 1 — Autonomous build loop

Initialize `docs/darkfactory/PROGRESS.md` from the plan. Then, for each milestone in order:

1. **Build** — apply `incremental-implementation` (`skills/incremental-implementation/SKILL.md`): thin vertical slices, not one big drop. For UI, apply `ui-engineering`; for external APIs, apply `source-driven-development`; for input, auth, or storage, apply `security-and-hardening`.
2. **Test** — apply `test-driven-development` (`skills/test-driven-development/SKILL.md`): failing test first. Where there is a runtime or UI, confirm real behavior with `runtime-verification`.
3. **Fix** — on failure, apply `debugging-and-recovery` (`skills/debugging-and-recovery/SKILL.md`): diagnose the failure *mode* first, then fix, then re-test. Allow a bounded number of focused attempts (default: 3) before escalating per the policy below.
4. **Close the milestone** — when its acceptance criteria pass *and* the full suite is green: make an atomic commit (commit discipline from `git-and-shipping`), mark the milestone done in `PROGRESS.md`, and move to the next.

Do not pause for approval between milestones — that is the autonomy the blueprint bought.

## Phase 2 — Integration & review

When every milestone is done:

1. Verify the whole app — the full suite plus runtime checks of the primary flows.
2. Apply `code-review` (`skills/code-review/SKILL.md`) across the change. For a release-grade gate, also run the review personas in `agents/`: `security-auditor`, `test-engineer`, and `performance-auditor` for user-facing work. Personas report; they do not auto-fix.
3. Address every Critical and Important finding, then re-verify.

Repeat Phase 2 until the project's acceptance criteria pass and no Critical findings remain.

## Phase 3 — Ship  *(secondary, only if asked)*

Deployment sits outside the core loop. If asked to ship, apply `git-and-shipping` (`skills/git-and-shipping/SKILL.md`): a pre-launch checklist and a rollback plan written before deploy. Deployment is outward-facing and hard to reverse — confirm with the developer before executing it.

## Autonomy & escalation

After the blueprint is approved, run unattended — under these hard rules.

**Stop and succeed** when all milestones are closed, the project's acceptance criteria pass, and no Critical review findings remain.

**Pause and ask** — only when genuinely necessary:

- A decision is required that the blueprint does not cover and cannot be settled from the existing code. Do not silently guess load-bearing decisions.
- A milestone fails past its retry budget — treat this as a possible wrong approach and surface the `debugging-and-recovery` diagnosis instead of thrashing.
- An action is **irreversible or reaches outside the workspace**: deploying, deleting data, handling or rotating secrets, sending external requests, force-pushing.
- Required access, credentials, or tools are missing.

When you pause, write a `memory-and-context` handoff (state, what is done, what is blocked, the recommended next move) so the work resumes cleanly — in this tool or another — then ask one clear question.

**Never** weaken a test or relax an acceptance criterion to make the loop pass. Green must mean genuinely green.

## Definition of done

- [ ] Every milestone in `PLAN.md` is closed in `PROGRESS.md`.
- [ ] The project's acceptance criteria in `PRD.md` pass, verified by tests and runtime behavior.
- [ ] No Critical review findings remain.
- [ ] The working tree is committed and the build is reproducible.
