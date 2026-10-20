# DarkFactory Autopilot orchestrator

This document routes the language-agnostic engineering workflow. The executable
runtime is the authority for scheduling, permissions, evidence and state. Loading
this document neither starts a background process nor enforces a policy.

## Engagement and restoration

Respect the target project's `.darkfactory` marker: engage enables routing;
ignore leaves the workflow inactive unless explicitly invoked. A missing marker
requires the existing one-time engagement choice. Never treat engagement as
blueprint approval, commit permission or final acceptance.

Restore approved runtime records first: blueprint/policy identity, task DAG,
source revision, attempt/check history, unresolved findings, ownership and limits.
Human-readable progress and memory files are projections. Existing approval
survives context loss or worker restart; report restored state and continue
within it. A material scope change requires a revised blueprint.

## Product discovery and blueprint

Use product-discovery, architect, api-and-interface-design and
implementation-planning. Discover intent, users, journeys, features, data,
nonfunctional requirements, security, constraints and non-goals. Ask only
consequential unanswered questions. Produce the complete PRD, architecture,
design/data/API decisions, dependency plan, verification strategy, environment
requirements, permissions and limits.

Every requirement has an observable criterion and mapped task/check. Validate
schemas, identifiers, dependencies and coverage. Present the complete proposed
blueprint and exact digest for authenticated human approval. No implementation
starts before it. Local commits/integration are covered only when explicitly
included in approved permissions; deployment is separate.

## Autonomous execution

Run a separate supervised factory worker after environment admission. Strict is
mandatory for unattended execution; unsupported capabilities refuse start.
Skills remain project-language independent; approved profiles choose actual
images and commands. The scheduler activates roles only for eligible tasks.

For each task: claim a fenced lease, rehydrate bounded context, implement in an
isolated source copy, preserve test-first failure evidence, execute protected
checks on an immutable candidate, assign independent read-only reviews, repair
blocking failures with bounded fresh attempts, and submit for controlled Git
integration. Serialize overlapping ownership; run independent tasks concurrently.
Reverify the actual merged revision before publishing authoritative refs.

Agents propose edits/commands/findings. They cannot submit passing evidence,
approve themselves, change active policies, delete audit history, publish Git
refs or accept the product. The runtime owns these decisions. Preserve failures,
findings and checkpoints; do not weaken criteria to turn a gate green.

## Recovery and escalation

Supervise process lifetime and resource limits independently of chat. Heartbeats
and fencing prevent stale publication. Journal nontransactional effects and
reconcile them before retries. New sessions receive approved context and prior
diagnoses. Exhausted tasks remain blocked while eligible independent work
continues. Request human input for material unresolved decisions, increased
permissions/resources or unavailable operator-provisioned capabilities.

## Delivery and acceptance

After integration, run full verification, real user-journey QA and independent
acceptance auditing on the actual delivery revision. Use documentation-delivery
to export runnable source, setup instructions, PRD, architecture, plan, tests,
reports, requirement evidence and known limitations.

READY_FOR_HUMAN_ACCEPTANCE means engineering gates passed for that revision.
Only the authenticated human channel records ACCEPTED. Human rejection preserves
feedback and returns work for scoped correction and renewed evidence. Acceptance
does not release software. The runtime currently has no deployment adapter.

Read [the runtime contract](docs/RUNTIME_CONTRACT.md), [operating guide](docs/AUTOPILOT.md)
and [current conformance status](docs/autopilot/PROGRESS.md). Never imply that
unimplemented or untested blueprint capabilities are complete.
