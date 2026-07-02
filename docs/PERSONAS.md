# Personas

Fresh-context sub-agents, each providing one perspective on one artifact. They let a review run in a clean context window, separate from the session that produced the code.

## The governing rule

**The user, or a slash command, is the orchestrator. Personas never invoke other personas.**

A persona that delegates to another creates hidden call chains that are hard to follow. If `code-reviewer` thinks a security deep-dive is warranted, it *says so in its report* — it does not spawn `security-auditor`. Orchestration belongs to slash commands.

## Patterns

- **Direct** — one persona, one perspective. `"Review this PR"` → `code-reviewer`. The default.
- **Single-persona command** — a slash command wraps one persona with the right skills (`/review` → `code-reviewer`). A saved, repeatable prompt.
- **Parallel fan-out + merge** — independent perspectives run concurrently, then the main agent merges. `/ship` fans out to `code-reviewer` + `security-auditor` + `test-engineer` (+ `performance-auditor` for user-facing changes) and synthesizes a go/no-go with a rollback note.

Use fan-out only when the perspectives are genuinely independent and each benefits from its own context window. Otherwise prefer direct invocation.

## The personas

| Persona | Perspective | Backing skill |
|---|---|---|
| `code-reviewer` | Five-axis quality before merge | `code-review` |
| `security-auditor` | Adversarial security audit | `security-and-hardening` |
| `test-engineer` | Coverage and reproduction tests | `test-driven-development` |
| `performance-auditor` | Bottlenecks and Core Web Vitals | `performance-optimization` |
