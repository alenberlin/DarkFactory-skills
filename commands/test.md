---
description: "Drive a change with tests — failing test first, reproduction test for bugs — and prove it works."
---

Apply the `test-driven-development` skill.

$ARGUMENTS

If this is a bug, write a reproduction test that fails against the current code first, then fix, then confirm it passes. For new behavior, write the failing test before the implementation. Test state not interactions, prefer real implementations over mocks, and name tests like a specification. For browser behavior, pair with `runtime-verification`. Finish by running the full suite and reporting the result — no skipped or disabled tests.
