---
description: Implement the confirmed plan in thin, test-driven vertical slices, one verified commit at a time.
---

Implement the current plan using `incremental-implementation`, driven by `test-driven-development`.

$ARGUMENTS

For each slice, riskiest first: write a failing test, make it pass with the minimum code, refactor green, verify, and commit it atomically before starting the next. Use `source-driven-development` for any external API you're not certain about, and stay surgical — touch only what the slice needs. Stop and switch to `debugging-and-recovery` if a slice won't go green.

**`/build auto`:** if the argument is `auto`, generate the task plan and implement every slice in one approved pass — still test-driven and committed individually, pausing on failures or risky steps. Approve the plan once, then it runs.
