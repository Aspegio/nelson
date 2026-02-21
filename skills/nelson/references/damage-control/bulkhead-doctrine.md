# Bulkhead Doctrine: Cascading Failure Containment

Use to allocate and enforce per-ship token budgets that prevent a single ship's overconsumption from sinking the squadron.

Watertight bulkheads on a warship contain flooding to one compartment. The bulkhead doctrine applies the same principle to token budgets: each ship operates within a sealed allocation so that one ship's overrun cannot drain resources from the rest of the fleet.

## Token Budget Allocation

The admiral assigns each ship an explicit token allocation during the battle plan, expressed as a percentage of the total mission budget. Allocation is based on task complexity.

| Task Complexity | Suggested Allocation |
|---|---|
| Simple | 10 -- 15% |
| Medium | 15 -- 25% |
| Complex | 25 -- 35% |

The sum of all ship allocations plus the admiral reserve must equal 100% of the mission budget. If it does not, adjust allocations or reduce squadron size before issuing sailing orders.

## Admiral Reserve Pool

The admiral holds 15 -- 20% of the total budget as a reserve pool. This reserve is not assigned to any ship and is drawn upon only for:

1. Relief on station operations (spawning replacement ships).
2. Emergency coordination during escalations.
3. Unexpected work discovered mid-mission.
4. Absorbing minor overruns that do not warrant corrective action.

The reserve is not a general overflow buffer. If the reserve drops below 5%, the admiral must trigger colours struck or scuttle and re-form.

## Budget Monitoring

Track actual versus allocated spend at every quarterdeck checkpoint.

1. Each captain reports current token usage in their damage report.
2. Admiral compares each ship's usage against its allocation.
3. Admiral flags any ship that has consumed 80% or more of its allocation as "bulkhead pressure" on the squadron readiness board.
4. Admiral records budget status in the quarterdeck report under the budget section.

## Compartment Breach Rules

A compartment breach occurs when a ship's token consumption threatens the integrity of the wider squadron. The admiral responds according to the severity of the breach.

| Condition | Classification | Action |
|---|---|---|
| Single ship exceeds its allocation | Contained breach | Admiral triggers crew overrun procedure for that ship. Captain descopes, resolves blockers, or requests relief. |
| Single ship exceeds allocation and reserve is below 10% | Serious breach | Admiral halts the ship immediately and executes relief on station. No further reserve draw permitted for that task. |
| 3+ ships reach ZEBRA hull integrity simultaneously | Catastrophic breach | Admiral pauses ALL new work across the squadron and escalates to Admiralty (human). No work resumes until the Admiralty provides direction. |
| Upstream dependency is at ZEBRA integrity | Blocked compartment | Downstream tasks do not proceed. Admiral reassigns downstream ships to other work or stands them down to conserve budget. |

## Allocation Procedure

1. During the battle plan, admiral estimates task complexity for each ship's assignment.
2. Admiral assigns a token allocation percentage to each ship using the suggested ranges above.
3. Admiral verifies that all allocations plus the reserve sum to 100%.
4. Admiral records allocations in the battle plan alongside task assignments.
5. At each quarterdeck checkpoint, admiral reviews actual spend against allocations and adjusts if needed.
6. If a ship completes its task under budget, the surplus returns to the admiral reserve pool.
7. If a ship needs more budget, the admiral may transfer from the reserve pool, but only if the reserve remains above 5% after the transfer.

## Relationship to Other Damage Control Procedures

- **Hull Integrity** (`hull-integrity.md`): Threshold definitions that determine when a ship's context consumption is reaching dangerous levels. Bulkhead doctrine adds per-ship budget caps on top of hull integrity monitoring.
- **Crew Overrun** (`crew-overrun.md`): The first response to a contained breach. The captain attempts to recover the ship within its allocation before the admiral intervenes.
- **Colours Struck** (`colours-struck.md`): When multiple compartment breaches occur or the reserve pool is critically low, the admiral may need to degrade mission scope rather than continue at full capacity.
- **Relief on Station** (`relief-on-station.md`): Spawning a replacement ship draws from the admiral reserve. The bulkhead doctrine ensures this draw is tracked and bounded.
- **Scuttle and Re-Form** (`scuttle-and-reform.md`): A catastrophic breach with no viable recovery path leads to full mission abort.
