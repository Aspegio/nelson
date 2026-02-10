---
name: nelson
description: Coordinate complex coding missions with Codex subagents using a Royal Navy-style workflow (sailing orders, squadron formation, battle plan, quarterdeck checkpoints, action-station risk tiers, and a final captain's log). Use when work can be parallelized across files/modules, needs explicit ownership/dependencies, and requires verification evidence and rollback notes.
---

# Nelson

Execute this workflow for the user's mission.

## 1. Issue Sailing Orders

- Write one sentence for `outcome`, `metric`, and `deadline`.
- Set constraints: time budget, verification bar, compliance rules, and forbidden actions.
- Define scope: in-scope paths/modules and out-of-scope items.
- Define stop criteria and required handoff artifacts.

Use `references/admiralty-templates.md` when the user does not provide structure.

## 2. Form The Squadron (Codex)

- Select one mode:
- `single-session`: Sequential tasks, tight coupling, or heavy same-file editing.
- `subagents`: Parallel tasks using `functions.spawn_agent`. All coordination flows through the admiral.
- Set team size from mission complexity:
- Default to `1 admiral + 3-6 captains`.
- Add `1 red-cell navigator` for Station 1+ work or when assumptions are shaky.
- Do not exceed 10 squadron-level agents (admiral, captains, red-cell navigator). Crew are additional.
- Assign each captain a ship name from `references/crew-roles.md` matching task weight.
- Captain decides crew composition per ship using the crew-or-direct decision tree in `references/crew-roles.md`.

Subagent mapping:
- Use `agent_type: explorer` for read-only roles (NO, COX, red-cell navigator).
- Use `agent_type: worker` for implementation/testing roles (PWO, MEO, WEO, LOGO, XO).
- When spawning 3+ agents, prefer one `multi_tool_use.parallel` call.

Fleet comms (Codex approximation of agent-team):
- If mode is `subagents` and you spawn 2+ agents, Fleet Comms is mandatory. Set it up in the target repo per `references/fleet-comms.md` before spawning.
- Use `references/admiralty-templates/signal.md` for cross-ship signals.

Use `references/squadron-composition.md` for selection rules.
Use `references/crew-roles.md` for ship naming and crew composition.
Consult `references/standing-orders.md` before forming the squadron.

## 3. Draft Battle Plan

- Split mission into independent tasks with clear deliverables.
- Assign owner for each task and explicit dependencies.
- Assign file ownership when implementation touches code.
- Avoid two agents editing the same file concurrently. If unavoidable, schedule turns and an integration checkpoint.
- For each captain's task, include a ship manifest:
- If crew are mustered, list crew roles with scoped sub-tasks and order of execution.
- If the captain implements directly (0 crew), note "Captain implements directly."

Use `references/admiralty-templates.md` for the battle plan and ship manifest templates.
Consult `references/standing-orders.md` when assigning files or if scope is unclear.

## 4. Run Quarterdeck Rhythm

- Keep admiral focused on coordination and unblock actions.
- Run checkpoints at fixed cadence (for example every 15-30 minutes or after each major deliverable):
- Update progress by task state: `pending`, `in_progress`, `completed`.
- Identify blockers and choose a concrete next action.
- Reconcile dependencies and merge points.
- Track burn against time budget.
- When a mission encounters difficulties, consult `references/damage-control.md` for recovery and escalation procedures.

Codex comms:
- Use `functions.send_input` for targeted check-ins and course corrections.
- Use `functions.wait` to collect results and prevent idle agents.
- When Fleet Comms is enabled, route decisions and cross-ship signals via `.nelson/comms/` and send agents pointers to their inbox files instead of pasting long messages.

Use `references/admiralty-templates.md` for the quarterdeck report template.
Consult `references/standing-orders.md` if admiral is doing implementation or tasks are drifting from scope.

## 5. Set Action Stations

- Apply station tier from `references/action-stations.md` before execution.
- Require verification evidence before marking tasks complete:
- Test or validation output (or explicit reasoning if tests are unavailable).
- Failure modes and rollback notes (Station 1+).
- Red-cell review for Station 2+.
- Trigger quality checks on:
- Task completion.
- Agent idle with unverified outputs.
- Before final synthesis.
- For crewed tasks, verify crew outputs align with role boundaries (consult `references/crew-roles.md` and `references/standing-orders.md` if role violations are detected).

Consult `references/standing-orders.md` if tasks lack a tier or red-cell is assigned implementation work.

## 6. Stand Down And Log Action

- Close out all subagents once their deliverables are integrated (`functions.close_agent`).
- Produce captain's log:
- Decisions and rationale.
- Diffs or artifacts.
- Validation evidence.
- Open risks and follow-ups.
- Record reusable patterns and failure modes for future missions.

Use `references/admiralty-templates.md` for the captain's log template.

## Admiralty Doctrine

- Optimize for mission throughput, not equal work distribution.
- Prefer replacing stalled agents over waiting on undefined blockers.
- Keep coordination messages targeted and concise.
- Escalate uncertainty early with options and one recommendation.
