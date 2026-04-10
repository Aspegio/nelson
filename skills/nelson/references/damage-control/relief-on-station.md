# Relief on Station: Context Window Exhaustion

Use when a ship's context window is depleted and a fresh ship must take over its task.

Relief on station is a planned handover. For stuck or unresponsive agents, use `man-overboard.md`. For unplanned session interruptions, use `session-resumption.md`.

## Trigger Conditions

Initiate relief when any of the following are true:

- Ship reports Red hull integrity (40-59% context remaining).
- Ship reports Critical hull integrity (below 40% context remaining).
- Admiral observes degraded output quality (repetition, missed instructions, shallow reasoning).
- Ship explicitly requests relief.

Hull integrity monitoring may surface context exhaustion before crew overrun is noticed. If a ship is burning context fast, check both this procedure and `crew-overrun.md`.

## Relief Sequence

1. Admiral signals the damaged ship to prepare for turnover.
2. Damaged ship pauses current work and commits or saves any in-progress outputs.
3. Damaged ship writes a turnover brief to file at `{mission-dir}/turnover-briefs/{ship-name}-{timestamp}.md` using the template in `references/admiralty-templates/turnover-brief.md`. Do not send the brief as a message — write it to file to keep the replacement ship's context clean.
4. Damaged ship signals admiral that the turnover brief is written and provides the file path.
5. Admiral spawns a replacement ship. The replacement need not be the same ship class — select the class that matches the characteristics of the remaining work (e.g., swap a destroyer for a frigate if the remaining work is lighter).
6. Admiral briefs the replacement ship with a crew briefing that includes the turnover brief file path. The replacement reads the turnover brief as its first action.
7. Admiral reassigns the task to the replacement ship.
8. Admiral updates the task list entry with `TaskUpdate` to reflect the replacement ship as the new owner.
9. Admiral issues a shutdown request to the damaged ship.
10. Admiral updates the battle plan to reflect the new ship assignment.

## Flagship Self-Monitoring

The admiral must monitor its own hull integrity at every quarterdeck checkpoint.

### Green Hull Integrity (75-100% remaining)

No action required. Continue normal operations.

### Amber Hull Integrity (60-74% remaining)

1. Admiral notes hull status in the quarterdeck report.
2. Admiral begins drafting a flagship turnover brief in the background, capturing current mission state incrementally.
3. Admiral considers whether remaining coordination work can complete within budget. If not, begin planning the handover early.

### Red Hull Integrity (40-59% remaining)

1. Admiral writes a comprehensive flagship turnover brief to `{mission-dir}/turnover-briefs/flagship-{timestamp}.md` containing:
   - Full sailing orders (copied verbatim).
   - Battle plan with current task statuses, owners, and ship assignments.
   - All active ship statuses and their hull integrity levels.
   - Key decisions made during the mission and their rationale.
   - Active blockers, risks, and pending escalations.
   - Quarterdeck rhythm cadence and next scheduled checkpoint.
   - Relief chain history (see below).
2. Admiral notifies Admiralty (human) that the flagship is handing over and provides the turnover brief path.
3. Admiralty starts a new session. The new admiral reads the flagship turnover brief as its first action and resumes from the last quarterdeck checkpoint.

### Critical Hull Integrity (below 40% remaining)

1. Execute the Red procedure immediately. Do not wait for the next checkpoint.
2. Prioritize writing the flagship turnover brief over all other coordination work.

## Chained Reliefs

When a task requires multiple handovers (A hands to B, B hands to C), maintain institutional memory without unbounded growth.

1. Each turnover brief includes a "Relief chain" section listing all previous handovers for this task.
2. Each entry in the relief chain is a single-line summary: ship name, time on station, key accomplishment, and reason for relief.
3. The current ship writes a full turnover brief for its own work. Previous ships' work is represented only by their relief chain summaries, not by appending their full briefs.
4. Maximum 3 reliefs per task. If a third replacement is needed, the admiral should re-scope the task — it is likely too large or poorly defined for a single ship.
5. The relief chain gives the replacement ship a lineage of what has been tried and accomplished without consuming excessive context.

## Crew Variant

When a crew member aboard a ship exhausts their context, the captain handles relief at ship level.

1. Captain identifies the crew member at Red or Critical hull integrity.
2. Captain instructs the crew member to write a turnover brief to file.
3. Captain spawns a replacement crew member and provides the turnover brief path.
4. Captain issues a shutdown request to the exhausted crew member.
5. Captain updates the ship manifest to reflect the new assignment.
6. If the same role requires relief twice, captain escalates to admiral — the sub-task may need re-scoping.
