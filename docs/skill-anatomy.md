# Skill Anatomy — Dark Factory

Every skill in this pack has the same shape. Consistency is what makes the pack feel like one tool rather than a loose collection.

## File layout

- One skill per directory: `skills/<name>/SKILL.md`
- Supporting files only when `SKILL.md` would exceed ~250 lines — push long reference material to `references/<topic>.md` and link to it
- Scripts, if any, live in `skills/<name>/scripts/`

## Frontmatter (required)

```yaml
---
name: <kebab-case, matches the directory name>
description: <One sentence, third person, what the skill does.> Use when <trigger>. Use when <trigger>.
---
```

The `description` is the only thing an agent reads when deciding whether to load the skill. Lead with what it does, then give concrete `Use when …` triggers. No marketing voice — "Think like a senior engineer" is not a trigger; "Use when starting a new feature and no spec exists" is.

## Sections, in order

1. `# Title`
2. `## Overview` — 2–4 sentences. The principle and why it matters.
3. `## When to Use` — bullet triggers, followed by a **When NOT to use** list. Every skill must say when to stay out of the way.
4. `## Process` — the actual steps, in order, with **polyglot (TypeScript + Python)** examples wherever code clarifies the point.
5. `## Red Flags` — observable signals that the skill is being violated.
6. `## Verification` — a checklist. A task is not done until this passes.
7. `## Common Rationalizations` *(optional)* — a table of excuse → reality, for skills people are tempted to skip.

## Principles

- **Merge, don't accumulate.** If two skills overlap, reference instead of duplicating.
- **Workflows, not suggestions.** Steps run in order. Verification is not optional.
- **Report, don't auto-fix** where a human owns the decision (review, security, recovery diagnosis).
- **Amplify the developer's thinking — never replace the developer's judgment.**
- **Cut anything inessential.** If a staff engineer wouldn't read it twice, cut it.
