# PRD: Structured Fleet Data — Foundation for Visualisation

**Status:** Draft
**Date:** 2026-03-27
**Issue:** [#44](https://github.com/harrymunro/nelson/issues/44)
**Supersedes:** `docs/prd-fleet-visualisation.md` (original two-tier visualisation design)

---

## 1. Executive Summary

### Problem

Nelson produces 8 artifact types during a mission. Only 1 (damage report) uses a structured, machine-readable format. The other 7 store analytically valuable data — task state, budget burn, blockers, dependency graphs, admiral decisions, relief chains — as unparseable markdown prose. Four artifacts are never written to disk at all.

This means:
- No tool other than an LLM can read mission state.
- No dashboard, hook, or analytics script can consume Nelson's data.
- Cross-mission analysis is impossible.
- Session resumption depends on an LLM re-reading and re-interpreting prose.
- The admiral re-derives fleet state from scratch at every checkpoint instead of reading structured records.

### Root Cause

The original artifact templates were designed for LLM-to-LLM communication. Prose was sufficient because the reader was always another Claude instance. But this creates a closed loop — only LLMs can participate in the data flow, and even they must spend tokens re-parsing free text that could have been a JSON read.

### Proposed Solution

Python scripts embedded in the skill directory (`skills/nelson/scripts/`) handle all structured data capture. The admiral calls these scripts via Bash with simple key-value arguments. The scripts handle JSON schema compliance, validation, timestamps, and file I/O. No existing prose artifacts are removed — they continue to serve as narrative reasoning records.

This follows the [Anthropic skill authoring best practice](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills/skill-authoring) pattern: utility scripts executed via Bash are more reliable than LLM-generated code, save tokens (only stdout consumed, not the script source), and ensure consistency across uses.

Once structured data exists on disk, any consumer (hooks, dashboards, analytics scripts, IDE extensions) can read it without touching the conversation context.

### Key Principles

1. **Data first, visualisation later.** This PRD defines the data layer. Visualisation is a trivial consumer built on top.
2. **Scripts write JSON, not the LLM.** The admiral passes structured arguments to Python scripts via Bash. The scripts handle schema compliance, validation, and file I/O. This is cheaper (short Bash command vs. full JSON blob), more reliable (no malformed JSON), and deterministic.
3. **JSON alongside markdown, not instead of.** Prose artifacts serve a reasoning purpose. JSON artifacts serve a machine-readable purpose. Both are written at the same lifecycle moments.
4. **Write-once or append-only.** JSON artifacts are either immutable snapshots (sailing orders, battle plan) or append-only event logs (mission log). No overwrite-in-place except damage reports (which are already overwritten today).
5. **Incremental adoption.** Each JSON artifact is independent. They can be added one at a time without breaking existing workflows.

---

## 2. Current State Audit

### What Nelson Produces Today

| Artifact | Format | On Disk | Machine-Readable | Lifecycle |
|---|---|---|---|---|
| Sailing Orders | Prose | No | No | Write-once (Step 1) |
| Battle Plan | Prose | No | No | Write-once (Step 3) |
| Ship Manifest | Prose | No | No | Write-once (Step 3) |
| Crew Briefing | Prose | No | No | Write-once (Step 3) |
| Damage Report | **JSON** | Yes | **Yes** | Updated per checkpoint |
| Quarterdeck Report | Prose | Yes | No | Updated per checkpoint |
| Turnover Brief | Prose | Yes | No | Write-once (at relief) |
| Captain's Log | Prose | Yes | No | Write-once (Step 6) |

### What Data Is Trapped in Prose

| Data | Current Location | Type | Value for Visualisation/Analytics |
|---|---|---|---|
| Task state progression | Quarterdeck report | Counts (pending/in_progress/completed) | Core progress tracking |
| Budget burn | Quarterdeck report | Numeric ("~30% estimated") | Burn-rate charting |
| Admiral decision | Quarterdeck report | Enum (continue/rescope/stop) | Decision pattern analysis |
| Task dependency graph | Battle plan | DAG (task ID references) | Gantt charts, critical-path analysis |
| File ownership map | Battle plan | Map (agent -> file paths) | Conflict detection |
| Station tier assignments | Battle plan | Enum per task (0-3) | Risk distribution analysis |
| Blocker details + ETA | Quarterdeck report | Structured records | Duration prediction |
| Standing order violations | Quarterdeck report | Event records | Quality/compliance patterns |
| Relief chain | Turnover brief | Linked records | Context-window efficiency |
| Follow-up items | Captain's log | Records with due dates | Issue tracker integration |
| Mentioned in Despatches | Captain's log | Agent performance records | Cross-mission performance analysis |
| Reusable patterns | Captain's log | Adopt/avoid pairs | Institutional knowledge |
| Squadron composition | Battle plan (implied) | Hierarchy | Fleet structure visualisation |
| Crew roster per ship | Ship manifest | Role assignments | Workload analysis |

---

## 3. Proposed Structured Artifacts

Six new JSON artifacts, each written at the same lifecycle moment as its prose counterpart. All are stored in `{mission-dir}/`.

### 3.1 sailing-orders.json (Step 1 — Write-Once)

Written when the admiral issues sailing orders. Persists data that currently lives only in conversation context.

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
  "constraints": [
    "Do not modify the public API surface"
  ],
  "out_of_scope": [
    "Migration script for existing sessions"
  ],
  "stop_criteria": [
    "All tests pass",
    "No regressions in integration suite"
  ],
  "handoff_artifacts": [
    "Updated auth module",
    "Test results"
  ],
  "created_at": "2026-03-27T12:00:00Z"
}
```

**What this unlocks:** Budget tracking with actual numbers (not "~30% estimated"). Cross-mission analytics on scope size. Session-resumption reads a file instead of scanning conversation history.

### 3.2 battle-plan.json (Step 3 — Write-Once, Amendable)

Written when the admiral completes the battle plan. Captures the task DAG, squadron composition, file ownership, and station tiers.

```json
{
  "version": 1,
  "squadron": {
    "admiral": {
      "ship_name": "HMS Victory",
      "model": "opus"
    },
    "captains": [
      {
        "ship_name": "HMS Argyll",
        "ship_class": "frigate",
        "model": "sonnet",
        "task_id": 1,
        "crew": [
          { "role": "PWO", "sub_task": "Core endpoint development" },
          { "role": "MEO", "sub_task": "Test coverage" }
        ],
        "marine_capacity": 2,
        "estimated_token_budget": 50000
      }
    ],
    "red_cell": {
      "ship_name": "HMS Astute",
      "model": "haiku"
    }
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
    },
    {
      "id": 4,
      "name": "Integration testing",
      "owner": "HMS Argyll",
      "deliverable": "Integration test suite green",
      "dependencies": [1, 2],
      "dependents": [],
      "station_tier": 2,
      "file_ownership": ["tests/integration/**"],
      "validation_required": "All integration tests pass",
      "rollback_note_required": false,
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

**What this unlocks:** Task dependency graph for Gantt/DAG visualisation. File ownership map for conflict detection. Station tier distribution for risk analysis. Squadron composition for fleet structure views. Cross-mission analytics on team sizing patterns.

### 3.3 mission-log.json (Steps 2-6 — Append-Only Event Log)

The single most important new artifact. An append-only event log that captures every significant state change during the mission. Replaces the need to parse multiple quarterdeck report versions.

Each event is a JSON object appended to an array. The admiral appends events at the same moments it currently writes/updates the quarterdeck report.

```json
{
  "version": 1,
  "events": [
    {
      "type": "squadron_formed",
      "checkpoint": 0,
      "timestamp": "2026-03-27T12:05:00Z",
      "data": {
        "captain_count": 3,
        "has_red_cell": true,
        "execution_mode": "agent-team",
        "standing_order_check": {
          "triggered": ["light-squadron"],
          "remedies": ["Spawned third captain to match independent task count"]
        }
      }
    },
    {
      "type": "battle_plan_approved",
      "checkpoint": 0,
      "timestamp": "2026-03-27T12:08:00Z",
      "data": {
        "task_count": 5,
        "parallel_tracks": 3,
        "critical_path_length": 2,
        "standing_order_check": {
          "triggered": [],
          "remedies": []
        }
      }
    },
    {
      "type": "checkpoint",
      "checkpoint": 1,
      "timestamp": "2026-03-27T12:20:00Z",
      "data": {
        "progress": {
          "pending": 2,
          "in_progress": 2,
          "completed": 1,
          "blocked": 0
        },
        "budget": {
          "tokens_spent": 45000,
          "tokens_remaining": 155000,
          "pct_consumed": 22.5,
          "burn_rate_per_checkpoint": 15000
        },
        "hull_summary": {
          "green": 3,
          "amber": 1,
          "red": 0,
          "critical": 0
        },
        "blockers": [],
        "standing_order_violations": [],
        "admiral_decision": "continue",
        "admiral_rationale": "On track. HMS Kent approaching amber but no relief needed yet."
      }
    },
    {
      "type": "hull_threshold_crossed",
      "checkpoint": 2,
      "timestamp": "2026-03-27T12:35:00Z",
      "data": {
        "ship_name": "HMS Kent",
        "previous_status": "Green",
        "new_status": "Amber",
        "hull_integrity_pct": 68,
        "relief_requested": false
      }
    },
    {
      "type": "blocker_raised",
      "checkpoint": 2,
      "timestamp": "2026-03-27T12:36:00Z",
      "data": {
        "description": "Waiting for DB schema approval",
        "owner": "HMS Kent",
        "next_action": "Admiral to review schema",
        "blocking_task_id": 3,
        "blocked_task_ids": [4]
      }
    },
    {
      "type": "blocker_resolved",
      "checkpoint": 3,
      "timestamp": "2026-03-27T12:50:00Z",
      "data": {
        "description": "DB schema approved",
        "owner": "HMS Kent",
        "resolution": "Admiral reviewed and approved schema"
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
    },
    {
      "type": "standing_order_violation",
      "checkpoint": 2,
      "timestamp": "2026-03-27T12:40:00Z",
      "data": {
        "order": "admiral-at-the-helm",
        "description": "Admiral began implementing test fixture directly",
        "corrective_action": "Delegated to HMS Lancaster PWO",
        "severity": "signal"
      }
    },
    {
      "type": "relief_on_station",
      "checkpoint": 3,
      "timestamp": "2026-03-27T12:55:00Z",
      "data": {
        "outgoing_ship": "HMS Kent",
        "incoming_ship": "HMS Diamond",
        "reason": "Context window exhaustion (hull 41%)",
        "task_id": 2,
        "time_on_station_minutes": 55,
        "progress_at_handoff": "Schema migration 80% complete"
      }
    },
    {
      "type": "commendation",
      "checkpoint": 3,
      "timestamp": "2026-03-27T13:00:00Z",
      "data": {
        "ship_name": "HMS Argyll",
        "type": "signal_flag",
        "citation": "Completed auth refactor ahead of schedule with zero test regressions"
      }
    },
    {
      "type": "mission_complete",
      "checkpoint": 4,
      "timestamp": "2026-03-27T13:10:00Z",
      "data": {
        "outcome_achieved": true,
        "tasks_completed": 5,
        "tasks_total": 5,
        "total_tokens_consumed": 120000,
        "budget_pct_consumed": 60.0,
        "duration_minutes": 70,
        "ships_used": 4,
        "reliefs": 1,
        "standing_order_violations_total": 1,
        "open_risks": [
          {
            "risk": "JWT token rotation not tested under load",
            "owner": "follow-up",
            "mitigation": "Add load test in next sprint"
          }
        ],
        "follow_ups": [
          {
            "item": "Add JWT load testing",
            "owner": "team",
            "due": "next sprint"
          }
        ],
        "mentioned_in_despatches": [
          {
            "ship_name": "HMS Argyll",
            "contribution": "Fast, clean auth refactor"
          }
        ],
        "reusable_patterns": {
          "adopt": ["Station tier 1 for schema migrations worked well"],
          "avoid": ["Assigning DB work to a frigate — needed a destroyer"]
        }
      }
    }
  ]
}
```

**What this unlocks:** Complete mission timeline. Progress curves over time. Budget burn-rate charts. Blocker duration analysis. Relief frequency tracking. Standing order compliance trends. Cross-mission performance comparison. All without parsing a single line of prose.

### 3.4 fleet-status.json (Steps 2-6 — Overwritten Per Checkpoint)

A current-state snapshot for real-time consumers (hooks, dashboards). Derived from mission-log.json events + damage reports. This is the file that visualisation layers read.

```json
{
  "version": 1,
  "mission": {
    "outcome": "Refactor auth module to use JWT tokens",
    "status": "underway",
    "started_at": "2026-03-27T12:00:00Z",
    "checkpoint_number": 2
  },
  "progress": {
    "pending": 1,
    "in_progress": 2,
    "completed": 2,
    "blocked": 0,
    "total": 5
  },
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
      "relief_requested": false,
      "task_id": 3,
      "task_name": "API endpoint tests",
      "task_status": "in_progress"
    },
    {
      "ship_name": "HMS Kent",
      "ship_class": "destroyer",
      "role": "captain",
      "hull_integrity_pct": 68,
      "hull_integrity_status": "Amber",
      "relief_requested": false,
      "task_id": 2,
      "task_name": "Database migration",
      "task_status": "in_progress"
    }
  ],
  "blockers": [],
  "recent_events": [
    "Task 1 completed (HMS Argyll)",
    "HMS Kent hull crossed to Amber (68%)"
  ],
  "last_updated": "2026-03-27T12:35:00Z"
}
```

**What this unlocks:** Real-time hooks and dashboards read one file. No need to aggregate damage reports + quarterdeck report + TaskList.

### 3.5 Damage Reports (Existing — No Change)

Already JSON. Already on disk. No changes needed. The schema is defined in `references/admiralty-templates/damage-report.md`.

The only issue from the audit: **damage reports are not being reliably written in practice.** The SKILL.md instructions need strengthening to ensure captains actually produce them. This is a discipline problem, not a schema problem.

### 3.6 stand-down.json (Step 6 — Write-Once)

Structured version of the captain's log's analytical data. The prose captain's log continues to exist for narrative purposes.

```json
{
  "version": 1,
  "outcome_achieved": true,
  "planned_outcome": "Refactor auth module to use JWT tokens",
  "actual_outcome": "Auth module refactored with JWT support, all tests passing",
  "success_metric_result": "47/47 auth tests pass, 0 new dependencies",
  "duration_minutes": 70,
  "budget": {
    "tokens_consumed": 120000,
    "tokens_budgeted": 200000,
    "pct_consumed": 60.0
  },
  "fleet": {
    "ships_used": 4,
    "reliefs": 1,
    "max_concurrent_ships": 4
  },
  "tasks": {
    "completed": 5,
    "total": 5,
    "by_station_tier": { "0": 1, "1": 3, "2": 1, "3": 0 }
  },
  "quality": {
    "standing_order_violations": 1,
    "blockers_raised": 1,
    "blockers_resolved": 1,
    "avg_blocker_duration_minutes": 14
  },
  "open_risks": [
    {
      "risk": "JWT token rotation not tested under load",
      "owner": "follow-up",
      "mitigation": "Add load test in next sprint"
    }
  ],
  "follow_ups": [
    {
      "item": "Add JWT load testing",
      "owner": "team",
      "due": "next sprint"
    }
  ],
  "mentioned_in_despatches": [
    {
      "ship_name": "HMS Argyll",
      "contribution": "Fast, clean auth refactor"
    }
  ],
  "reusable_patterns": {
    "adopt": ["Station tier 1 for schema migrations worked well"],
    "avoid": ["Assigning DB work to a frigate — needed a destroyer"]
  },
  "created_at": "2026-03-27T13:10:00Z"
}
```

**What this unlocks:** Cross-mission dashboards. "Average mission duration", "budget utilisation trend", "most common standing order violations", "which ship classes perform best for which task types".

---

## 4. File Layout

```
skills/nelson/
  scripts/                          ← NEW: Utility scripts (executed, not loaded)
    nelson-data.py                    ← Single script, multiple subcommands
  references/
    structured-data.md                ← NEW: Schemas + script usage reference

.nelson/missions/{YYYY-MM-DD_HHMMSS}/
  # Structured (NEW — written by scripts)
  sailing-orders.json         ← Write-once (Step 1)
  battle-plan.json            ← Write-once (Step 3), amendable
  mission-log.json            ← Append-only event log (Steps 2-6)
  fleet-status.json           ← Overwritten per checkpoint (Steps 2-6)
  stand-down.json             ← Write-once (Step 6)

  # Structured (EXISTING)
  damage-reports/
    {ship-name}.json          ← Overwritten per checkpoint

  # Prose (EXISTING — unchanged)
  quarterdeck-report.md       ← Updated per checkpoint (admiral reasoning)
  quarterdeck-report-{N}.md   ← Versioned history
  captains-log.md             ← Write-once (Step 6, admiral narrative)
  turnover-briefs/
    {ship-name}.md            ← Write-once (at relief)
```

---

## 5. Write Timing

| Lifecycle Moment | Script Command | JSON Written | Prose (existing) |
|---|---|---|---|
| Step 1: Sailing Orders | `nelson-data.py init` | `sailing-orders.json`, `mission-log.json` | (conversation-only) |
| Step 2: Form Squadron | `nelson-data.py squadron` | `battle-plan.json`, `mission-log.json`, `fleet-status.json` | (conversation-only) |
| Step 3: Battle Plan | `nelson-data.py task` (per task), then `plan-approved` | `battle-plan.json`, `mission-log.json`, `fleet-status.json` | (conversation-only) |
| Step 4: Each Checkpoint | `nelson-data.py checkpoint` | `mission-log.json`, `fleet-status.json` | `quarterdeck-report.md` |
| Step 4: Between Checkpoints | `nelson-data.py event` | `mission-log.json` | — |
| Step 4: Relief on Station | `nelson-data.py event --type relief_on_station` | `mission-log.json` | `turnover-briefs/{ship}.md` |
| Step 5: Action Stations | `nelson-data.py event --type task_completed` | `mission-log.json` | — |
| Step 6: Stand Down | `nelson-data.py stand-down` | `mission-log.json`, `fleet-status.json`, `stand-down.json` | `captains-log.md` |

---

## 6. Script Interface — `nelson-data.py`

A single Python script (`skills/nelson/scripts/nelson-data.py`) with subcommands for each data operation. The admiral calls it via Bash. The script handles JSON schema compliance, validation, timestamps, and file I/O.

### Design Principles

Following the [Anthropic skill authoring best practices](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills/skill-authoring):

- **Low freedom.** Data capture is fragile — schema consistency is critical. The script enforces the schema; the admiral provides values.
- **Solve, don't punt.** The script handles missing directories, creates files if absent, validates inputs, and returns clear error messages. It never fails silently.
- **Executed, not loaded.** The script's source code is never loaded into context. Only its stdout is consumed.

### Subcommands

#### `init` — Create mission directory and sailing orders

```bash
python3 scripts/nelson-data.py init \
  --outcome "Refactor auth module to use JWT tokens" \
  --metric "All 47 auth tests pass, no new dependencies" \
  --deadline "this_session" \
  --token-budget 200000
```

Creates `{mission-dir}/sailing-orders.json` and empty `mission-log.json`. Prints the mission directory path to stdout.

#### `squadron` — Record squadron formation

```bash
python3 scripts/nelson-data.py squadron \
  --mission-dir .nelson/missions/2026-03-27_120000 \
  --admiral "HMS Victory" --admiral-model opus \
  --captain "HMS Argyll" --class frigate --model sonnet --task-id 1 \
  --captain "HMS Kent" --class destroyer --model sonnet --task-id 2 \
  --red-cell "HMS Astute" --red-cell-model haiku \
  --mode agent-team
```

Updates `battle-plan.json` with squadron section. Appends `squadron_formed` event to `mission-log.json`. Writes initial `fleet-status.json`. Prints confirmation.

#### `task` — Add task to battle plan

```bash
python3 scripts/nelson-data.py task \
  --mission-dir .nelson/missions/2026-03-27_120000 \
  --id 1 --name "Auth module refactor" --owner "HMS Argyll" \
  --deliverable "Refactored auth module with JWT support" \
  --deps "" --station-tier 1 \
  --files "src/auth/**"
```

Appends task to `battle-plan.json`. Can be called multiple times (once per task). Prints confirmation.

#### `plan-approved` — Finalize battle plan

```bash
python3 scripts/nelson-data.py plan-approved \
  --mission-dir .nelson/missions/2026-03-27_120000
```

Reads `battle-plan.json`, computes `parallel_tracks` and `critical_path_length` from the dependency graph. Appends `battle_plan_approved` event to `mission-log.json`. Updates `fleet-status.json`. Prints summary.

#### `event` — Log a mission event

```bash
python3 scripts/nelson-data.py event \
  --mission-dir .nelson/missions/2026-03-27_120000 \
  --type task_completed \
  --checkpoint 2 \
  --task-id 1 --task-name "Auth module refactor" --owner "HMS Argyll" \
  --station-tier 1 --verification passed
```

Appends an event to `mission-log.json`. Accepts type-specific key-value pairs. Each event type has required and optional fields validated by the script. Prints confirmation.

Supported event types: `task_started`, `task_completed`, `blocker_raised`, `blocker_resolved`, `hull_threshold_crossed`, `relief_on_station`, `standing_order_violation`, `commendation`, `admiralty_action_required`, `admiralty_action_completed`, `battle_plan_amended`.

#### `checkpoint` — Record a quarterdeck checkpoint

```bash
python3 scripts/nelson-data.py checkpoint \
  --mission-dir .nelson/missions/2026-03-27_120000 \
  --pending 2 --in-progress 2 --completed 1 --blocked 0 \
  --tokens-spent 45000 --tokens-remaining 155000 \
  --hull-green 3 --hull-amber 1 --hull-red 0 --hull-critical 0 \
  --decision continue \
  --rationale "On track. HMS Kent approaching amber but no relief needed yet."
```

Appends a `checkpoint` event to `mission-log.json`. Overwrites `fleet-status.json` with current state (aggregated from battle-plan.json + this checkpoint data). Prints compact status line to stdout.

#### `stand-down` — Record mission completion

```bash
python3 scripts/nelson-data.py stand-down \
  --mission-dir .nelson/missions/2026-03-27_120000 \
  --outcome-achieved \
  --actual-outcome "Auth module refactored with JWT support, all tests passing" \
  --metric-result "47/47 auth tests pass, 0 new dependencies"
```

Reads `mission-log.json` and `battle-plan.json` to auto-compute duration, budget consumption, ship counts, relief counts, violation counts, and blocker statistics. Writes `stand-down.json`. Appends `mission_complete` event. Writes final `fleet-status.json`. Prints mission summary to stdout.

#### `status` — Print current fleet status (read-only)

```bash
python3 scripts/nelson-data.py status \
  --mission-dir .nelson/missions/2026-03-27_120000
```

Reads `fleet-status.json` and prints a compact status summary. Useful for hooks and quick checks. Prints nothing if no mission data exists (silent no-op outside Nelson missions).

### Script Output

All subcommands print a brief confirmation or status to stdout. The admiral sees this output as the Bash tool result. Example:

```
[nelson-data] Checkpoint 2 recorded
Fleet: 3/5 done | Budget: 62% | Hull: 3G 1A 0R | Blockers: 0
```

This stdout line (~20 tokens) replaces what would have been a ~200-token JSON Write call. The script has already written the full JSON to disk.

### Error Handling

- Missing `--mission-dir`: prints error and exits 1.
- Invalid event type: prints valid types and exits 1.
- Missing required field for event type: prints required fields and exits 1.
- Corrupt JSON on disk: prints warning, backs up corrupt file, creates fresh.
- Missing directories: creates them automatically.

---

## 7. Token Cost Analysis

### Cost Per Operation (Script via Bash)

The admiral runs a Bash command. Token cost = tool call overhead (~15 tokens) + the command string + stdout result.

| Operation | Bash Command Tokens | Stdout Tokens | Total | Frequency | Per-Mission |
|---|---|---|---|---|---|
| `init` | ~40 | ~15 | ~55 | Once | ~55 |
| `squadron` | ~60 | ~10 | ~70 | Once | ~70 |
| `task` (per task) | ~45 | ~5 | ~50 | ~5 tasks | ~250 |
| `plan-approved` | ~20 | ~15 | ~35 | Once | ~35 |
| `event` (per event) | ~40 | ~5 | ~45 | ~8 events | ~360 |
| `checkpoint` | ~60 | ~20 | ~80 | ~4 checkpoints | ~320 |
| `stand-down` | ~35 | ~20 | ~55 | Once | ~55 |
| **Total** | | | | | **~1,145** |

### Comparison: Script vs. Direct JSON Write

| Approach | Per-Mission Tokens | Machine-Readable | Schema-Validated |
|---|---|---|---|
| Current (prose only) | ~2,400 | No | No |
| Direct JSON Write (v2 draft) | ~2,130 | Yes | No (LLM can produce malformed JSON) |
| **Script via Bash** | **~1,145** | **Yes** | **Yes (script enforces schema)** |

**Scripts save ~50% of tokens compared to direct JSON writes** because the admiral passes short argument strings instead of composing full JSON blobs. The script handles all the boilerplate — timestamps, file paths, schema structure, array appending, file creation.

### Net Cost vs. Current Prose

| | Tokens | Context % (200K mission) |
|---|---|---|
| Current prose writes | ~2,400 | 1.2% |
| Script calls (new) | ~1,145 | 0.57% |
| Prose writes (kept) | ~2,400 | 1.2% |
| **Total with both** | **~3,545** | **1.77%** |

Well within the 3% ceiling. And once the JSON data proves reliable, the prose quarterdeck report can be slimmed (saving ~1,000 tokens) since the structured data captures the same information.

---

## 8. Event Types Reference

Complete list of `mission-log.json` event types:

| Event Type | Trigger | Key Data Fields |
|---|---|---|
| `squadron_formed` | Step 2 complete | captain_count, has_red_cell, execution_mode, standing_order_check |
| `battle_plan_approved` | Step 3 complete | task_count, parallel_tracks, critical_path_length, standing_order_check |
| `checkpoint` | Each quarterdeck checkpoint | progress, budget, hull_summary, blockers, admiral_decision |
| `task_completed` | Task verified complete | task_id, task_name, owner, station_tier, verification |
| `task_started` | Captain begins work | task_id, task_name, owner |
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

---

## 9. Integration With Nelson

### SKILL.md Changes

Replace prose-only data capture with script calls at each step. The SKILL.md instructions tell the admiral to **execute** the scripts, following the [Anthropic best practice](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills/skill-authoring): "Run `nelson-data.py init ...` to create the mission directory."

- **Step 1:** After sailing orders are agreed, run `nelson-data.py init`.
- **Step 2:** After squadron formation, run `nelson-data.py squadron`.
- **Step 3:** For each task, run `nelson-data.py task`. After all tasks, run `nelson-data.py plan-approved`.
- **Step 4:** At each checkpoint, run `nelson-data.py checkpoint`. Between checkpoints, run `nelson-data.py event` for state changes (blockers, hull crossings, task completions).
- **Step 6:** Run `nelson-data.py stand-down`.

The admiral continues to write prose artifacts (quarterdeck report, captain's log) as before. The script calls are additive.

### New Reference File

Create `skills/nelson/references/structured-data.md` containing:
- Script subcommand reference with examples (the "how to run" guide)
- JSON schemas for all artifacts (for consumers, not the admiral)
- Event type reference table
- Write timing rules

This file is the detailed reference. SKILL.md points to it: "For structured data capture, see [structured-data.md](references/structured-data.md)."

### Damage Report Enforcement

Strengthen SKILL.md Step 4 to require damage reports at every checkpoint, not just when hulls cross thresholds. The current instructions allow captains to skip writing damage reports when hull is Green, which means the `damage-reports/` directory is often empty.

### Session Resumption

Update `references/damage-control/session-resumption.md` to prefer reading `fleet-status.json` and `mission-log.json` over re-parsing `quarterdeck-report.md` prose. The admiral can run `nelson-data.py status` for a quick read of current state.

---

## 10. Visualisation Layer (Future Work)

With structured data on disk, visualisation becomes a trivial consumer. The v2 visualisation PRD's hook and dashboard designs remain valid and can be implemented as a follow-on:

### Hook-Driven Terminal (Zero Context Cost)
- PostToolUse hook on Write reads `fleet-status.json`
- Prints ANSI-coloured status line to terminal
- Hook output is outside conversation context

### Browser Dashboard (Opt-In, Zero Context Cost)
- Static HTML reads `fleet-status.js` (generated from JSON by hook script)
- Polls via `<script src>` tag re-insertion (avoids file:// CORS)
- Auto-opens via hook on first checkpoint

### Cross-Mission Analytics (Future)
- Script reads `stand-down.json` from all `missions/*/` directories
- Aggregates: budget efficiency, relief frequency, violation patterns, team sizing trends

These are separate implementation efforts that depend on the data layer defined in this PRD.

---

## 11. Phased Rollout

### Phase 1: Data Capture Script + Skill Integration

**Goal:** Machine-readable mission data on disk via Python scripts embedded in the skill.

**Deliverables:**
1. `skills/nelson/scripts/nelson-data.py` — single script with all subcommands.
2. `skills/nelson/references/structured-data.md` — subcommand reference, schemas, event types.
3. `skills/nelson/SKILL.md` updated with script execution instructions at Steps 1, 2, 3, 4, 6.
4. Damage report enforcement strengthened in Step 4.
5. Session resumption updated to prefer JSON.

**Files added:**
- `skills/nelson/scripts/nelson-data.py`
- `skills/nelson/references/structured-data.md`

**Files changed:**
- `skills/nelson/SKILL.md`
- `skills/nelson/references/damage-control/session-resumption.md`

**Files unchanged:** All existing templates, standing orders, and prose artifacts.

**Estimated effort:** Medium. One Python script (~300-400 lines), one reference doc, SKILL.md edits. No external dependencies (stdlib only: `json`, `argparse`, `datetime`, `pathlib`).

### Phase 2: Hook-Driven Terminal Visualisation

**Goal:** ANSI-coloured fleet status in the terminal at zero context cost.

**Depends on:** Phase 1 (`fleet-status.json` exists on disk).

**Deliverables:**
1. `scripts/fleet-status-hook.py` — PostToolUse hook that reads `fleet-status.json` and prints ANSI-coloured status.
2. `settings.json` updated with hook configuration.

**Note:** The `nelson-data.py status` subcommand already prints a compact status line. The hook script can simply call it, or duplicate the rendering logic with ANSI colour support (hooks can use ANSI; Bash tool output cannot).

### Phase 3: Browser Dashboard

**Goal:** Interactive HTML dashboard.

**Depends on:** Phase 1 (`fleet-status.json` exists on disk).

**Deliverables:**
1. `skills/nelson/fleet-dashboard.html` — single-file vanilla HTML/CSS/JS.
2. Hook extension to generate `fleet-status.js` from JSON (for `file://` CORS avoidance).
3. Optional auto-open hook.

### Phase 4: Cross-Mission Analytics

**Goal:** Aggregate insights across multiple missions.

**Depends on:** Phase 1 (`stand-down.json` exists across missions).

**Deliverables:**
1. `nelson-data.py analytics` subcommand that reads `stand-down.json` from all mission directories.
2. Summary output: budget efficiency, relief frequency, violation patterns, team sizing trends.

---

## 12. Open Questions

| ID | Question | Impact | Proposed Resolution |
|---|---|---|---|
| OQ-1 | Should `nelson-data.py` use `argparse` subcommands or a simpler positional-argument pattern? | DX: affects how natural the Bash calls feel for the admiral. | Recommend `argparse` subcommands. They are self-documenting (`--help`), validate inputs, and handle optional fields cleanly. |
| OQ-2 | Should the script handle `mission-log.json` as a single file (read-modify-write) or one JSON file per event? | Single file is simpler for consumers; per-event avoids read-modify-write complexity. | Recommend single file. The script reads, appends to the events array, and writes back. Atomic enough for single-writer (admiral) usage. |
| OQ-3 | Should the quarterdeck report prose be slimmed down now that the script captures structured data? | Could save ~1,000 tokens per mission by reducing prose to decisions/rationale only. | Defer to after Phase 1 validation. Keep both full initially to verify the script data matches what the prose would have captured. |
| OQ-4 | How do we validate that the admiral actually runs the scripts? | Without enforcement, adoption may be unreliable (as seen with damage reports). | Add a standing order: "log-without-ledger" — symptoms: `fleet-status.json` missing or stale at checkpoint; remedy: run the script before proceeding. |
| OQ-5 | Should `nelson-data.py` also handle damage report writes (replacing the current captain-writes-JSON pattern)? | Would unify all structured data through one script. But captains are separate agents that may not have access to the skill's scripts directory. | Defer. Keep damage reports as direct JSON writes by captains for now. The admiral's `checkpoint` subcommand can read and aggregate them. |
| OQ-6 | Should the script validate that referenced task IDs and ship names exist in `battle-plan.json` when logging events? | Catches errors early vs. adds complexity. | Recommend yes for required references (task_id in `task_completed`), no for optional ones. Script should warn but not block on unknown references. |
