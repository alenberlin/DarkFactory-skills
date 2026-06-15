---
name: performance-optimization
description: Improves performance by measuring first and optimizing only what the data implicates. Use when performance requirements exist, when you suspect a regression, or when load times or Core Web Vitals need to improve. Use when profiling reveals a real bottleneck.
---

# Performance Optimization

## Overview

Most performance work is wasted because it optimizes the wrong thing. The discipline is: **measure first.** Find the actual bottleneck with data, fix that, then measure again to confirm the win. Intuition about what's slow is frequently wrong, and "optimized" code that's harder to read but no faster is a pure loss. Optimize what the profiler implicates — nothing else.

## When to Use

- A stated performance budget or SLA exists
- A regression is suspected (it got slower)
- Core Web Vitals (LCP, CLS, INP) or server latency need to improve
- Profiling has surfaced a concrete hotspot

**When NOT to use:** speculative micro-optimization with no measurement, or trading real readability for an unmeasured "maybe faster." Don't optimize before there's a number.

## Process

### 1. Set the target and measure the baseline
Define what "fast enough" means (a number: p95 latency, LCP < 2.5s, query < 50ms). Measure current state under realistic conditions — production-like data volume, not a 3-row dev table. Without a baseline you can't prove a win.

### 2. Profile to find the real bottleneck
Let the data point to the hotspot. Common, high-yield culprits:
- **N+1 queries** — a query per row instead of one batched query. The most common backend killer.
- **Unbounded data** — fetching/rendering an unpaginated list that grows without limit.
- **Missing indexes** — full scans on filtered/sorted columns.
- **Synchronous work on the hot path** — blocking I/O that should be async or backgrounded.
- **Frontend:** oversized bundles, render-blocking resources, unnecessary re-renders, unoptimized images, layout thrash.

### 3. Fix the implicated bottleneck — measure again
Change the one thing the profile implicated, then re-measure against the baseline. If it didn't move the number, revert it — an optimization that doesn't measurably help is just added complexity.
```python
# N+1 → one query
# Before: one lookup per task
tasks = get_tasks()
for t in tasks:
    t.assignee = get_user(t.assignee_id)   # N queries
# After: batch
assignees = get_users([t.assignee_id for t in tasks])  # 1 query
```

### 4. Respect the order of magnitude
Algorithmic and I/O wins (remove N+1, add an index, cache a slow call) dwarf micro-optimizations. Fix the big rock before polishing pebbles. Caching is powerful but adds invalidation complexity — reach for it after the cheaper structural fixes.

### 5. Guard the win
Add a test or budget so the regression can't silently return — see the CI quality gates in `git-and-shipping`. A performance fix with no guard decays.

## Checklist

For backend and Core Web Vitals specifics, see `references/performance-checklist.md`.

## Red Flags

- Optimizing with no baseline measurement
- "This should be faster" with no profile to back it
- A readability sacrifice with no measured speedup
- Caching added before the underlying query/algorithm was addressed
- A fix declared a win without a re-measurement
- N+1 queries shipped because they were fast on dev-sized data

## Verification

- [ ] A concrete target and a baseline measurement exist
- [ ] The fix targets a profiler-implicated bottleneck, not a guess
- [ ] Re-measurement confirms the improvement against the baseline
- [ ] Changes that didn't move the number were reverted
- [ ] A test or budget guards against regression
