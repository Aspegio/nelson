"""Mission lifecycle commands for Nelson data capture.

Implements the core mission workflow: init, squadron, task, plan-approved,
event, checkpoint, stand-down, and status subcommands.

No external dependencies — stdlib only.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from nelson_data_memory import _update_patterns_store, _update_standing_order_stats
from nelson_data_utils import (
    VALID_DECISIONS,
    VALID_EVENT_TYPES,
    VALID_MODES,
    _append_event,
    _count_events_of_type,
    _die,
    _err,
    _get_last_checkpoint_number,
    _mission_dir_stamp,
    _now_iso,
    _parse_extra_kv,
    _read_battle_plan,
    _read_damage_reports,
    _read_json,
    _require_mission_dir,
    _write_json,
)


# ---------------------------------------------------------------------------
# Subcommand: init
# ---------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> None:
    """Create mission directory and write sailing-orders.json."""
    base = Path(".nelson") / "missions" / _mission_dir_stamp()
    base.mkdir(parents=True, exist_ok=True)
    (base / "damage-reports").mkdir(exist_ok=True)
    (base / "turnover-briefs").mkdir(exist_ok=True)

    budget: dict[str, Any] = {}
    if args.token_budget is not None:
        budget["token_limit"] = args.token_budget
    else:
        budget["token_limit"] = None
    if args.time_limit is not None:
        budget["time_limit_minutes"] = args.time_limit
    else:
        budget["time_limit_minutes"] = None

    sailing_orders = {
        "version": 1,
        "outcome": args.outcome,
        "success_metric": args.metric,
        "deadline": args.deadline,
        "budget": budget,
        "constraints": list(args.constraints or []),
        "out_of_scope": list(args.out_of_scope or []),
        "stop_criteria": list(args.stop_criteria or []),
        "handoff_artifacts": list(args.handoff_artifacts or []),
        "created_at": _now_iso(),
    }

    mission_log = {"version": 1, "events": []}

    _write_json(base / "sailing-orders.json", sailing_orders)
    _write_json(base / "mission-log.json", mission_log)

    # Print the mission directory path (consumed by admiral)
    print(str(base))


# ---------------------------------------------------------------------------
# Subcommand: squadron
# ---------------------------------------------------------------------------


def cmd_squadron(args: argparse.Namespace) -> None:
    """Record squadron formation in battle-plan.json and mission-log.json."""
    mission_dir = _require_mission_dir(args)

    # Parse captain specs: "name:class:model:task_id"
    captains: list[dict[str, Any]] = []
    for spec in args.captain or []:
        parts = spec.split(":")
        if len(parts) != 4:
            _die(f"Error: captain spec must be 'name:class:model:task_id', got: {spec}")
        ship_name, ship_class, model, task_id_str = parts
        try:
            task_id = int(task_id_str)
        except ValueError:
            _die(f"Error: task_id must be an integer, got: {task_id_str}")
            return  # unreachable but helps type checkers
        captains.append(
            {
                "ship_name": ship_name,
                "ship_class": ship_class,
                "model": model,
                "task_id": task_id,
            }
        )

    squadron: dict[str, Any] = {
        "admiral": {
            "ship_name": args.admiral,
            "model": args.admiral_model,
        },
        "captains": captains,
    }

    if args.red_cell:
        squadron["red_cell"] = {
            "ship_name": args.red_cell,
            "model": args.red_cell_model or "haiku",
        }

    if args.mode and args.mode not in VALID_MODES:
        _die(f"Error: --mode must be one of {sorted(VALID_MODES)}")

    # Build/update battle-plan.json
    bp_path = mission_dir / "battle-plan.json"
    if bp_path.exists():
        battle_plan = _read_json(bp_path)
    else:
        battle_plan = {"version": 1}

    new_battle_plan = {**battle_plan, "squadron": squadron, "created_at": _now_iso()}
    _write_json(bp_path, new_battle_plan)

    # Append squadron_formed event
    event = {
        "type": "squadron_formed",
        "checkpoint": 0,
        "timestamp": _now_iso(),
        "data": {
            "captain_count": len(captains),
            "has_red_cell": args.red_cell is not None,
            "execution_mode": args.mode or "subagents",
            "standing_order_check": {"triggered": [], "remedies": []},
        },
    }
    _append_event(mission_dir, event)

    # Write initial fleet-status.json
    squadron_list: list[dict[str, Any]] = []
    for cap in captains:
        squadron_list.append(
            {
                "ship_name": cap["ship_name"],
                "ship_class": cap["ship_class"],
                "role": "captain",
                "hull_integrity_pct": 100,
                "hull_integrity_status": "Green",
                "relief_requested": False,
                "task_id": cap["task_id"],
                "task_name": None,
                "task_status": "pending",
            }
        )

    fleet_status = {
        "version": 1,
        "mission": {
            "outcome": None,
            "status": "forming",
            "started_at": _now_iso(),
            "checkpoint_number": 0,
        },
        "progress": {
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "blocked": 0,
            "total": 0,
        },
        "budget": {
            "tokens_spent": 0,
            "tokens_remaining": None,
            "pct_consumed": 0.0,
            "burn_rate_per_checkpoint": 0,
        },
        "squadron": squadron_list,
        "blockers": [],
        "recent_events": [f"Squadron formed: {len(captains)} captains"],
        "last_updated": _now_iso(),
    }

    # Pull outcome from sailing-orders if available
    so_path = mission_dir / "sailing-orders.json"
    if so_path.exists():
        sailing_orders = _read_json(so_path)
        fleet_status = {
            **fleet_status,
            "mission": {
                **fleet_status["mission"],
                "outcome": sailing_orders.get("outcome"),
            },
        }

    _write_json(mission_dir / "fleet-status.json", fleet_status)

    print(
        f"[nelson-data] Squadron formed: admiral {args.admiral}, "
        f"{len(captains)} captains"
        + (f", red cell {args.red_cell}" if args.red_cell else "")
    )


# ---------------------------------------------------------------------------
# Subcommand: task
# ---------------------------------------------------------------------------


def cmd_task(args: argparse.Namespace) -> None:
    """Add a task to battle-plan.json."""
    mission_dir = _require_mission_dir(args)

    deps: list[int] = []
    if args.deps:
        for d in args.deps.split(","):
            d = d.strip()
            if d:
                try:
                    deps.append(int(d))
                except ValueError:
                    _die(f"Error: dependency must be an integer, got: {d}")

    files: list[str] = []
    if args.files:
        files = [f.strip() for f in args.files.split(",") if f.strip()]

    task: dict[str, Any] = {
        "id": args.id,
        "name": args.name,
        "owner": args.owner,
        "deliverable": args.deliverable,
        "dependencies": deps,
        "dependents": [],
        "station_tier": args.station_tier,
        "file_ownership": files,
        "validation_required": args.validation or None,
        "rollback_note_required": bool(args.rollback_note),
        "admiralty_action_required": bool(args.admiralty_action),
    }

    bp_path = mission_dir / "battle-plan.json"
    if bp_path.exists():
        battle_plan = _read_json(bp_path)
    else:
        battle_plan = {"version": 1}

    existing_tasks = list(battle_plan.get("tasks", []))
    new_tasks = existing_tasks + [task]

    # Recompute dependents for all tasks
    new_tasks = _recompute_dependents(new_tasks)

    new_battle_plan = {**battle_plan, "tasks": new_tasks}
    _write_json(bp_path, new_battle_plan)

    print(f"[nelson-data] Task {args.id} added: {args.name} -> {args.owner}")


def _recompute_dependents(tasks: list[dict]) -> list[dict]:
    """Return a new task list with dependents computed from dependencies."""
    # Build a map of task_id -> set of dependent task_ids
    dependents_map: dict[int, list[int]] = {}
    for t in tasks:
        for dep_id in t.get("dependencies", []):
            dependents_map.setdefault(dep_id, [])
            if t["id"] not in dependents_map[dep_id]:
                dependents_map[dep_id].append(t["id"])

    return [{**t, "dependents": sorted(dependents_map.get(t["id"], []))} for t in tasks]


# ---------------------------------------------------------------------------
# Subcommand: plan-approved
# ---------------------------------------------------------------------------


def cmd_plan_approved(args: argparse.Namespace) -> None:
    """Finalize the battle plan — compute DAG metrics and log event."""
    mission_dir = _require_mission_dir(args)

    bp_path = mission_dir / "battle-plan.json"
    if not bp_path.exists():
        _die("Error: battle-plan.json does not exist. Run 'squadron' and 'task' first.")

    battle_plan = _read_json(bp_path)
    tasks = battle_plan.get("tasks", [])

    if not tasks:
        _die("Error: no tasks in battle-plan.json. Run 'task' to add tasks first.")

    # Compute parallel_tracks and critical_path_length from dependency graph
    parallel_tracks, critical_path_length = _compute_dag_metrics(tasks)

    # Stamp the battle plan as approved
    new_battle_plan = {
        **battle_plan,
        "amended_at": None,
    }
    _write_json(bp_path, new_battle_plan)

    # Append battle_plan_approved event
    event = {
        "type": "battle_plan_approved",
        "checkpoint": 0,
        "timestamp": _now_iso(),
        "data": {
            "task_count": len(tasks),
            "parallel_tracks": parallel_tracks,
            "critical_path_length": critical_path_length,
            "standing_order_check": {
                "triggered": [],
                "remedies": [],
            },
        },
    }
    _append_event(mission_dir, event)

    # Update fleet-status.json
    fs_path = mission_dir / "fleet-status.json"
    if fs_path.exists():
        fleet_status = _read_json(fs_path)
    else:
        fleet_status = {"version": 1}

    new_fleet_status = {
        **fleet_status,
        "mission": {
            **fleet_status.get("mission", {}),
            "status": "underway",
        },
        "progress": {
            **fleet_status.get("progress", {}),
            "pending": len(tasks),
            "total": len(tasks),
        },
        "last_updated": _now_iso(),
    }
    _write_json(fs_path, new_fleet_status)

    print(
        f"[nelson-data] Battle plan approved: {len(tasks)} tasks, "
        f"{parallel_tracks} parallel tracks, "
        f"critical path length {critical_path_length}"
    )


def _compute_dag_metrics(tasks: list[dict]) -> tuple[int, int]:
    """Compute parallel track count and critical path length from tasks.

    parallel_tracks: number of tasks with no dependencies (can start immediately)
    critical_path_length: longest chain in the dependency DAG
    """
    task_map = {t["id"]: t for t in tasks}

    # Parallel tracks = tasks with empty dependencies
    parallel_tracks = sum(1 for t in tasks if not t.get("dependencies"))

    # Critical path = longest path in DAG via DFS with memoisation
    memo: dict[int, int] = {}
    visiting: set[int] = set()

    def longest_path(task_id: int) -> int:
        if task_id in memo:
            return memo[task_id]
        if task_id in visiting:
            cycle_members = ", ".join(str(t) for t in sorted(visiting))
            _die(
                f"Cycle detected in task dependencies (task IDs involved: {cycle_members})"
            )
        visiting.add(task_id)
        task = task_map.get(task_id)
        if task is None:
            visiting.discard(task_id)
            return 0
        deps = task.get("dependencies", [])
        if not deps:
            memo[task_id] = 1
            visiting.discard(task_id)
            return 1
        length = 1 + max(longest_path(d) for d in deps)
        memo[task_id] = length
        visiting.discard(task_id)
        return length

    if not tasks:
        return 0, 0

    critical_path_length = max(longest_path(t["id"]) for t in tasks)
    return parallel_tracks, critical_path_length


# ---------------------------------------------------------------------------
# Subcommand: event
# ---------------------------------------------------------------------------


def cmd_event(args: argparse.Namespace, extra: list[str]) -> None:
    """Log a mission event to mission-log.json."""
    mission_dir = _require_mission_dir(args)

    event_type = args.type
    if event_type not in VALID_EVENT_TYPES:
        _die(
            f"Error: invalid event type '{event_type}'. "
            f"Valid types: {', '.join(sorted(VALID_EVENT_TYPES))}"
        )

    checkpoint = args.checkpoint
    if checkpoint is None:
        # Auto-detect from last checkpoint in the log
        log = _read_json(mission_dir / "mission-log.json")
        checkpoint = _get_last_checkpoint_number(log.get("events", []))

    data = _parse_extra_kv(extra)

    event = {
        "type": event_type,
        "checkpoint": checkpoint,
        "timestamp": _now_iso(),
        "data": data,
    }
    _append_event(mission_dir, event)

    print(f"[nelson-data] Event logged: {event_type} (checkpoint {checkpoint})")


# ---------------------------------------------------------------------------
# Subcommand: checkpoint
# ---------------------------------------------------------------------------


def cmd_checkpoint(args: argparse.Namespace) -> None:
    """Record a quarterdeck checkpoint."""
    mission_dir = _require_mission_dir(args)

    # Determine checkpoint number by auto-incrementing
    log = _read_json(mission_dir / "mission-log.json")
    events = log.get("events", [])
    checkpoint_num = _get_last_checkpoint_number(events) + 1

    total = args.pending + args.in_progress + args.completed
    tokens_total = args.tokens_spent + args.tokens_remaining
    pct_consumed = round(
        (args.tokens_spent / tokens_total * 100) if tokens_total > 0 else 0.0,
        1,
    )

    # Estimate burn rate from previous checkpoints
    prev_checkpoints = [e for e in events if e.get("type") == "checkpoint"]
    if prev_checkpoints:
        last_cp_data = prev_checkpoints[-1].get("data", {})
        last_spent = last_cp_data.get("budget", {}).get("tokens_spent", 0)
        burn_rate = args.tokens_spent - last_spent
    else:
        burn_rate = args.tokens_spent

    if args.decision not in VALID_DECISIONS:
        _die(f"Error: --decision must be one of {sorted(VALID_DECISIONS)}")

    checkpoint_event = {
        "type": "checkpoint",
        "checkpoint": checkpoint_num,
        "timestamp": _now_iso(),
        "data": {
            "progress": {
                "pending": args.pending,
                "in_progress": args.in_progress,
                "completed": args.completed,
                "blocked": args.blocked,
            },
            "budget": {
                "tokens_spent": args.tokens_spent,
                "tokens_remaining": args.tokens_remaining,
                "pct_consumed": pct_consumed,
                "burn_rate_per_checkpoint": burn_rate,
            },
            "hull_summary": {
                "green": args.hull_green,
                "amber": args.hull_amber,
                "red": args.hull_red,
                "critical": args.hull_critical,
            },
            "blockers": [],
            "standing_order_violations": [],
            "admiral_decision": args.decision,
            "admiral_rationale": args.rationale,
        },
    }
    _append_event(mission_dir, checkpoint_event)

    # Build fleet-status.json from checkpoint data + available context
    battle_plan = _read_battle_plan(mission_dir)
    damage_reports = _read_damage_reports(mission_dir)

    # Build squadron status from damage reports if available
    squadron_status: list[dict[str, Any]] = []
    for report in damage_reports:
        squadron_status.append(
            {
                "ship_name": report.get("ship_name", "unknown"),
                "ship_class": None,
                "role": "captain",
                "hull_integrity_pct": report.get("hull_integrity_pct", 100),
                "hull_integrity_status": report.get("hull_integrity_status", "Green"),
                "relief_requested": report.get("relief_requested", False),
                "task_id": None,
                "task_name": None,
                "task_status": None,
            }
        )

    # If no damage reports, try to carry forward squadron from battle plan
    if not squadron_status and battle_plan.get("squadron"):
        bp_squadron = battle_plan["squadron"]
        for cap in bp_squadron.get("captains", []):
            squadron_status.append(
                {
                    "ship_name": cap.get("ship_name"),
                    "ship_class": cap.get("ship_class"),
                    "role": "captain",
                    "hull_integrity_pct": 100,
                    "hull_integrity_status": "Green",
                    "relief_requested": False,
                    "task_id": cap.get("task_id"),
                    "task_name": None,
                    "task_status": None,
                }
            )

    # Read sailing orders for outcome
    so_path = mission_dir / "sailing-orders.json"
    outcome = None
    token_limit = None
    if so_path.exists():
        sailing_orders = _read_json(so_path)
        outcome = sailing_orders.get("outcome")
        token_limit = sailing_orders.get("budget", {}).get("token_limit")

    fleet_status = {
        "version": 1,
        "mission": {
            "outcome": outcome,
            "status": "underway",
            "started_at": None,
            "checkpoint_number": checkpoint_num,
        },
        "progress": {
            "pending": args.pending,
            "in_progress": args.in_progress,
            "completed": args.completed,
            "blocked": args.blocked,
            "total": total,
        },
        "budget": {
            "tokens_spent": args.tokens_spent,
            "tokens_remaining": args.tokens_remaining,
            "pct_consumed": pct_consumed,
            "burn_rate_per_checkpoint": burn_rate,
        },
        "squadron": squadron_status,
        "blockers": [],
        "recent_events": [],
        "last_updated": _now_iso(),
    }

    # Carry forward started_at from existing fleet-status if available
    fs_path = mission_dir / "fleet-status.json"
    if fs_path.exists():
        old_fs = _read_json(fs_path)
        old_started = old_fs.get("mission", {}).get("started_at")
        if old_started:
            fleet_status = {
                **fleet_status,
                "mission": {**fleet_status["mission"], "started_at": old_started},
            }

    _write_json(fs_path, fleet_status)

    hull_summary = (
        f"{args.hull_green}G {args.hull_amber}A {args.hull_red}R {args.hull_critical}C"
    )
    print(
        f"[nelson-data] Checkpoint {checkpoint_num} recorded\n"
        f"Fleet: {args.completed}/{total} done | "
        f"Budget: {pct_consumed}% | "
        f"Hull: {hull_summary} | "
        f"Blockers: {args.blocked}"
    )


# ---------------------------------------------------------------------------
# Subcommand: stand-down
# ---------------------------------------------------------------------------


def cmd_stand_down(args: argparse.Namespace) -> None:
    """Record mission completion and write stand-down.json."""
    mission_dir = _require_mission_dir(args)

    log = _read_json(mission_dir / "mission-log.json")
    events = log.get("events", [])
    battle_plan = _read_battle_plan(mission_dir)
    tasks = battle_plan.get("tasks", [])

    # Read sailing orders for planned outcome and budget
    so_path = mission_dir / "sailing-orders.json"
    sailing_orders: dict[str, Any] = {}
    if so_path.exists():
        sailing_orders = _read_json(so_path)

    planned_outcome = sailing_orders.get("outcome", "")
    token_limit = sailing_orders.get("budget", {}).get("token_limit")

    # Auto-compute from event log
    relief_count = _count_events_of_type(events, "relief_on_station")
    violation_count = _count_events_of_type(events, "standing_order_violation")
    blockers_raised = _count_events_of_type(events, "blocker_raised")
    blockers_resolved = _count_events_of_type(events, "blocker_resolved")
    tasks_completed = _count_events_of_type(events, "task_completed")

    # Compute duration from first to last event
    timestamps = [e.get("timestamp", "") for e in events if e.get("timestamp")]
    duration_minutes = 0
    if len(timestamps) >= 2:
        try:
            parsed_times = [
                datetime.fromisoformat(ts.replace("Z", "+00:00")) for ts in timestamps
            ]
            first = min(parsed_times)
            last = max(parsed_times)
            duration_minutes = int((last - first).total_seconds() / 60)
        except (ValueError, TypeError):
            pass

    # Budget from last checkpoint
    last_checkpoint_data: dict[str, Any] = {}
    for e in reversed(events):
        if e.get("type") == "checkpoint":
            last_checkpoint_data = e.get("data", {})
            break

    budget_data = last_checkpoint_data.get("budget", {})
    tokens_consumed = budget_data.get("tokens_spent", 0)
    pct_consumed = budget_data.get("pct_consumed", 0.0)

    # Ship count: unique ship names from squadron
    squadron = battle_plan.get("squadron", {})
    captains = squadron.get("captains", [])
    ship_names = {c.get("ship_name") for c in captains}
    # Include relief ships
    for e in events:
        if e.get("type") == "relief_on_station":
            incoming = e.get("data", {}).get("incoming_ship")
            if incoming:
                ship_names.add(incoming)
    ships_used = len(ship_names)

    # Tasks by station tier
    by_station_tier: dict[str, int] = {"0": 0, "1": 0, "2": 0, "3": 0}
    for t in tasks:
        tier_key = str(t.get("station_tier", 0))
        by_station_tier[tier_key] = by_station_tier.get(tier_key, 0) + 1

    stand_down = {
        "version": 1,
        "outcome_achieved": bool(args.outcome_achieved),
        "planned_outcome": planned_outcome,
        "actual_outcome": args.actual_outcome or "",
        "success_metric_result": args.metric_result or "",
        "duration_minutes": duration_minutes,
        "budget": {
            "tokens_consumed": tokens_consumed,
            "tokens_budgeted": token_limit,
            "pct_consumed": pct_consumed,
        },
        "fleet": {
            "ships_used": ships_used,
            "reliefs": relief_count,
            "max_concurrent_ships": len(captains),
        },
        "tasks": {
            "completed": tasks_completed,
            "total": len(tasks),
            "by_station_tier": by_station_tier,
        },
        "quality": {
            "standing_order_violations": violation_count,
            "blockers_raised": blockers_raised,
            "blockers_resolved": blockers_resolved,
            "avg_blocker_duration_minutes": None,
        },
        "open_risks": [],
        "follow_ups": [],
        "mentioned_in_despatches": [],
        "reusable_patterns": {
            "adopt": list(args.adopt or []),
            "avoid": list(args.avoid or []),
        },
        "created_at": _now_iso(),
    }
    _write_json(mission_dir / "stand-down.json", stand_down)

    # Append mission_complete event
    complete_event = {
        "type": "mission_complete",
        "checkpoint": _get_last_checkpoint_number(events) + 1,
        "timestamp": _now_iso(),
        "data": {
            "outcome_achieved": bool(args.outcome_achieved),
            "tasks_completed": tasks_completed,
            "tasks_total": len(tasks),
            "total_tokens_consumed": tokens_consumed,
            "budget_pct_consumed": pct_consumed,
            "duration_minutes": duration_minutes,
            "ships_used": ships_used,
            "reliefs": relief_count,
            "standing_order_violations_total": violation_count,
        },
    }
    _append_event(mission_dir, complete_event)

    # Write final fleet-status.json
    fs_path = mission_dir / "fleet-status.json"
    if fs_path.exists():
        fleet_status = _read_json(fs_path)
    else:
        fleet_status = {"version": 1}

    final_fleet_status = {
        **fleet_status,
        "mission": {
            **fleet_status.get("mission", {}),
            "status": "complete",
            "checkpoint_number": _get_last_checkpoint_number(events) + 1,
        },
        "last_updated": _now_iso(),
    }
    _write_json(fs_path, final_fleet_status)

    # Update cross-mission memory store (best-effort, non-fatal)
    try:
        _update_patterns_store(mission_dir)
        _update_standing_order_stats(mission_dir)
    except Exception as exc:
        _err(f"Warning: failed to update memory store: {exc}")

    # Print mission summary
    achieved = "ACHIEVED" if args.outcome_achieved else "NOT ACHIEVED"
    print(
        f"[nelson-data] Mission complete — outcome {achieved}\n"
        f"Duration: {duration_minutes}m | "
        f"Budget: {pct_consumed}% consumed | "
        f"Ships: {ships_used} ({relief_count} reliefs) | "
        f"Tasks: {tasks_completed}/{len(tasks)} | "
        f"Violations: {violation_count}"
    )


# ---------------------------------------------------------------------------
# Subcommand: status
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> None:
    """Print current fleet status from fleet-status.json (read-only)."""
    raw = getattr(args, "mission_dir", None)
    if not raw:
        return  # silent no-op
    mission_dir = Path(raw)
    fs_path = mission_dir / "fleet-status.json"
    if not fs_path.exists():
        return  # silent no-op

    fs = _read_json(fs_path)
    mission = fs.get("mission", {})
    progress = fs.get("progress", {})
    budget = fs.get("budget", {})

    status = mission.get("status", "unknown")
    cp = mission.get("checkpoint_number", 0)
    completed = progress.get("completed", 0)
    total = progress.get("total", 0)
    pct = budget.get("pct_consumed", 0.0)
    spent = budget.get("tokens_spent", 0)

    squadron = fs.get("squadron", [])
    hull_counts = {"G": 0, "A": 0, "R": 0, "C": 0}
    for ship in squadron:
        hull_status = ship.get("hull_integrity_status", "Green")
        if hull_status == "Green":
            hull_counts["G"] += 1
        elif hull_status == "Amber":
            hull_counts["A"] += 1
        elif hull_status == "Red":
            hull_counts["R"] += 1
        elif hull_status == "Critical":
            hull_counts["C"] += 1

    blockers = len(fs.get("blockers", []))

    hull_str = (
        f"{hull_counts['G']}G {hull_counts['A']}A "
        f"{hull_counts['R']}R {hull_counts['C']}C"
    )

    print(
        f"[nelson-data] Status: {status} (checkpoint {cp})\n"
        f"Fleet: {completed}/{total} done | "
        f"Budget: {pct}% ({spent} tokens) | "
        f"Hull: {hull_str} | "
        f"Blockers: {blockers}"
    )
