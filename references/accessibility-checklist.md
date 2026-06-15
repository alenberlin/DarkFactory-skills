# Accessibility Checklist (WCAG-aligned)

Companion to the `ui-engineering` skill. Accessibility is part of "production-quality," not a later pass.

## Semantics & structure
- [ ] Native elements used for their meaning (`button`, `a`, `nav`, `main`, headings in order)
- [ ] One `h1` per page; headings nest logically (no skipped levels)
- [ ] Lists, tables, and landmarks marked up as such (not `div` soup)
- [ ] ARIA only where native semantics fall short — and used correctly

## Keyboard & focus
- [ ] Every interactive element reachable and operable by keyboard
- [ ] Visible focus indicator on all focusable elements
- [ ] Logical tab order; no keyboard traps
- [ ] Custom widgets implement expected key interactions (Esc, arrows, Enter/Space)

## Forms
- [ ] Every input has an associated `<label>` (not placeholder-as-label)
- [ ] Errors announced and tied to their field (`aria-describedby`)
- [ ] Required/invalid states conveyed beyond color alone

## Visual & content
- [ ] Text contrast ≥ 4.5:1 (≥ 3:1 for large text and UI components)
- [ ] Information never conveyed by color alone
- [ ] Images have meaningful `alt`; decorative images have empty `alt=""`
- [ ] Layout reflows without loss at 200% zoom / narrow viewports
- [ ] Motion respects `prefers-reduced-motion`

## States
- [ ] Loading, empty, and error states are perceivable to assistive tech
- [ ] Live updates announced (`aria-live`) where relevant
