# DarkFactory workflow

Describe the product → resolve important requirements → review the complete
blueprint → approve explicit scope/permissions/limits → run the supervised
factory → inspect verified delivery → accept or request corrections. Release is
separate. See [the TAM diagram](autopilot/TAM.md) and [orchestrator](../ORCHESTRATOR.md).

## Opt in once per project

Check .darkfactory in the target project. engage loads workflow routing;
ignore keeps it inactive. If missing, ask: “Engage the Dark Factory workflow
for this project? (engage / ignore)” and record the answer. /darkfactory is an
explicit invocation. Individual commands remain available without engaging the
whole workflow. Do not change global agent configuration as a side effect.

The session hook respects the marker. It supplies routing guidance only; it
cannot enforce checks, grant permissions, start a daemon or approve a blueprint.

## Two human decisions

The human approves the complete proposed blueprint before implementation and
accepts the exact verified delivery afterward. Ordinary engineering work,
independent reviews and bounded repairs proceed autonomously between them.
Material scope/permission changes return for approval. Local commits require
explicit scope in the approval record. External release needs separate approval.

## Real runtime authority

SQLite, protected evidence, immutable source and controller-owned Git record
actual progress. Task leases, ownership, dependency gates, usage reservations
and journals support concurrency and recovery. Markdown reports/memory are
projections. Read [the runtime contract](RUNTIME_CONTRACT.md) for the authority
boundary and [operating guide](AUTOPILOT.md) for commands and support limitations.

A continuing chat is not a background service. Use the separately supervised
worker for unattended operation. Strict execution refuses unsupported
configurations and cannot silently downgrade. The skills and task contracts
remain language agnostic; images/checks select the target stack.
