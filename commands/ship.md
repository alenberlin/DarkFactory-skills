---
description: Pre-ship gate — fan out to reviewer, security, and test personas in parallel, merge into a go/no-go with a rollback plan, then ship safely.
---

Run the pre-ship gate for the current change.

$ARGUMENTS

**1. Fan out (parallel, independent contexts).** Invoke these personas concurrently on the change:
- `code-reviewer` — five-axis quality
- `security-auditor` — vulnerability audit
- `test-engineer` — coverage and missing reproduction tests
- `performance-auditor` — only if the change is user-facing or touches a hot path

Personas do not call each other; each returns its own report.

**2. Merge.** Synthesize the reports in this context into a single decision:
- **GO** only if no persona reports a Critical finding.
- **NO-GO** otherwise — list the blocking findings and stop.

**3. Ship (on GO).** Apply `git-and-shipping`: confirm CI gates green, migrations reversible, then state the staged-rollout and **rollback plan (with its trigger symptom) before deploying**. Deploying is outward-facing and hard to reverse — confirm with the developer before executing it, even on GO. After deploy, confirm post-deploy health rather than assuming it. Record any non-obvious decision via `memory-and-context`.

Output a go/no-go summary, the merged Critical/Important findings, and the rollback plan.
