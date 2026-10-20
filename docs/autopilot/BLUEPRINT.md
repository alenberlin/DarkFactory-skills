# DarkFactory Autopilot upgrade blueprint

Version: 1 · Status: proposed, awaiting human approval

This blueprint proposes upgrading this folder in place into a reusable skills pack
and a working local software factory. It implements the vision agreed in this
conversation, including the mandatory Policy Enforcement Engine addendum.
Approval has not been recorded. Creating these documents does not authorize the
factory to approve its own blueprint or declare the implementation complete.

## Intended experience

Describe a product, resolve important requirements, review the PRD, architecture,
and implementation plan, and authorize a bounded autonomous run. The factory then
builds, tests, reviews, repairs, integrates, and documents the product while
persisting its state. It presents the runnable application and requirement-linked
evidence for human acceptance. Release requires its own authorization.

The skills and lifecycle remain language agnostic. Project profiles select the
toolchain, container image, dependencies, verification commands, and runtime
checks for Node.js/TypeScript, Rust, Python, or mixed projects.

## Documents to review

| Document | Purpose |
| --- | --- |
| [Repository analysis](REPOSITORY_ANALYSIS.md) | Inspected foundation, reuse decisions, and gaps |
| [Product requirements](PRD.md) | Identified requirements and measurable acceptance criteria |
| [Technical architecture](ARCHITECTURE.md) | Components, trust boundaries, state, adapters, and controls |
| [Implementation plan](IMPLEMENTATION_PLAN.md) | Dependency-ordered tasks and requirement coverage |
| [Verification plan](VERIFICATION_PLAN.md) | Functional, recovery, adversarial, language, and pilot tests |

The generated `BLUEPRINT_MANIFEST.json` records the digest of these six blueprint
documents. Approval applies to this version and digest; later material changes
require a revised blueprint.

## Proposed decisions

- Keep the existing plugin identity, license, attribution, engineering disciplines,
  and individual commands. Update conflicting behavior and documentation together.
- Extend the 15 existing skills with nine factory skills. Extend four personas to
  the 14 required roles. Roles are activated per task, not permanently running.
- Add a Python runtime with SQLite transactional state, a supervised worker,
  a typed local API, CLI, and optional web dashboard in this repository.
- Use Docker isolation for Strict execution. Never mount the Docker socket,
  controller storage, human credentials, or authoritative repository into an
  ordinary agent or untrusted test container.
- Require protected approvals, revision-bound verification, and controlled
  integration. The runtime owns these records and gate decisions.
- Default unattended runs to Strict; refuse unsupported configurations. Support
  Advisory and Enforced modes with accurately described guarantees.
- Deliver Claude Code and Codex adapters with version/capability checks and
  conformance tests. A CLI's availability does not establish Strict compatibility.
- Prove the complete workflow with a project-board pilot, plus actual Node.js,
  Rust, and Python toolchain conformance runs.

## Scope and non-goals

Included: requirements discovery, approved blueprints, dependency scheduling,
multi-agent work, independent review, background execution, recovery, Git
isolation, enforcement, accounting, evidence, dashboard, CLI/API, documentation,
and a nontrivial pilot application.

The first release targets one workstation or small dedicated server. Multi-host
distributed scheduling, multi-tenant hosting, Kubernetes, automatic production
deployment, new model frameworks, and a new source-control system are outside
this blueprint. Linux and macOS are the initial factory host targets; execution
uses Linux containers. Other host configurations require a tested adapter before
being advertised as supported.

## Permissions and approvals

For development of this upgrade, the current request authorizes workspace edits,
local development tools, and tests. Actual source commits still require the
user's explicit green light. Approval of this blueprint also requests explicit
authorization for local commits solely in isolated test-fixture and pilot
repositories under this workspace, to exercise Git integration and the real
pilot. Those fixture/pilot commits cannot start until the user approves this
permission. No global configuration or system service is installed automatically.

For projects produced by the factory, blueprint approval records explicit,
scoped permissions. The approval interface separately states whether local task
commits and final local integration are authorized. A generic approval, an
engagement marker, and approval of this document cannot silently grant unrelated
privileges. Production deployment, publication, external communications,
unrelated repositories, destructive data operations, additional spending, and
policy administration remain separately authorized operations.

Live model testing requires operator-provisioned access and explicit resource
limits. Secrets are provisioned through an administrative channel and never
copied into project artifacts. No credential inspection or enrollment is part of
this document-writing step. Missing access or an unset required budget blocks the
live pilot, and must be reported without substituting a simulated success.

The proposed default allows two independent implementation tasks concurrently,
with separate bounded verification/review jobs. CPU, memory, disk, command/output
and provider limits are explicit configuration checked at admission. Provider
spending limits and model selection require operator input before a live run;
the blueprint makes no unsupported promise about future charges or execution
duration.

## Outstanding technical risks

Native CLI routing through a credential-isolating inference gateway must be
proved for each adapter. The prototype must also prove immutable snapshot
verification, preservation of failing evidence, interrupted Git recovery, and
rejection of stale worker results. These are early implementation gates, not
assumptions that may be hidden behind a dashboard.

Containers protect the declared boundary against ordinary agent processes;
privileged host administrators and container/kernel compromise are outside the
first release's threat model. Maintainability, semantic scope adherence, and
complete absence of vulnerabilities require review and human judgment in
addition to mechanical checks.

## Approval record

Pending. Human approval of version 1 authorizes implementation within this
blueprint. It is not final acceptance, release permission, approval of generated
products, or a claim that security controls already exist. Material changes to
scope or trust boundaries must return for authorization.
