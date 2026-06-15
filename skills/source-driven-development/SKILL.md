---
name: source-driven-development
description: Grounds implementation in official, current documentation instead of memory. Use when building with any framework or library where correctness matters, when using an API you're not certain about, or when you want code free of outdated or hallucinated patterns.
---

# Source-Driven Development

## Overview

Model memory has a cutoff and a confidence problem: it will produce plausible, outdated, or invented API usage with total conviction. The fix is cheap — verify against the official source before writing code that depends on it. The most current, authoritative documentation wins over what "looks right." This is the guardrail that keeps a codebase on current standards instead of last year's patterns.

## When to Use

- Using a framework/library API you're not 100% certain about
- Building on anything fast-moving (framework majors, cloud SDKs, browser APIs)
- A method signature, config option, or default that you're recalling from memory
- Behavior that must be exactly right (auth flows, payment APIs, security primitives)

**When NOT to use:** stable language built-ins and well-worn patterns you can verify by running them; trivial code where the cost of a quick test is lower than a doc lookup.

## Process

### 1. Identify the load-bearing claims
Before implementing, list the specific things you're assuming about the external API — the signature, the option name, the default, the return shape, the error behavior. Those are what to verify.

### 2. Go to the authoritative source, in order of trust
1. Official documentation for the exact version in `package.json` / `requirements.txt` / lockfile
2. Official type definitions or the library source itself
3. Official changelog/migration guide (for "did this change?" questions)
4. Reputable secondary sources only to find the primary one

Check the **version**. Docs for v5 are wrong for your v4. Match the source to the installed version.

### 3. Verify, then cite
Confirm the claim, then leave a short cite so the next reader (human or agent) can trust it without re-deriving:
```typescript
// Per React 19 docs: `use()` unwraps a promise and must be called during render.
// https://react.dev/reference/react/use
const data = use(dataPromise);
```
```python
# httpx 0.27: `AsyncClient` must be used as an async context manager or explicitly aclose()'d.
# https://www.python-httpx.org/async/
async with httpx.AsyncClient() as client:
    resp = await client.get(url)
```

### 4. When the source disagrees with your memory, the source wins
If the docs contradict what you were about to write, stop and correct course. Don't average them. Don't assume the docs are wrong.

### 5. When the source is silent
If the official docs don't cover it, say so explicitly, prefer the most conservative interpretation, and verify behavior with a small test (`test-driven-development`) rather than guessing.

## Red Flags

- Confident API usage you can't point to a source for
- Code that matches a pattern from "a couple years ago"
- A method or option name you're "pretty sure" exists
- Docs consulted for the wrong major version
- Copy-pasted snippets with no check against the installed version

## Verification

- [ ] Load-bearing external API usage was checked against official docs for the installed version
- [ ] Non-obvious external calls carry a short source cite
- [ ] Where memory and source disagreed, the source was followed
- [ ] Anything the docs didn't cover was confirmed with a test, not a guess
