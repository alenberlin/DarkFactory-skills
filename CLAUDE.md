# Dark Factory — agent entry point

Read **[`AGENTS.md`](AGENTS.md)** in this same folder and follow it.

Claude Code reads `CLAUDE.md`; Codex and most other tools read `AGENTS.md`. Keeping the instructions in `AGENTS.md` and pointing this file at it means every tool follows one source of truth, with no lock-in to a single assistant.

These two files are the canonical entry layer for the Dark Factory workflow. To enable it elsewhere, copy both into your global agent config or a project root and set the path inside `AGENTS.md`. See [`docs/WORKFLOW.md`](docs/WORKFLOW.md).
