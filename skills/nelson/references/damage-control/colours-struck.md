# Colours Struck: Graceful Degradation

Use when a mission cannot deliver its full scope but can still achieve a meaningful outcome by shedding non-essential work.

Striking the colours is a controlled withdrawal, not a surrender. The admiral preserves mission-critical deliverables by deliberately deferring lower-priority tasks before budget exhaustion forces an uncontrolled abort.

## Task Tiers

At each quarterdeck checkpoint, the admiral classifies every remaining task into one of three tiers.

| Tier | Label | Definition |
|---|---|---|
| 1 | Mission Critical (MVP) | Must deliver for the mission to be considered successful. Without these, the mission has failed. |
| 2 | High Value | Adds significant value but the mission can succeed without it. Deferral is acceptable if budget demands it. |
| 3 | Polish | Quality-of-life improvements, minor enhancements, or cosmetic work. Can be deferred entirely with no impact on mission success. |

Tier classification is set during the battle plan and revisited at each quarterdeck checkpoint. Tasks may be re-tiered as the mission evolves.

## Degradation Levels

The admiral selects a degradation level based on remaining budget and squadron health.

| Level | What Proceeds | What Is Deferred | When to Use |
|---|---|---|---|
| Staged Degradation | All Mission Critical tasks plus admiral-selected High Value tasks | Remaining High Value tasks and all Polish tasks | Budget is constrained but not critical. Some high-value work can still be absorbed. |
| Full Degradation | Mission Critical tasks only | All High Value and Polish tasks | Budget is severely constrained. Only MVP deliverables proceed. |
| Abort | Nothing | Everything | Mission cannot succeed even with full degradation. Execute scuttle and re-form. |

## Trigger Conditions

Strike the colours when any of the following are true:

1. Token budget is below 40% with significant work remaining.
2. Time budget is below 30% with significant work remaining.
3. Three or more ships are at ZEBRA hull integrity simultaneously.
4. Admiral judges that full scope delivery is no longer achievable at the current burn rate.

## Degradation Procedure

1. Admiral halts new task assignments across the squadron.
2. Admiral classifies all remaining tasks into the three tiers (Mission Critical, High Value, Polish).
3. Admiral selects the appropriate degradation level based on remaining budget and squadron health.
4. Admiral identifies ships assigned to deferred tasks and issues stand-down orders to those ships.
5. Admiral reassigns any freed capacity to Mission Critical tasks that need reinforcement.
6. Admiral updates the battle plan to reflect the reduced scope and records the degradation decision in the quarterdeck report.
7. Ships working on Mission Critical tasks continue without interruption.
8. Admiral produces a Degraded Capability Report (see below).

## Degraded Capability Report

The admiral writes a Degraded Capability Report to file at `.claude/nelson/degraded-capability-report.md` and presents it to the Admiralty (human) at stand-down.

The report contains:

| Section | Contents |
|---|---|
| Degradation Level | Staged or Full. |
| Trigger | What condition triggered the degradation. |
| Delivered | List of completed tasks with outputs. |
| In Progress | List of Mission Critical tasks still underway. |
| Deferred | List of deferred tasks, their tier, and the reason for deferral. |
| Recommendation | Whether deferred work should be attempted in a follow-up mission, descoped permanently, or abandoned. |

## Relationship to Other Damage Control Procedures

- **Scuttle and Re-Form** (`scuttle-and-reform.md`): Use when degradation is insufficient and the mission must be fully aborted. Colours struck is the step before scuttle — always attempt degradation first.
- **Hull Integrity** (`hull-integrity.md`): Threshold definitions that feed the trigger conditions. Three or more ships at ZEBRA triggers colours struck; individual ships at Red or Critical trigger relief on station.
- **Relief on Station** (`relief-on-station.md`): Relief replaces an individual exhausted ship. Colours struck reduces mission scope across the entire squadron. Both may be active simultaneously.
- **Crew Overrun** (`crew-overrun.md`): A crew overrun on multiple ships may be an early signal that degradation is needed. If corrective action fails to recover budget, escalate to colours struck.
