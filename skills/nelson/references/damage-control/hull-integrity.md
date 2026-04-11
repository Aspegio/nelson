# Hull Integrity: Context Window Management

Use to monitor and manage context window consumption across the squadron.

## Hull Integrity Thresholds

Each ship maintains a hull integrity percentage representing its remaining context window capacity.

| Status | Remaining | Action |
|---|---|---|
| Green | 75 -- 100% | No action required. Continue normal operations. |
| Amber | 60 -- 74% | Admiral notes the ship on the readiness board. Captain prioritises completing current task and avoids taking new work that would extend the session. |
| Red | 40 -- 59% | Captain files a damage report with `relief_requested: true`. Admiral plans relief on station: spawn a replacement ship, brief it with completed and remaining work, then transfer the task. Captain focuses on producing a clean handoff summary before context runs out. |
| Critical | Below 40% | Admiral executes relief on station immediately. If no replacement is available, admiral descopes the ship's remaining work or redistributes it to ships with Green or Amber status. Captain ceases non-essential activity and writes a final status report. |

## Squadron Readiness Board

The admiral maintains a readiness board to track hull integrity across all ships. Build the board by reading damage reports from `{mission-dir}/damage-reports/`.

1. At each quarterdeck checkpoint, collect the latest damage report from every active ship.
2. List each ship with its hull integrity status, percentage, and whether relief is requested.
3. Flag any ship at Red or Critical for immediate attention.
4. Record the board in the quarterdeck report under the "Hull integrity (squadron readiness board):" section.

The readiness board gives the admiral a single view of squadron endurance and drives decisions about task reassignment, descoping, and relief.

## Integration with Quarterdeck Rhythm

Check hull integrity at every quarterdeck checkpoint:

1. Each captain files a damage report using the template from `references/admiralty-templates/damage-report.md`.
2. Admiral reads all damage reports and updates the squadron readiness board.
3. If any ship has crossed a threshold boundary since the last checkpoint, admiral takes the action defined for that threshold.
4. Admiral records hull integrity status in the quarterdeck report.

Between checkpoints, captains file an immediate damage report when hull integrity crosses any threshold boundary. Do not wait for the next scheduled checkpoint to report a status change.

## Relief on Station

Trigger relief on station when a ship reaches Red hull integrity. Execute as follows:

1. Admiral spawns a replacement ship with the same role and ship class.
2. The outgoing captain writes a handoff summary: task definition, completed sub-tasks, partial outputs, known blockers, and file ownership.
3. Admiral briefs the replacement captain with the handoff summary and the original crew briefing.
4. Replacement captain resumes from the last verified checkpoint, not from scratch.
5. Admiral updates the battle plan to reflect the new ship assignment.
6. Admiral issues a shutdown request to the outgoing ship.

If multiple ships reach Red simultaneously, prioritise relief for the ship closest to Critical.

## Flagship Self-Monitoring

The admiral must monitor its own hull integrity with the same discipline applied to the squadron.

1. Admiral tracks its own token usage and calculates hull integrity at each checkpoint.
2. For Amber, Red, and Critical flagship actions, follow the procedure in
   `references/damage-control/relief-on-station.md`. The admiral does not wait for
   Critical — losing coordination state at Critical cannot be recovered.

## Relationship to Other Damage Control Procedures

Hull integrity monitoring works alongside existing damage control procedures:

- **Session Resumption** (`session-resumption.md`): Use when hull integrity reaches Critical and the session must end. The session resumption procedure picks up from the last quarterdeck report.
- **Crew Overrun** (`crew-overrun.md`): A crew overrun accelerates hull integrity loss. When a captain detects a crew overrun, the corrective action should account for the ship's current hull integrity — a ship already at Amber has less margin to absorb an overrun than one at Green.
- **Man Overboard** (`man-overboard.md`): Replacing a stuck agent consumes additional context. Factor hull integrity into the decision to replace versus descope.
- **Scuttle and Reform** (`scuttle-and-reform.md`): When the flagship reaches Red and multiple ships are also at Red or Critical, consider scuttling the current mission and reforming with fresh context rather than attempting piecemeal relief.

## Automated Circuit Breaker

In addition to the damage-report-driven readiness board, Nelson's automated circuit breakers emit a `hull_integrity_breach` advisory at each checkpoint when any ship's `hull_integrity_pct` falls at or below `circuit_breakers.hull_integrity_threshold` (default 80%). See `damage-control/circuit-breakers.md` for thresholds, configuration, and output format.

## Advanced: TeammateIdle Hook

Nelson ships a `TeammateIdle` hook in `hooks/hooks.json` that triggers an
automatic check when a captain goes idle. The hook reads fleet status to
determine whether the ship's task is complete and whether pending dependents
remain. If the task is complete with no dependents, it advises executing the
paid-off standing order. This supplements the quarterdeck checkpoint rhythm
with event-driven monitoring.
