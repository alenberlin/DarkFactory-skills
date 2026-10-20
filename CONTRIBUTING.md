# Contributing to Dark Factory Skills

Thanks for helping make AI coding agents better! Here's how to contribute.

## Quick start

1. **Find something to work on.** Check [open issues](https://github.com/alenberlin/DarkFactory-skills/issues) or open one yourself.
2. **Fork and clone.** Standard GitHub flow.
3. **Make your change.** Skills are Markdown; runtime changes also require the executable checks below.
4. **Open a PR.** Describe what you changed and why. Link any related issues.

## What to contribute

### Skills

The highest-impact contributions are improvements to existing skills:

- **Sharper instructions** — clearer language, fewer ambiguities
- **Better examples** — real-world scenarios that demonstrate the skill in action
- **Edge cases** — situations where the skill currently gives wrong or incomplete guidance
- **Language coverage** — adding Python examples alongside TypeScript (or vice versa)
- **Tool-specific guidance** — instructions for agent tools beyond Claude Code

### New skills

New skills are welcome if they cover a distinct lifecycle phase not already handled. Before writing one:

1. Open an issue describing the gap — what phase isn't covered, and what a good outcome looks like
2. Follow the [skill anatomy guide](docs/skill-anatomy.md) for structure
3. Add it to the README skill table in the right phase

### Agents (personas)

Review personas are specialized sub-agents. To contribute a new one:

1. Open an issue explaining the perspective (what kind of review it does, why the existing four don't cover it)
2. Write it following the pattern in `agents/`
3. Register it in `.claude-plugin/plugin.json` and the runtime role routing; roles never auto-grant permissions

## Runtime verification

Use the supported Python/SQLite environment documented in `docs/AUTOPILOT.md`.
Run the relevant narrow test first, then `uv run ruff check src tests scripts`,
`uv run mypy`, `uv run pytest`, `uv build`, and
`uv run python scripts/validate_pack.py`. Regenerate contracts with
`uv run python scripts/export_schemas.py`; do not edit generated schemas or
lockfiles by hand. Real Docker/Git tests must remain real. Label offline fixtures
separately from live provider evidence, and preserve failed evidence and known gaps.

### Documentation

Docs improvements are always welcome — typos, clarity, missing sections, better examples.

## Style guide

- **Imperative, not descriptive.** Write "Do X" not "You should do X."
- **One idea per sentence.** Skills are consumed by LLMs — shorter sentences parse better.
- **No fluff.** If a sentence doesn't change what the agent does, cut it.
- **Checklists over prose.** Agents follow checklists more reliably than paragraphs.
- **Verification is mandatory.** Every skill must tell the agent how to verify its work.

## Pull request checklist

- [ ] Your change has a clear purpose (linked issue or explained in PR description)
- [ ] You've read the relevant [skill anatomy guide](docs/skill-anatomy.md)
- [ ] For new skills: it covers a distinct phase not already handled
- [ ] Documentation is updated if needed (README skill table, user guide)
- [ ] License headers are preserved

## License

By contributing, you agree your work will be licensed under [Apache 2.0](LICENSE).
