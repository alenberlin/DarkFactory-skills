# DarkFactory user guide

Use individual skills for a specific engineering phase, or opt into the full
Autopilot workflow for a product. The pack includes 24 skills, 14 roles and seven
commands. The executable factory manages protected approvals, checks, task
scheduling, independent review and integration. [Workflow](WORKFLOW.md) explains
the lifecycle; [runtime setup](AUTOPILOT.md) explains actual commands and current
limitations.

## A product from an idea

Start /darkfactory with the goal and available context. Product discovery
clarifies users, journeys, features, data, security, constraints and observable
success criteria. Architecture and planning produce the full proposed PRD,
contracts, design decisions, dependency plan and verification strategy.

Review that blueprint and its explicit commit/integration permissions, model,
images and resource bounds. Approve the exact digest through the operator
channel. Provision the declared images and dedicated provider access. Successful
preflight allows the separate supervised worker to start. A chat command alone
does not establish durable background operation.

The runtime claims eligible tasks, isolates their source, verifies real behavior,
assigns independent reviewers and repairs failures within bounds. Independent
components can run concurrently; overlapping ownership serializes. Integration
rechecks the actual merged source. Failed attempts and unresolved findings stay
visible in the optional dashboard and CLI reports.

The delivered product includes source, setup instructions, requirements,
architecture, plan, tests and evidence. Run and inspect it, then accept the exact
revision or request concrete corrections. Acceptance is your decision. Deployment
and publication remain separate.

## Individual commands

| Command | Use |
| --- | --- |
| /architect | Align on scope and technical blueprint before coding |
| /build | Implement an approved plan in verified slices; commit only with permission |
| /test | Reproduce failures and verify behavior with meaningful real tests |
| /review | Independent five-axis findings, with explicit coverage limits |
| /ship | Pre-release review and rollback planning; deployment requires authorization |
| /darkfactory | Explicitly engage the complete product workflow |
| /factory | Inspect and operate the executable runtime |

Individual workflows can remain interactive. Factory work uses the shared
runtime contract; loading a skill does not grant the role administrative powers.
Read [roles](PERSONAS.md) and the relevant skill rather than loading the entire
pack for every task.

## Common situations

- Bug: write a reliable failing reproduction, diagnose the cause, fix it and
  reverify. Preserve failure evidence.
- Failed agent context: preserve the candidate/diagnosis and let the scheduler
  create a fresh bounded attempt. Existing approved scope remains valid.
- Changed product direction: propose a new blueprint version; review material
  changes and renew approval before dependent implementation.
- Missing toolchain or provider access: preflight remains blocked. Provision
  it through the operator channel; never silently run untrusted code on the host.
- Human correction: reject the delivered revision with concrete feedback.
  Corrective work must satisfy the original criteria and produce new evidence.

Project profiles choose actual commands for Python, Node.js/TypeScript, Rust or
mixed projects. [Compatibility](AUTOPILOT.md#compatibility-and-remaining-verification)
separates implemented contracts from tested toolchain/provider support.
