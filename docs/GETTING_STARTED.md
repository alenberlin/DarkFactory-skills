# Getting started with DarkFactory Autopilot

Think of the skills as the team's instructions and the runtime as its workshop.
The runtime records approvals, assigns work, runs protected checks and preserves
what happened. A provider supplies the agents' reasoning. Docker supplies the
isolated toolchains. Your approval authorizes a particular plan; your later
acceptance confirms that the delivered revision meets your needs.

## 1. Check the local installation without using a provider

Open a terminal in this folder. You need Python 3.12+ with SQLite 3.51.3+, uv,
Git, Node/npm for dashboard development checks, and a responding Docker engine.
Use the Python executable appropriate for your machine:

```sh
uv sync --python /opt/homebrew/bin/python3
uv run factory --help
npm ci
```

Build the six declared toolchain/test images using [the operating guide](AUTOPILOT.md#development-setup).
For the browser regression, install Chrome separately or select an already
installed Playwright-compatible channel using `FACTORY_BROWSER_CHANNEL`.
Then run the complete local engineering checks:

```sh
uv run python scripts/verify_local.py
```

Success produces `PASS` in `docs/autopilot/evidence/local-validation.json` with
zero test failures. It checks the actual source, containers, Git operations,
recovery, browser workflow and clean package installation. These tests use
explicit offline agents and synthetic credentials. They make no live provider
calls and do not build your eventual real product. Test state stays in
`.factory-dev/`; evidence remains in `docs/autopilot/evidence/`.

## 2. Prepare your real project configuration

Choose a separate application source directory and a protected factory state
directory outside it. Never import this whole factory folder as the target.
Use `--state /absolute/path/to/state` before every operator command when you do
not want the default `.factory/state` in the current folder.

Create a **new** configuration directory. Replace the example model identifier
with the model you choose, and choose your own total token allowance:

```sh
uv run factory init ./my-project-config --provider openai --model YOUR_MODEL_ID --max-tokens 100000 --profile python
```

Use `--provider anthropic` for Claude; profiles are `python`, `node`, `rust` and
`node-rust`. The last expects `node/` and `rust/` subdirectories. The controller's
Python implementation does not restrict the target language. Other layouts can
use explicitly approved checks and an image containing their toolchains.

This command writes `inference.json`, `limits.json`, `policy.json`, `profile.json`
and an explanation. It does not contact a provider, approve a blueprint, install
a background service or alter your application. Review every file. A token cap
is not a dollar cap: an optional `--max-cost-microusd` also requires your explicit
conservative `--input-rate` and `--output-rate`, in micro-USD per token.

Provision the chosen local images with the application's dependencies already
installed. Ordinary tasks cannot fetch packages from the internet. Review test,
lint, typecheck and build commands for the actual project; configure bounded
build outputs in `/tmp`. Images are identified by actual local IDs at admission.

Provider access is an operator step when you decide to run the real trial.
Enroll a dedicated owner-only regular file in the selected state's
`credentials/openai` or `credentials/anthropic`; see
[credentials and inference](AUTOPILOT.md#credentials-and-inference).
Do not paste keys into chat, source or configuration JSON. Existing personal CLI
credentials are not imported. No provider access was enrolled by this upgrade.

## 3. Describe the goal and review the proposed blueprint

After you have explicitly chosen to enable provider access, run discovery with
your actual goal, configuration files and separate application source path:

```sh
uv run factory discover "YOUR PRODUCT GOAL" --adapter codex --inference ./my-project-config/inference.json --limits ./my-project-config/limits.json --profile ./my-project-config/profile.json --source /absolute/path/to/application
```

For Anthropic use `--adapter claude`. Discovery can ask questions; write the
answers as a JSON array of strings, in the question order, then run:

```sh
uv run factory answer DISCOVERY_ID --answers ./answers.json
```

Continue until it returns an unapproved project. Planning consumes the allowance
but cannot authorize implementation. Inspect its requirements, architecture,
tasks, check definitions, images, models, resource limits and explicit local
commit/integration permissions. `factory report PROJECT_ID` exposes the full
blueprint and policy. If you already have valid blueprint/policy JSON, use
`factory propose blueprint.json --policy policy.json --source /absolute/path/to/application`.
`factory init` policy settings are proposals; they apply only when actually
included in the project policy. Material revisions create a new unapproved
project through `factory revise`; previous approvals do not carry forward.

## 4. Approve and execute

`factory status PROJECT_ID` returns the exact `blueprint_hash`. Approve that
identity only after reviewing the complete proposal:

```sh
uv run factory approve PROJECT_ID --digest EXACT_BLUEPRINT_HASH
uv run factory preflight PROJECT_ID
uv run factory start PROJECT_ID
uv run factory worker --project PROJECT_ID
```

The worker is a separate process. Keeping a chat open is unnecessary, but closing
that worker's terminal can stop it. For unattended continuity, you must install
and manage a supervisor using [the supplied templates](../examples/supervision/README.md).
The upgrade does not install one or change your global skills/configuration.

Strict is the unattended mode. For deliberately attached Advisory/Enforced runs:

```sh
uv run factory preflight PROJECT_ID --foreground
uv run factory run PROJECT_ID
```

Advisory can continue past intermediate quality findings while recording them.
Every mode still requires actual final checks and current independent reviews
before delivery/acceptance. A mode never authorizes missing permissions.

## 5. Inspect, correct and accept

```sh
uv run factory status PROJECT_ID
uv run factory report PROJECT_ID
uv run factory pause PROJECT_ID
uv run factory resume PROJECT_ID
```

Pause prevents new claims while bounded active work settles. A blocked project
needs the specific blocker resolved before retry/resume; increasing scope or
limits needs a fresh approved revision. Failed checks and unknown usage remain
visible. Never invent accounting values to release an unknown reservation.

When state is `READY_FOR_HUMAN_ACCEPTANCE`, export to a **new** directory:

```sh
uv run factory export PROJECT_ID ./my-delivery
```

Read the application's `source/README.md` and `source/RUNBOOK.md`; run it yourself
and compare it to the requirements. The export also contains the plan, progress,
review/security/test reports, corrections and exact source identity. Nonempty
setup/runbook files are required by default; reviewers judge their accuracy.

Accept the exact `delivery_digest` from the report, or describe a correction:

```sh
uv run factory accept PROJECT_ID --revision EXACT_DELIVERY_DIGEST
uv run factory reject PROJECT_ID --revision EXACT_DELIVERY_DIGEST --reason "Concrete behavior to correct" --criteria FR-001
uv run factory resume PROJECT_ID
```

Corrections create separate scoped tasks and preserve original history. They
produce renewed checks/reviews and return for acceptance again. Finding
exceptions require an exact revision and human rationale; see the operating
guide. They cannot waive mandatory tests. Acceptance does not publish or deploy.

## Optional dashboard

Prepare a separate administrator credential file with at least 32 characters,
owned by you and readable only by you. It is not the provider key. Start:

```sh
uv run factory serve --token-file /absolute/path/to/admin.token --port 8787
```

Open `http://127.0.0.1:8787`, connect and select your project. The dashboard shows
actual state and offers approval/correction/acceptance controls. It does not
supervise the worker. The credential stays in tab memory.

## Bounded state volume

Storage accounting applies on every host. For an additional whole-state kernel
bound, use a dedicated filesystem whose total capacity is no larger than the
approved `state_storage_mb`, and set `require_filesystem_quota=true` in limits
before approval. Include this choice during `init` with
`--require-filesystem-quota`.

On supported macOS, the explicit operator command creates a **new** APFS image
and mount; select your own paths/capacity, allowing room for filesystem overhead:

```sh
uv run factory create-state-volume --image /absolute/path/to/factory.asif --mount /absolute/path/to/factory-volume --size-mb 2048
uv run factory --state /absolute/path/to/factory-volume/state status
```

The image is preserved. Stop all workers/servers and close state connections
before normal `diskutil eject /absolute/path/to/factory-volume`. To resume, attach
the same preserved image at the same mount with `diskutil image attach --nobrowse
--mountPoint /absolute/path/to/factory-volume /absolute/path/to/factory.asif`.
Keep the adjacent registration marker; missing registered mounts refuse startup.
Linux operators provision a bounded local filesystem separately. A capacity check
is implemented there; actual Linux operational deployment was not tested here.

Back up through `factory backup NEW_DATABASE_PATH`, preserving snapshots/evidence
alongside the database. Restore into new protected state with workers stopped.
