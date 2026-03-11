---
name: nelson
description: Orchestrates multi-agent task execution using a Royal Navy squadron metaphor — from mission planning through parallel work coordination to stand-down. Use when work needs parallel agent orchestration, tight task coordination with quality gates, structured delegation with progress checkpoints, or a documented decision log.
argument-hint: "[mission description]"
---

# Nelson

Execute this workflow for the user's mission.

## 1. Issue Sailing Orders

- Review the user's brief for ambiguity. If the outcome, scope, or constraints are unclear, ask the user to clarify before drafting sailing orders.
- Write one sentence for `outcome`, `metric`, and `deadline`.
- Set constraints: token budget, reliability floor, compliance rules, and forbidden actions.
- Define what is out of scope.
- Define stop criteria and required handoff artifacts.

You MUST read `references/admiralty-templates/sailing-orders.md` and use the sailing-orders template when the user does not provide structure.

Example sailing orders summary:
```
Outcome: Refactor auth module to use JWT tokens
Metric: All 47 auth tests pass, no new dependencies
Deadline: This session
Constraints: Do not modify the public API surface
Out of scope: Migration script for existing sessions
```

**Session Hygiene:** Before forming the squadron, execute session hygiene per `references/damage-control/session-hygiene.md`. Clear stale damage reports and turnover briefs from any previous session. Skip this step when resuming an interrupted session.

## 2. Form The Squadron

- Brief captains on mission intent and constraints. Make the plan clear, invite questions early.
- Select one mode:
  - `single-session`: Use for sequential tasks, low complexity, or heavy same-file editing.
  - `subagents`: Use for parallel scouting or isolated tasks that report only to admiral.
  - `agent-team`: Use when independent agents must coordinate with each other directly.
- Set team size from mission complexity:
    - Default to `1 admiral + 3-6 captains`.
    - Add `1 red-cell navigator` for medium/high threat work.
    - Do not exceed 10 squadron-level agents (admiral, captains, red-cell navigator). Crew are additional.
    - Assign each captain a ship name from `references/crew-roles.md` matching task weight (frigate for general, destroyer for high-risk, patrol vessel for small, flagship for critical-path, submarine for research).
    - Captain decides crew composition per ship using the crew-or-direct decision tree in `references/crew-roles.md`.
    - Captains may also deploy Royal Marines during execution for short-lived sorties — see `references/royal-marines.md` and use `references/admiralty-templates/marine-deployment-brief.md` for the deployment brief.

Reference `references/squadron-composition.md` for selection rules and `references/crew-roles.md` for ship naming and crew composition. Consult the Standing Orders table below before forming the squadron.

## 3. Draft Battle Plan

- Split mission into independent tasks with clear deliverables.
- Assign owner for each task and explicit dependencies.
- Assign file ownership when implementation touches code.
- Keep one task in progress per agent unless the mission explicitly requires multitasking.
- For each captain's task, include a ship manifest. If crew are mustered, list crew roles with sub-tasks and sequence. If the captain implements directly (0 crew), note "Captain implements directly." If the captain anticipates needing marine support, note marine capacity in the ship manifest (max 2).

Reference `references/admiralty-templates/battle-plan.md` for the battle plan template and `references/admiralty-templates/ship-manifest.md` for the ship manifest. Consult the Standing Orders table below when assigning files or if scope is unclear.

**Before proceeding to Step 4:** Verify sailing orders exist, squadron is formed, and every task has an owner, deliverable, and action station tier.

**Crew Briefing:** Spawning and task assignment are two steps. First, spawn each captain with the `Agent` tool, including a crew briefing from `references/admiralty-templates/crew-briefing.md` in their prompt. Then create and assign work with `TaskCreate` + `TaskUpdate`. Teammates do NOT inherit the lead's conversation context — they start with a clean slate and need explicit mission context. See `references/tool-mapping.md` for full parameter details by mode.

**Turnover Briefs:** When a ship is relieved due to context exhaustion, it writes a turnover brief using `references/admiralty-templates/turnover-brief.md`. See `references/damage-control/relief-on-station.md` for the full procedure.

## 4. Run Quarterdeck Rhythm

- Keep admiral focused on coordination and unblock actions.
- The admiral sets the mood of the squadron. Acknowledge progress, recognise strong work, and maintain cheerfulness under pressure.
- Run a quarterdeck checkpoint after every 2-3 task completions, when a captain reports a blocker, or when a captain goes idle with unverified outputs:
    - Update progress by checking `TaskList` for task states: `pending`, `in_progress`, `completed`.
    - Identify blockers and choose a concrete next action.
    - Use `SendMessage` to unblock captains or redirect their approach.
    - Confirm each crew member has active sub-tasks; flag idle crew or role mismatches.
    - Check for active marine deployments; verify marines have returned and outputs are incorporated.
    - Clean up idle ships unless you believe they will continue their tasking. (E.g., Work has paused waiting on input from another ship.)
    - Track burn against token/time budget.
    - Check hull integrity: collect damage reports from all ships, update the squadron readiness board, and take action per `references/damage-control/hull-integrity.md`. The admiral must also check its own hull integrity at each checkpoint.
- Re-scope early when a task drifts from mission metric.
- When a mission encounters difficulties, consult the Damage Control table below for recovery and escalation procedures.

Example quarterdeck checkpoint:
```
Status: 3/5 tasks complete, 1 blocked, 1 in progress
Blocker: HMS Resolute waiting on API schema from HMS Swift
Action: Redirect HMS Swift to prioritise schema export
Budget: ~40% tokens consumed, on track
Hull: All ships green
```

Reference `references/tool-mapping.md` for coordination tools, `references/admiralty-templates/quarterdeck-report.md` for the report template, and `references/admiralty-templates/damage-report.md` for damage report format. Use `references/commendations.md` for recognition signals and graduated correction. Consult the Standing Orders table below if admiral is doing implementation or tasks are drifting from scope.

## 5. Set Action Stations

- You MUST read and apply station tiers from `references/action-stations.md`.
- Require verification evidence before marking tasks complete:
    - Test or validation output.
    - Failure modes and rollback notes.
    - Red-cell review for medium+ station tiers.
- Trigger quality checks on:
    - Task completion.
    - Agent idle with unverified outputs.
    - Before final synthesis.
- For crewed tasks, verify crew outputs align with role boundaries (consult `references/crew-roles.md` and the Standing Orders table below if role violations are detected).
- Marine deployments follow station-tier rules in `references/royal-marines.md`. Station 2+ marine deployments require admiral approval.

Reference `references/admiralty-templates/red-cell-review.md` for the red-cell review template. Consult the Standing Orders table below if tasks lack a tier or red-cell is assigned implementation work.

## 6. Stand Down And Log Action

- Stop or archive all agent sessions, including crew.
- Write the captain's log to a file named `captains-log.md` in the mission working directory. The log MUST be written to disk — outputting it to chat only does not satisfy this requirement. The captain's log should contain:
    - Decisions and rationale.
    - Diffs or artifacts.
    - Validation evidence.
    - Open risks and follow-ups.
    - Mentioned in Despatches: name agents and contributions that were exemplary.
    - Record reusable patterns and failure modes for future missions.

Reference `references/admiralty-templates/captains-log.md` for the captain's log template and `references/commendations.md` for Mentioned in Despatches criteria.

**Mission Complete Gate:** You MUST NOT declare the mission complete until `captains-log.md` exists on disk and has been confirmed readable. If context pressure is high, write a minimal log noting which sections were abbreviated — but the file must exist. Skipping Step 6 is never permitted.

## Standing Orders

Consult the specific standing order that matches the situation.

| Situation | Standing Order |
|---|---|
| Choosing between single-session and multi-agent | `references/standing-orders/becalmed-fleet.md` |
| Deciding whether to add another agent | `references/standing-orders/crew-without-canvas.md` |
| Assigning files to agents in the battle plan | `references/standing-orders/split-keel.md` |
| Task scope drifting from sailing orders | `references/standing-orders/drifting-anchorage.md` |
| Admiral doing implementation instead of coordinating | `references/standing-orders/admiral-at-the-helm.md` |
| Assigning work to the red-cell navigator | `references/standing-orders/press-ganged-navigator.md` |
| Tasks proceeding without a risk tier classification | `references/standing-orders/unclassified-engagement.md` |
| Captain implementing instead of coordinating crew | `references/standing-orders/captain-at-the-capstan.md` |
| Crewing every role regardless of task needs | `references/standing-orders/all-hands-on-deck.md` |
| Spawning one crew member for an atomic task | `references/standing-orders/skeleton-crew.md` |
| Assigning crew work outside their role | `references/standing-orders/pressed-crew.md` |
| Captain deploying marines for crew work or sustained tasks | `references/standing-orders/battalion-ashore.md` |

## Damage Control

Consult the specific procedure that matches the situation.

| Situation | Procedure |
|---|---|
| Agent unresponsive, looping, or producing no useful output | `references/damage-control/man-overboard.md` |
| Session interrupted (context limit, crash, timeout) | `references/damage-control/session-resumption.md` |
| Completed task found faulty, other tasks are sound | `references/damage-control/partial-rollback.md` |
| Mission cannot succeed, continuing wastes budget | `references/damage-control/scuttle-and-reform.md` |
| Issue exceeds current authority or needs clarification | `references/damage-control/escalation.md` |
| Ship's crew consuming disproportionate tokens or time | `references/damage-control/crew-overrun.md` |
| Ship's context window depleted, needs replacement | `references/damage-control/relief-on-station.md` |
| Ship context window approaching limits | `references/damage-control/hull-integrity.md` |
| Starting a new session with stale data from a previous mission | `references/damage-control/session-hygiene.md` |

## Admiralty Doctrine

- Include this instruction in any admiral's compaction summary: Re-read `references/standing-orders/admiral-at-the-helm.md` to confirm you are in coordination role.
- Optimize for mission throughput, not equal work distribution.
- Prefer replacing stalled agents over waiting on undefined blockers.
- Recognise strong performance; motivation compounds across missions.
- Keep coordination messages targeted and concise.
- Escalate uncertainty early with options and one recommendation.
