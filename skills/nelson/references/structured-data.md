# Structured Data Capture

Reference for the `nelson-data.py` script. Run these commands via Bash at each workflow step to write machine-readable JSON alongside prose artifacts.

The script lives at `scripts/nelson-data.py` relative to the skill directory. All subcommands handle schema validation, timestamps, and file I/O. Only stdout is consumed — the script source is never loaded into context.

## Script Commands

### `init` — Create mission and sailing orders

Run at Step 1 after sailing orders are agreed.

Creates `sailing-orders.json` and empty `mission-log.json`. Prints the mission directory path to stdout.

```bash
python3 scripts/nelson-data.py init \
  --outcome "Refactor auth module to use JWT tokens" \
  --metric "All 47 auth tests pass, no new dependencies" \
  --deadline "this_session" \
  --token-budget 200000
```

### `squadron` — Record squadron formation

Run at Step 3 after the squadron is formed.

Updates `battle-plan.json` with the squadron section. Appends `squadron_formed` event to `mission-log.json`. Writes initial `fleet-status.json`.

```bash
python3 scripts/nelson-data.py squadron \
  --mission-dir .nelson/missions/2026-03-27_120000 \
  --admiral "HMS Victory" --admiral-model opus \
  --captain "HMS Argyll:frigate:sonnet:1" \
  --captain "HMS Kent:destroyer:sonnet:2" \
  --red-cell "HMS Astute" --red-cell-model haiku \
  --mode agent-team
```

Repeat `--captain "name:class:model:task_id"` for each captain. Fields are colon-delimited.

### `task` — Add task to battle plan

Run at Step 2 once per task.

Appends task to `battle-plan.json`.

```bash
python3 scripts/nelson-data.py task \
  --mission-dir .nelson/missions/2026-03-27_120000 \
  --id 1 --name "Auth module refactor" --owner "HMS Argyll" \
  --deliverable "Refactored auth module with JWT support" \
  --deps "" --station-tier 1 \
  --files "src/auth/**"
```

### `plan-approved` — Finalize battle plan

Run at Step 2 after all tasks are added.

Computes `parallel_tracks` and `critical_path_length` from the dependency graph. Appends `battle_plan_approved` event to `mission-log.json`. Updates `fleet-status.json`.

```bash
python3 scripts/nelson-data.py plan-approved \
  --mission-dir .nelson/missions/2026-03-27_120000
```

### `event` — Log a mission event

Run at Step 4 between checkpoints for state changes.

Appends an event to `mission-log.json`. Accepts type-specific key-value pairs validated by the script.

```bash
python3 scripts/nelson-data.py event \
  --mission-dir .nelson/missions/2026-03-27_120000 \
  --type task_completed \
  --checkpoint 2 \
  --task-id 1 --task-name "Auth module refactor" --owner "HMS Argyll" \
  --station-tier 1 --verification passed
```

### `checkpoint` — Record a quarterdeck checkpoint

Run at Step 4 at each checkpoint, alongside the prose quarterdeck report.

Appends a `checkpoint` event to `mission-log.json`. Overwrites `fleet-status.json` with current state.

```bash
python3 scripts/nelson-data.py checkpoint \
  --mission-dir .nelson/missions/2026-03-27_120000 \
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
python3 scripts/nelson-data.py stand-down \
  --mission-dir .nelson/missions/2026-03-27_120000 \
  --outcome-achieved \
  --actual-outcome "Auth module refactored with JWT support, all tests passing" \
  --metric-result "47/47 auth tests pass, 0 new dependencies"
```

### `status` — Print current fleet status (read-only)

Run at any time for a quick status check. Useful for session resumption and hooks.

Reads `fleet-status.json` and prints a compact summary. Silent no-op if no mission data exists.

```bash
python3 scripts/nelson-data.py status \
  --mission-dir .nelson/missions/2026-03-27_120000
```

## Write Timing

| Workflow Step | Script Command | JSON Written | Prose (existing) |
|---|---|---|---|
| Step 1: Sailing Orders | `init` | `sailing-orders.json`, `mission-log.json` | (conversation-only) |
| Step 2: Battle Plan | `task` (per task), then `plan-approved` | `battle-plan.json`, `mission-log.json`, `fleet-status.json` | (conversation-only) |
| Step 3: Form Squadron | `squadron` | `battle-plan.json`, `mission-log.json`, `fleet-status.json` | (conversation-only) |
| Step 4: Each Checkpoint | `checkpoint` | `mission-log.json`, `fleet-status.json` | `quarterdeck-report.md` |
| Step 4: Between Checkpoints | `event` | `mission-log.json` | -- |
| Step 4: Relief on Station | `event --type relief_on_station` | `mission-log.json` | `turnover-briefs/{ship}.md` |
| Step 5: Action Stations | `event --type task_completed` | `mission-log.json` | -- |
| Step 6: Stand Down | `stand-down` | `mission-log.json`, `fleet-status.json`, `stand-down.json` | `captains-log.md` |

## Event Types

| Event Type | Trigger | Key Data Fields |
|---|---|---|
| `squadron_formed` | Step 3 complete | captain_count, has_red_cell, execution_mode, standing_order_check |
| `battle_plan_approved` | Step 2 complete | task_count, parallel_tracks, critical_path_length, standing_order_check |
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
