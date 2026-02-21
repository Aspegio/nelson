# Hull Integrity: Context Window Management

Use to monitor and manage context window consumption across the squadron.

## Material Conditions

Each ship maintains a hull integrity percentage representing its remaining context window capacity. Hull integrity is expressed using Royal Navy material conditions that govern watertight closure throughout the ship.

| Condition | Remaining | Closure Rules |
|---|---|---|
| Condition XRAY | 75 -- 100% | Routine cruising. All compartments open, normal operations. No action required. |
| Condition YOKE | 60 -- 74% | Heightened readiness. Non-essential compartments secured. Admiral notes the ship on the readiness board. Captain prioritises completing current task and avoids taking new work that would extend the session. |
| Condition ZEBRA | 40 -- 59% | Action stations. Maximum watertight integrity. Captain files a damage report with `relief_requested: true`. Admiral plans relief on station: spawn a replacement ship, brief it with completed and remaining work, then transfer the task. Captain focuses on producing a clean handoff summary before context runs out. |
| Condition ZEBRA (Critical) | Below 40% | Hull breach imminent. All hands to damage control. Admiral executes relief on station immediately. If no replacement is available, admiral descopes the ship's remaining work or redistributes it to ships at Condition XRAY or YOKE. Captain ceases non-essential activity and writes a final status report. |

### Interpreting the Conditions

- **XRAY** reflects peacetime steaming. The ship has ample capacity and operates without restriction.
- **YOKE** is set when the ship enters waters that demand caution. Context is being consumed at a rate that warrants attention, but the ship can still complete its current task.
- **ZEBRA** means the ship is closed up for action. Context is scarce and every token must count. The ship's priority shifts from task completion to producing a clean handoff.
- **ZEBRA (Critical)** is ZEBRA with active flooding. The ship is in danger of losing useful output capacity entirely. Immediate relief or descoping is mandatory.

Transition between conditions is one-directional during a session: a ship moves from XRAY toward ZEBRA as context is consumed. A ship never returns to a lower condition without relief on station (a fresh ship starts at Condition XRAY).

## Squadron Readiness Board

The admiral maintains a readiness board to track hull integrity across all ships. Build the board by reading damage reports from `.claude/nelson/damage-reports/`.

1. At each quarterdeck checkpoint, collect the latest damage report from every active ship.
2. List each ship with its material condition, hull integrity percentage, and whether relief is requested.
3. Flag any ship at Condition ZEBRA or ZEBRA (Critical) for immediate attention.
4. Record the board in the quarterdeck report under the budget section.

The readiness board gives the admiral a single view of squadron endurance and drives decisions about task reassignment, descoping, and relief.

## Integration with Quarterdeck Rhythm

Check hull integrity at every quarterdeck checkpoint:

1. Each captain files a damage report using the template from `references/admiralty-templates/damage-report.md`.
2. Admiral reads all damage reports and updates the squadron readiness board.
3. If any ship has crossed a condition boundary since the last checkpoint, admiral takes the action defined for that condition.
4. Admiral records hull integrity status in the quarterdeck report.

Between checkpoints, captains file an immediate damage report when hull integrity crosses any condition boundary. Do not wait for the next scheduled checkpoint to report a change in material condition.

## Relief on Station

Trigger relief on station when a ship reaches Condition ZEBRA. Execute as follows:

1. Admiral spawns a replacement ship with the same role and ship class.
2. The outgoing captain writes a handoff summary: task definition, completed sub-tasks, partial outputs, known blockers, and file ownership.
3. Admiral briefs the replacement captain with the handoff summary and the original crew briefing.
4. Replacement captain resumes from the last verified checkpoint, not from scratch.
5. Admiral updates the battle plan to reflect the new ship assignment.
6. Admiral issues a shutdown request to the outgoing ship.

If multiple ships reach Condition ZEBRA simultaneously, prioritise relief for the ship closest to ZEBRA (Critical).

## Flagship Self-Monitoring

The admiral must monitor its own hull integrity with the same discipline applied to the squadron.

1. Admiral tracks its own token usage and calculates hull integrity at each checkpoint.
2. At Condition YOKE, admiral begins preparing a session resumption handoff using `references/damage-control/session-resumption.md`.
3. At Condition ZEBRA, admiral writes a full quarterdeck report and session state to disk, then signals the Admiralty (human) that a session resumption will be needed.
4. The admiral does not wait for ZEBRA (Critical). An admiral at ZEBRA (Critical) risks losing coordination state that cannot be recovered.

## Relationship to Other Damage Control Procedures

Hull integrity monitoring works alongside existing damage control procedures:

- **Session Resumption** (`session-resumption.md`): Use when hull integrity reaches ZEBRA (Critical) and the session must end. The session resumption procedure picks up from the last quarterdeck report.
- **Crew Overrun** (`crew-overrun.md`): A crew overrun accelerates hull integrity loss. When a captain detects a crew overrun, the corrective action should account for the ship's current material condition — a ship already at Condition YOKE has less margin to absorb an overrun than one at Condition XRAY.
- **Man Overboard** (`man-overboard.md`): Replacing a stuck agent consumes additional context. Factor the ship's material condition into the decision to replace versus descope.
- **Scuttle and Reform** (`scuttle-and-reform.md`): When the flagship reaches Condition ZEBRA and multiple ships are also at ZEBRA or ZEBRA (Critical), consider scuttling the current mission and reforming with fresh context rather than attempting piecemeal relief.
- **Soundings** (`soundings.md`): Proactive budget monitoring between quarterdeck checkpoints. Soundings detect approaching condition boundaries early so the admiral can act before a ship crosses into ZEBRA unexpectedly.
