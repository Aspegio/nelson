---
name: nelson
description: Orchestrates multi-agent task execution using a Royal Navy squadron metaphor — from mission planning through parallel work coordination to stand-down. Use when work needs parallel agent orchestration, tight task coordination with quality gates, structured delegation with progress checkpoints, or a documented decision log.
argument-hint: "[mission description]"
paths: [".nelson/**"]
---

# Nelson

```!
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nelson/scripts/nelson-data.py" status
```

Execute this workflow for the user's mission.

Write as Nelson's captains would write: concise, elegant, confident. Not eighteenth-century prose — the clear register of an officer who respects the reader's time. The skill's voice sets the example for the admiral's voice.

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
- **New session:** Run `nelson-data.py init` (see "Structured Data Capture" below). The script owns directory creation: it generates an 8-character hex SESSION_ID, creates `.nelson/missions/{YYYY-MM-DD_HHMMSS}_{SESSION_ID}/` with the `damage-reports/` and `turnover-briefs/` subdirectories, writes `sailing-orders.json`, `mission-log.json`, and `fleet-status.json`, writes `.nelson/.active-{SESSION_ID}` as the session marker, and prints the mission directory path to stdout. Capture that path as `{mission-dir}` for the remainder of this mission. The SESSION_ID is the segment after the last underscore in the directory name. If you need a specific SESSION_ID (e.g., testing or resuming a known id), pass `--session-id <8-hex>`.
- **Resumed session:** First, attempt auto-recovery by running `python3 .claude/skills/nelson/scripts/nelson-data.py recover --missions-dir .nelson/missions`. If this finds an active mission with handoff packets, use the structured recovery briefing to resume directly. Otherwise, if you know the SESSION_ID, read `.nelson/.active-{SESSION_ID}` to recover the mission path. Set that path as `{mission-dir}`. If you cannot determine your SESSION_ID (e.g., after a full restart), list `.nelson/missions/` and present the options to the user for selection. Set the chosen directory as `{mission-dir}`. Recover state per `references/damage-control/session-resumption.md` (prefer JSON files, fall back to quarterdeck report prose). **Re-establish the standing goal:** a `/goal` is restored automatically on `--resume`/`--continue` but not in a fresh session, so if none is active (check with a bare `/goal`) and `sailing-orders.json` carries a recorded `goal_condition`, re-issue it per `references/goal-alignment.md`.

All mission artifacts — captain's log, quarterdeck reports, damage reports, and turnover briefs — are written inside `{mission-dir}`.

**Structured Data Capture:** Run the `nelson-data.py` script located in the skill's directory (e.g., `python3 .claude/skills/nelson/scripts/nelson-data.py init --outcome "..." --metric "..." --deadline "..."`). If installed globally, it may be in `~/.claude/skills/nelson/scripts/`. `init` creates the mission directory, the initial JSON files (`sailing-orders.json`, `mission-log.json`, `fleet-status.json` with initial phase `SAILING_ORDERS`), and the `.nelson/.active-{SESSION_ID}` marker in one atomic step. See `references/structured-data.md` for the full argument list.

**Phase Advance:** After structured data capture, advance the mission phase from SAILING_ORDERS to ESTIMATE:

```bash
python3 .claude/skills/nelson/scripts/nelson-phase.py advance --mission-dir {mission-dir}
```

**Session Hygiene:** Execute session hygiene per `references/damage-control/session-hygiene.md`. Skip this step when resuming an interrupted session.

**Standing Goal (optional):** For long autonomous, headless (`-p`), scheduled, or ultracode missions — where standing down too early is the failure mode — offer to set a Claude Code `/goal` that keeps the session from stopping until the mission is genuinely complete. Compose it from the sailing orders rather than by hand:

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py goal-condition \
  --mission-dir {mission-dir} --record
```

Present the printed `/goal ...` line for the user to set. If the user already set a `/goal` before invoking Nelson, do NOT replace it — read it back with a bare `/goal`, reconcile the sailing orders to it, and only re-issue a composed goal with the user's agreement. Skip this for short interactive missions where the human is steering turn by turn. You MUST read `references/goal-alignment.md` before setting a goal — the evaluator judges the condition against the conversation transcript only, so completion evidence must be surfaced into chat (this shapes Stand Down in Step 8).

**The Estimate opt-in:** Before proceeding, ask the user:

> *"Shall I carry out The Estimate before drafting the Battle Plan? I would recommend it for this mission — [brief reason]."*

Give an honest recommendation. For straightforward missions with clear scope in a single subsystem, proceed without the Estimate. For complex, ambiguous, or multi-system missions, recommend conducting it. If the user accepts, proceed to Step 2. If the user declines, record the decision and skip to Step 3:

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py skip-estimate \
  --mission-dir {mission-dir} --reason "[one-line rationale]"
python3 .claude/skills/nelson/scripts/nelson-phase.py advance --mission-dir {mission-dir}
python3 .claude/skills/nelson/scripts/nelson-phase.py advance --mission-dir {mission-dir}
```

The first `advance` moves from SAILING_ORDERS to ESTIMATE. The second `advance` moves from ESTIMATE to BATTLE_PLAN; the exit validator accepts the transition because `skip-estimate` has already recorded the opt-out in `sailing-orders.json`.

## 2. Conduct The Estimate

Read `references/the-estimate.md` for the full thought process, and use `references/admiralty-templates/estimate.md` as the scaffold. Work through seven questions that turn a mission brief into a plan worth executing:

1. **Reconnaissance** — What is the terrain? What are we working with?
2. **Intent** — What are we really trying to achieve, and why?
3. **Effects** — What changes must occur to fulfil the intent?
4. **Terrain** — Where in the codebase does each effect land?
5. **Forces** — What agents, models, and context do we need?
6. **Coordination** — What depends on what? What runs in parallel?
7. **Control** — Where are the quality gates and intervention points?

**Q1 dispatches Explore sub-agents.** Send one or more Explore agents into the codebase with a scouting brief derived from the Sailing Orders; synthesise their findings into the Reconnaissance section. Q1 must follow the Explorer discipline rules in `references/the-estimate.md` (multiple focused dispatches, structured summaries, no raw file contents).

**Q2–Q3 and Q4–Q7 are delegated in two separate sub-agent dispatches** so Q2–Q7 reasoning does not consume admiral context. The first dispatch (Estimate-Drafter) produces commander's intent and effects after Q1 and before Checkpoint 2; the second dispatch (Estimate-Planner) produces terrain, forces, coordination, and control after Checkpoint 2 approves intent and effects. Both subagents inherit the admiral's model; The Estimate phase is exempt from cost-savings model selection. See `references/the-estimate.md` for the briefing contents and dispatch templates.

**Two checkpoints bracket the analytical work.** After Q1, present findings to the user and invite correction or reframing. After Q3, present intent and effects for substantive approval before planning *how*. Q4-Q7 flow from approved effects and are the admiral's professional judgement — work through them without interrupting the user. Collapse both checkpoints into a single final review only when all three conditions hold: sailing orders specify outcome, metric, and deadline; Q1 reveals no surprises; the work lands in a single subsystem. See `references/the-estimate.md` for full checkpoint discipline.

Each effect in §3 must carry **commander's guidance** (how to do it) and **acceptance criteria** (what must be true when done). Criteria flow through to captains and are verified at stand-down; captains choose the verification method per criterion (test, type-check, lint, review, visual).

Write the estimate to `{mission-dir}/estimate.md` with one H2 section per question. Split to `{mission-dir}/estimate/0N-name.md` only when a section grows unwieldy.

**Phase Advance:** After the user approves the final estimate, advance from ESTIMATE to BATTLE_PLAN:

```bash
python3 .claude/skills/nelson/scripts/nelson-phase.py advance --mission-dir {mission-dir}
```

## 3. Draft Battle Plan

When The Estimate has been conducted, the Battle Plan inherits the analytical work: terrain, forces, coordination, and control are already decided. The Battle Plan step is operational — it turns approved effects into task assignments. When the Estimate was skipped, the admiral performs the analysis inline at this step.

**Scope preservation:** When the Sailing Orders describe extending, expanding, or modifying an existing feature, every task must modify the existing implementation — not create a parallel or replacement implementation. Populate the `Modification targets` field in each task's brief with the specific functions, env vars, and config identified during Reconnaissance. A task that creates new files, functions, or environment variables where modification of existing ones would satisfy the effect is a planning error.

- Translate each effect from the Estimate (§3) into one or more tasks. Each task must stay within the scope of its parent effect — do not introduce work that the effect does not call for. When the Estimate was skipped, derive tasks directly from the Sailing Orders.
- Prepend the commander's intent paragraph (Estimate §2) to every captain's brief so each ship sails under a shared understanding of purpose.
- Inherit acceptance criteria from the parent effect onto each task. Captains own the choice of verification method per criterion.
- Inherit terrain (file ownership), coordination (dependencies), forces (captain sizing, model class), and control (action-station tier) from the Estimate. When the Estimate was skipped, supply these at this step.
- If cost-savings is a priority, also consider task inputs — avoid multiple agents independently loading the same large inputs into their contexts.
- For each task, note expected crew composition using the crew-or-direct decision tree in `references/crew-roles.md`. If crew are mustered, list crew roles with sub-tasks and sequence. If the captain implements directly (0 crew), note "Captain implements directly." If the captain anticipates needing marine support, note marine capacity (max 2).
- For each task, consciously mark `admiralty-action-required: yes` or `no`.
- Keep one task in progress per agent unless the mission explicitly requires multitasking.

Reference `references/admiralty-templates/battle-plan.md` for the schema of each captain's brief and `references/admiralty-templates/ship-manifest.md` for the ship manifest.

**Workflow Suitability Check:** If the mission has large fan-out, repeatable orchestration, codebase-wide analysis, broad migrations, audits, or cross-checking needs, you MUST read `references/workflow-doctrine.md` and decide whether `workflow` or `hybrid-workflow` is appropriate. For workflow modes, add a compact Workflow Charter to the battle plan with execution primitive, suitability, phases, human gates, verification contract, cost guardrail, and fallback mode. For non-workflow modes, include one line: `Workflow suitability: not selected because ...`. Station 2/3 workflow work should default to `hybrid-workflow` because human approval belongs between separate workflow runs, not inside one arbitrary mid-run pause.

**Battle Plan Gate — Standing Order Check:** You MUST NOT finalize task assignments until each question below is answered in writing and any triggered standing order remedy has been applied. Show your reasoning — a bare yes/no is not sufficient.
- `becalmed-fleet.md`: Should this mission use single-session instead of multi-agent? If yes, skip Step 4 — single-session has no squadron to form.
- `light-squadron.md`: Is the task count equal to the number of independent work units, or have tasks been under-split?
- `split-keel.md`: Does each task have exclusive file ownership with no conflicts? (This will be automatically verified in Step 4).
- `unclassified-engagement.md`: Does every task have a risk tier?
- `all-hands-on-deck.md`: Has each task been crewed only with roles its work actually demands?
- `skeleton-crew.md`: Would any task deploy exactly one crew member for an atomic task the captain should handle directly?
- `crew-without-canvas.md`: Is every agent justified by actual task scope?
- `captain-at-the-capstan.md`: For each task with crew, is the captain's role coordination, not implementation?
- `press-ganged-navigator.md`: Is the red-cell navigator being assigned implementation work?
- `admiral-at-the-helm.md`: Does the battle plan assign any implementation work (excluding permitted read-only recombination) to the admiral?
- `wrong-ensign.md`: Do the planned coordination tools match the selected execution mode?
- `pulling-the-oar.md`: For tasks that involve dispatched subagents, is the failure-recovery plan to fix the brief and re-dispatch, rather than absorb the work into senior context?

If any answer triggers a standing order, you MUST apply the corrective action and re-answer the question before proceeding. For situations not covered by this gate, consult the Standing Orders table below.

**Persist the drafted plan.** Before proceeding to Step 4, write the complete battle plan to `{mission-dir}/battle-plan.md` using the template at `references/admiralty-templates/battle-plan.md`. Include the commander's intent verbatim from Estimate §2, each task brief in template form, and the Standing Order Check answers. **This is a safe compaction point — admiral state is now fully on disk.**

**Structured Data Capture:** Task registration requires owners, which are assigned in Step 4. No `nelson-data.py` script calls at this step.

## 4. Form the Squadron

- Select execution mode per `references/squadron-composition.md`. If the user explicitly requested a mode, use it — user preference overrides the decision matrix.
    - `single-session`: sequential tasks, low complexity, or heavy same-file editing.
    - `subagents`: parallel, fully independent tasks that report only to the admiral.
    - `agent-team`: captains benefit from a shared task list, peer messaging, or coordinated deliverables; or 4+ captains are needed.
    - `workflow`: one autonomous dynamic workflow run for large fan-out, repeatable review, broad migration, audit, or cross-checked research.
    - `hybrid-workflow`: Nelson-gated sequence of workflow stages with human approval between stages.

**Mode-Tool Consistency Gate:** Before assigning ships, confirm your tool usage matches the selected mode by reviewing `references/tool-mapping.md`:
- **`subagents` mode:** Captains do NOT use `TaskCreate`, `TaskList`, `TaskGet`, `TaskUpdate`, or `SendMessage(type="message")`. Captains report via the `Agent` tool return value only. The admiral uses `TaskCreate`/`TaskUpdate`/`TaskList` to track progress in the session task list (visibility only — captains cannot see these tasks).
- **`agent-team` mode:** Do NOT use `Agent` with `subagent_type` to spawn captains (marines still use `subagent_type`). Use `TeamCreate` first, then `Agent` with `team_name` + `name`. Coordinate via `TaskList` and `SendMessage`.
- **`single-session` mode:** The admiral uses `TaskCreate`, `TaskUpdate`, `TaskList`, and `TaskGet` to track progress as it completes each task sequentially.
- **`workflow` mode:** Treat the workflow as a fleet asset, not ordinary captains. Nelson v1 produces a Workflow Charter/prompt and telemetry plan; it does not directly invoke a workflow API or generate runnable `.claude/workflows/*.js`.
- **`hybrid-workflow` mode:** Treat each workflow stage as a separate fleet asset. Stop at the planned gate, present results, and launch the next workflow run only after explicit approval.

**Task List Visibility:** After selecting the execution mode, create a `TaskCreate` entry for each battle plan task to make mission progress visible in the Claude Code task list (Ctrl+T). This applies in **all execution modes** — it is admiral-level visibility tracking, not inter-agent coordination. In `workflow` and `hybrid-workflow`, also create visibility entries for workflow phases or gates when they are the operational units being tracked.

For each task:
- `subject`: Task name from the battle plan (imperative form, e.g., "Refactor auth module")
- `description`: One-line deliverable
- `activeForm`: Present-continuous form shown in the UI spinner (e.g., "Refactoring auth module")

All tasks start as `pending`. They will be updated with owners and status as the mission progresses. In `single-session` mode (where Step 4 is otherwise skipped), the admiral still creates these entries before proceeding to Step 5.

- Assign each task a captain and a ship name from `references/crew-roles.md` matching task weight (frigate for general, destroyer for high-risk, patrol vessel for small, flagship for critical-path, submarine for research).
- Finalize ship manifests: confirm crew roles per task, or note "Captain implements directly."
- Add `1 red-cell navigator` for medium/high threat work. Do not exceed 10 squadron-level agents (admiral, captains, red-cell navigator). Crew are additional.
- If the sailing orders express cost-savings priority, load `references/model-selection.md` before assigning models. Apply weight-based model selection to all `Agent` tool calls and include haiku briefing enhancements for agents assigned to haiku.

```
SQUADRON FORMATION ORDERS

Mode: [single-session | subagents | agent-team | workflow | hybrid-workflow]
Captain count: [N]

Ships:
  [Ship name] — [vessel type] — [one-line task summary]
    Crew: [roles, or "Captain implements directly"]
  [repeat for each ship]

[Red-cell navigator — HMS X, if present]
```

For `workflow` and `hybrid-workflow`, include:

```
WORKFLOW CHARTER
Execution primitive: [workflow | hybrid-workflow]
Suitability: [why dynamic workflow orchestration is justified]
Phases: [probe / full run / stage names]
Human gates: [approval points, especially for hybrid-workflow]
Verification contract: [how accepted, rejected, and uncertain findings are handled]
Cost guardrail: [Sounding-the-Channel probe, scope cap, token/time stop]
Fallback mode: [agent-team | single-session]
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

Do not spawn any agents, create any tasks, or launch any `workflow` / `hybrid-workflow` run until the user approves. If the user requests changes, revise and redisplay before proceeding.

> **Note:** For headless and CI invocation, use `nelson-data.py headless --auto-approve` which combines Steps 1-3 and skips the interactive approval gate. See `references/structured-data.md` for details.

**Structured Data Capture:** Once formation is approved, use the composite `form` command (recommended) or the individual commands below.

**Recommended — composite `form` command:** Write a plan JSON file with the task and squadron definitions, then run a single command:

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py form \
  --mission-dir {mission-dir} \
  --plan {mission-dir}/plan-input.json \
  --mode [mode]
```

This registers all tasks, records the squadron, computes DAG metrics, and runs the conflict scan in one step. See `references/structured-data.md` for the plan JSON schema and output format.

**Alternative — individual commands:**
1. `python3 .claude/skills/nelson/scripts/nelson-data.py task --mission-dir {mission-dir} --id N --name "..." --owner "..." ...` for each task (owners are now known from formation). See `references/structured-data.md` for task arguments.
2. `python3 .claude/skills/nelson/scripts/nelson-data.py plan-approved --mission-dir {mission-dir}` to finalise the battle plan and compute DAG metrics.
3. `python3 .claude/skills/nelson/scripts/nelson-phase.py advance --mission-dir {mission-dir}` to advance from BATTLE_PLAN to FORMATION (validates all tasks have station tiers).
4. `python3 .claude/skills/nelson/scripts/nelson-data.py squadron --mission-dir {mission-dir} --admiral "..." --admiral-model [model] --captain "name:class:model:task_id" ... --mode [mode]` to record squadron composition. Repeat `--captain` for each captain. See `references/structured-data.md` for the full argument list.
5. `python3 .claude/skills/nelson/scripts/nelson_conflict_scan.py --plan {mission-dir}/battle-plan.json` to verify there are no file ownership conflicts. If conflicts are found, you MUST resolve them and update the battle plan before proceeding.
6. `python3 .claude/skills/nelson/scripts/nelson-phase.py advance --mission-dir {mission-dir}` to advance from FORMATION to PERMISSION.

**Before proceeding to Step 5:** Verify that sailing orders exist, all tasks have owners and deliverables, and every task has an action station tier.

**Crew Briefing:** Spawning and task assignment are two steps. First, spawn each captain with the `Agent` tool, including a crew briefing from `references/admiralty-templates/crew-briefing.md` in their prompt. Then assign work to the existing task entries with `TaskUpdate`. Teammates do NOT inherit the lead's conversation context — they start with a clean slate and need explicit mission context. See `references/tool-mapping.md` for full parameter details by mode.

**Task Status Updates:** After formation, update the task list entries created earlier in this step:
- **`agent-team` mode:** Use `TaskUpdate` to set `owner` to each captain's name and `status` to `in_progress` as captains are spawned. The team's shared task list now serves both visibility and coordination.
- **`subagents` mode:** Use `TaskUpdate` to set `status` to `in_progress` as each captain is dispatched. The admiral tracks these directly.
- **`single-session` mode:** Use `TaskUpdate` to set `status` to `in_progress` as the admiral begins each task.
- **`workflow` mode:** Use `TaskUpdate` to mark the workflow run or phase as `in_progress`, and log `workflow_run_started`.
- **`hybrid-workflow` mode:** Use `TaskUpdate` to mark only the currently approved workflow stage as `in_progress`; later stages remain `pending` until their human gate is passed.

**Edit permissions:** When spawning any agent whose task involves editing files, set `mode: "acceptEdits"` on the `Agent` tool call. Omitting this can cause a permission race condition that silently stalls the agent at its first edit. When in doubt, include it.

**Turnover Briefs:** When a ship is relieved due to context exhaustion, it writes a typed handoff packet using `python3 .claude/skills/nelson/scripts/nelson-data.py handoff ...` (see `references/structured-data.md`). An optional prose companion brief may also be written using `references/admiralty-templates/turnover-brief.md`. See `references/damage-control/relief-on-station.md` for the full procedure.

## 5. Get Permission to Sail

**Display and Permission Gate:**
1. Display the complete battle plan to the user if `becalmed-fleet.md` is in effect.
2. Display the complete squadron formation to the user if `becalmed-fleet.md` is not in effect. The battle plan (drafted in Step 3) should also be available for review.
3. If `workflow` or `hybrid-workflow` is selected, display the Workflow Charter, verification contract, cost guardrail, fallback mode, and next human gate.
4. You are REQUIRED to wait for explicit permission to proceed. Workflow and hybrid-workflow modes require explicit approval before every launch; for `hybrid-workflow`, repeat this gate between stages.

**Phase Advance:** After the user grants permission, log the event and advance:

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py event \
  --mission-dir {mission-dir} --type permission_granted --checkpoint 0
python3 .claude/skills/nelson/scripts/nelson-phase.py advance --mission-dir {mission-dir}
```

This transitions the mission from PERMISSION to UNDERWAY, unlocking agent spawning and task creation.

## 6. Run Quarterdeck Rhythm

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
    - For `workflow` and `hybrid-workflow`, record workflow telemetry when available: phase, agents complete/total, token burn, elapsed time, failed agents, accepted findings, rejected findings, uncertain findings, and next gate. Use `workflow_probe_completed`, `workflow_run_completed`, or `workflow_run_stopped` events as appropriate.
    - Check hull integrity: collect damage reports from all ships, update the squadron readiness board, and take action per `references/damage-control/hull-integrity.md`. The admiral must also check its own hull integrity at each checkpoint. **Every ship must file a damage report at every checkpoint** to `{mission-dir}/damage-reports/{ship-name}.json` using the schema in `references/admiralty-templates/damage-report.md` — do not skip this when hull is Green.
    - Standing order scan: For each order below, ask "Has this situation arisen since the last checkpoint?" If yes, apply the corrective action now — do not defer.
        - `admiral-at-the-helm.md`: Has the admiral drifted into implementation work (excluding permitted read-only recombination)?
        - `drifting-anchorage.md`: Has any task scope crept beyond the sailing orders? Has any captain created a parallel implementation, duplicate function, or new environment variable instead of extending existing code?
        - `captain-at-the-capstan.md`: Has any captain started implementing instead of coordinating crew?
        - `pressed-crew.md`: Has any crew member been assigned work outside their role?
        - `press-ganged-navigator.md`: Has the red-cell navigator been assigned implementation work?
        - `all-hands-on-deck.md`: Has any ship mustered crew roles that are idle or unjustified?
        - `battalion-ashore.md`: Has any captain deployed marines for crew work or sustained tasks?
        - `wrong-ensign.md`: Is the admiral or any captain using tools from the wrong execution mode?
        - `pulling-the-oar.md`: Has any senior agent (admiral or captain) absorbed work from a failed subagent dispatch instead of fixing the brief and re-dispatching?
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

## 7. Set Action Stations

- You MUST read and apply station tiers from `references/action-stations.md`.
- Require verification evidence before marking tasks complete:
    - Test or validation output.
    - Failure modes and rollback notes.
    - Red-cell review for medium+ station tiers.
- For `workflow` and `hybrid-workflow`, require the battle plan's verification contract before accepting workflow outputs. Accepted findings need the promised evidence, rejected or uncertain findings must be surfaced separately, and Station 2+ outputs still require adversarial review or human confirmation per `references/action-stations.md`.
- Trigger quality checks on:
    - Task completion.
    - Agent idle with unverified outputs.
    - Before final synthesis.
- For crewed tasks, verify crew outputs align with role boundaries (consult `references/crew-roles.md` and the Standing Orders table below if role violations are detected).
- Marine deployments follow station-tier rules in `references/royal-marines.md`. Station 2+ marine deployments require admiral approval. Captains use `references/admiralty-templates/marine-deployment-brief.md` when deploying a marine.

Reference `references/admiralty-templates/red-cell-review.md` for the red-cell review template. Consult the Standing Orders table below if tasks lack a tier or red-cell is assigned implementation work.

## 8. Stand Down And Log Action

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

**Mission Complete Gate:** You MUST NOT declare the mission complete until `{mission-dir}/captains-log.md` exists on disk and has been confirmed readable. If context pressure is high, write a minimal log noting which sections were abbreviated — but the file must exist. Skipping Step 8 is never permitted.

**Clear the Standing Goal:** If a `/goal` is active, its evaluator only sees this conversation — so state the completion evidence in chat for the goal to auto-clear: the success metric result (matching the sailing orders' metric), that `captains-log.md` was written (with its path), and that stand-down was recorded. Do NOT tell the user to run `/goal clear` on a successful mission — the goal clears itself once this evidence is visible. Only if the mission was abandoned: run `scuttle-and-reform`, state the blocking reason in chat, and log a `goal_cleared` event via `nelson-data.py event`. See `references/goal-alignment.md`.

**GitHub Star Prompt (one-time, success only):** After the Mission Complete Gate passes, ask the user once whether they would like to star the Nelson repo (canonical slug `harrymunro/nelson`). Run all three preflight checks below; if any prints `SKIP`, skip the prompt silently and finish Stand Down.

```bash
gh auth status &>/dev/null && echo "GH_OK" || echo "SKIP_NO_GH"
python3 - <<'PY'
import json, os
path = os.path.expanduser('~/.nelson/prefs.json')
prefs = {}
if os.path.exists(path):
    try:
        with open(path, encoding='utf-8') as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            prefs = loaded
    except Exception:
        prefs = {}
print("SKIP_ALREADY_ASKED" if prefs.get('star_asked') is True else "PREFS_OK")
PY
python3 - <<'PY'
import json, os, sys
mission_dir = os.environ.get('MISSION_DIR', '{mission-dir}')
sd_path = os.path.join(mission_dir, 'stand-down.json')
try:
    with open(sd_path, encoding='utf-8') as f:
        sd = json.load(f)
    print("OUTCOME_OK" if sd.get('outcome_achieved') is True else "SKIP_OUTCOME_NOT_ACHIEVED")
except Exception:
    print("SKIP_NO_STAND_DOWN")
PY
```

Substitute `{mission-dir}` with the actual mission directory path (or export `MISSION_DIR` first). If all three lines are `GH_OK`, `PREFS_OK`, `OUTCOME_OK`, invoke `AskUserQuestion` with:

- **Question:** "Nelson helped finish that mission. Would you star the repo on GitHub?"
- **Star Nelson** — "Helps the project grow."
- **Maybe later** — "Skip for now (won't ask again)."

On **Star Nelson**, run `gh api -X PUT /user/starred/harrymunro/nelson` (idempotent — returns 204 whether or not the repo is already starred). If the call fails, print `Couldn't reach GitHub — try 'gh api -X PUT /user/starred/harrymunro/nelson' manually.` and continue. Never let this step block Stand Down.

On any answer (including a custom "Other" response), set `star_asked: true` in `~/.nelson/prefs.json`, preserving any existing keys:

```bash
python3 - <<'PY'
import json, os
path = os.path.expanduser('~/.nelson/prefs.json')
os.makedirs(os.path.dirname(path), exist_ok=True)
try:
    with open(path, encoding='utf-8') as f:
        prefs = json.load(f)
    if not isinstance(prefs, dict):
        prefs = {}
except Exception:
    prefs = {}
prefs['star_asked'] = True
with open(path, 'w', encoding='utf-8') as f:
    json.dump(prefs, f, indent=2)
    f.write('\n')
PY
```

This is a single ask per user across all Nelson projects. Either answer locks the prompt forever.

## Standing Orders

Consult the specific standing order that matches the situation. The library is empirically extensible: see `scripts/nelson_data_patterns.py` for the promotion workflow that mines new candidate orders from mission patterns and surfaces them for human review.

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
| Senior absorbing failed subagent's work instead of fixing the brief | `references/standing-orders/pulling-the-oar.md` |

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
| Automated budget, hull, and idle alarms crossing thresholds | `references/damage-control/circuit-breakers.md` |
| Preparing the mission directory at session start | `references/damage-control/session-hygiene.md` |
| Agent team communication failure (lost agent IDs, message bus down) | `references/damage-control/comms-failure.md` |

## Admiralty Doctrine

- Include this instruction in any admiral's compaction summary: Re-read the quarterdeck report at the mission directory path to recover `{mission-dir}`. If the path is unknown, read `.nelson/.active-{SESSION_ID}` if you know the SESSION_ID, otherwise list `.nelson/missions/` and present the options to the user for selection. Then re-read `references/standing-orders/admiral-at-the-helm.md` to confirm you are in coordination role.
- Treat `/compact` as safe at any phase boundary (after Step 1, 2, 3, 4, and at every quarterdeck checkpoint in Step 6). The narrow unsafe window is inside Step 5 — between user approval and the admiral's `permission_granted` / phase advance / agent spawn turn.
- Optimize for mission throughput, not equal work distribution.
- Prefer replacing stalled agents over waiting on undefined blockers.
- Recognise strong performance; motivation compounds across missions.
- Keep coordination messages targeted and concise.
- Escalate uncertainty early with options and one recommendation.
