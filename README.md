# DarkFactory Autopilot

Language-agnostic engineering skills and a local software factory runtime.
Describe a product, resolve its requirements, approve the complete blueprint,
and run isolated implementation → verification → independent review → repair →
integration. The verified delivery awaits your acceptance. Release is separate.

The pack has **24 skills, 14 roles and seven commands**, with a Python runtime,
transactional SQLite state, Docker execution, protected policy/evidence gates,
controlled Git integration, a CLI, loopback API and optional dashboard.
The local implementation includes foreground modes, durable recovery, scoped finding
exceptions and correction tasks. Engineering checks are recorded against exact source;
your real-project acceptance and live provider pilot remain pending. [Current evidence and limits](docs/autopilot/PROGRESS.md) are authoritative
for this upgrade. Skills alone do not enforce policies or run in the background.

- [Workflow and trust-boundary diagram](docs/autopilot/TAM.md)
- [Step-by-step setup and trial](docs/GETTING_STARTED.md)
- [Operating guide and compatibility](docs/AUTOPILOT.md)
- [User guide](docs/USER_GUIDE.md)
- [Shared runtime/agent contract](docs/RUNTIME_CONTRACT.md)
- [Approved upgrade blueprint](docs/autopilot/BLUEPRINT.md)

## Skill routing

| Responsibility | Skills |
| --- | --- |
| Discover and define | product-discovery, architect, api-and-interface-design, implementation-planning |
| Implement | incremental-implementation, ui-engineering, source-driven-development |
| Verify and repair | test-driven-development, runtime-verification, debugging-and-recovery, quality-assurance |
| Review and improve | code-review, security-and-hardening, performance-optimization, code-simplification |
| Operate and integrate | factory-control, durable-execution, policy-enforcement, parallel-integration |
| Deliver and sustain | acceptance-validation, documentation-delivery, git-and-shipping, memory-and-context |
| Route | using-skills |

Individual skills remain useful in interactive work. Full Autopilot is opt-in per
project through `.darkfactory`; `ignore` keeps it inactive unless explicitly
invoked. Approval records scope, permissions and limits; human acceptance binds
to the delivery revision. Python, Node.js/TypeScript, Rust and mixed targets use
the same lifecycle with project-selected toolchain images and real commands.

## Local runtime

```sh
uv sync --python /path/to/python-with-supported-sqlite
uv run factory --help
uv run python scripts/export_schemas.py
uv run python scripts/validate_pack.py
uv run ruff check src tests scripts
uv run mypy
uv run pytest
uv build
```

Python 3.12+ and SQLite 3.51.3+ are required. Tests exercise actual Docker and Git;
provision the declared local test images using the operating guide. Native CLI
and provider conformance are recorded separately from offline fixture tests.
No global service or configuration is installed automatically.

## Claude Code plugin

```text
/plugin marketplace add alenberlin/DarkFactory-skills
/plugin install darkfactory@darkfactory-skills
```

For this modified folder, use your host's supported local plugin-loading method;
the remote marketplace release is not updated by these local changes. Commands:
`/architect`, `/build`, `/test`, `/review`, `/ship`, `/darkfactory`, `/factory`.
The session hook respects project opt-in and only supplies routing instructions.
[Roles](docs/PERSONAS.md) are activated per task and cannot grant themselves
administrative powers.

## License and contributions

[Apache License 2.0](LICENSE) © 2026 [Alen Mikic](https://alen-ai.com).
Preserve [NOTICE](NOTICE) when redistributing. Existing attribution, reference
checklists and individual engineering guidance are retained.
[Contribution guidance](CONTRIBUTING.md), [code of conduct](CODE_OF_CONDUCT.md),
and [changelog](CHANGELOG.md) remain part of the pack.
