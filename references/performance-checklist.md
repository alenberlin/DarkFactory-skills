# Performance Checklist

Companion to the `performance-optimization` skill. Measure before and after — every box here is a hypothesis to confirm with data, not a blanket rule.

## Always first
- [ ] A target number is defined (p95 latency, LCP, query time)
- [ ] A baseline is measured under production-like data volume
- [ ] A profile points to the bottleneck before any change

## Backend / data
- [ ] No N+1 queries (batch, join, or preload instead)
- [ ] Indexes cover filtered/sorted/joined columns
- [ ] List endpoints paginated; no unbounded result sets
- [ ] Expensive/slow calls cached only after structural fixes — with an invalidation plan
- [ ] Blocking I/O on the hot path made async or backgrounded
- [ ] Connection pooling configured; no per-request connect/teardown

## Frontend / Core Web Vitals
- [ ] **LCP < 2.5s** — optimize the largest element; preload critical assets
- [ ] **CLS < 0.1** — reserve space for images/embeds; no layout shift on load
- [ ] **INP < 200ms** — break up long tasks (>50ms); defer non-critical JS
- [ ] Bundle size budgeted; code-split; tree-shaken
- [ ] Images right-sized, modern formats, lazy-loaded below the fold
- [ ] No unnecessary re-renders (memoization where the profile shows churn)

## Guard the win
- [ ] Re-measured against baseline — the number actually moved
- [ ] Changes that didn't help were reverted
- [ ] A test or CI budget guards against regression
