---
name: ui-engineering
description: "Builds production-quality, accessible UI and keeps it visually consistent via a component registry. Use when creating or modifying user-facing components, layouts, or state. Use when the output needs to look intentional and cohesive rather than AI-generated."
---

## Autopilot handoff

Use the approved design baseline, tokens and component registry within the task’s scope. Reuse the existing UI conventions and verify responsive behavior, keyboard access, focus, labels, errors and empty/loading states. Resolve ordinary design choices autonomously; material changes to approved requirements return for clarification.

For assigned factory work, read [the shared runtime contract](../../docs/RUNTIME_CONTRACT.md). It defines authority, proposal fields, approval scope and evidence identity. These skills remain language agnostic; the approved profile selects actual commands.


# UI Engineering

## Overview

AI-built UIs drift. Each component is generated in isolation, so spacing wanders, radii vary, colors are *almost* the same, and the app ends up looking like five people with different taste built it. This skill does two things: it sets the bar for production-quality, accessible components, and it maintains a `ui-registry.md` ledger so every new component matches the ones already built.

## When to Use

- Building or modifying any user-facing component, layout, or interaction
- Managing component state, loading, empty, and error views
- Any time visual consistency across the app matters

**When NOT to use:** non-visual logic, build config, or throwaway internal tooling where polish doesn't matter.

## Process

### 1. Check the registry before you build
At the start of UI work, read `ui-registry.md`. Building a new card? Match the existing card's background, border, radius, padding. A new button? Reuse the established button pattern. The registry is the source of truth for "what does a thing like this already look like here."

### 2. Build to production quality
- **Accessibility is not optional.** Semantic elements, labels, keyboard operability, focus states, and adequate contrast. See `references/accessibility-checklist.md`.
- **Handle every state.** Loading, empty, error, and success — not just the happy path. An empty list and a failed fetch are real UI, not afterthoughts.
- **Use the design system.** Tokens/variables and system classes, never hardcoded hex or one-off magic numbers. If a value isn't in the system, that's a decision to surface, not to hardcode.
- **Responsive by default**, but capture the base pattern in the registry, not every breakpoint.

### 3. Imprint what you built into the registry
After a component is built, record the consistency-bearing properties (not the context-dependent ones) so the next component can match.

**Capture:** background, border, radius, text colors/sizes/weights, padding and gaps, hover/focus/active states, shadow, accent usage.
**Skip:** width/height, flex/grid structure, positioning/z-index, animation timing, breakpoint variants.

Append (don't overwrite) an entry; update in place if the component type already exists:
```markdown
### Card
File: src/components/Card.tsx  ·  Updated: 2026-06-15

| Property        | Class / token        |
| --------------- | -------------------- |
| Background      | bg-surface           |
| Border          | border border-subtle |
| Radius          | rounded-lg           |
| Text — primary  | text-foreground      |
| Text — muted    | text-muted           |
| Padding         | p-4                  |
| Hover           | hover:bg-surface-hover |
| Shadow          | shadow-sm            |

**Notes:** All cards match these. Accent border (border-accent) only for the selected state.
```

### 4. Flag inconsistency when you see it
If building this component surfaced a conflict with the registry (a second radius, a near-duplicate color), surface it to the developer rather than silently picking one.

### Audit mode
When inheriting an untracked UI: scan all components, list every variation per property (every `rounded-*`, every bg color, every hardcoded hex), recommend a baseline from what the majority does correctly, and — after the developer confirms — write that baseline to `ui-registry.md` plus a list of components that deviate. Establish the baseline before imprinting individual components going forward.

## Red Flags

- Hardcoded hex values or magic spacing instead of tokens
- A new component built without checking the registry first
- Only the happy path implemented — no empty/loading/error state
- Missing focus states, labels, or keyboard support
- A second radius/shadow/color introduced where one already existed

## Verification

- [ ] The registry was checked before building, and updated after
- [ ] Loading, empty, and error states are handled
- [ ] Accessibility checklist passes (semantics, labels, keyboard, contrast, focus)
- [ ] No hardcoded values that should be design tokens
- [ ] New component matches existing patterns, or the conflict was surfaced
