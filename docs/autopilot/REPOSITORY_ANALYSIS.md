# Repository reuse and gap analysis

Status: source inspection completed; runtime implementation not started

## Inspection boundary

Inspected the 15 `skills/*/SKILL.md` files, four `agents/*.md` personas, six
`commands/*.md` wrappers, `ORCHESTRATOR.md`, root agent entry files, both plugin
manifests, the hook configuration and script, README, workflow and user guides,
persona and anatomy guides, contribution guidance, reference checklists, notice,
changelog, ignore rules, and issue/PR templates.

The existing codebase-memory index identifies Markdown sections and a single
Bash script. There is no runtime implementation, package manifest, database,
worker, test suite, API, or dashboard in the inspected folder. No existing test
suite was executed because none is present. This analysis does not certify
provider integrations, security enforcement, or continuous execution.

The folder is not currently a Git checkout. Its `.darkfactory` marker contains
`ignore`. The orchestrator was inspected as source for this requested upgrade;
its autonomous workflow was not activated and the marker was not changed.

Read-only environment probes found Python, Node.js, uv, Docker with a responding
Linux engine, Claude Code, and Codex. Both coding CLIs expose noninteractive
execution and structured output. These observations establish development
prerequisites only; they do not prove sandboxing, authentication, or Strict
adapter compatibility. Rust tooling has not yet been probed.

## Reuse assessment

| Existing asset | Decision | Required upgrade |
| --- | --- | --- |
| `using-skills` | Retain and update | Route factory tasks; distinguish approved autonomous scope from interactive discovery |
| `architect` | Retain and expand | Full architecture, threat model, design artifacts, and approved blueprint revisions |
| `api-and-interface-design` | Retain | Versioned task, policy, evidence, approval, and adapter contracts |
| `incremental-implementation` | Retain and update | Requirement-linked tasks, isolated workspaces, gated completion and authorized commits |
| `test-driven-development` | Retain and update | Protected verification definitions, red/green evidence, revision identity, meaningful coverage |
| `runtime-verification` | Retain and update | Browser and backend observations with trusted execution and evidence capture |
| `debugging-and-recovery` | Retain and update | Durable attempt history, bounded strategies, fresh sessions, safe continuation of independent tasks |
| `code-review` | Retain and update | Independent reviewer identity, persistent blocking findings, remediation and re-review |
| `code-simplification` | Retain | Preserve behavior and approved scope; revalidate affected evidence |
| `security-and-hardening` | Retain and extend | Separate application security from factory execution security |
| `performance-optimization` | Retain | Approved measurable targets, reproducible profiles, revision-linked evidence |
| `git-and-shipping` | Retain and update | Explicit commit permissions, trusted integration, separate release authorization |
| `memory-and-context` | Retain and update | Database authority, bounded context rehydration, Markdown as human-readable projections |
| `ui-engineering` | Retain and update | Preserve component registry and accessibility; delegate ordinary design choices within approved scope |
| `source-driven-development` | Retain | Verify provider/toolchain APIs by actual version and record sources |
| Four review personas | Retain and update | Structured, independently attributed findings with explicit coverage limits |
| Six slash commands | Preserve and adapt | Route factory operation through the real runtime; retain individual interactive workflows |
| `ORCHESTRATOR.md` | Replace operational assumptions | Runtime-controlled orchestration; initial approval plus final human acceptance |
| Session hook | Retain as discovery aid | Do not present instruction injection as enforcement or persistent execution |
| Plugin manifests | Retain identity and update registration | Add skills, roles, and factory command without unsupported compatibility claims |
| Reference checklists | Retain and connect | Attach relevant criteria to configured trusted checks and review evidence |
| Guides and contribution templates | Update together | Explain install, commands, permission boundaries, modes, tests, and actual support |
| License, NOTICE, assets | Preserve | Keep attribution and add an accurate modification notice where required |

## Behavioral gaps in the current pack

1. The orchestrator describes one human checkpoint and a final success report.
   Autopilot requires distinct initial approval, engineering completion, final
   human acceptance, and separately authorized release.
2. `PROGRESS.md` and `.memory/` are described as the source of resumable state.
   They cannot supply transactional scheduling, leases, or protected evidence.
3. The hook prints instructions into a session. There is no independent
   authority preventing a skipped check, forged report, or modified policy.
4. The current reset strategy assumes a continuing conversation and sometimes
   requires manual session restart. The runtime must supervise and rehydrate
   replacement sessions itself.
5. Review reports use severity and recommendations, but there is no durable
   finding lifecycle or independently enforced resolution gate.
6. The current workflow is milestone-sequential. It lacks executable dependency
   graphs, concurrency ownership, worktree coordination, and controlled merging.
7. Approval and commit language differs among the orchestrator, commands, and
   Git skill. Authorization must be explicit and consistent across entry points.
8. Language examples concentrate on TypeScript and Python. Language-neutral
   contracts and tested Node.js, Rust, and Python profiles are required.
9. There is no actual resource accounting, worker lifecycle, crash recovery,
   permission broker, audit ledger, acceptance state, or monitoring interface.

## Added skills and roles

Add nine distinct skills: `product-discovery`, `implementation-planning`,
`factory-control`, `durable-execution`, `policy-enforcement`,
`parallel-integration`, `quality-assurance`, `acceptance-validation`, and
`documentation-delivery`. Existing engineering detail stays in its current
skill; new skills define factory-specific contracts and handoffs.

The 14 role definitions are factory orchestrator, product analyst, software
architect, implementation planner, backend engineer, frontend engineer, test
engineer, security auditor, code reviewer, performance auditor, QA engineer,
release engineer, documentation engineer, and acceptance auditor. Existing
review files remain reusable. Only the trusted scheduler creates and assigns
jobs; a role cannot grant itself another role or approve its own output.
