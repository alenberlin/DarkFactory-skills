# The Dark Factory Workflow

An opt-in mode that runs a project through the full development lifecycle — discovery, build, verification, and review — with a single planning checkpoint up front and autonomous execution after it. The agent follows [`ORCHESTRATOR.md`](../ORCHESTRATOR.md); this page explains what it does and how to turn it on.

It is **off by default.** Simple, one-off tasks are untouched. You engage it deliberately, per project.

## What it does

1. **Discovery** — the `architect` skill interviews you to absolute clarity on intent, tech stack, functionality, and non-goals, then writes a blueprint (a PRD and a phased plan with acceptance criteria) into your project.
2. **Approval (the one checkpoint)** — you approve the blueprint. Nothing is built before this; little interrupts you after.
3. **Autonomous loop** — milestone by milestone, the agent builds, tests, fixes, and commits, without pausing between milestones, until each milestone's acceptance criteria pass.
4. **Integration & review** — whole-app verification plus a five-axis review, looping until the project's acceptance criteria pass and no critical issues remain.

Deployment is deliberately secondary, and never automatic.

## Turning it on

### Claude Code — the `/darkfactory` command

```
/darkfactory build a task tracker with a GET /tasks endpoint and a dashboard list
```

This loads the orchestrator and starts discovery immediately. It also records engagement for the project (see the marker below) so the choice stays consistent.

### Any tool — the engagement gate

For a tool-agnostic, "ask me once per project" setup, add this block to your **global** agent instruction file (`~/.claude/CLAUDE.md`, your `AGENTS.md`, or your Cursor rules), and replace `<path-to-darkfactory>` with where this pack lives:

```
## Dark Factory workflow  (lives at <path-to-darkfactory>)
Before engaging, check this project for a file named `.darkfactory`:
- contains `engage`  → read <path-to-darkfactory>/ORCHESTRATOR.md and follow it.
- contains `ignore`  → proceed normally; don't mention this again.
- missing            → ask once: "Engage the Dark Factory workflow for this project? (engage / ignore)",
                       then write the answer to `.darkfactory`.
Do not load the orchestrator unless engaged.
```

Because it lives in the file every agent reads on startup, the same setup works in Claude Code, Codex, Cursor, and anything else that reads an instruction file — and because it is gated by a question, it never runs on a project you did not opt into.

## The `.darkfactory` marker

A one-line file in the project root recording your choice — `engage` or `ignore`. The gate writes it the first time you answer, then honors it silently, so you are asked at most once per project. Delete it to be asked again.

Commit it to share the decision with your team, or add it to `.gitignore` to keep it personal.

## What it creates in your project

| Path | Purpose |
|---|---|
| `.darkfactory` | Your engage / ignore choice. |
| `docs/darkfactory/PRD.md` | The blueprint: scope, acceptance criteria, non-goals. |
| `docs/darkfactory/PLAN.md` | Phased milestones, each with acceptance criteria. |
| `docs/darkfactory/PROGRESS.md` | Milestone status — the loop is resumable and visible. |
| `.memory/` | Session handoff and pickup (via `memory-and-context`). |

## Relationship to the session hook

The `SessionStart` hook loads only the light baseline — task routing and the core operating behaviors (`using-skills`). The full workflow is **never auto-loaded**; it engages only through the `/darkfactory` command or the gate above. Leaving the workflow off changes nothing about that baseline.
