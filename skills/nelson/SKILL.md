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
- Select one mode per `references/squadron-composition.md`. If the user explicitly requested a mode, use it — user preference overrides the decision matrix.
  - `single-session`: Use for sequential tasks, low complexity, or heavy same-file editing.
  - `subagents`: Use for parallel, fully independent tasks that report only to admiral.
  - `agent-team`: Use when captains benefit from a shared task list, peer messaging, or coordinated deliverables. Also use when 4+ captains are needed.
- Set team size from task independence, not mission complexity:
    - Count the independent work units first. Each unit that can run with zero shared state or sequencing dependency receives its own captain, unless bundling conditions apply (shared files, sequencing dependency, or setup cost exceeds the work). That count — not a size tier — sets the target captain count.
    - Add `1 red-cell navigator` for medium/high threat work.
    - Do not exceed 10 squadron-level agents (admiral, captains, red-cell navigator). Crew are additional.
    - Assign each captain a ship name from `references/crew-roles.md` matching task weight (frigate for general, destroyer for high-risk, patrol vessel for small, flagship for critical-path, submarine for research).
    - Captain decides crew composition per ship using the crew-or-direct decision tree in `references/crew-roles.md`.
    - Captains may also deploy Royal Marines during execution for short-lived sorties — see `references/royal-marines.md` and use `references/admiralty-templates/marine-deployment-brief.md` for the deployment brief.
- If the sailing orders express cost-savings priority, load `references/model-selection.md` before assigning models to the squadron. Apply weight-based model selection to all `Agent` tool calls and include haiku briefing enhancements for agents assigned to haiku.

Reference `references/squadron-composition.md` for selection rules and `references/crew-roles.md` for ship naming and crew composition.

**Formation Gate — Standing Order Check:** You MUST NOT finalize the squadron until each question below is answered in writing and any triggered standing order remedy has been applied. Show your reasoning — a bare yes/no is not sufficient. If becalmed-fleet triggers, skip the remaining questions — single-session mode has no squadron to validate.
- `becalmed-fleet.md`: Should this mission use single-session instead of multi-agent?
- `light-squadron.md`: Is the captain count equal to the number of independent work units, or have tasks been under-split onto fewer captains than independence warrants?
- `all-hands-on-deck.md`: Does every captain carry genuinely independent work, or are some roles speculative?
- `crew-without-canvas.md`: Is every agent justified by actual task scope?
- `skeleton-crew.md`: Would any ship deploy exactly one crew member for an atomic task?
- `admiral-at-the-helm.md`: Is the admiral assigned only coordination, not implementation?

If any answer triggers a standing order, you MUST apply the corrective action and re-answer the question before proceeding. Proceeding with a triggered standing order unresolved is never permitted. For situations not covered by this gate, consult the Standing Orders table below.

## 3. Draft Battle Plan

- Split mission into independent tasks with clear deliverables.
    - Map the dependency graph: enumerate units of work that can run without shared state or ordering constraints. Each independent unit receives its own captain. Only group tasks onto one captain when they share files, require sequential ordering, or the context-setup cost demonstrably exceeds the work itself.
- Assign owner for each task and explicit dependencies.
- Assign file ownership when implementation touches code.
- Keep one task in progress per agent unless the mission explicitly requires multitasking.
- For each captain's task, include a ship manifest. If crew are mustered, list crew roles with sub-tasks and sequence. If the captain implements directly (0 crew), note "Captain implements directly." If the captain anticipates needing marine support, note marine capacity in the ship manifest (max 2).

Reference `references/admiralty-templates/battle-plan.md` for the battle plan template and `references/admiralty-templates/ship-manifest.md` for the ship manifest.

**Battle Plan Gate — Standing Order Check:** You MUST NOT finalize task assignments until each question below is answered in writing and any triggered standing order remedy has been applied. Show your reasoning — a bare yes/no is not sufficient.
- `split-keel.md`: Does each agent have exclusive file ownership with no conflicts?
- `captain-at-the-capstan.md`: For each captain with crew in the ship manifest, is the captain's role coordination (not implementation)?
- `unclassified-engagement.md`: Does every task have a risk tier assigned?
- `press-ganged-navigator.md`: Is the red-cell navigator being assigned implementation work?
- `all-hands-on-deck.md`: Are all crew roles justified by actual sub-task needs, or are some speculative?
- `skeleton-crew.md`: Would any ship deploy exactly one crew member for an atomic task that the captain should implement directly?

If any answer triggers a standing order, you MUST apply the corrective action and re-answer the question before proceeding. Proceeding with a triggered standing order unresolved is never permitted. For situations not covered by this gate, consult the Standing Orders table below.

**Before proceeding to Step 4:** You MUST verify that sailing orders exist, squadron is formed, and every task has an owner, deliverable, and action station tier. Do not proceed until all three conditions are confirmed.

**Admiralty Action List:** For each task, consciously mark `admiralty-action-required:` as `yes` or `no`. Then scan the battle plan for tasks marked `admiralty-action-required: yes`. If any exist, surface an Admiralty Action List to the user before spawning any agents:

```
ADMIRALTY ACTION LIST — Actions required from Admiralty

1. [Task name]
   action: [what you must do]
   timing: [before task starts | after task completes]
   unblocks: [task name or stand-down]

No action needed now. These will be raised by the captain when each step is reached.
```

If no tasks are marked `admiralty-action-required: yes`, omit the list — no noise on routine missions. This list is informational, not a gate. The user acknowledges by continuing the conversation. Squadron formation proceeds immediately after.

**Crew Briefing:** Spawning and task assignment are two steps. First, spawn each captain with the `Agent` tool, including a crew briefing from `references/admiralty-templates/crew-briefing.md` in their prompt. Then create and assign work with `TaskCreate` + `TaskUpdate`. Teammates do NOT inherit the lead's conversation context — they start with a clean slate and need explicit mission context. See `references/tool-mapping.md` for full parameter details by mode.

**Turnover Briefs:** When a ship is relieved due to context exhaustion, it writes a turnover brief using `references/admiralty-templates/turnover-brief.md`. See `references/damage-control/relief-on-station.md` for the full procedure.

## 4. Run Quarterdeck Rhythm

**Idle notification rule (immediate — do not defer to checkpoint):** Every time an idle notification arrives from a ship, ask two questions before doing anything else:
1. Is this ship's task marked complete?
2. Does any remaining pending task depend on this ship's output?

If the task is complete and no pending task depends on it, send `shutdown_request` immediately — in the same response. Do not wait for the next checkpoint cadence. Check the current `TaskList` state at the moment the idle notification arrives; each notification is evaluated independently against current state. This applies even when other ships are still running and even when a captain's results were delivered inline (not as a separate artifact). The `paid-off.md` standing order governs this; consult it if uncertain.

- Keep admiral focused on coordination and unblock actions.
- The admiral sets the mood of the squadron. Acknowledge progress, recognise strong work, and maintain cheerfulness under pressure.
- Run a quarterdeck checkpoint after every 1-2 task completions, when a captain reports a blocker, or when a captain goes idle with unverified outputs:
    - Update progress by checking `TaskList` for task states: `pending`, `in_progress`, `completed`.
    - Identify blockers and choose a concrete next action.
    - Use `SendMessage` to unblock captains or redirect their approach.
    - Confirm each crew member has active sub-tasks; flag idle crew or role mismatches.
    - Check for active marine deployments; verify marines have returned and outputs are incorporated.
    - Safety net: if any idle ship with a complete task was missed between checkpoints, send `shutdown_request` now before continuing.
    - Track burn against token/time budget.
    - Check hull integrity: collect damage reports from all ships, update the squadron readiness board, and take action per `references/damage-control/hull-integrity.md`. The admiral must also check its own hull integrity at each checkpoint.
    - Standing order scan: For each order below, ask "Has this situation arisen since the last checkpoint?" If yes, apply the corrective action now — do not defer.
        - `admiral-at-the-helm.md`: Has the admiral drifted into implementation work?
        - `drifting-anchorage.md`: Has any task scope crept beyond the sailing orders?
        - `captain-at-the-capstan.md`: Has any captain started implementing instead of coordinating crew?
        - `pressed-crew.md`: Has any crew member been assigned work outside their role?
        - `press-ganged-navigator.md`: Has the red-cell navigator been assigned implementation work?
        - `all-hands-on-deck.md`: Has any ship mustered crew roles that are idle or unjustified?
        - `battalion-ashore.md`: Has any captain deployed marines for crew work or sustained tasks?
    - **Write the quarterdeck report to disk** at every checkpoint using `references/admiralty-templates/quarterdeck-report.md`. Do not skip this when hull is Green — compaction can occur at any time and the on-disk report is the only recovery point. Before writing, if `quarterdeck-report.md` already exists in the working directory, find all files matching `quarterdeck-report-N.md`, determine N as one greater than the highest N found (0 if none exist), rename the existing file to `quarterdeck-report-N.md`, then write the new report. This keeps the latest report at the canonical path while preserving history.
    - Check `TaskList` for any tasks with description prefixed `[AWAITING-ADMIRALTY]:`. If any exist, surface the ask to Admiralty immediately — do not batch to the next checkpoint.
    - Cross-reference the battle plan against `TaskList`: for any task marked `admiralty-action-required: yes` in the battle plan that shows status `completed`, confirm there is a quarterdeck log entry recording admiralty sign-off. If no such entry exists, flag to Admiralty for manual verification — the task may have completed without the intended human step.
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
- Write the captain's log to a file named `captains-log.md` in the mission working directory. Before writing, if `captains-log.md` already exists, find all files matching `captains-log-N.md`, determine N as one greater than the highest N found (0 if none exist), rename the existing file to `captains-log-N.md`, then write the new report. This keeps the latest log at the canonical path while preserving history. The log MUST be written to disk — outputting it to chat only does not satisfy this requirement. The captain's log should contain:
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
| Tasks under-split onto fewer captains than independence warrants | `references/standing-orders/light-squadron.md` |
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
| Captain completed autonomous work and needs human action to continue | `references/standing-orders/awaiting-admiralty.md` |
| Agent completed task with no remaining work in the dependency graph | `references/standing-orders/paid-off.md` |

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
| Agent team communication failure (lost agent IDs, message bus down) | `references/damage-control/comms-failure.md` |

## Admiralty Doctrine

- Include this instruction in any admiral's compaction summary: Re-read `references/standing-orders/admiral-at-the-helm.md` to confirm you are in coordination role.
- Optimize for mission throughput, not equal work distribution.
- Prefer replacing stalled agents over waiting on undefined blockers.
- Recognise strong performance; motivation compounds across missions.
- Keep coordination messages targeted and concise.
- Escalate uncertainty early with options and one recommendation.
