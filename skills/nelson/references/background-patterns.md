# Background Agent Patterns

Use this reference when a captain's task is long-running and would otherwise block the admiral's quarterdeck rhythm. Background agents free the admiral to process other captains' completions while a long-running task continues.

## When to background a captain

- The task duration exceeds two quarterdeck checkpoint intervals.
- The captain is producing intermediate output that the admiral does not need to review until completion (long builds, large refactors, exhaustive test runs).
- The captain has no upstream dependencies on other captains' output.

Do NOT background:
- Station 2 or Station 3 captains — admiral oversight is required.
- Captains whose output unblocks others (the admiral must be present to relay).
- Captains in `agent-team` mode where peer-messaging from other captains may require routing.

## Spawning a background captain

Use `run_in_background: true` on the `Agent` tool:

```
Agent(
  name="HMS Argyll",
  subagent_type="general-purpose",
  prompt="<captain brief>",
  mode="acceptEdits",
  model="sonnet",
  run_in_background=true,
)
```

The admiral receives a notification when the background agent completes; do not poll, do not insert sleep loops. Continue the quarterdeck rhythm with foreground captains while the background agent runs.

## Monitoring a background captain mid-task

Use the `Monitor` tool to stream events from a background agent's stdout. Each output line arrives as a notification:

```
Monitor(target="HMS Argyll")
```

Monitor is appropriate when:
- The captain's progress is visible in stdout and the admiral wants periodic visibility without spawning a quarterdeck checkpoint specifically for this ship.
- A circuit-breaker condition (token budget overrun, hull-integrity threshold) needs to be detected from output rather than a checkpoint.

If you only need to know when the background agent is done, do not start a Monitor — the completion notification is sufficient.

## Quarterdeck integration

When a background agent's completion notification arrives:
1. Treat it identically to a foreground idle notification — apply the three questions in `SKILL.md` Step 5.
2. Mark the captain's task `completed` in the shared task list (or session task list in `subagents` mode).
3. Continue the rhythm; do not write a checkpoint specifically for the background agent unless the cadence rule requires it.

If a background agent's circuit-breaker trips (hull integrity Red, idle timeout), invoke the corresponding damage-control procedure exactly as for a foreground captain.

## Related

- `references/damage-control/circuit-breakers.md` — automated breaker rules.
- `references/damage-control/hull-integrity.md` — threshold response.
- `references/tool-mapping.md` — Long-Running Tools section.
