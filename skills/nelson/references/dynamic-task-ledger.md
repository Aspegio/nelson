# Dynamic Task Ledger

The battle plan is a living document. It evolves with mission reality rather than remaining fixed at the point of first contact. At each quarterdeck checkpoint, the admiral reviews the ledger and updates task priorities, the dependency graph, ship assignments, and scope. This pattern is inspired by the continuously re-evaluated task ledger in Microsoft's Magentic-One framework.

## Concept

A static battle plan assumes perfect information at planning time. In practice, new information surfaces as ships report progress, blockers appear, and priorities shift. The dynamic task ledger treats the battle plan as the current best understanding of the mission, not a contract. The admiral owns the ledger and is responsible for keeping it accurate.

The ledger serves two purposes:

1. **Situational awareness** — any agent can read the ledger to understand current priorities, dependencies, and assignments.
2. **Decision record** — changes to the ledger are communicated at checkpoints, creating an audit trail of how and why the plan evolved.

## Ledger Format

Maintain a compact, scannable table as the authoritative state of all active tasks.

```text
| Task ID | Ship           | Status      | Priority | Dependencies | Notes                        |
|---------|----------------|-------------|----------|--------------|------------------------------|
| T1      | HMS Argyll     | Complete    | —        | —            | Merged to main               |
| T2      | HMS Kent       | In progress | High     | —            | On track, 60% complete       |
| T3      | HMS Lancaster  | In progress | Medium   | T2           | Blocked until T2 delivers API|
| T4      | Unassigned     | Pending     | Low      | T2, T3       | Descope candidate            |
```

- **Task ID**: Short identifier matching the battle plan.
- **Ship**: Assigned ship or "Unassigned" if not yet allocated.
- **Status**: Pending, In progress, Blocked, Complete, or Descoped.
- **Priority**: High, Medium, or Low. Relative to other active tasks.
- **Dependencies**: Task IDs that must complete before this task can proceed.
- **Notes**: One-line summary of current state, blockers, or decisions.

## Ledger Update Procedure

At each quarterdeck checkpoint, the admiral walks through these steps in order.

1. **Review completed tasks.** Remove them from the active list. Confirm deliverables are verified and accepted.
2. **Reassess priorities.** New information may change the relative value of remaining tasks. Re-rank High, Medium, and Low accordingly.
3. **Update the dependency graph.** Remove resolved dependencies. Add newly discovered dependencies. Flag any circular dependencies as immediate blockers.
4. **Reallocate resources.** Ships that have completed their tasks carry spare capacity. Assign them to the highest-priority unblocked work or stand them down.
5. **Flag drift.** If any active task has diverged from the original sailing orders metric, mark it for re-scoping or descoping.
6. **Communicate changes.** Signal affected captains with their updated orders. Every priority change, reassignment, or scope adjustment must reach the relevant captain before the next work period begins.

## When to Reprioritise

Reprioritisation happens at quarterdeck checkpoints, not continuously. The admiral should update the ledger when any of the following conditions are met.

| Trigger | Action |
|---|---|
| New information changes relative value of tasks | Re-rank affected tasks |
| A blocker shifts the critical path | Reorder dependencies and reassign if needed |
| A ship completes early and has capacity | Assign highest-priority unblocked task |
| Budget constraints require descoping | Mark lowest-priority tasks as Descoped |
| A task has drifted from the original metric | Re-scope or descope; reference sailing orders |

## Anti-Patterns

| Anti-Pattern | Problem | Remedy |
|---|---|---|
| Static battle plan that never updates | Plan diverges from reality; ships work on stale priorities | Update the ledger at every quarterdeck checkpoint. See `standing-orders/drifting-anchorage.md` |
| Updating without communicating | Captains continue on outdated orders; wasted effort | Every ledger change must be signalled to affected captains before the next work period |
| Reprioritising every turn | Constant churn prevents ships from making progress; thrashing | Restrict updates to quarterdeck checkpoints only, not mid-period |
| Admiral hoarding the ledger | Captains cannot self-organise or anticipate upcoming work | Keep the ledger visible to all squadron agents |

## Cross-References

- `admiralty-templates/battle-plan.md` — the initial battle plan template that seeds the ledger.
- `admiralty-templates/quarterdeck-report.md` — the checkpoint report where ledger updates are communicated.
- `standing-orders/drifting-anchorage.md` — the standing order governing scope drift, which the ledger helps detect and correct.
