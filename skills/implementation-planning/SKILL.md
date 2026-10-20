---
name: implementation-planning
description: "Convert a resolved factory blueprint into requirement-linked tasks, ownership and a validated dependency graph."
---

# Implementation Planning

Plan around logical dependencies and independently verifiable behavior. Every TaskSpec includes a stable ID, requirement IDs, description, dependencies, role, deliverables, affected components/permitted paths, acceptance criteria, check IDs and security considerations.

Cover every requirement with executable verification and assigned work. Reject duplicate IDs, cycles, unknown references and unmapped criteria. Put the walking skeleton and uncertain foundations before dependent features. Allow independent tasks concurrently only when ownership permits it; shared contracts precede their consumers.

Use actual project-selected argv commands and immutable toolchain inputs. Do not invent passing checks or mark a task complete by writing its plan. Return schema-valid task/check proposals for protected blueprint approval. A changed material plan returns as a new blueprint version.

Read [the runtime contract](../../docs/RUNTIME_CONTRACT.md) for proposal and authority boundaries and [the operating guide](../../docs/AUTOPILOT.md) for actual commands and compatibility limits.
