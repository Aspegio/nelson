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

**Establish Mission Directory:**
- **New session:** Generate a short session identifier by running `uuidgen | cut -d- -f1` (produces an 8-character hex string). This identifier is stable for the duration of the mission. Create a mission directory at `.nelson/missions/{YYYY-MM-DD_HHMMSS}_{SESSION_ID}/` using the current date and time (24-hour format, including seconds) and the SESSION_ID generated above. Create the subdirectories `damage-reports/` and `turnover-briefs/` within it. Record the mission directory path and refer to it as `{mission-dir}` for the remainder of this mission. After creating the mission directory, write its path to `.nelson/.active-{SESSION_ID}`. This file persists the mission directory for this session.
- **Resumed session:** If you have previously created a mission directory in this session and know the SESSION_ID, read `.nelson/.active-{SESSION_ID}` to recover the mission path. Set that path as `{mission-dir}`. If you cannot determine your SESSION_ID (e.g., after a full restart), list `.nelson/missions/` and present the options to the user for selection. Set the chosen directory as `{mission-dir}`. Recover state per `references/damage-control/session-resumption.md` (prefer JSON files, fall back to quarterdeck report prose).

All mission artifacts — captain's log, quarterdeck reports, damage reports, and turnover briefs — are written inside `{mission-dir}`.

**Structured Data Capture:** After establishing the mission directory, run the `nelson-data.py` script located in the skill's directory (e.g., `python3 .claude/skills/nelson/scripts/nelson-data.py init --outcome "..." --metric "..." --deadline "..."`). If installed globally, it may be in `~/.claude/skills/nelson/scripts/`. This creates `sailing-orders.json` and initialises `mission-log.json`. See `references/structured-data.md` for the full argument list.

**Session Hygiene:** Execute session hygiene per `references/damage-control/session-hygiene.md`. Skip this step when resuming an interrupted session.

## 2. Draft Battle Plan

- Split mission into independent tasks with clear deliverables.
    - Map the dependency graph: enumerate units of work that can run without shared state or ordering constraints. Each independent unit receives its own captain. Only group tasks onto one captain when they share files, require sequential ordering, or the context-setup cost demonstrably exceeds the work itself.
    - The default is one captain per independent task. Grouping is the exception and requires a concrete reason.
    - If cost-savings is a priority, also consider task inputs — avoid multiple agents independently loading the same large inputs into their contexts.
- Assign explicit dependencies for each task.
- Assign file ownership when implementation touches code.
- Assign an action station tier to each task (see `references/action-stations.md`).
- For each task, note expected crew composition using the crew-or-direct decision tree in `references/crew-roles.md`. If crew are mustered, list crew roles with sub-tasks and sequence. If the captain implements directly (0 crew), note "Captain implements directly." If the captain anticipates needing marine support, note marine capacity (max 2).
- For each task, consciously mark `admiralty-action-required: yes` or `no`.
- Keep one task in progress per agent unless the mission explicitly requires multitasking.

Reference `references/admiralty-templates/battle-plan.md` for the battle plan template and `references/admiralty-templates/ship-manifest.md` for the ship manifest.

**Battle Plan Gate — Standing Order Check:** You MUST NOT finalize task assignments until each question below is answered in writing and any triggered standing order remedy has been applied. Show your reasoning — a bare yes/no is not sufficient.
- `becalmed-fleet.md`: Should this mission use single-session instead of multi-agent? If yes, skip Step 3 — single-session has no squadron to form.
- `light-squadron.md`: Is the task count equal to the number of independent work units, or have tasks been under-split?
- `split-keel.md`: Does each task have exclusive file ownership with no conflicts? (This will be automatically verified in Step 3).
- `unclassified-engagement.md`: Does every task have a risk tier?
- `all-hands-on-deck.md`: Has each task been crewed only with roles its work actually demands?
- `skeleton-crew.md`: Would any task deploy exactly one crew member for an atomic task the captain should handle directly?
- `crew-without-canvas.md`: Is every agent justified by actual task scope?
- `captain-at-the-capstan.md`: For each task with crew, is the captain's role coordination, not implementation?
- `press-ganged-navigator.md`: Is the red-cell navigator being assigned implementation work?
- `admiral-at-the-helm.md`: Does the battle plan assign any implementation work (excluding permitted read-only recombination) to the admiral?
- `wrong-ensign.md`: Do the planned coordination tools match the selected execution mode?

If any answer triggers a standing order, you MUST apply the corrective action and re-answer the question before proceeding. For situations not covered by this gate, consult the Standing Orders table below.

**Structured Data Capture:** Task registration requires owners, which are assigned in Step 3. No `nelson-data.py` script calls at this step.

## 3. Form the Squadron

- Select execution mode per `references/squadron-composition.md`. If the user explicitly requested a mode, use it — user preference overrides the decision matrix.
    - `single-session`: sequential tasks, low complexity, or heavy same-file editing.
    - `subagents`: parallel, fully independent tasks that report only to the admiral.
    - `agent-team`: captains benefit from a shared task list, peer messaging, or coordinated deliverables; or 4+ captains are needed.

**Mode-Tool Consistency Gate:** Before assigning ships, confirm your tool usage matches the selected mode by reviewing `references/tool-mapping.md`:
- **`subagents` mode:** Captains do NOT use `TaskCreate`, `TaskList`, `TaskGet`, `TaskUpdate`, or `SendMessage(type="message")`. Captains report via the `Agent` tool return value only. The admiral uses `TaskCreate`/`TaskUpdate`/`TaskList` to track progress in the session task list (visibility only — captains cannot see these tasks).
- **`agent-team` mode:** Do NOT use `Agent` with `subagent_type` to spawn captains (marines still use `subagent_type`). Use `TeamCreate` first, then `Agent` with `team_name` + `name`. Coordinate via `TaskList` and `SendMessage`.
- **`single-session` mode:** The admiral uses `TaskCreate`, `TaskUpdate`, `TaskList`, and `TaskGet` to track progress as it completes each task sequentially.

**Task List Visibility:** After selecting the execution mode, create a `TaskCreate` entry for each battle plan task to make mission progress visible in the Claude Code task list (Ctrl+T). This applies in **all execution modes** — it is admiral-level visibility tracking, not inter-agent coordination.

For each task:
- `subject`: Task name from the battle plan (imperative form, e.g., "Refactor auth module")
- `description`: One-line deliverable
- `activeForm`: Present-continuous form shown in the UI spinner (e.g., "Refactoring auth module")

All tasks start as `pending`. They will be updated with owners and status as the mission progresses. In `single-session` mode (where Step 3 is otherwise skipped), the admiral still creates these entries before proceeding to Step 4.

- Assign each task a captain and a ship name from `references/crew-roles.md` matching task weight (frigate for general, destroyer for high-risk, patrol vessel for small, flagship for critical-path, submarine for research).
- Finalize ship manifests: confirm crew roles per task, or note "Captain implements directly."
- Add `1 red-cell navigator` for medium/high threat work. Do not exceed 10 squadron-level agents (admiral, captains, red-cell navigator). Crew are additional.
- If the sailing orders express cost-savings priority, load `references/model-selection.md` before assigning models. Apply weight-based model selection to all `Agent` tool calls and include haiku briefing enhancements for agents assigned to haiku.

```
SQUADRON FORMATION ORDERS

Mode: [single-session | subagents | agent-team]
Captain count: [N]

Ships:
  [Ship name] — [vessel type] — [one-line task summary]
    Crew: [roles, or "Captain implements directly"]
  [repeat for each ship]

[Red-cell navigator — HMS X, if present]
```

If any tasks are marked `admiralty-action-required: yes`, append before awaiting approval:

```
ADMIRALTY ACTION LIST — Actions required from Admiralty

1. [Task name]
   action: [what you must do]
   timing: [before task starts | after task completes]
   unblocks: [task name or stand-down]

Actions marked `timing: before task starts` require your sign-off before the relevant captain is spawned.
```

Do not spawn any agents or create any tasks until the user approves. If the user requests changes, revise and redisplay before proceeding.

> **Note:** Nelson requires an interactive session for formation approval. Headless and CI invocation are not supported at this time.

**Structured Data Capture:** Once formation is approved, run these commands in order:
1. `python3 .claude/skills/nelson/scripts/nelson-data.py task --mission-dir {mission-dir} --id N --name "..." --owner "..." ...` for each task (owners are now known from formation). See `references/structured-data.md` for task arguments.
2. `python3 .claude/skills/nelson/scripts/nelson-data.py plan-approved --mission-dir {mission-dir}` to finalise the battle plan and compute DAG metrics.
3. `python3 .claude/skills/nelson/scripts/nelson-data.py squadron --mission-dir {mission-dir} --admiral "..." --admiral-model [model] --captain "name:class:model:task_id" ... --mode [mode]` to record squadron composition. Repeat `--captain` for each captain. See `references/structured-data.md` for the full argument list.
4. `python3 .claude/skills/nelson/scripts/nelson_conflict_scan.py --plan {mission-dir}/battle-plan.json` to verify there are no file ownership conflicts. If conflicts are found, you MUST resolve them and update the battle plan before proceeding.

**Before proceeding to Step 4:** Verify that sailing orders exist, all tasks have owners and deliverables, and every task has an action station tier.

**Crew Briefing:** Spawning and task assignment are two steps. First, spawn each captain with the `Agent` tool, including a crew briefing from `references/admiralty-templates/crew-briefing.md` in their prompt. Then assign work to the existing task entries with `TaskUpdate`. Teammates do NOT inherit the lead's conversation context — they start with a clean slate and need explicit mission context. See `references/tool-mapping.md` for full parameter details by mode.

**Task Status Updates:** After formation, update the task list entries created earlier in this step:
- **`agent-team` mode:** Use `TaskUpdate` to set `owner` to each captain's name and `status` to `in_progress` as captains are spawned. The team's shared task list now serves both visibility and coordination.
- **`subagents` mode:** Use `TaskUpdate` to set `status` to `in_progress` as each captain is dispatched. The admiral tracks these directly.
- **`single-session` mode:** Use `TaskUpdate` to set `status` to `in_progress` as the admiral begins each task.

**Edit permissions:** When spawning any agent whose task involves editing files, set `mode: "acceptEdits"` on the `Agent` tool call. Omitting this can cause a permission race condition that silently stalls the agent at its first edit. When in doubt, include it.

**Turnover Briefs:** When a ship is relieved due to context exhaustion, it writes a turnover brief using `references/admiralty-templates/turnover-brief.md`. See `references/damage-control/relief-on-station.md` for the full procedure.

## 4. Get Permission to Sail

**Display and Permission Gate:**
1. Display the complete battle plan to the user if `becalmed-fleet.md` is in effect.
2. Display the complete squadron formation to the user if `becalmed-fleet.md` is not in effect. The battle plan (drafted in Step 2) should also be available for review.
3. You are REQUIRED to wait for explicit permission to proceed.

## 5. Run Quarterdeck Rhythm

**Idle notification rule (immediate — do not defer to checkpoint):** Every time an idle notification arrives from a ship, ask three questions before doing anything else:
1. Is this ship's task marked complete?
2. Does any remaining pending task depend on this ship's output?
3. **Agent-team mode only:** Has the admiral received and processed this ship's results?

If the task is complete and no pending task depends on it, proceed to shutdown per `references/standing-orders/paid-off.md`. In agent-team mode, the admiral must confirm receipt of the captain's results before sending `shutdown_request` — retrieve them via `SendMessage` or by reading output files if not already received. In subagents mode, results are returned synchronously by the `Agent` tool, so no additional confirmation is needed. Do not wait for the next checkpoint cadence. Check the current `TaskList` state at the moment the idle notification arrives; each notification is evaluated independently against current state. This applies even when other ships are still running.

**Shutdown attempt ceiling:** If a `shutdown_request` to a ship goes unacknowledged, do not loop indefinitely. After 3 failed attempts to the same agent, abandon the shutdown attempt, note the failure in the captain's log, and continue the mission. If `TeamDelete` is blocked by stuck agents, manual cleanup is available — see `references/damage-control/man-overboard.md` for the procedure.

- Keep admiral focused on coordination and unblock actions.
- The admiral sets the mood of the squadron. Acknowledge progress, recognise strong work, and maintain cheerfulness under pressure.
- **Checkpoint Cadence Gate:** You MUST NOT process a third task completion without writing a quarterdeck checkpoint. Before dispatching new work or processing the next completion, confirm the last checkpoint is no more than 2 completions old. The quarterdeck report is your only recovery point if context compaction occurs — stale reports mean lost coordination state.
- Run a quarterdeck checkpoint after every 1-2 task completions, when a captain reports a blocker, or when a captain goes idle with unverified outputs:
    - Update progress by checking `TaskList` for task states: `pending`, `in_progress`, `completed`.
    - Mark completed tasks with `TaskUpdate` setting `status` to `completed`. In `subagents` and `single-session` modes, the admiral updates the session task list directly; in `agent-team` mode, captains or the admiral update the shared task list.
    - Identify blockers and choose a concrete next action.
    - Use `SendMessage` to unblock captains or redirect their approach.
    - Confirm each crew member has active sub-tasks; flag idle crew or role mismatches.
    - Check for active marine deployments; verify marines have returned and outputs are incorporated.
    - Safety net: if any idle ship with a complete task was missed between checkpoints, apply the `references/standing-orders/paid-off.md` shutdown procedure now before continuing.
    - Track burn against token/time budget.
    - Check hull integrity: collect damage reports from all ships, update the squadron readiness board, and take action per `references/damage-control/hull-integrity.md`. The admiral must also check its own hull integrity at each checkpoint. **Every ship must file a damage report at every checkpoint** to `{mission-dir}/damage-reports/{ship-name}.json` using the schema in `references/admiralty-templates/damage-report.md` — do not skip this when hull is Green.
    - Standing order scan: For each order below, ask "Has this situation arisen since the last checkpoint?" If yes, apply the corrective action now — do not defer.
        - `admiral-at-the-helm.md`: Has the admiral drifted into implementation work (excluding permitted read-only recombination)?
        - `drifting-anchorage.md`: Has any task scope crept beyond the sailing orders?
        - `captain-at-the-capstan.md`: Has any captain started implementing instead of coordinating crew?
        - `pressed-crew.md`: Has any crew member been assigned work outside their role?
        - `press-ganged-navigator.md`: Has the red-cell navigator been assigned implementation work?
        - `all-hands-on-deck.md`: Has any ship mustered crew roles that are idle or unjustified?
        - `battalion-ashore.md`: Has any captain deployed marines for crew work or sustained tasks?
        - `wrong-ensign.md`: Is the admiral or any captain using tools from the wrong execution mode?
    - **Write the quarterdeck report to disk** at `{mission-dir}/quarterdeck-report.md` at every checkpoint using `references/admiralty-templates/quarterdeck-report.md`. Do not skip this when hull is Green — compaction can occur at any time and the on-disk report is the only recovery point. Before writing, if `quarterdeck-report.md` already exists in `{mission-dir}`, find all files matching glob pattern `quarterdeck-report-[0-9]*.md`, determine N as one greater than the highest N found (0 if none exist), rename the existing file to `quarterdeck-report-N.md`, then write the new report. This keeps the latest report at the canonical path while preserving history.
    - **Structured data capture:** Run `python3 .claude/skills/nelson/scripts/nelson-data.py checkpoint --mission-dir {mission-dir} --pending N --in-progress N --completed N ...` with current progress, budget, hull, and decision data. Between checkpoints, run `python3 .claude/skills/nelson/scripts/nelson-data.py event --mission-dir {mission-dir} --type <event_type> ...` for state changes (task completions, blockers, hull threshold crossings, standing order violations). See `references/structured-data.md` for event types and arguments.
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

## 6. Set Action Stations

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
- Marine deployments follow station-tier rules in `references/royal-marines.md`. Station 2+ marine deployments require admiral approval. Captains use `references/admiralty-templates/marine-deployment-brief.md` when deploying a marine.

Reference `references/admiralty-templates/red-cell-review.md` for the red-cell review template. Consult the Standing Orders table below if tasks lack a tier or red-cell is assigned implementation work.

## 7. Stand Down And Log Action

- Stop or archive all agent sessions, including crew.
- Write the captain's log to `{mission-dir}/captains-log.md`. The log MUST be written to disk — outputting it to chat only does not satisfy this requirement. The captain's log should contain:
    - Decisions and rationale.
    - Diffs or artifacts.
    - Validation evidence.
    - Open risks and follow-ups.
    - Mentioned in Despatches: name agents and contributions that were exemplary.
    - Record reusable patterns and failure modes for future missions.

Reference `references/admiralty-templates/captains-log.md` for the captain's log template and `references/commendations.md` for Mentioned in Despatches criteria.

**Structured Data Capture:** Before writing the captain's log, run `python3 .claude/skills/nelson/scripts/nelson-data.py stand-down --mission-dir {mission-dir} --outcome-achieved --actual-outcome "..." --metric-result "..."` to capture the structured mission summary. See `references/structured-data.md` for the full argument list.

**Task List Cleanup:** Verify all task list entries reflect final state. Mark any remaining `in_progress` tasks as `completed` if their work is done, or note incomplete tasks in the captain's log. This ensures the Claude Code task list shows an accurate final summary.

**Session State Cleanup:** Remove the session state file by deleting `.nelson/.active-{SESSION_ID}`.

**Mission Complete Gate:** You MUST NOT declare the mission complete until `{mission-dir}/captains-log.md` exists on disk and has been confirmed readable. If context pressure is high, write a minimal log noting which sections were abbreviated — but the file must exist. Skipping Step 7 is never permitted.

## Standing Orders

Consult the specific standing order that matches the situation.

| Situation | Standing Order |
|---|---|
| Choosing between single-session and multi-agent | `references/standing-orders/becalmed-fleet.md` |
| Tasks under-split onto fewer captains than independence warrants | `references/standing-orders/light-squadron.md` |
| Deciding whether to add another agent | `references/standing-orders/crew-without-canvas.md` |
| Assigning files to agents in the battle plan | `references/standing-orders/split-keel.md` |
| Task scope drifting from sailing orders | `references/standing-orders/drifting-anchorage.md` |
| Admiral doing implementation instead of coordinating (excluding permitted read-only recombination) | `references/standing-orders/admiral-at-the-helm.md` |
| Assigning work to the red-cell navigator | `references/standing-orders/press-ganged-navigator.md` |
| Tasks proceeding without a risk tier classification | `references/standing-orders/unclassified-engagement.md` |
| Captain implementing instead of coordinating crew | `references/standing-orders/captain-at-the-capstan.md` |
| Crewing every role regardless of task needs | `references/standing-orders/all-hands-on-deck.md` |
| Spawning one crew member for an atomic task | `references/standing-orders/skeleton-crew.md` |
| Assigning crew work outside their role | `references/standing-orders/pressed-crew.md` |
| Captain deploying marines for crew work or sustained tasks | `references/standing-orders/battalion-ashore.md` |
| Captain completed autonomous work and needs human action to continue | `references/standing-orders/awaiting-admiralty.md` |
| Agent completed task with no remaining work in the dependency graph | `references/standing-orders/paid-off.md` |
| Using tools from the wrong execution mode | `references/standing-orders/wrong-ensign.md` |

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
| Preparing the mission directory at session start | `references/damage-control/session-hygiene.md` |
| Agent team communication failure (lost agent IDs, message bus down) | `references/damage-control/comms-failure.md` |

## Admiralty Doctrine

- Include this instruction in any admiral's compaction summary: Re-read the quarterdeck report at the mission directory path to recover `{mission-dir}`. If the path is unknown, read `.nelson/.active-{SESSION_ID}` if you know the SESSION_ID, otherwise list `.nelson/missions/` and present the options to the user for selection. Then re-read `references/standing-orders/admiral-at-the-helm.md` to confirm you are in coordination role.
- Optimize for mission throughput, not equal work distribution.
- Prefer replacing stalled agents over waiting on undefined blockers.
- Recognise strong performance; motivation compounds across missions.
- Keep coordination messages targeted and concise.
- Escalate uncertainty early with options and one recommendation.
