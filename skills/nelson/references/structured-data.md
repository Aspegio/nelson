# Structured Data Capture

Reference for the `nelson-data.py` script. Run these commands via Bash at each workflow step to write machine-readable JSON alongside prose artifacts.

The script lives at `scripts/nelson-data.py` relative to the skill directory. All subcommands handle schema validation, timestamps, and file I/O. Only stdout is consumed — the script source is never loaded into context.

## Script Commands

### `init` — Create mission and sailing orders

Run at Step 1 after sailing orders are agreed.

`init` owns the mission-directory contract end-to-end. It generates (or accepts via `--session-id`) an 8-character hex SESSION_ID, creates `.nelson/missions/{YYYY-MM-DD_HHMMSS}_{SESSION_ID}/` with the `damage-reports/` and `turnover-briefs/` subdirectories, writes `sailing-orders.json`, `mission-log.json`, and `fleet-status.json` (initial phase `SAILING_ORDERS`), and writes `.nelson/.active-{SESSION_ID}` as the session marker consumed by recovery/hooks. The mission directory path is printed to stdout; the SESSION_ID is the segment after the last underscore in the directory name.

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py init \
  --outcome "Refactor auth module to use JWT tokens" \
  --metric "All 47 auth tests pass, no new dependencies" \
  --deadline "this_session" \
  --token-budget 200000
```

Optional: pass `--session-id <8-hex>` to use a specific session identifier (e.g., for deterministic tests or when resuming with a known id). Must be exactly 8 lowercase hex characters; invalid values are rejected.

### `squadron` — Record squadron formation

Run at Step 3 after the squadron is formed.

Updates `battle-plan.json` with the squadron section. Appends `squadron_formed` event to `mission-log.json`. Writes initial `fleet-status.json`.

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py squadron \
  --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 \
  --admiral "HMS Victory" --admiral-model opus \
  --captain "HMS Argyll:frigate:sonnet:1" \
  --captain "HMS Kent:destroyer:sonnet:2" \
  --red-cell "HMS Astute" --red-cell-model haiku \
  --mode agent-team
```

Repeat `--captain "name:class:model:task_id"` for each captain. Fields are colon-delimited.

### `task` — Add task to battle plan

Run at Step 3 once per task, after owners are assigned during squadron formation.

Appends task to `battle-plan.json`.

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py task \
  --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 \
  --id 1 --name "Auth module refactor" --owner "HMS Argyll" \
  --deliverable "Refactored auth module with JWT support" \
  --deps "" --station-tier 1 \
  --files "src/auth/**"
```

### `plan-approved` — Finalize battle plan

Run at Step 3 after all tasks are added, before the `squadron` call.

Computes `parallel_tracks` and `critical_path_length` from the dependency graph. Appends `battle_plan_approved` event to `mission-log.json`. Updates `fleet-status.json`.

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py plan-approved \
  --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4
```

### `event` — Log a mission event

Run at Step 4 between checkpoints for state changes.

Appends an event to `mission-log.json`. Accepts type-specific key-value pairs validated by the script.

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py event \
  --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 \
  --type task_completed \
  --checkpoint 2 \
  --task-id 1 --task-name "Auth module refactor" --owner "HMS Argyll" \
  --station-tier 1 --verification passed
```

### `handoff` — Write a typed handoff packet

Run at Step 5 when a ship is relieved due to context exhaustion, session resumption, or mid-mission resize.

Writes a schema-validated JSON handoff packet to `{mission-dir}/turnover-briefs/{ship-name}-{timestamp}.json`. Appends a `relief_on_station` event to `mission-log.json` with the packet path. This supersedes `event --type relief_on_station` as the preferred relief path.

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py handoff \
  --mission-dir .nelson/missions/2026-04-08_140000_a1b2c3d4 \
  --ship-name "HMS Argyll" \
  --task-id 3 --task-name "API endpoint implementation" \
  --handoff-type relief_on_station \
  --completed-subtask "Schema design" \
  --completed-subtask "GET endpoint" \
  --partial-output "POST endpoint:60%:Validation logic pending" \
  --file-ownership "src/api/endpoints.py" \
  --file-ownership "src/api/validators.py" \
  --next-step "Complete POST validation" \
  --next-step "Write integration tests" \
  --hull-at-handoff 38 --tokens-consumed 145000 \
  --key-finding "API rate limiting needs custom middleware" \
  --key-finding "Existing auth works with new endpoints" \
  --relief-entry "HMS Argyll:context_exhaustion:2026-04-08T14:30:00Z" \
  --incoming-ship "HMS Kent"
```

Repeatable arguments: `--completed-subtask`, `--partial-output` (format: `subtask:progress:notes`), `--known-blocker`, `--file-ownership`, `--next-step`, `--open-decision`, `--key-finding`, `--relief-entry` (format: `ship:reason:time`).

Validations:
- `--handoff-type` must be `relief_on_station`, `session_resumption`, or `mid_mission_resize`.
- At least one `--next-step` is required.
- `--relief-entry` is bounded to a maximum of 3 entries.
- `--file-ownership` is required when the task has `station_tier > 0` (looked up from `battle-plan.json`).

### `checkpoint` — Record a quarterdeck checkpoint

Run at Step 4 at each checkpoint, alongside the prose quarterdeck report.

Appends a `checkpoint` event to `mission-log.json`. Overwrites `fleet-status.json` with current state.

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py checkpoint \
  --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 \
  --pending 2 --in-progress 2 --completed 1 --blocked 0 \
  --tokens-spent 45000 --tokens-remaining 155000 \
  --hull-green 3 --hull-amber 1 --hull-red 0 --hull-critical 0 \
  --decision continue \
  --rationale "On track. HMS Kent approaching amber but no relief needed yet."
```

### `stand-down` — Record mission completion

Run at Step 6 alongside the prose captain's log.

Auto-computes duration, budget consumption, ship counts, relief counts, violation counts, and blocker statistics from `mission-log.json` and `battle-plan.json`. Writes `stand-down.json`. Appends `mission_complete` event. Writes final `fleet-status.json`.

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py stand-down \
  --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 \
  --outcome-achieved \
  --actual-outcome "Auth module refactored with JWT support, all tests passing" \
  --metric-result "47/47 auth tests pass, 0 new dependencies" \
  --adopt "Station tier 1 for schema migrations worked well" \
  --adopt "Dedicated destroyer for DB-heavy tasks" \
  --avoid "Assigning DB work to a frigate"
```

Repeat `--adopt` and `--avoid` for each pattern. These are optional — omitting them produces empty lists. After writing `stand-down.json`, the script automatically updates the cross-mission memory store (`.nelson/memory/patterns.json` and `.nelson/memory/standing-order-stats.json`).

### `form` — Composite formation (recommended)

Run at Step 3 instead of individual `task`, `squadron`, and `plan-approved` calls. Consolidates the entire formation phase into a single command.

Reads a plan JSON file containing tasks and squadron definitions. Registers all tasks, records the squadron, computes DAG metrics, and runs the conflict scan. Outputs a structured JSON summary to stdout; progress messages go to stderr.

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py form \
  --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 \
  --plan battle-plan-input.json \
  --mode subagents
```

The plan JSON file must contain `squadron` and `tasks` keys:

```json
{
  "squadron": {
    "admiral": { "ship_name": "HMS Victory", "model": "opus" },
    "captains": [
      { "ship_name": "HMS Argyll", "ship_class": "frigate", "model": "sonnet", "task_id": 1 }
    ],
    "red_cell": { "ship_name": "HMS Astute", "model": "haiku" }
  },
  "tasks": [
    {
      "id": 1,
      "name": "Auth module refactor",
      "owner": "HMS Argyll",
      "deliverable": "Refactored auth module with JWT support",
      "dependencies": [],
      "station_tier": 1,
      "file_ownership": ["src/auth/**"]
    }
  ]
}
```

Output summary (stdout):

```json
{
  "status": "ok",
  "mission_dir": ".nelson/missions/2026-03-27_120000_a1b2c3d4",
  "tasks_registered": 1,
  "squadron": { "admiral": "HMS Victory", "captains": 1, "mode": "subagents", "has_red_cell": true },
  "dag_metrics": { "parallel_tracks": 1, "critical_path_length": 1 },
  "conflict_scan": { "clean": true, "exit_code": 0, "stdout": "..." }
}
```

### `headless` — Headless mission (init + form)

Run to create a mission and complete formation in a single command. Reads sailing orders and battle plan from JSON files. Designed for CI/CD pipeline integration.

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py headless \
  --sailing-orders sailing-orders.json \
  --battle-plan battle-plan.json \
  --mode subagents \
  --auto-approve
```

The sailing orders JSON uses the same fields as `sailing-orders.json`:

```json
{
  "outcome": "Refactor auth module to use JWT tokens",
  "metric": "All 47 auth tests pass, no new dependencies",
  "deadline": "this_session",
  "budget": { "token_limit": 200000 },
  "constraints": ["Do not modify the public API surface"],
  "out_of_scope": ["Migration script for existing sessions"]
}
```

Outputs a combined JSON summary to stdout containing `mission_dir`, `sailing_orders`, and `formation` sections.

### `status` — Print current fleet status (read-only)

Run at any time for a quick status check. Useful for session resumption, hooks, and dynamic context injection. Auto-invoked by SKILL.md's `!` block on skill activation.

Reads `fleet-status.json` and `mission-log.json` to produce a compact briefing with per-ship status and elapsed time. Silent no-op if no mission data exists. The `--mission-dir` argument is optional — omitting it is a silent no-op.

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py status \
  --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4
```

Example output:

```
NELSON FLEET STATUS
Mission: 2026-04-08_201214_a1b2c3d4 (underway)
Progress: 3/5 tasks complete | 1 blocked
Ships: HMS Argyll (Green 82%) | HMS Kent (Amber 65%) | HMS Daring (completed)
Last checkpoint: 2 (12 min ago)
Budget: 45% consumed
```

### `recover` — Auto-recover session state (read-only)

Run at session resumption to auto-discover the active mission and build a structured recovery briefing.

Reads `fleet-status.json`, `battle-plan.json`, and any `.json` handoff packets in `turnover-briefs/`. Outputs a structured recovery briefing to stdout. No files are written.

```bash
# Auto-discover active mission
python3 .claude/skills/nelson/scripts/nelson-data.py recover \
  --missions-dir .nelson/missions

# Target a specific mission
python3 .claude/skills/nelson/scripts/nelson-data.py recover \
  --mission-dir .nelson/missions/2026-04-08_140000_a1b2c3d4

# Human-readable output
python3 .claude/skills/nelson/scripts/nelson-data.py recover \
  --mission-dir .nelson/missions/2026-04-08_140000_a1b2c3d4 \
  --format text
```

Auto-discovery checks `.nelson/.active-*` files first, then falls back to the most recent mission directory without a `stand-down.json`.

Output (JSON):

```json
{
  "mission_dir": ".nelson/missions/2026-04-08_140000_a1b2c3d4",
  "mission_status": "underway",
  "fleet_status": { "..." },
  "handoff_packets": [ { "..." } ],
  "pending_tasks": [ { "task_id": 3, "task_name": "...", "owner": "...", "status": "..." } ],
  "recommended_actions": ["Resume task 3 from handoff packet (HMS Argyll)"]
}
```

### `brief` — Mission intelligence brief (read-only)

Run before Step 1 to surface relevant patterns from past missions.

Reads `fleet-intelligence.json`, `.nelson/memory/patterns.json`, and `.nelson/memory/standing-order-stats.json`. Outputs a compact brief suitable for context injection. Use `--context` to surface precedents from similar past missions.

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py brief \
  --missions-dir .nelson/missions \
  --context "auth module refactor"
```

Add `--json` for machine-readable output.

### `analytics` — Cross-mission analytics (read-only)

Run at any time for focused metric analysis across completed missions.

Reads `fleet-intelligence.json` and `.nelson/memory/standing-order-stats.json`. Supports four metrics:

- `success-rate` — Win rate, trend, outcome by fleet size
- `standing-orders` — Violation frequency, top offenders, failure correlation
- `efficiency` — Tokens per task, duration per task, budget utilization
- `all` — All three analyses combined

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py analytics \
  --missions-dir .nelson/missions \
  --metric success-rate

python3 .claude/skills/nelson/scripts/nelson-data.py analytics \
  --missions-dir .nelson/missions \
  --metric all --json --last 10
```

## Phase Engine

The `nelson-phase.py` script manages the deterministic phase engine. It enforces phase transitions with defined entry/exit criteria and validates phase-appropriate tool usage via PreToolUse hooks.

Phases progress linearly: `SAILING_ORDERS` → `BATTLE_PLAN` → `FORMATION` → `PERMISSION` → `UNDERWAY` → `STAND_DOWN`.

### `current` — Print current phase

```bash
python3 .claude/skills/nelson/scripts/nelson-phase.py current \
  --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4
```

Auto-discovers active mission from `.nelson/.active-*` files if `--mission-dir` is omitted.

### `advance` — Advance to next phase

Validates exit criteria for the current phase before transitioning. Appends a `phase_transition` event to `mission-log.json`.

```bash
python3 .claude/skills/nelson/scripts/nelson-phase.py advance \
  --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4
```

### `validate-tool` — Check tool permission (for hooks)

Used by PreToolUse hooks to block phase-inappropriate tool usage. Exits 0 if allowed, 1 if blocked.

```bash
python3 .claude/skills/nelson/scripts/nelson-phase.py validate-tool \
  --tool Agent --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4
```

### `set` — Force-set phase (recovery)

Escape hatch for recovery scenarios. Skips exit criteria validation.

```bash
python3 .claude/skills/nelson/scripts/nelson-phase.py set \
  --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 --phase UNDERWAY
```

## Write Timing

| Workflow Step | Script Command | JSON Written | Prose (existing) |
|---|---|---|---|
| Step 1: Sailing Orders | `init` | `sailing-orders.json`, `mission-log.json` | (conversation-only) |
| Step 2: Battle Plan | (none — owners not yet assigned) | — | (conversation-only) |
| Step 3: Form Squadron | `form` (recommended), or individual `task` + `plan-approved` + `squadron` | `battle-plan.json`, `mission-log.json`, `fleet-status.json` | (conversation-only) |
| Step 1-3: Headless | `headless` (CI/CD) | all of the above in one step | — |
| Step 4: Get Permission to Sail | (none) | — | (conversation-only) |
| Step 5: Each Checkpoint | `checkpoint` | `mission-log.json`, `fleet-status.json` | `quarterdeck-report.md` |
| Step 5: Between Checkpoints | `event` | `mission-log.json` | -- |
| Step 5: Relief on Station | `handoff` | `mission-log.json`, `turnover-briefs/{ship}.json` | `turnover-briefs/{ship}.md` (optional companion) |
| Step 5: Action Stations | `event --type task_completed` | `mission-log.json` | -- |
| Step 6: Stand Down | `stand-down` | `mission-log.json`, `fleet-status.json`, `stand-down.json`, `.nelson/memory/patterns.json`, `.nelson/memory/standing-order-stats.json` | `captains-log.md` |
| Post-mission | `index` | `fleet-intelligence.json`, `.nelson/memory/patterns.json`, `.nelson/memory/standing-order-stats.json` | — |
| Pre-mission | `brief` | (read-only) | — |
| Any time | `analytics` | (read-only) | — |

## Event Types

| Event Type | Trigger | Key Data Fields |
|---|---|---|
| `squadron_formed` | Step 3 complete | captain_count, has_red_cell, execution_mode, standing_order_check |
| `battle_plan_approved` | Step 3 complete | task_count, parallel_tracks, critical_path_length, standing_order_check |
| `task_started` | Captain begins work | task_id, task_name, owner |
| `task_completed` | Task verified complete | task_id, task_name, owner, station_tier, verification |
| `checkpoint` | Each quarterdeck checkpoint | progress, budget, hull_summary, blockers, admiral_decision |
| `blocker_raised` | Blocker identified | description, owner, blocking_task_id, blocked_task_ids |
| `blocker_resolved` | Blocker cleared | description, resolution |
| `hull_threshold_crossed` | Ship crosses G/A/R/C boundary | ship_name, previous_status, new_status, hull_integrity_pct |
| `relief_on_station` | Ship relieved | outgoing_ship, incoming_ship, reason, time_on_station_minutes |
| `standing_order_violation` | Standing order triggered | order, description, corrective_action, severity |
| `commendation` | Signal flag or MID | ship_name, type, citation |
| `admiralty_action_required` | Task needs human input | task_id, action, timing |
| `admiralty_action_completed` | Human completed action | task_id, resolution |
| `battle_plan_amended` | Admiral rescopes | changes, rationale |
| `phase_transition` | Phase engine advances | from_phase, to_phase |
| `phase_override` | Manual phase set (recovery) | from_phase, to_phase |
| `permission_granted` | User approves formation | (empty data) |
| `mission_complete` | Step 6 | outcome_achieved, tasks_completed, total_tokens_consumed, duration_minutes |

## JSON Schemas

All artifacts are stored in `{mission-dir}/`.

### sailing-orders.json (Write-Once)

```json
{
  "version": 1,
  "outcome": "Refactor auth module to use JWT tokens",
  "success_metric": "All 47 auth tests pass, no new dependencies",
  "deadline": "this_session",
  "budget": {
    "token_limit": 200000,
    "time_limit_minutes": null
  },
  "constraints": ["Do not modify the public API surface"],
  "out_of_scope": ["Migration script for existing sessions"],
  "stop_criteria": ["All tests pass", "No regressions in integration suite"],
  "handoff_artifacts": ["Updated auth module", "Test results"],
  "created_at": "2026-03-27T12:00:00Z"
}
```

### battle-plan.json (Write-Once, Amendable)

```json
{
  "version": 1,
  "squadron": {
    "mode": "subagents",
    "admiral": { "ship_name": "HMS Victory", "model": "opus" },
    "captains": [
      {
        "ship_name": "HMS Argyll",
        "ship_class": "frigate",
        "model": "sonnet",
        "task_id": 1,
        "crew": [
          { "role": "PWO", "sub_task": "Core endpoint development" }
        ],
        "marine_capacity": 2,
        "estimated_token_budget": 50000
      }
    ],
    "red_cell": { "ship_name": "HMS Astute", "model": "haiku" }
  },
  "tasks": [
    {
      "id": 1,
      "name": "Auth module refactor",
      "owner": "HMS Argyll",
      "deliverable": "Refactored auth module with JWT support",
      "dependencies": [],
      "dependents": [4],
      "station_tier": 1,
      "file_ownership": ["src/auth/**"],
      "validation_required": "Unit tests pass, no API surface change",
      "rollback_note_required": true,
      "admiralty_action_required": false
    }
  ],
  "admiralty_actions": [
    {
      "task_id": 3,
      "action": "Approve database schema before migration begins",
      "timing": "before_task_starts",
      "unblocks": "Task 3: Database migration"
    }
  ],
  "created_at": "2026-03-27T12:05:00Z",
  "amended_at": null
}
```

### mission-log.json (Append-Only)

Array of events. Each event has `type`, `checkpoint`, `timestamp`, and type-specific `data`.

```json
{
  "version": 1,
  "events": [
    {
      "type": "checkpoint",
      "checkpoint": 1,
      "timestamp": "2026-03-27T12:20:00Z",
      "data": {
        "progress": { "pending": 2, "in_progress": 2, "completed": 1, "blocked": 0 },
        "budget": { "tokens_spent": 45000, "tokens_remaining": 155000, "pct_consumed": 22.5 },
        "hull_summary": { "green": 3, "amber": 1, "red": 0, "critical": 0 },
        "blockers": [],
        "standing_order_violations": [],
        "admiral_decision": "continue",
        "admiral_rationale": "On track."
      }
    },
    {
      "type": "task_completed",
      "checkpoint": 2,
      "timestamp": "2026-03-27T12:38:00Z",
      "data": {
        "task_id": 1,
        "task_name": "Auth module refactor",
        "owner": "HMS Argyll",
        "station_tier": 1,
        "verification": "passed"
      }
    }
  ]
}
```

### fleet-status.json (Overwritten Per Checkpoint)

Current-state snapshot for real-time consumers (hooks, dashboards).

```json
{
  "version": 1,
  "mission": {
    "outcome": "Refactor auth module to use JWT tokens",
    "status": "underway",
    "phase": "UNDERWAY",
    "started_at": "2026-03-27T12:00:00Z",
    "checkpoint_number": 2
  },
  "progress": { "pending": 1, "in_progress": 2, "completed": 2, "blocked": 0, "total": 5 },
  "budget": {
    "tokens_spent": 80000,
    "tokens_remaining": 120000,
    "pct_consumed": 40.0,
    "burn_rate_per_checkpoint": 15000
  },
  "squadron": [
    {
      "ship_name": "HMS Argyll",
      "ship_class": "frigate",
      "role": "captain",
      "hull_integrity_pct": 72,
      "hull_integrity_status": "Green",
      "task_id": 3,
      "task_name": "API endpoint tests",
      "task_status": "in_progress"
    }
  ],
  "blockers": [],
  "recent_events": ["Task 1 completed (HMS Argyll)", "HMS Kent hull crossed to Amber (68%)"],
  "last_updated": "2026-03-27T12:35:00Z"
}
```

### handoff-packet.json (Write-Once Per Relief)

Written to `{mission-dir}/turnover-briefs/{ship-name}-{timestamp}.json` by the `handoff` command.

```json
{
  "version": 1,
  "ship_name": "HMS Argyll",
  "task_id": 3,
  "task_name": "API endpoint implementation",
  "handoff_type": "relief_on_station",
  "state": {
    "completed_subtasks": ["Schema design", "GET endpoint"],
    "partial_outputs": [
      {"subtask": "POST endpoint", "progress": "60%", "notes": "Validation logic pending"}
    ],
    "known_blockers": [],
    "file_ownership": ["src/api/endpoints.py", "src/api/validators.py"],
    "next_steps": ["Complete POST validation", "Write integration tests"],
    "open_decisions": []
  },
  "context": {
    "hull_at_handoff": 38,
    "tokens_consumed": 145000,
    "checkpoint_number": 4,
    "key_findings": ["API rate limiting needs custom middleware", "Existing auth works with new endpoints"]
  },
  "relief_chain": [
    {"ship": "HMS Argyll", "reason": "context_exhaustion", "handoff_time": "2026-04-08T14:30:00Z"}
  ],
  "created_at": "2026-04-08T14:30:00Z"
}
```

### stand-down.json (Write-Once)

Auto-computed from `mission-log.json` and `battle-plan.json` by the `stand-down` command.

```json
{
  "version": 1,
  "outcome_achieved": true,
  "planned_outcome": "Refactor auth module to use JWT tokens",
  "actual_outcome": "Auth module refactored with JWT support, all tests passing",
  "success_metric_result": "47/47 auth tests pass, 0 new dependencies",
  "duration_minutes": 70,
  "budget": { "tokens_consumed": 120000, "tokens_budgeted": 200000, "pct_consumed": 60.0 },
  "fleet": { "ships_used": 4, "reliefs": 1, "max_concurrent_ships": 4 },
  "tasks": { "completed": 5, "total": 5, "by_station_tier": { "0": 1, "1": 3, "2": 1, "3": 0 } },
  "quality": {
    "standing_order_violations": 1,
    "blockers_raised": 1,
    "blockers_resolved": 1,
    "avg_blocker_duration_minutes": 14
  },
  "open_risks": [{ "risk": "JWT rotation not load-tested", "owner": "follow-up", "mitigation": "Add load test next sprint" }],
  "follow_ups": [{ "item": "Add JWT load testing", "owner": "team", "due": "next sprint" }],
  "mentioned_in_despatches": [{ "ship_name": "HMS Argyll", "contribution": "Fast, clean auth refactor" }],
  "reusable_patterns": {
    "adopt": ["Station tier 1 for schema migrations worked well"],
    "avoid": ["Assigning DB work to a frigate -- needed a destroyer"]
  },
  "created_at": "2026-03-27T13:10:00Z"
}
```

## Memory Store

Cross-mission data is stored in `.nelson/memory/`. This directory is created automatically by `stand-down` and `index`.

### patterns.json (Append-Only)

Accumulated pattern library from all completed missions. Updated automatically at stand-down.

```json
{
  "version": 1,
  "updated_at": "2026-04-08T14:30:00Z",
  "pattern_count": 5,
  "patterns": [
    {
      "mission_id": "2026-04-08_120000",
      "completed_at": "2026-04-08T14:30:00Z",
      "outcome_achieved": true,
      "planned_outcome": "Refactor auth module",
      "adopt": ["Station tier 1 for schema migrations worked well"],
      "avoid": ["Assigning DB work to a frigate"],
      "standing_order_violations": [
        {
          "order": "split-keel",
          "description": "File ownership overlap",
          "severity": "medium",
          "corrective_action": "Reassigned file ownership"
        }
      ],
      "damage_control_events": 1,
      "quality": {
        "violations": 1,
        "blockers_raised": 2,
        "blockers_resolved": 2,
        "task_completion_rate": 1.0
      }
    }
  ]
}
```

### standing-order-stats.json (Overwritten)

Aggregate violation statistics across all missions. Updated at stand-down and index.

```json
{
  "version": 1,
  "updated_at": "2026-04-08T14:30:00Z",
  "total_missions": 5,
  "total_violations": 3,
  "violations_per_mission": 0.6,
  "by_order": {
    "split-keel": { "count": 2, "missions": ["2026-04-08_120000", "2026-04-07_100000"] },
    "skeleton-crew": { "count": 1, "missions": ["2026-04-06_090000"] }
  },
  "correlation": {
    "missions_with_violations": 2,
    "failures_with_violations": 1,
    "successes_with_violations": 1
  }
}
```

## Error Handling

The script handles errors and prints clear messages to stderr:

- Missing `--mission-dir` -- prints error, exits 1.
- Invalid event type -- prints valid types, exits 1.
- Missing required field for event type -- prints required fields, exits 1.
- Corrupt JSON on disk -- backs up corrupt file, creates fresh.
- Missing directories -- creates them automatically.

## Script Output

All subcommands print a brief confirmation to stdout. Example:

```
[nelson-data] Checkpoint 2 recorded
Fleet: 3/5 done | Budget: 62% | Hull: 3G 1A 0R | Blockers: 0
```

This stdout line (~20 tokens) replaces a ~200-token JSON Write call. The full JSON is already on disk.

## Schema Coupling

The `_build_mission_record` and `_extract_fleet_details` functions in `nelson-data.py` depend on the JSON schemas defined above. If you rename or restructure fields in the schemas (e.g. `stand-down.json`, `battle-plan.json`, `sailing-orders.json`, `mission-log.json`), you must update those functions to match. `_compute_analytics` also depends on the field names produced by `_build_mission_record`. The memory store functions (`_extract_patterns_from_mission`, `_update_patterns_store`, `_update_standing_order_stats`, `_build_intelligence_brief`) depend on both the mission JSON schemas and the memory store schemas (`patterns.json`, `standing-order-stats.json`).
