# Factory roles

Roles are task-specific responsibilities. The trusted scheduler creates bounded
sessions with exact blueprint/task/source context. Role files are prompts, not
permission grants. Review sessions are distinct from implementation sessions and
receive read-only source. Roles never assign themselves peers.

| Role | Responsibility |
| --- | --- |
| factory-orchestrator | Dependencies, ownership, recovery, capacity and real state |
| product-analyst | Adaptive discovery and observable requirements |
| software-architect | Architecture, data/API/design decisions and threat model |
| implementation-planner | Requirement-linked executable DAG and ownership |
| backend-engineer | Backend behavior, persistence and application security |
| frontend-engineer | Accessible product journeys and consistent components |
| test-engineer | Meaningful coverage and protected acceptance checks |
| security-auditor | Application/factory threats and demonstrated controls |
| code-reviewer | Correctness, readability, architecture, security, performance |
| performance-auditor | Measured targets and regression guards |
| qa-engineer | Real end-to-end journeys and negative cases |
| release-engineer | Reproducible builds, integration proposals and rollback |
| documentation-engineer | Tested setup and complete truthful delivery |
| acceptance-auditor | Current requirement-evidence coverage and readiness |

The four existing review personas remain available for interactive /review
and /ship. In Autopilot they return structured examined/unexamined scope,
criterion-linked findings and explicitly reverified resolved finding IDs.
Blocking judgments persist until trusted verification and renewed independent
review. No reviewer can accept the product for the human or approve a release.
