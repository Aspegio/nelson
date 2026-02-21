# Squadron Metrics Framework

Six measures of squadron performance, drawn from existing captain's log fields. These metrics give the admiral a quantitative picture of mission health alongside the qualitative quarterdeck reports. No new tooling is required — all values are extractable from data already recorded during normal operations.

## Metrics Overview

| Metric | RN Name | What It Measures | How to Calculate |
|---|---|---|---|
| Mission success rate | **Homecoming Rate** | Percentage of missions achieving their stated outcome | Successful missions / Total missions |
| Token efficiency | **Coal Consumption** | Tokens spent per completed task | Total tokens / Completed tasks |
| Time to first output | **Anchor to Sail** | Duration from sailing orders to first deliverable | Timestamp of first task completion - Mission start time |
| Blocker resolution speed | **Signal Clarity** | Average time from blocker raised to blocker resolved | Sum of resolution times / Number of blockers |
| Verification pass rate | **Dock Inspection** | Percentage of tasks passing validation on first attempt | First-pass validations / Total validations |
| Hull integrity at stand-down | **Seaworthiness Index** | Average hull integrity across the squadron at mission end | Average of all ships' final hull integrity percentage |

## Metric Definitions

### Homecoming Rate

A mission is successful when it achieves the outcome stated in the sailing orders. Partial completion counts as a failure for this metric — the sailing orders define the bar, not the effort expended.

Record the outcome (success or failure) in the captain's log at stand-down. Over multiple missions, the homecoming rate reveals whether sailing orders are being scoped realistically and whether the squadron is executing effectively.

**Healthy range:** Above 80%. A consistently low homecoming rate suggests sailing orders are too ambitious for the squadron size, or that blocker resolution is too slow.

### Coal Consumption

Measures how efficiently the squadron converts tokens into completed work. High coal consumption may indicate confusion, rework, standing order violations, or poor task decomposition.

Calculate by dividing total tokens consumed across all ships by the number of tasks marked complete in the battle plan.

**Healthy range:** Below 5,000 tokens per task. Spikes in coal consumption warrant investigation — check for crew overruns, idle crew, or ships operating at Condition ZEBRA for extended periods.

### Anchor to Sail

The interval between the admiral issuing sailing orders and the first verified deliverable landing. A long anchor-to-sail time may indicate over-planning, unclear orders, or slow squadron formation.

Measure from the timestamp of the sailing orders to the timestamp of the first task completion recorded in the captain's log.

**Healthy range:** Dependent on mission scope. For small missions, under 10 minutes. For medium missions, under 20 minutes. If the squadron consistently takes longer, review whether the battle plan phase is introducing unnecessary deliberation.

### Signal Clarity

When a blocker is raised (by any agent, at any level), the clock starts. When the blocker is resolved — by the admiral, by another captain, or by the blocking agent itself — the clock stops. Signal clarity is the average of all blocker durations in a mission.

Low signal clarity indicates that blockers are being raised but not surfaced, acknowledged, or resolved promptly. This is often an admiral coordination problem rather than a captain execution problem.

**Healthy range:** Below 5 minutes per blocker. Persistent slow resolution suggests the admiral is too deep in implementation (see `standing-orders/admiral-at-the-helm.md`) or that the quarterdeck rhythm interval is too long.

### Dock Inspection

The percentage of tasks that pass their verification criteria on the first attempt. A low dock inspection rate means rework is consuming squadron capacity — ships are spending tokens fixing outputs rather than producing new ones.

Record pass or fail for each task's first verification attempt in the captain's log. Calculate the ratio at stand-down.

**Healthy range:** Above 70%. Below this threshold, review whether verification criteria are clear in the battle plan, whether captains are self-verifying before reporting completion, and whether crew roles include adequate quality assurance.

### Seaworthiness Index

At stand-down, record each ship's final hull integrity percentage. The seaworthiness index is the average across all ships. This measures whether the squadron is finishing missions with capacity to spare or routinely running ships into ZEBRA and ZEBRA (Critical).

A low seaworthiness index across multiple missions suggests the squadron is undersized for the work being assigned, or that relief on station is being triggered too late.

**Healthy range:** Above 50% average hull integrity at stand-down. If the squadron routinely finishes below this, consider adding ships or reducing mission scope.

## Collection

Start with these five lightweight metrics that require no tooling beyond the existing captain's log:

1. **Homecoming Rate** — Recorded as a success/failure flag at stand-down.
2. **Coal Consumption** — Derived from token usage (already tracked for hull integrity) and task completion count.
3. **Dock Inspection** — Recorded as pass/fail on first verification per task.
4. **Seaworthiness Index** — Derived from final damage reports (already filed for hull integrity monitoring).
5. **Signal Clarity** — Derived from blocker timestamps in quarterdeck reports.

**Anchor to Sail** requires timestamp recording that may not be present in all captain's log entries. Add it when the logging practice matures.

All collection is manual during initial adoption. The admiral records metric values in the captain's log at stand-down. No automated extraction is required at this stage.

## Reporting

Metrics are recorded in the captain's log under a dedicated **Squadron Performance** section at stand-down. A minimal entry looks like:

```
## Squadron Performance

- Homecoming Rate: 1/1 (100%)
- Coal Consumption: ~3,200 tokens/task
- Dock Inspection: 8/10 first-pass (80%)
- Seaworthiness Index: 62% average hull integrity
- Signal Clarity: 3 blockers, avg 4 min resolution
```

Over time, the **nelson-metrics** companion plugin (see `companion-plugins.md`) can parse these entries and aggregate metrics across missions, generating trend reports and identifying systemic issues.

## Benchmarks

| Metric | Healthy | Warning | Critical |
|---|---|---|---|
| Homecoming Rate | > 80% | 60 -- 80% | < 60% |
| Coal Consumption | < 5,000 tokens/task | 5,000 -- 10,000 tokens/task | > 10,000 tokens/task |
| Anchor to Sail | < 10 min (small) / < 20 min (medium) | 2x healthy range | > 3x healthy range |
| Signal Clarity | < 5 min/blocker | 5 -- 15 min/blocker | > 15 min/blocker |
| Dock Inspection | > 70% | 50 -- 70% | < 50% |
| Seaworthiness Index | > 50% | 30 -- 50% | < 30% |

When a metric falls into the warning range, the admiral should investigate at the next quarterdeck checkpoint. When a metric reaches critical, the admiral should address it as a standing agenda item until it recovers.

## Cross-References

- `admiralty-templates/captains-log.md` — Template where metrics are recorded at stand-down.
- `companion-plugins.md` — The nelson-metrics companion plugin for cross-mission aggregation.
- `damage-control/hull-integrity.md` — Source data for the Seaworthiness Index and Coal Consumption metrics.
