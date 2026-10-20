# DarkFactory Autopilot — workflow and architecture map

This map describes the approved design. Implementation status and test results
are tracked separately; the diagram does not certify that a component is built.

## The complete workflow

```mermaid
flowchart TD
    IDEA[You describe the product] --> DISC[Discovery conversation\nGoals, users, workflows and constraints]
    DISC --> BLUE[Project blueprint\nPRD + architecture + implementation plan]
    BLUE --> APPROVE{You approve scope,\npermissions and limits?}
    APPROVE -- Revise --> DISC
    APPROVE -- Approved --> PREFLIGHT{Strict environment\nand adapter checks pass?}
    PREFLIGHT -- No --> BLOCK[Preserve work and evidence\nReport the actual blocker]
    PREFLIGHT -- Yes --> SCHEDULE[Durable scheduler\nSelect eligible tasks from dependency graph]

    subgraph WORK[Autonomous engineering in isolated workspaces]
        SCHEDULE --> CODE[Specialist implementation agents\nBackend, frontend and supporting roles]
        CODE --> CHECK[Trusted verification\nTests, types, lint, build and runtime checks]
        CHECK --> GATE{Required checks pass\nfor this exact source revision?}
        GATE -- No --> REPAIR[Diagnose and repair\nBounded retries, fresh context if needed]
        REPAIR --> CODE
        REPAIR -- Recovery exhausted --> BLOCK
        GATE -- Yes --> REVIEW[Independent review\nCode, security, tests and applicable performance]
        REVIEW --> FINDINGS{Blocking findings resolved\nor explicitly excepted?}
        FINDINGS -- No --> REPAIR
        FINDINGS -- Yes --> INTEGRATE[Controlled integration\nMerge and verify the merged revision]
        INTEGRATE -- More tasks ready --> SCHEDULE
    end

    INTEGRATE -- All required tasks integrated --> QA[Whole-product QA\nReal user workflows, security and acceptance criteria]
    QA -- Failed criteria --> REPAIR
    QA -- All required gates pass --> DELIVERY[Ready for human acceptance\nRunnable application + documentation + evidence matrix]
    DELIVERY --> ACCEPT{You accept this\ndelivery revision?}
    ACCEPT -- Corrections --> CORRECT[Create criterion-linked corrective tasks]
    CORRECT --> SCHEDULE
    ACCEPT -- Accepted --> ACCEPTED[Human accepted]
    ACCEPTED --> RELEASE{Separate release\nauthorization?}
    RELEASE -- Authorized --> RELEASED[Controlled release + health checks]
    RELEASE -- No --> RETAIN[Accepted application retained locally]

    BLOCK -- Authorized resolution / safe recovery --> SCHEDULE
```

Independent tasks may run concurrently. Tasks depending on blocked work remain
unscheduled. An incomplete or blocked project cannot pass final acceptance gates.

## What keeps the workflow operating and controlled

```mermaid
flowchart TB
    HUMAN[Human operator\nCLI / dashboard / API] --> AUTH[Protected approval channel]
    AUTH --> RUNTIME[Durable factory runtime\nScheduler, supervisor and recovery]
    RUNTIME <--> DB[Transactional state\nTasks, leases, checkpoints and history]
    RUNTIME --> POLICY[Trusted policy engine\nPermissions, stage gates and evidence rules]
    POLICY --> BROKER[Execution broker\nRestricted filesystem, shell, Git and network effects]
    SKILLS[DarkFactory skills + role definitions\nEngineering knowledge and instructions] --> AGENTS
    BROKER --> AGENTS[Isolated coding agents\nTested Claude Code / Codex adapters]
    BROKER --> VERIFY[Independent check and review environments]
    AGENTS --> CANDIDATE[Candidate source snapshot\nNode.js, Rust, Python or mixed project]
    CANDIDATE --> VERIFY
    VERIFY --> EVIDENCE[Protected evidence and findings\nBound to source and policy versions]
    EVIDENCE --> POLICY
    POLICY --> MERGE[Trusted integration coordinator]
    MERGE --> REPO[Authoritative project repository]
    DB --> STATUS[Accurate progress, reports and operator notifications]
    STATUS --> HUMAN
```

Skills guide engineering decisions. The runtime keeps authorized work moving
and survives interruptions. The policy engine decides whether operations and
transitions are permitted. Agents cannot grant themselves approval or certify
their own completion. The project's language selects its toolchain; the
surrounding workflow stays the same.

See the [approved blueprint](BLUEPRINT.md), [architecture](ARCHITECTURE.md) and
[implementation plan](IMPLEMENTATION_PLAN.md) for the detailed contracts.
