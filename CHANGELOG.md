# Changelog

## [0.2.0] — 2026-07-08

### Changed
- Fixed plugin machinery for Claude Code marketplace compatibility
- Hardened the autonomous workflow (`/darkfactory`) — more robust recovery from failures

## [0.1.0] — 2026-07-07

### Added
- Initial release with 15 lifecycle skills (define → build → verify → review → ship → sustain)
- 6 commands: `/architect`, `/build`, `/test`, `/review`, `/ship`, `/darkfactory`
- 4 review personas: `code-reviewer`, `security-auditor`, `test-engineer`, `performance-auditor`
- Autonomous workflow (`/darkfactory`) — end-to-end lifecycle from a single planning checkpoint
- `SessionStart` hook that auto-loads the `using-skills` meta-skill
- Claude Code plugin manifest (`marketplace.json`, `plugin.json`)
- Apache 2.0 license
