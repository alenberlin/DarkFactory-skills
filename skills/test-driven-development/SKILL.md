---
name: test-driven-development
description: Drives implementation with tests — a failing test before the code, a reproduction test before a bug fix. Use when implementing any logic, fixing any bug, or changing any behavior. Use when you need proof that code works rather than a feeling that it does.
---

# Test-Driven Development

## Overview

Write a failing test before the code that makes it pass. For bug fixes, reproduce the bug with a failing test before attempting a fix. Tests are proof — "seems right" is not done. A codebase with good tests can be changed safely; one without is a liability, because nothing catches the regression your next change introduces.

## When to Use

- Implementing any new logic or behavior
- Fixing any bug (the Prove-It pattern below)
- Modifying or refactoring existing functionality
- Adding edge-case handling

**When NOT to use:** pure config changes, documentation, or static content with no behavioral impact. Don't write a test that asserts a constant.

## The Cycle: Red → Green → Refactor

```
   RED                 GREEN                REFACTOR
Write a test      Write the minimum     Clean up with the
that fails   ──→  code to pass it  ──→  tests still green  ──→ (repeat)
```

### RED — write a failing test
It must fail first. A test that passes immediately proves nothing.

```typescript
// TypeScript (vitest/jest)
it('creates a task with a default pending status', async () => {
  const task = await createTask({ title: 'Buy groceries' });
  expect(task.id).toBeDefined();
  expect(task.title).toBe('Buy groceries');
  expect(task.status).toBe('pending');
});
```
```python
# Python (pytest)
async def test_creates_task_with_default_pending_status():
    task = await create_task(title="Buy groceries")
    assert task.id is not None
    assert task.title == "Buy groceries"
    assert task.status == "pending"
```

### GREEN — make it pass
Write the *minimum* to go green. Don't over-engineer ahead of a test that demands it.

### REFACTOR — clean up
With tests green, improve names, remove duplication, extract shared logic — running the tests after each step to confirm behavior is unchanged.

## The Prove-It Pattern (bug fixes)

When a bug is reported, **do not start by fixing it.** Start by writing a test that reproduces it.

```
Bug report → write a test that demonstrates it → test FAILS (bug confirmed)
          → implement the fix → test PASSES (fix proven) → run full suite (no regressions)
```

The reproduction test is the thing that stops the bug from coming back. A fix without one is a fix on probation.

## The Test Pyramid

Most tests small and fast; progressively fewer higher up.

```
        ╱╲      E2E (~5%)         full user flows, real browser/runtime
       ╱──╲     Integration (~15%) boundaries: API, DB, file system
      ╱────╲    Unit (~80%)        pure logic, isolated, milliseconds
```

| Size | Constraints | Speed | Example |
|------|-------------|-------|---------|
| Small | One process, no I/O, no network, no DB | ms | pure functions, transforms |
| Medium | Localhost only, no external services | seconds | API tests with a test DB |
| Large | External services allowed | minutes | E2E, perf benchmarks |

Keep large tests to genuinely critical paths — they're slow and flakier.

## Writing Good Tests

**Test state, not interactions.** Assert on the outcome, not on which internal methods were called — interaction tests break on every refactor even when behavior is unchanged.
```typescript
// Good: outcome
expect(tasks[0].createdAt.getTime()).toBeGreaterThan(tasks[1].createdAt.getTime());
// Bad: implementation detail
expect(db.query).toHaveBeenCalledWith(expect.stringContaining('ORDER BY created_at DESC'));
```

**DAMP over DRY in tests.** Production code prefers DRY; tests prefer *Descriptive And Meaningful Phrases*. A test should read like a spec without forcing the reader to trace shared helpers. Some duplication is fine when it makes each test independently readable.

**Prefer real implementations.** Confidence order: real > fake (in-memory) > stub > mock. Mock only at boundaries that are slow, non-deterministic, or have uncontrollable side effects (external APIs, email). Over-mocking yields tests that pass while production breaks.

**Arrange–Act–Assert**, one concept per test, and names that read like a specification:
```python
def test_marks_task_overdue_when_deadline_has_passed():
    task = create_task(title="Test", deadline=date(2025, 1, 1))   # Arrange
    result = check_overdue(task, today=date(2025, 1, 2))          # Act
    assert result.is_overdue is True                              # Assert
```
```
describe('completeTask'):
  ✓ sets status to completed and records the timestamp
  ✓ throws NotFoundError for a non-existent task
  ✓ is idempotent — completing a completed task is a no-op
```

## Anti-Patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| Testing implementation details | Breaks on refactor despite unchanged behavior | Test inputs and outputs |
| Flaky tests (timing/order) | Erode trust in the whole suite | Deterministic assertions, isolated state |
| Testing framework code | Wastes effort on third-party behavior | Test only your code |
| Snapshot abuse | Huge snapshots nobody reviews | Use sparingly, review every change |
| Mocking everything | Green tests, broken production | Mock only at slow/non-deterministic boundaries |

## Browser-based behavior

Unit tests alone can't confirm something renders and behaves correctly in a real browser. For that, pair this skill with `runtime-verification` to inspect the DOM, console, and network with live data.

## Red Flags

- Code written with no corresponding test
- A test that passed on its very first run (it may not test what you think)
- "All tests pass" when no test was actually run
- A bug fix with no reproduction test
- Skipping or disabling tests to make the suite green
- Re-running an unchanged suite "just to be sure" — after a clean run, that adds nothing until the code changes

## Verification

- [ ] Every new behavior has a test
- [ ] The full suite passes (`npm test` / `pytest`)
- [ ] Each bug fix includes a reproduction test that failed before the fix
- [ ] Test names describe the behavior being verified
- [ ] No tests were skipped or disabled to pass
- [ ] Coverage did not decrease (if tracked)

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll write tests after it works" | You won't. And after-the-fact tests test the implementation, not the intent. |
| "Too simple to test" | Simple code grows complicated. The test documents the expected behavior. |
| "Tests slow me down" | Now, yes. They speed up every future change to this code. |
| "I tested it manually" | Manual testing doesn't persist. Tomorrow's change breaks it silently. |
| "It's just a prototype" | Prototypes become production. Tests from day one prevent the test-debt crisis. |
