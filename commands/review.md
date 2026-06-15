---
description: Five-axis review of the current change in a fresh context — report findings by severity, don't auto-fix.
---

Invoke the `code-reviewer` persona to review the current change (staged changes or recent commits).

$ARGUMENTS

Review across all five axes — correctness, readability, architecture, security, performance — reading the tests first to establish intent. Categorize every finding as Critical, Important, or Suggestion with `file:line` references and a fix recommendation for each Critical/Important. Report only; do not apply fixes. The developer decides what to act on.
