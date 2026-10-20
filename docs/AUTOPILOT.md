# Running DarkFactory Autopilot

This pack includes executable runtime modules as well as skills. Local checks
exercise real containers, Git, native CLI protocols and worker processes with
explicitly labeled offline agent fixtures. The live project-board pilot remains
pending at the operator's request. See [progress](autopilot/PROGRESS.md) and
[verification coverage](autopilot/EVIDENCE.md). The [TAM diagram](autopilot/TAM.md)
shows the workflow and control boundaries.

## Development setup

Use Python 3.12+ with SQLite 3.51.3 or newer, uv, Git and a responding Docker
engine. The development environment here uses Python 3.14.6 / SQLite 3.53.3.
The SQLite requirement protects concurrent WAL state. The factory never runs
target commands on the host as a fallback.

```sh
uv sync --python /opt/homebrew/bin/python3
uv run factory --help
uv run ruff check src tests scripts
uv run mypy
uv run pytest
npm ci
npm run lint
npm run typecheck
uv build
```

On other hosts select a suitable Python executable. Keep `.factory/state`
outside every imported target source directory. Do not share the state directory
over a network filesystem or give ordinary agents access to it.

Provision local fixture/toolchain images before running the full suite:

```sh
docker pull python:3.12-slim
docker pull rust:1.98.1-slim-bookworm
docker build -t darkfactory-native-adapters:0.3.0 containers/agents
docker build -t darkfactory-python-tools:0.3.0 containers/python
docker build -t darkfactory-rust-tools:0.3.0 containers/rust
docker build -t darkfactory-mixed-tools:0.3.0 containers/mixed
```

The base toolchain builds use digest-pinned images and locked packages; the mixed
image composes the locally built native and Rust toolchain images. Image creation
can contact official package registries; admitted task execution cannot install
dependencies or silently pull an image. Admission records actual local image
IDs. The Python toolchain image includes pytest, mypy, Ruff and build; the Rust
image adds Clippy/rustfmt; the native CLI image includes Node.js/TypeScript.
Provision a target-specific image containing its dependencies before proposing
a product. The `node-rust` profile composes eight checks for `node/` and `rust/` directories.
Other mixed layouts use explicit approved commands and a combined dependency image.

Generated contracts are under `schemas/`, including OpenAPI. Regenerate them
with `uv run python scripts/export_schemas.py`; do not edit them by hand.
`uv run python scripts/validate_pack.py` checks skills, roles and registration.

## Operator flow

Follow [the step-by-step getting started guide](GETTING_STARTED.md) for configuration,
planning, approval, execution and acceptance. `factory init` creates unapproved,
credential-free proposals; it requires your provider, model and total token choice.
It never starts inference or installs a service.


Generate schemas using `uv run python scripts/export_schemas.py`. Create a
schema-valid blueprint with actual approved images/checks, requirement coverage,
explicit local commit/integration permissions and inference limits. Protect
critical behavior with a driver and service_argv: the application runs in a
separate container, reachable by the driver at FACTORY_TARGET on port 8080.
Check definitions, driver text, positive success markers and per-check toolchain
probes are part of the approved blueprint. Default `protect_test_paths` covers common tests, runners, manifests and lockfiles.
Review it for the actual project and explicitly add custom security-critical paths.
Required test commands reject empty or skipped execution by default. Any legitimate
skip allowance must be explicit in the approved check definition.
New blueprints require nonempty source `README.md` and `RUNBOOK.md`; final reviewers
must also judge whether their instructions actually describe the product. Independent drivers remain outside source mounts.

For natural-language planning, provide credential-free JSON configuration and
an answers file containing one string per pending question:

```sh
uv run factory discover "Describe the product goal" --adapter claude --inference ./inference.json --limits ./limits.json --source ./product --profile ./profile.json
uv run factory answer DISCOVERY_ID --answers ./answers.json
```

Discovery saves stages and questions transactionally, includes bounded existing
source context, and runs analyst → architect → planner. It validates structured
replies and produces a separate unapproved project. Planning permission never
authorizes implementation. `documents` carries the approved PRD, architecture,
design, plan, threat model and decisions into delivery.

```sh
uv run factory propose blueprint.json --policy policy.json --source ./product
uv run factory status
uv run factory approve PROJECT_ID --digest EXACT_BLUEPRINT_DIGEST
uv run factory preflight PROJECT_ID
uv run factory start PROJECT_ID
uv run factory worker --project PROJECT_ID
```

The last command is a separate foreground worker process. Run it under an
operator-configured service supervisor for unattended operation; no global
service is installed by the pack. Closing the chat does not terminate a
separately supervised worker. A machine shutdown requires the supervisor to
restart it; the pack cannot claim continuity while a machine is off.
Operator installation templates are in [examples/supervision](../examples/supervision/README.md).
No template is installed automatically.

```sh
uv run factory pause PROJECT_ID
uv run factory resume PROJECT_ID
uv run factory cancel PROJECT_ID
uv run factory report PROJECT_ID
uv run factory export PROJECT_ID ./delivery-new-directory
uv run factory accept PROJECT_ID --revision EXACT_DELIVERY_DIGEST
uv run factory reject PROJECT_ID --revision EXACT_DELIVERY_DIGEST --reason "Concrete correction"
uv run factory reject PROJECT_ID --revision EXACT_DELIVERY_DIGEST --reason "Criterion failed" --criteria FR-001
uv run factory retry PROJECT_ID
uv run factory review PROJECT_ID
uv run factory backup ./factory-backup-new.sqlite3
```

Pause stops new claims and allows bounded active work to settle. Cancellation
invalidates ownership so active work cannot publish integration. Usage already
consumed cannot be undone. Reports retain failed attempts/checks and outstanding
findings. Rejection preserves the original integrated tasks and their attempt counts, records
the revision/criteria/feedback, and creates separate scoped correction tasks. Resume
starts those tasks; it does not weaken criteria. Automatic QA retries retain their
bounded attempt counts. Backup uses SQLite's live backup API. Stop workers before
restoring a backup to a new protected state directory; preserve the snapshot
and evidence directories alongside the database.

All quality modes support explicit attached execution:

```sh
uv run factory preflight PROJECT_ID --foreground
uv run factory run PROJECT_ID
```

Unattended workers accept Strict only. Advisory records intermediate quality failures;
Enforced blocks them. Both retain authorization, isolation and source identity gates.
Every mode requires actual passing checks, delivery documents and current independent
reviews before final readiness/acceptance. Closing an attached process ends that run.

A human may grant a reasoned exception to a particular finding on an exact revision:

```sh
uv run factory allow-finding PROJECT_ID FINDING_ID --revision EXACT_SOURCE_DIGEST --reason "Reviewed rationale"
uv run factory revoke-exception PROJECT_ID EXCEPTION_ID
```

Exceptions retain the adverse review and unresolved finding. They bind to the project,
source, blueprint and policy; they cannot waive mandatory checks, authorize execution,
or follow later revisions. Accepted/cancelled projects cannot be retroactively changed.

## Credentials and inference

No existing personal CLI credentials are imported. The operator must provision
a dedicated provider credential file at STATE/credentials/anthropic or
STATE/credentials/openai, owned by the operator with permissions 0600. This
enrollment is an explicit operator action, never an agent workspace task.
Do not paste the credential into a blueprint, chat, report or source file.

The approved inference configuration selects provider/model, CLI image,
gateway image, per-attempt token reservation/output bound and optional
conservative input/output monetary rates. Pricing is an operator-provided bound,
not a guarantee of provider billing. The gateway refuses unknown models/routes
and provider-executed tools, keeps vendor credentials outside task containers,
and retains unknown usage as reserved capacity. Missing pricing blocks a run
that requires a monetary cap. Increasing limits requires a revised approval.

Optional `role_bindings` selects a different approved adapter/model/image for
specific roles. Every binding is included in the blueprint identity and monetary
reservation bound. Model routing does not grant broader tool permissions.
If a killed inference session leaves unknown charges, the worker blocks further
inference. The operator must reconcile a documented observation explicitly:

```sh
uv run factory reconcile-usage PROJECT_ID USAGE_ID --tokens OBSERVED_TOKENS --reference ACCOUNTING_REFERENCE
```

Supply `--cost-microusd` when a monetary cap requires it. Reconciliation cannot
reduce recorded usage or grant new allowances; it records the human accounting
decision and leaves the project blocked until explicitly resumed/retried.

Provision local images before admission. Native CLI images must contain the
declared Claude Code or Codex version; target images must contain all required
project toolchains/dependencies. Dependency acquisition inside ordinary task
containers is disabled. The inference container can reach only its private
model gateway; target execution containers have no network access. No Docker
socket, privileged mounts or host user configuration is admitted.

State storage admission serializes bulk snapshots, workspaces and reports
against `limits.state_storage_mb` and available disk. This conservative accounting
is separate from the optional kernel filesystem bound. Set
`limits.require_filesystem_quota=true` to refuse admission unless the actual entire
state filesystem fits within that approved capacity. On macOS, create a new bounded
APFS image explicitly using `factory create-state-volume`; on Linux, provide a
bounded local filesystem. See [the setup guide](GETTING_STARTED.md#bounded-state-volume).
A registered missing mount refuses startup rather than creating empty replacement state.
Temporary directories and container outputs are bounded; interrupted staging
and evidence are retained. Archive/export preserved work under operator control
when storage fills. Journaled managed scratch worktrees are cleaned after use;
recovery removes abandoned scratch work only after its owner OS lock is released.
Unrecognized files and interrupted initial-repository staging remain preserved
for operator reconciliation.
Target network allowlists are unsupported and refused; the model gateway alone
has its fixed provider destinations. Unattended execution accepts Strict only; other modes require `factory run`.

Checks and native adapter calls write durable operation intents before execution.
Recovery uses released owner locks to distinguish abandoned work from live owners;
aborted work is recorded as failure, with redacted bounded diagnostics and preserved
unknown usage reservations. Reports include `adapter_runs`, correction history and
finding exceptions. Rehydration always includes the assignment and references full
protected manifests/blueprints when source previews exceed the input budget.

## Dashboard and administrative API

Provide a separate owner-only administrative credential file containing at
least 32 characters. It is not a provider key. Start the server with:

```sh
uv run factory serve --token-file /absolute/operator/admin.token --port 8787
```

Open http://127.0.0.1:8787 and enter that credential in the operator form.
The browser keeps it only in tab memory. The server binds loopback, authenticates
all state reads/mutations and validates Host/Origin. The dashboard reads actual
project/task/check/review/usage records; it is optional and does not supervise
the worker. Remote hosting and external notification sinks are unsupported.

## Compatibility and remaining verification

| Surface | Current evidence | Limit |
| --- | --- | --- |
| Python controller | Full local suite, strict mypy, Ruff, package build/install smoke | Host tested: macOS arm64 with Docker Desktop; Linux service deployment not exercised |
| Docker target isolation | Non-root, read-only root, no egress, host-path absence, timeout/output bounds | Host administrator/kernel compromise outside threat model |
| Claude Code 2.1.179 / Codex 0.139.0 | Actual CLI processes and structured output over offline protocol fixtures; gateway route/credential/egress checks | Actual vendor service, authentication, outage/rate-limit and live agent runs pending |
| Python 3.14.6 target tools | Real passing/failing behavior and pytest/mypy/Ruff/build | Product-specific protected acceptance drivers must be supplied |
| Node.js 22.22.3 / TypeScript 5.9.3 | Real behavior, Node test runner, compiler, project lint/build scripts | Fixture lint uses compiler/syntax checks; other framework scripts need project-specific probes |
| Rust 1.98.1 / Cargo / Clippy | Real passing/failing behavior and locked offline test/check/lint/build | Target dependencies must already exist in the image |
| Mixed Node.js/Rust | Actual eight-check combined-image fixture; both defective implementations fail | Other layouts/dependencies require an approved image/profile |
| Recovery | Actual supervisor/worker SIGKILL, orphan cleanup, fenced restart, checkpoint rehydration, interrupted Git and discovery creation | Actual OS reboot/service installation and live provider session recovery pending |
| Human acceptance | Protected service/API actions; browser approval → run → correction → reverify → acceptance | Offline agent fixture only; live pilot acceptance pending |

Unsupported configuration refuses admission; it never silently falls back to
host execution or a weaker unattended mode. See the frozen approved blueprint
and verification plan under docs/autopilot/ for the complete required scope.
