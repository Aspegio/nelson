"""Mission lifecycle commands for Nelson data capture.

Implements the core mission workflow: init, squadron, task, plan-approved,
event, checkpoint, stand-down, and status subcommands.

No external dependencies — stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nelson_circuit_breakers import (
    compute_budget_metrics,
    format_alarm_line,
)
from nelson_circuit_breakers import (
    evaluate as evaluate_circuit_breakers,
)
from nelson_data_calibration import (
    _print_calibration_advisories,
    _update_override_calibration,
)
from nelson_data_memory import _update_patterns_store, _update_standing_order_stats
from nelson_data_utils import (
    ADMIRAL_SESSION_MARKER,
    FLEET_STATUS_EVENT_TYPES,
    FLEET_STATUS_STALENESS_THRESHOLD_SECONDS,
    JSON_INDENT,
    VALID_ADMIRALTY_OUTCOMES,
    VALID_DECISIONS,
    VALID_ESTIMATE_OUTCOME_METHODS,
    VALID_ESTIMATE_OUTCOME_STATUSES,
    VALID_EVENT_TYPES,
    VALID_HANDOFF_TYPES,
    VALID_MODES,
    _append_estimate_outcome,
    _append_event,
    _count_events_of_type,
    _die,
    _err,
    _generate_session_id,
    _get_last_checkpoint_number,
    _is_valid_session_id,
    _mission_dir_stamp,
    _now_iso,
    _parse_extra_kv,
    _read_battle_plan,
    _read_damage_reports,
    _read_json,
    _read_json_optional,
    _require_mission_dir,
    _validate_calibration_key,
    _write_json,
)

_CONFLICT_SCAN_SCRIPT = Path(__file__).resolve().parent / "nelson_conflict_scan.py"


# Per-phase recovery guidance for `cmd_recover`. UNDERWAY is intentionally
# omitted: when the mission is underway, recovery uses handoff-packet-derived
# actions instead of static guidance.
PHASE_RECOVERY_GUIDANCE: dict[str, list[str]] = {
    "SAILING_ORDERS": [
        "You are in SAILING_ORDERS phase (Step 1).",
        "Read sailing-orders.json for outcome, metric, deadline, and constraints.",
        "Decide with the user whether to conduct The Estimate before drafting the Battle Plan.",
    ],
    "ESTIMATE": [
        "You are in ESTIMATE phase (Step 2).",
        "Read sailing-orders.json and any partial estimate.md to resume the seven-question Maritime Tactical Estimate.",
        "Continue from the next unanswered question; honour the Q1 and Q3 checkpoints with the user.",
    ],
    "BATTLE_PLAN": [
        "You are in BATTLE_PLAN phase (Step 3).",
        ("Read estimate.md for commander's intent and effects, and battle-plan.md for any drafted plan."),
        (
            "Complete the Standing Order Check, then persist the final plan to "
            "{mission-dir}/battle-plan.md before advancing to Step 4."
        ),
    ],
    "FORMATION": [
        "You are in FORMATION phase (Step 4).",
        "Read battle-plan.json for tasks and squadron, and battle-plan.md for the prose plan.",
        "Confirm formation orders with the user before advancing to PERMISSION.",
    ],
    "PERMISSION": [
        "You are in PERMISSION phase (Step 5).",
        "Read battle-plan.json and battle-plan.md, then re-display the complete battle plan and squadron formation.",
        "Wait for explicit user permission before logging permission_granted and advancing to UNDERWAY.",
    ],
    "STAND_DOWN": [
        "You are in STAND_DOWN phase (Step 8).",
        "Read stand-down.json for the recorded mission summary.",
        "Verify {mission-dir}/captains-log.md exists and remove .nelson/.active-{SESSION_ID} if still present.",
    ],
}


BATTLE_PLAN_MD_REQUIRED_PHASES: frozenset[str] = frozenset({"BATTLE_PLAN", "FORMATION", "PERMISSION"})


# ---------------------------------------------------------------------------
# Internal helper: _do_init (used by cmd_init and cmd_headless)
# ---------------------------------------------------------------------------


def _do_init(  # noqa: PLR0913 -- args mirror the sailing-orders.json schema; collapsing them into a config dict would obscure the contract. Refactor (e.g. SailingOrders dataclass) tracked in nelson-e6j.
    outcome: str,
    metric: str,
    deadline: str,
    token_budget: int | None = None,
    time_limit: int | None = None,
    constraints: list[str] | None = None,
    out_of_scope: list[str] | None = None,
    stop_criteria: list[str] | None = None,
    handoff_artifacts: list[str] | None = None,
    circuit_breakers: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> Path:
    """Create mission directory and write initial JSON files.  Returns the path.

    Owns the full mission-directory contract: picks (or accepts) a session id,
    creates ``.nelson/missions/{stamp}_{session_id}/`` with the two standard
    subdirectories, writes ``sailing-orders.json``, ``mission-log.json``, and
    ``fleet-status.json``, and writes the ``.nelson/.active-{session_id}``
    marker file consumed by hooks and recovery logic.
    """
    if session_id is None:
        session_id = _generate_session_id()
    elif not _is_valid_session_id(session_id):
        _die(f"Error: --session-id must be exactly 8 lowercase hex characters (got: {session_id!r})")

    nelson_root = Path(".nelson")
    base = nelson_root / "missions" / f"{_mission_dir_stamp()}_{session_id}"
    base.mkdir(parents=True, exist_ok=True)
    (base / "damage-reports").mkdir(exist_ok=True)
    (base / "turnover-briefs").mkdir(exist_ok=True)

    sailing_orders = {
        "version": 1,
        "outcome": outcome,
        "success_metric": metric,
        "deadline": deadline,
        "budget": {
            "token_limit": token_budget,
            "time_limit_minutes": time_limit,
        },
        "constraints": list(constraints or []),
        "out_of_scope": list(out_of_scope or []),
        "stop_criteria": list(stop_criteria or []),
        "handoff_artifacts": list(handoff_artifacts or []),
        "circuit_breakers": dict(circuit_breakers) if circuit_breakers else {},
        "created_at": _now_iso(),
    }

    fleet_status: dict[str, Any] = {
        "version": 1,
        "mission": {
            "outcome": outcome,
            "status": "forming",
            "phase": "SAILING_ORDERS",
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
            "tokens_remaining": token_budget,
            "pct_consumed": 0.0,
            "burn_rate_per_checkpoint": 0,
        },
        "squadron": [],
        "blockers": [],
        "recent_events": ["Mission initialized"],
        "last_updated": _now_iso(),
    }

    _write_json(base / "sailing-orders.json", sailing_orders)
    _write_json(base / "mission-log.json", {"version": 1, "events": []})
    _write_json(base / "fleet-status.json", fleet_status)

    # Active-session marker — consumed by hooks/nelson_hooks.py::_find_mission_dir
    # and nelson_data_lifecycle._find_active_mission for recovery.
    sidecar = nelson_root / f".active-{session_id}"
    sidecar.write_text(str(base) + "\n", encoding="utf-8")

    return base


# ---------------------------------------------------------------------------
# Subcommand: init
# ---------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> None:
    """Create mission directory and write sailing-orders.json."""
    base = _do_init(
        outcome=args.outcome,
        metric=args.metric,
        deadline=args.deadline,
        token_budget=args.token_budget,
        time_limit=getattr(args, "time_limit", None),
        constraints=getattr(args, "constraints", None),
        out_of_scope=getattr(args, "out_of_scope", None),
        stop_criteria=getattr(args, "stop_criteria", None),
        handoff_artifacts=getattr(args, "handoff_artifacts", None),
        session_id=getattr(args, "session_id", None),
    )

    # Print the mission directory path (consumed by admiral).
    # The trailing path segment is "{stamp}_{session_id}" — callers that
    # need the session id can split on the last underscore.
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

    # Carry forward existing phase from fleet-status if available
    existing_phase = None
    existing_started_at = _now_iso()
    fs_path_check = mission_dir / "fleet-status.json"
    if fs_path_check.exists():
        old_fs = _read_json(fs_path_check)
        existing_phase = old_fs.get("mission", {}).get("phase")
        existing_started_at = old_fs.get("mission", {}).get("started_at", existing_started_at)

    fleet_status = {
        "version": 1,
        "mission": {
            "outcome": None,
            "status": "forming",
            "phase": existing_phase,
            "started_at": existing_started_at,
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
        f"{len(captains)} captains" + (f", red cell {args.red_cell}" if args.red_cell else "")
    )


# ---------------------------------------------------------------------------
# Subcommand: task
# ---------------------------------------------------------------------------


def cmd_task(args: argparse.Namespace) -> None:
    """Add a task to battle-plan.json."""
    mission_dir = _require_mission_dir(args)

    deps: list[int] = []
    if args.deps:
        for raw_dep in args.deps.split(","):
            d = raw_dep.strip()
            if d:
                try:
                    deps.append(int(d))
                except ValueError:
                    _die(f"Error: dependency must be an integer, got: {d}")

    files: list[str] = []
    if args.files:
        files = [f.strip() for f in args.files.split(",") if f.strip()]

    mod_targets: list[str] = []
    if getattr(args, "modification_targets", None):
        mod_targets = [m.strip() for m in args.modification_targets.split(",") if m.strip()]

    task_type_raw = getattr(args, "task_type", None)
    task_type: str | None = None
    if task_type_raw:
        try:
            task_type = _validate_calibration_key(task_type_raw, "task_type")
        except ValueError as exc:
            _die(f"Error: invalid --task-type: {exc}")

    task: dict[str, Any] = {
        "id": args.id,
        "name": args.name,
        "owner": args.owner,
        "deliverable": args.deliverable,
        "dependencies": deps,
        "dependents": [],
        "station_tier": args.station_tier,
        "file_ownership": files,
        "modification_targets": mod_targets,
        "validation_required": args.validation or None,
        "rollback_note_required": bool(args.rollback_note),
        "admiralty_action_required": bool(args.admiralty_action),
        "task_type": task_type,
    }

    bp_path = mission_dir / "battle-plan.json"
    if bp_path.exists():
        battle_plan = _read_json(bp_path)
    else:
        battle_plan = {"version": 1}

    existing_tasks = list(battle_plan.get("tasks", []))
    new_tasks = [*existing_tasks, task]

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

    # Emit trust calibration advisories (stderr, best-effort, non-fatal).
    try:
        _print_calibration_advisories(mission_dir, tasks)
    except (OSError, ValueError, KeyError) as exc:
        _err(f"Warning: trust calibration advisory failed: {exc}")

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

    existing_mission = fleet_status.get("mission", {})
    new_fleet_status = {
        **fleet_status,
        "mission": {
            **existing_mission,
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
            _die(f"Cycle detected in task dependencies (task IDs involved: {cycle_members})")
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
# Subcommand: skip-estimate
# ---------------------------------------------------------------------------


def cmd_skip_estimate(args: argparse.Namespace) -> None:
    """Record that the ESTIMATE phase is being skipped for this mission.

    Writes ``estimate_skipped: true`` and ``estimate_skip_reason`` into
    ``sailing-orders.json`` and logs an ``estimate_skipped`` mission event.
    Allows the phase exit validator to advance SAILING_ORDERS/ESTIMATE to
    BATTLE_PLAN without requiring an ``estimate.md`` file.
    """
    mission_dir = _require_mission_dir(args)

    reason = (args.reason or "").strip()
    if not reason:
        _die("Error: --reason is required and must be non-empty.")

    so_path = mission_dir / "sailing-orders.json"
    if not so_path.exists():
        _die("Error: sailing-orders.json does not exist. Run 'init' before skipping the estimate.")

    sailing_orders = _read_json(so_path)
    new_sailing_orders = {
        **sailing_orders,
        "estimate_skipped": True,
        "estimate_skip_reason": reason,
    }
    _write_json(so_path, new_sailing_orders)

    event = {
        "type": "estimate_skipped",
        "checkpoint": 0,
        "timestamp": _now_iso(),
        "data": {"reason": reason},
    }
    _append_event(mission_dir, event)

    print(f"[nelson-data] Estimate skipped: {reason}")


# ---------------------------------------------------------------------------
# Subcommand: estimate-outcome
# ---------------------------------------------------------------------------


def cmd_record_estimate_outcome(args: argparse.Namespace) -> None:
    """Record a per-criterion verification outcome for The Estimate.

    Appends to ``{mission-dir}/estimate-outcomes.json`` and logs an
    ``estimate_outcome_recorded`` event. Captains call this at the moment
    they verify a criterion during UNDERWAY; the quarterdeck aggregates
    at stand-down.
    """
    mission_dir = _require_mission_dir(args)

    status = args.status
    if status not in VALID_ESTIMATE_OUTCOME_STATUSES:
        _die(f"Error: invalid status '{status}'. Valid: {', '.join(sorted(VALID_ESTIMATE_OUTCOME_STATUSES))}")

    method = args.method
    if method not in VALID_ESTIMATE_OUTCOME_METHODS:
        _die(f"Error: invalid method '{method}'. Valid: {', '.join(sorted(VALID_ESTIMATE_OUTCOME_METHODS))}")

    effect_id = (args.effect_id or "").strip()
    criterion_id = (args.criterion_id or "").strip()
    recorded_by = (args.recorded_by or "").strip()
    if not effect_id or not criterion_id or not recorded_by:
        _die("Error: --effect-id, --criterion-id and --recorded-by are required and must be non-empty.")

    outcome = {
        "effect_id": effect_id,
        "criterion_id": criterion_id,
        "status": status,
        "method": method,
        "evidence": args.evidence or "",
        "recorded_by": recorded_by,
        "recorded_at": _now_iso(),
    }
    _append_estimate_outcome(mission_dir, outcome)

    event = {
        "type": "estimate_outcome_recorded",
        "checkpoint": 0,
        "timestamp": _now_iso(),
        "data": {
            "effect_id": effect_id,
            "criterion_id": criterion_id,
            "status": status,
            "method": method,
            "recorded_by": recorded_by,
        },
    }
    _append_event(mission_dir, event)

    print(
        f"[nelson-data] Estimate outcome recorded: {effect_id}/{criterion_id} {status} via {method} (by {recorded_by})"
    )


# ---------------------------------------------------------------------------
# Subcommand: event
# ---------------------------------------------------------------------------


def _resolve_ship_class(mission_dir: Path, owner: str | None) -> str | None:
    """Return *owner*'s ship_class from fleet-status.json, or None if unknown."""
    if not owner:
        return None
    fs_path = mission_dir / "fleet-status.json"
    if not fs_path.exists():
        return None
    fleet_status = _read_json(fs_path)
    for ship in fleet_status.get("squadron", []):
        if ship.get("ship_name") == owner:
            return ship.get("ship_class")
    return None


def _validate_optional_calibration_key(value: str | None, field: str) -> str | None:
    """Validate a non-empty calibration key, exiting fatally on a bad value.

    Empty/None passes through unchanged (the attribute is simply absent).
    """
    if not value:
        return value
    try:
        return _validate_calibration_key(value, field)
    except ValueError as exc:
        _die(f"Error: invalid {field}: {exc}")
    return None


def _resolve_calibration_attrs(mission_dir: Path, task: dict[str, Any], task_id: int) -> tuple[str | None, str | None]:
    """Resolve and validate (task_type, ship_class) for an admiralty decision.

    task_type comes from the battle-plan task; ship_class is resolved via the
    task owner against fleet-status.json. Both are validated as calibration
    keys (a bad value is fatal). A missing task_type is a non-fatal warning:
    the decision is still recorded, it just won't feed the calibration store.
    """
    task_type = _validate_optional_calibration_key(task.get("task_type"), "task_type")
    ship_class = _validate_optional_calibration_key(_resolve_ship_class(mission_dir, task.get("owner")), "ship_class")
    if not task_type:
        _err(f"Warning: task {task_id} has no task_type — this decision will not feed calibration.")
    return task_type, ship_class


def cmd_admiralty_decision(args: argparse.Namespace) -> None:
    """Record an admiralty action completion with a decision outcome.

    Writes an ``admiralty_action_completed`` event whose data captures the
    decision_type, task_id, task_type (resolved from battle-plan.json), and
    ship_class (resolved via the task owner against fleet-status.json
    squadron). Calibration aggregation runs at stand-down and consumes these
    events.

    ``--recorded-by`` is required (mirrors ``record-effect-outcome``) and is
    captured into ``data.recorded_by`` for later audit. The presence of the
    admiral session marker at the time of recording is captured into
    ``data.session_marker_present`` so a v2 calibration pipeline can
    distinguish admiral-confirmed decisions from self-reported ones.
    """
    mission_dir = _require_mission_dir(args)

    decision_type = args.decision_type
    if decision_type not in VALID_ADMIRALTY_OUTCOMES:
        _die(f"Error: invalid decision-type '{decision_type}'. Valid: {', '.join(sorted(VALID_ADMIRALTY_OUTCOMES))}")

    recorded_by = (getattr(args, "recorded_by", None) or "").strip()
    if not recorded_by:
        _die("Error: --recorded-by is required and must be non-empty.")

    task_id = int(args.task_id)
    bp_path = mission_dir / "battle-plan.json"
    if not bp_path.exists():
        _die("Error: battle-plan.json does not exist. Run 'task' first.")
    battle_plan = _read_json(bp_path)
    task = next(
        (t for t in battle_plan.get("tasks", []) if t.get("id") == task_id),
        None,
    )
    if task is None:
        _die(f"Error: task_id {task_id} not found in battle-plan.json")

    task_type, ship_class = _resolve_calibration_attrs(mission_dir, task, task_id)

    marker_path = mission_dir.parent.parent / ADMIRAL_SESSION_MARKER
    session_marker_present = marker_path.exists()

    log = _read_json(mission_dir / "mission-log.json")
    checkpoint = _get_last_checkpoint_number(log.get("events", []))

    data: dict[str, Any] = {
        "task_id": task_id,
        "decision_type": decision_type,
        "recorded_by": recorded_by,
        "session_marker_present": session_marker_present,
    }
    if task_type:
        data["task_type"] = task_type
    if ship_class:
        data["ship_class"] = ship_class
    notes = (getattr(args, "notes", None) or "").strip()
    if notes:
        data["notes"] = notes

    event = {
        "type": "admiralty_action_completed",
        "checkpoint": checkpoint,
        "timestamp": _now_iso(),
        "data": data,
    }
    _append_event(mission_dir, event)

    print(f"[nelson-data] Admiralty decision recorded: task {task_id} -> {decision_type}")


def cmd_event(args: argparse.Namespace, extra: list[str]) -> None:
    """Log a mission event to mission-log.json."""
    mission_dir = _require_mission_dir(args)

    event_type = args.type
    if event_type not in VALID_EVENT_TYPES:
        _die(f"Error: invalid event type '{event_type}'. Valid types: {', '.join(sorted(VALID_EVENT_TYPES))}")

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
    event_id = _append_event(mission_dir, event)
    _update_fleet_status_from_event(mission_dir, event, event_id)

    print(f"[nelson-data] Event logged: {event_type} (checkpoint {checkpoint})")


# ---------------------------------------------------------------------------
# Subcommand: checkpoint
# ---------------------------------------------------------------------------


def cmd_checkpoint(args: argparse.Namespace) -> None:  # noqa: C901, PLR0912 -- end-to-end checkpoint command; refactor tracked in nelson-e6j
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
    if so_path.exists():
        sailing_orders = _read_json(so_path)
        outcome = sailing_orders.get("outcome")

    # Carry forward existing phase from fleet-status
    existing_phase = None
    fs_path = mission_dir / "fleet-status.json"
    if fs_path.exists():
        old_fs = _read_json(fs_path)
        existing_phase = old_fs.get("mission", {}).get("phase")

    budget_metrics = compute_budget_metrics(
        tokens_spent=args.tokens_spent,
        tokens_remaining=args.tokens_remaining,
        completed=args.completed,
        total=total,
    )

    fleet_status = {
        "version": 1,
        "mission": {
            "outcome": outcome,
            "status": "underway",
            "phase": existing_phase,
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
            "burn_rate_per_task": budget_metrics["burn_rate_per_task"],
            "projected_budget_at_completion": budget_metrics["projected_budget_at_completion"],
        },
        "squadron": squadron_status,
        "blockers": [],
        "recent_events": [],
        "last_updated": _now_iso(),
    }

    # Carry forward started_at from existing fleet-status if available
    if fs_path.exists():
        old_started = old_fs.get("mission", {}).get("started_at")
        if old_started:
            fleet_status = {
                **fleet_status,
                "mission": {**fleet_status["mission"], "started_at": old_started},
            }

    _write_json(fs_path, fleet_status)

    # Evaluate automated circuit breakers against the freshly-written state.
    # Trips are advisory — surface them to the admiral via stdout and append
    # structured events so post-mission analysis can see what fired.
    sailing_orders_for_breakers = _read_json_optional(so_path) if so_path.exists() else None
    trips = evaluate_circuit_breakers(
        fleet_status=fleet_status,
        sailing_orders=sailing_orders_for_breakers,
        mission_log_events=[*events, checkpoint_event],
        now_iso=_now_iso(),
    )
    for trip in trips:
        _append_event(
            mission_dir,
            {
                "type": "circuit_breaker_tripped",
                "checkpoint": checkpoint_num,
                "timestamp": _now_iso(),
                "data": trip.to_event_data(),
            },
        )

    hull_summary = f"{args.hull_green}G {args.hull_amber}A {args.hull_red}R {args.hull_critical}C"
    print(
        f"[nelson-data] Checkpoint {checkpoint_num} recorded\n"
        f"Fleet: {args.completed}/{total} done | "
        f"Budget: {pct_consumed}% | "
        f"Hull: {hull_summary} | "
        f"Blockers: {args.blocked}"
    )
    for trip in trips:
        print(format_alarm_line(trip))


# ---------------------------------------------------------------------------
# Subcommand: stand-down
# ---------------------------------------------------------------------------


def cmd_stand_down(args: argparse.Namespace) -> None:  # noqa: C901, PLR0912, PLR0915 -- end-to-end stand-down command; refactor tracked in nelson-e6j
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
            parsed_times = [datetime.fromisoformat(ts.replace("Z", "+00:00")) for ts in timestamps]
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
            "phase": "STAND_DOWN",
            "checkpoint_number": _get_last_checkpoint_number(events) + 1,
        },
        "last_updated": _now_iso(),
    }
    _write_json(fs_path, final_fleet_status)

    # Update cross-mission memory store (best-effort, non-fatal)
    try:
        _update_patterns_store(mission_dir)
        _update_standing_order_stats(mission_dir)
        _update_override_calibration(mission_dir)
    except Exception as exc:
        _err(f"Warning: failed to update memory store: {exc}")

    # Best-effort cleanup of admiral session marker (mission-scoped lifecycle).
    # Marker lives at .nelson/<ADMIRAL_SESSION_MARKER>, two levels up from
    # mission_dir (.nelson/missions/<id>/).
    try:
        (mission_dir.parent.parent / ADMIRAL_SESSION_MARKER).unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass

    # Best-effort cleanup of the .active-<session_id> recovery sidecar written
    # by _do_init. The mission dir is named "{stamp}_{session_id}", so the
    # session id is the trailing segment. Without this, stale markers
    # accumulate in .nelson/ across missions (nelson-a06).
    session_id = mission_dir.name.rsplit("_", 1)[-1]
    try:
        (mission_dir.parent.parent / f".active-{session_id}").unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass

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
    raw = getattr(args, "mission_dir", None) or ""
    if not raw.strip():
        # Auto-detect latest mission directory when none provided.
        missions_root = Path(".nelson/missions")
        if not missions_root.is_dir():
            print("No active missions")
            return
        candidates = sorted(
            (d for d in missions_root.iterdir() if d.is_dir()),
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            print("No active missions")
            return
        raw = str(candidates[0])
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

    hull_str = f"{hull_counts['G']}G {hull_counts['A']}A {hull_counts['R']}R {hull_counts['C']}C"

    print(
        f"[nelson-data] Status: {status} (checkpoint {cp})\n"
        f"Fleet: {completed}/{total} done | "
        f"Budget: {pct}% ({spent} tokens) | "
        f"Hull: {hull_str} | "
        f"Blockers: {blockers}"
    )


# ---------------------------------------------------------------------------
# Internal helpers for composite commands (form, headless)
# ---------------------------------------------------------------------------


def _parse_captain_specs(specs: list[str]) -> list[dict[str, Any]]:
    """Parse colon-delimited captain specs into dicts."""
    captains: list[dict[str, Any]] = []
    for spec in specs:
        parts = spec.split(":")
        if len(parts) != 4:
            _die(f"Error: captain spec must be 'name:class:model:task_id', got: {spec}")
        ship_name, ship_class, model, task_id_str = parts
        try:
            task_id = int(task_id_str)
        except ValueError:
            _die(f"Error: task_id must be an integer, got: {task_id_str}")
            return []  # unreachable but helps type checkers
        captains.append(
            {
                "ship_name": ship_name,
                "ship_class": ship_class,
                "model": model,
                "task_id": task_id,
            }
        )
    return captains


def _register_squadron(  # noqa: PLR0913 -- args are shaped by the squadron-registration CLI surface (admiral + admiral_model + captains + mode + optional red-cell pair); merging admiral/red-cell into dicts would just move the same kwargs to the caller.
    mission_dir: Path,
    admiral: str,
    admiral_model: str,
    captains: list[dict[str, Any]],
    mode: str = "subagents",
    red_cell: str | None = None,
    red_cell_model: str | None = None,
) -> None:
    """Register squadron in battle-plan.json and fleet-status.json."""
    squadron: dict[str, Any] = {
        "mode": mode,
        "admiral": {"ship_name": admiral, "model": admiral_model},
        "captains": captains,
    }
    if red_cell:
        squadron["red_cell"] = {
            "ship_name": red_cell,
            "model": red_cell_model or "haiku",
        }

    bp_path = mission_dir / "battle-plan.json"
    if bp_path.exists():
        battle_plan = _read_json(bp_path)
    else:
        battle_plan = {"version": 1}

    new_battle_plan = {**battle_plan, "squadron": squadron, "created_at": _now_iso()}
    _write_json(bp_path, new_battle_plan)

    event = {
        "type": "squadron_formed",
        "checkpoint": 0,
        "timestamp": _now_iso(),
        "data": {
            "captain_count": len(captains),
            "has_red_cell": red_cell is not None,
            "execution_mode": mode,
            "standing_order_check": {"triggered": [], "remedies": []},
        },
    }
    _append_event(mission_dir, event)

    # Build initial fleet-status squadron list
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

    fs_path = mission_dir / "fleet-status.json"
    if fs_path.exists():
        fleet_status = _read_json(fs_path)
    else:
        fleet_status = {"version": 1}

    so_path = mission_dir / "sailing-orders.json"
    outcome = None
    if so_path.exists():
        so = _read_json(so_path)
        outcome = so.get("outcome")

    new_fleet_status = {
        **fleet_status,
        "mission": {
            **fleet_status.get("mission", {}),
            "outcome": outcome,
            "status": "forming",
        },
        "squadron": squadron_list,
        "recent_events": [f"Squadron formed: {len(captains)} captains"],
        "last_updated": _now_iso(),
    }
    _write_json(fs_path, new_fleet_status)


def _build_task_record(  # noqa: PLR0913 -- params mirror the task record schema 1:1 (id, name, owner, deliverable, deps, station_tier, files, …); a TaskRecord dataclass is the right refactor and is tracked in nelson-e6j.
    task_id: int,
    name: str,
    owner: str,
    deliverable: str,
    deps: list[int],
    station_tier: int,
    files: list[str],
    modification_targets: list[str] | None = None,
    validation: str | None = None,
    rollback_note: bool = False,
    admiralty_action: bool = False,
    task_type: str | None = None,
) -> dict[str, Any]:
    """Build a task dict from typed parameters."""
    return {
        "id": task_id,
        "name": name,
        "owner": owner,
        "deliverable": deliverable,
        "dependencies": list(deps),
        "dependents": [],
        "station_tier": station_tier,
        "file_ownership": list(files),
        "modification_targets": list(modification_targets or []),
        "validation_required": validation or None,
        "rollback_note_required": rollback_note,
        "admiralty_action_required": admiralty_action,
        "task_type": task_type or None,
    }


def _register_tasks(mission_dir: Path, tasks: list[dict[str, Any]]) -> None:
    """Write a list of tasks to battle-plan.json (bulk registration)."""
    bp_path = mission_dir / "battle-plan.json"
    if bp_path.exists():
        battle_plan = _read_json(bp_path)
    else:
        battle_plan = {"version": 1}

    existing_tasks = list(battle_plan.get("tasks", []))
    all_tasks = existing_tasks + list(tasks)
    all_tasks = _recompute_dependents(all_tasks)

    new_battle_plan = {**battle_plan, "tasks": all_tasks}
    _write_json(bp_path, new_battle_plan)


def _finalize_plan(mission_dir: Path) -> dict[str, Any]:
    """Finalize battle plan: compute DAG metrics, log event, update fleet status.

    Returns a dict with ``task_count``, ``parallel_tracks``, and
    ``critical_path_length``.
    """
    bp_path = mission_dir / "battle-plan.json"
    if not bp_path.exists():
        _die("Error: battle-plan.json does not exist. Run 'squadron' and 'task' first.")

    battle_plan = _read_json(bp_path)
    tasks = battle_plan.get("tasks", [])

    if not tasks:
        _die("Error: no tasks in battle-plan.json. Run 'task' to add tasks first.")

    parallel_tracks, critical_path_length = _compute_dag_metrics(tasks)

    new_battle_plan = {**battle_plan, "amended_at": None}
    _write_json(bp_path, new_battle_plan)

    event = {
        "type": "battle_plan_approved",
        "checkpoint": 0,
        "timestamp": _now_iso(),
        "data": {
            "task_count": len(tasks),
            "parallel_tracks": parallel_tracks,
            "critical_path_length": critical_path_length,
            "standing_order_check": {"triggered": [], "remedies": []},
        },
    }
    _append_event(mission_dir, event)

    fs_path = mission_dir / "fleet-status.json"
    if fs_path.exists():
        fleet_status = _read_json(fs_path)
    else:
        fleet_status = {"version": 1}

    existing_mission = fleet_status.get("mission", {})
    new_fleet_status = {
        **fleet_status,
        "mission": {
            **existing_mission,
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

    return {
        "task_count": len(tasks),
        "parallel_tracks": parallel_tracks,
        "critical_path_length": critical_path_length,
    }


# ---------------------------------------------------------------------------
# Subcommand: handoff
# ---------------------------------------------------------------------------


def _parse_partial_outputs(raw: list[str] | None) -> list[dict[str, str]]:
    """Parse colon-delimited partial output specs into structured dicts.

    Format: "subtask:progress:notes" — notes may contain colons.
    """
    results: list[dict[str, str]] = []
    for po in raw or []:
        parts = po.split(":", 2)
        if len(parts) != 3:
            _die(f"Error: --partial-output must be 'subtask:progress:notes', got: {po}")
        results.append({"subtask": parts[0], "progress": parts[1], "notes": parts[2]})
    return results


def _parse_relief_chain(raw: list[str] | None) -> list[dict[str, str]]:
    """Parse colon-delimited relief chain entries into structured dicts.

    Format: "ship:reason:handoff_time" — handoff_time may contain colons.
    """
    entries: list[dict[str, str]] = []
    for entry in raw or []:
        parts = entry.split(":", 2)
        if len(parts) != 3:
            _die(f"Error: --relief-entry must be 'ship:reason:time', got: {entry}")
        entries.append({"ship": parts[0], "reason": parts[1], "handoff_time": parts[2]})
    return entries


def _sanitize_ship_name(name: str) -> str:
    """Sanitize a ship name for use in filenames.

    Replaces all non-alphanumeric characters (except hyphens and
    underscores) with hyphens to prevent path traversal.
    """
    return re.sub(r"[^a-zA-Z0-9_-]", "-", name)


def cmd_handoff(args: argparse.Namespace) -> None:
    """Write a typed handoff packet and log the relief event."""
    mission_dir = _require_mission_dir(args)

    if args.handoff_type not in VALID_HANDOFF_TYPES:
        _die(f"Error: --handoff-type must be one of {sorted(VALID_HANDOFF_TYPES)}")

    partial_outputs = _parse_partial_outputs(args.partial_output)
    relief_chain = _parse_relief_chain(args.relief_entry)

    if len(relief_chain) > 3:
        _die("Error: relief chain exceeds maximum of 3 entries")

    next_steps = list(args.next_step or [])
    if not next_steps:
        _die("Error: at least one --next-step is required")

    file_ownership = list(args.file_ownership or [])
    bp = _read_battle_plan(mission_dir)
    for t in bp.get("tasks", []):
        if t.get("id") == args.task_id and t.get("station_tier", 0) > 0:
            if not file_ownership:
                _die("Error: --file-ownership is required for implementation tasks (station_tier > 0)")
            break

    log = _read_json(mission_dir / "mission-log.json")
    checkpoint_num = _get_last_checkpoint_number(log.get("events", []))

    now_dt = datetime.now(UTC)
    now = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    now_file = now_dt.strftime("%Y%m%dT%H%M%SZ")

    packet = {
        "version": 1,
        "ship_name": args.ship_name,
        "task_id": args.task_id,
        "task_name": args.task_name,
        "handoff_type": args.handoff_type,
        "state": {
            "completed_subtasks": list(args.completed_subtask or []),
            "partial_outputs": partial_outputs,
            "known_blockers": list(args.known_blocker or []),
            "file_ownership": file_ownership,
            "next_steps": next_steps,
            "open_decisions": list(args.open_decision or []),
        },
        "context": {
            "hull_at_handoff": args.hull_at_handoff,
            "tokens_consumed": args.tokens_consumed,
            "checkpoint_number": checkpoint_num,
            "key_findings": list(args.key_finding or []),
        },
        "relief_chain": relief_chain,
        "created_at": now,
    }

    safe_name = _sanitize_ship_name(args.ship_name)
    packet_filename = f"{safe_name}-{now_file}.json"
    packet_path = mission_dir / "turnover-briefs" / packet_filename
    _write_json(packet_path, packet)

    event = {
        "type": "relief_on_station",
        "checkpoint": checkpoint_num,
        "timestamp": now,
        "data": {
            "outgoing_ship": args.ship_name,
            "incoming_ship": args.incoming_ship or None,
            "reason": args.handoff_type,
            "handoff_packet_path": str(packet_path),
        },
    }
    _append_event(mission_dir, event)

    print(
        f"[nelson-data] Handoff packet written: {packet_filename}\n"
        f"Ship: {args.ship_name} | Task: {args.task_id} | "
        f"Type: {args.handoff_type}"
    )


# ---------------------------------------------------------------------------
# Subcommand: form (composite formation)
# ---------------------------------------------------------------------------


def _validate_plan_json(plan: dict) -> None:  # noqa: C901, PLR0912 -- schema validator with many shape checks; refactor tracked in nelson-e6j
    """Validate plan JSON structure.  Calls _die on failure."""
    if "squadron" not in plan:
        _die("Error: plan JSON must contain a 'squadron' key.")
    sq = plan["squadron"]
    if "admiral" not in sq or "captains" not in sq:
        _die("Error: squadron must contain 'admiral' and 'captains'.")

    admiral = sq["admiral"]
    if not isinstance(admiral, dict):
        _die(
            "Error: squadron.admiral must be an object with 'ship_name' and "
            '\'model\' keys, e.g. {"ship_name": "HMS Victory", "model": "opus"}; '
            f"got {type(admiral).__name__}."
        )
    admiral_missing = {"ship_name", "model"} - set(admiral.keys())
    if admiral_missing:
        _die(f"Error: squadron.admiral is missing required fields: {sorted(admiral_missing)}")

    if not sq["captains"]:
        _die("Error: squadron must have at least one captain.")
    required_captain_fields = {"ship_name", "ship_class", "model", "task_id"}
    for i, cap in enumerate(sq["captains"]):
        if not isinstance(cap, dict):
            _die(
                f"Error: squadron.captains[{i}] must be an object with "
                f"{sorted(required_captain_fields)} keys; got {type(cap).__name__}."
            )
        cap_missing = required_captain_fields - set(cap.keys())
        if cap_missing:
            _die(f"Error: squadron.captains[{i}] is missing required fields: {sorted(cap_missing)}")

    red_cell = sq.get("red_cell")
    if red_cell is not None:
        if not isinstance(red_cell, dict):
            _die(
                "Error: squadron.red_cell must be an object with a 'ship_name' "
                f"key (and optional 'model'); got {type(red_cell).__name__}."
            )
        if "ship_name" not in red_cell:
            _die("Error: squadron.red_cell is missing required field: 'ship_name'.")

    tasks = plan.get("tasks", [])
    if not tasks:
        _die("Error: plan JSON must contain a non-empty 'tasks' array.")
    required_task_fields = {"id", "name", "owner", "deliverable", "station_tier"}
    for i, task in enumerate(tasks):
        missing = required_task_fields - set(task.keys())
        if missing:
            _die(f"Error: task {i} is missing required fields: {sorted(missing)}")


def _run_conflict_scan(battle_plan_path: Path) -> dict[str, Any]:
    """Run nelson_conflict_scan.py and return structured result."""
    if not _CONFLICT_SCAN_SCRIPT.exists():
        return {"clean": True, "skipped": True, "stdout": "conflict scan script not found"}
    result = subprocess.run(  # noqa: S603 -- args are repo-internal paths, sys.executable is trusted
        [sys.executable, str(_CONFLICT_SCAN_SCRIPT), "--plan", str(battle_plan_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    has_warning = "[!] WARNING" in result.stdout
    return {
        "clean": not has_warning,
        "exit_code": result.returncode,
        "stdout": result.stdout.strip(),
    }


def _do_form(
    mission_dir: Path,
    plan: dict,
    mode: str = "subagents",
) -> dict[str, Any]:
    """Execute the full formation sequence.  Returns a summary dict."""
    tasks = plan["tasks"]
    sq = plan["squadron"]
    mode = plan.get("mode", mode)

    task_records = [
        _build_task_record(
            task_id=t["id"],
            name=t["name"],
            owner=t["owner"],
            deliverable=t["deliverable"],
            deps=list(t.get("dependencies", [])),
            station_tier=t["station_tier"],
            files=list(t.get("file_ownership", [])),
            modification_targets=list(t.get("modification_targets", [])),
            validation=t.get("validation_required"),
            rollback_note=bool(t.get("rollback_note_required", False)),
            admiralty_action=bool(t.get("admiralty_action_required", False)),
            task_type=t.get("task_type"),
        )
        for t in tasks
    ]

    _err(f"[nelson-data] Registering {len(task_records)} tasks...")
    _register_tasks(mission_dir, task_records)

    admiral = sq["admiral"]
    captains = sq["captains"]
    red_cell = sq.get("red_cell")

    _err(f"[nelson-data] Forming squadron: {admiral['ship_name']}, {len(captains)} captains...")
    _register_squadron(
        mission_dir=mission_dir,
        admiral=admiral["ship_name"],
        admiral_model=admiral["model"],
        captains=captains,
        mode=mode,
        red_cell=red_cell["ship_name"] if red_cell else None,
        red_cell_model=red_cell.get("model") if red_cell else None,
    )

    _err("[nelson-data] Finalizing battle plan...")
    metrics = _finalize_plan(mission_dir)

    _err("[nelson-data] Running conflict scan...")
    scan_result = _run_conflict_scan(mission_dir / "battle-plan.json")

    return {
        "status": "ok",
        "mission_dir": str(mission_dir),
        "tasks_registered": len(task_records),
        "squadron": {
            "admiral": admiral["ship_name"],
            "captains": len(captains),
            "mode": mode,
            "has_red_cell": red_cell is not None,
        },
        "dag_metrics": {
            "parallel_tracks": metrics["parallel_tracks"],
            "critical_path_length": metrics["critical_path_length"],
        },
        "conflict_scan": scan_result,
    }


def cmd_form(args: argparse.Namespace) -> None:
    """Composite formation: register tasks, squadron, finalize plan, scan conflicts."""
    mission_dir = _require_mission_dir(args)

    plan_path = Path(args.plan)
    if not plan_path.exists():
        _die(f"Error: plan file does not exist: {plan_path}")

    plan = _read_json(plan_path)
    _validate_plan_json(plan)

    summary = _do_form(mission_dir, plan, mode=args.mode or "subagents")

    print(json.dumps(summary, indent=JSON_INDENT))


# ---------------------------------------------------------------------------
# Subcommand: headless (init + form)
# ---------------------------------------------------------------------------


def cmd_headless(args: argparse.Namespace) -> None:
    """Headless mission: create mission directory and run full formation."""
    so_path = Path(args.sailing_orders)
    if not so_path.exists():
        _die(f"Error: sailing orders file does not exist: {so_path}")

    bp_path = Path(args.battle_plan)
    if not bp_path.exists():
        _die(f"Error: battle plan file does not exist: {bp_path}")

    so_data = _read_json(so_path)
    plan_data = _read_json(bp_path)
    _validate_plan_json(plan_data)

    budget_block = so_data.get("budget") if isinstance(so_data.get("budget"), dict) else {}
    mission_dir = _do_init(
        outcome=so_data.get("outcome", ""),
        metric=so_data.get("metric", so_data.get("success_metric", "")),
        deadline=so_data.get("deadline", "this_session"),
        token_budget=budget_block.get("token_limit", so_data.get("token_budget")),
        time_limit=budget_block.get("time_limit_minutes", so_data.get("time_limit")),
        constraints=so_data.get("constraints"),
        out_of_scope=so_data.get("out_of_scope"),
        stop_criteria=so_data.get("stop_criteria"),
        handoff_artifacts=so_data.get("handoff_artifacts"),
    )

    _err(f"[nelson-data] Mission directory: {mission_dir}")

    formation = _do_form(mission_dir, plan_data, mode=args.mode or "subagents")

    summary = {
        "status": "ok",
        "mission_dir": str(mission_dir),
        "sailing_orders": {
            "outcome": so_data.get("outcome", ""),
            "success_metric": so_data.get("metric", so_data.get("success_metric", "")),
            "deadline": so_data.get("deadline", "this_session"),
        },
        "formation": formation,
    }

    print(json.dumps(summary, indent=JSON_INDENT))


# ---------------------------------------------------------------------------
# Subcommand: recover
# ---------------------------------------------------------------------------


def _find_active_mission(missions_dir: Path) -> Path | None:  # noqa: C901 -- active-mission heuristic with several fallbacks; refactor tracked in nelson-e6j
    """Find the most recent active mission directory.

    Walks all ``.active-*`` markers, resolves each to a mission directory,
    skips ones that are missing or already stood down, and returns the
    candidate with the latest timestamp-prefixed directory name. Falls back
    to scanning ``missions_dir`` directly when no usable markers exist.

    Multiple markers may point at the same mission directory using different
    path forms (e.g., a relative ``.nelson/missions/...`` written by ``init``
    and an absolute path written by another caller). Candidates are
    deduplicated by resolved path and rewritten to the canonical form under
    ``missions_dir`` when they refer to the same directory, so the result is
    independent of filesystem glob ordering.
    """
    nelson_dir = missions_dir.parent
    seen_resolved: set[Path] = set()
    candidates: list[tuple[str, Path]] = []
    for af in nelson_dir.glob(".active-*"):
        try:
            mission_path = Path(af.read_text(encoding="utf-8").strip())
        except OSError:
            continue
        if not mission_path.is_dir() or (mission_path / "stand-down.json").exists():
            continue
        try:
            resolved = mission_path.resolve()
        except OSError:
            continue
        if resolved in seen_resolved:
            continue
        seen_resolved.add(resolved)
        canonical = missions_dir / mission_path.name
        if canonical != mission_path:
            try:
                if canonical.is_dir() and canonical.resolve() == resolved:
                    mission_path = canonical
            except OSError:
                pass
        candidates.append((mission_path.name, mission_path))
    if candidates:
        candidates.sort(key=lambda c: c[0], reverse=True)
        return candidates[0][1]

    if not missions_dir.is_dir():
        return None
    fallback = sorted(
        (d for d in missions_dir.iterdir() if d.is_dir() and not (d / "stand-down.json").exists()),
        key=lambda d: d.name,
        reverse=True,
    )
    return fallback[0] if fallback else None


def _update_fleet_status_from_event(mission_dir: Path, event: dict, event_id: int) -> None:
    """Apply a state-changing event's delta to fleet-status.json.

    Only event types in FLEET_STATUS_EVENT_TYPES update fleet-status; other
    types are silently ignored. ``event_id`` is the index returned by
    ``_append_event`` and is stamped as ``last_event_id``.
    """
    if event.get("type") not in FLEET_STATUS_EVENT_TYPES:
        return

    fs_path = mission_dir / "fleet-status.json"
    fs = _read_json_optional(fs_path)
    if fs is None:
        return

    progress = dict(fs.get("progress", {}))

    def bump(key: str, delta: int) -> None:
        progress[key] = max(0, progress.get(key, 0) + delta)

    etype = event["type"]
    if etype == "task_started":
        bump("in_progress", +1)
        bump("pending", -1)
    elif etype == "task_completed":
        bump("in_progress", -1)
        bump("completed", +1)
    elif etype == "blocker_raised":
        bump("blocked", +1)
    elif etype == "blocker_resolved":
        bump("blocked", -1)
    # hull_threshold_crossed and relief_on_station refresh freshness fields
    # only; squadron/hull rebuilds happen at checkpoint.

    new_fs = {
        **fs,
        "progress": progress,
        "last_updated": _now_iso(),
        "last_event_id": event_id,
    }
    _write_json(fs_path, new_fs)


def _read_handoff_packets(mission_dir: Path) -> list[dict]:
    """Read all JSON handoff packets from the turnover-briefs directory."""
    briefs_dir = mission_dir / "turnover-briefs"
    if not briefs_dir.is_dir():
        return []
    packets: list[dict] = []
    for p in sorted(briefs_dir.glob("*.json")):
        data = _read_json_optional(p)
        if data is not None and data.get("version") == 1:
            packets.append(data)
    return packets


def _compute_fleet_status_staleness(fleet_status: dict | None, mission_log: dict | None) -> dict | None:
    """Return a dict describing fleet-status staleness, or None if fresh.

    Considered stale when either:
      - last_updated is older than FLEET_STATUS_STALENESS_THRESHOLD_SECONDS
      - mission-log contains events newer than last_event_id
    """
    if fleet_status is None:
        return None

    age_seconds: int | None = None
    last_updated = fleet_status.get("last_updated")
    if last_updated:
        try:
            ts = datetime.strptime(last_updated, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            age_seconds = int((datetime.now(UTC) - ts).total_seconds())
        except ValueError:
            age_seconds = None

    last_event_id = fleet_status.get("last_event_id")
    events = (mission_log or {}).get("events", [])
    pending_count = 0
    last_event_summary: str | None = None
    if isinstance(last_event_id, int):
        pending_count = max(0, len(events) - last_event_id - 1)
        if pending_count:
            tail = events[-1]
            tail_data = tail.get("data", {}) or {}
            tail_id = tail_data.get("task_id")
            label = tail.get("type", "unknown")
            last_event_summary = f"{label} task-{tail_id}" if tail_id is not None else label

    age_threshold_exceeded = age_seconds is not None and age_seconds > FLEET_STATUS_STALENESS_THRESHOLD_SECONDS
    if not age_threshold_exceeded and pending_count == 0:
        return None

    return {
        "last_updated": last_updated,
        "age_seconds": age_seconds,
        "pending_event_count": pending_count,
        "last_event_summary": last_event_summary,
    }


def _build_recovery_briefing(
    mission_dir: Path,
    fleet_status: dict | None,
    handoff_packets: list[dict],
    battle_plan: dict,
) -> dict:
    """Build a structured recovery briefing from available mission data."""
    tasks = battle_plan.get("tasks", [])
    mission_log = _read_json_optional(mission_dir / "mission-log.json")
    staleness = _compute_fleet_status_staleness(fleet_status, mission_log)

    pending_tasks = []
    for t in tasks:
        status = "unknown"
        if fleet_status:
            for ship in fleet_status.get("squadron", []):
                if ship.get("task_id") == t.get("id"):
                    status = ship.get("task_status", "unknown")
                    break
        pending_tasks.append(
            {
                "task_id": t.get("id"),
                "task_name": t.get("name"),
                "owner": t.get("owner"),
                "status": status,
            }
        )

    current_phase = fleet_status.get("mission", {}).get("phase", "unknown") if fleet_status else "unknown"

    recommended_actions: list[str] = []
    # Phase guidance takes precedence over handoff packets when both exist —
    # an anomalous mid-flight state, but if it occurs the phase wins because
    # it reflects the admiral's last recorded position in the workflow.
    if current_phase in PHASE_RECOVERY_GUIDANCE:
        recommended_actions = list(PHASE_RECOVERY_GUIDANCE[current_phase])
        if current_phase in BATTLE_PLAN_MD_REQUIRED_PHASES and not (mission_dir / "battle-plan.md").is_file():
            recommended_actions.insert(
                0,
                "WARNING: battle-plan.md is missing — rebuild from estimate.md",
            )
    else:
        # UNDERWAY (and any unknown phase): derive actions from handoff packets.
        for pkt in handoff_packets:
            ship = pkt.get("ship_name", "unknown")
            task_id = pkt.get("task_id")
            recommended_actions.append(f"Resume task {task_id} from handoff packet ({ship})")
        if not recommended_actions:
            recommended_actions.append("No handoff packets found — review fleet-status.json for current state")

    return {
        "mission_dir": str(mission_dir),
        "mission_status": (fleet_status.get("mission", {}).get("status", "unknown") if fleet_status else "unknown"),
        "current_phase": current_phase,
        "fleet_status": fleet_status,
        "fleet_status_staleness": staleness,
        "handoff_packets": handoff_packets,
        "pending_tasks": pending_tasks,
        "recommended_actions": recommended_actions,
    }


def _format_recovery_text(briefing: dict) -> str:
    """Format a recovery briefing as human-readable text."""
    lines: list[str] = []
    lines.append(f"[nelson-data] Recovery briefing for {briefing['mission_dir']}")
    lines.append(f"  Status: {briefing['mission_status']}")
    lines.append(f"  Phase: {briefing.get('current_phase', 'unknown')}")
    lines.append("")

    staleness = briefing.get("fleet_status_staleness")
    if staleness:
        age = staleness.get("age_seconds")
        last_updated = staleness.get("last_updated")
        pending = staleness.get("pending_event_count", 0)
        last_event = staleness.get("last_event_summary")
        lines.append("  ⚠ Fleet status may be stale.")
        if last_updated and age is not None:
            minutes = age // 60
            lines.append(f"    fleet-status last updated: {last_updated} ({minutes} minutes ago)")
        if pending > 0:
            tail = f" (last: {last_event})" if last_event else ""
            lines.append(f"    mission-log has {pending} events newer than fleet-status{tail}")
        lines.append("    Verify in-progress task state against handoff packets and file state before resuming.")
        lines.append("")

    fs = briefing.get("fleet_status")
    if fs:
        progress = fs.get("progress", {})
        budget = fs.get("budget", {})
        lines.append(f"  Progress: {progress.get('completed', 0)}/{progress.get('total', 0)} tasks done")
        lines.append(f"  Budget: {budget.get('pct_consumed', 0)}% consumed")
        lines.append("")

    packets = briefing.get("handoff_packets", [])
    if packets:
        lines.append(f"  Handoff packets: {len(packets)}")
        for pkt in packets:
            ship = pkt.get("ship_name", "unknown")
            task = pkt.get("task_name", "unknown")
            htype = pkt.get("handoff_type", "unknown")
            lines.append(f"    {ship} | {task} | {htype}")
        lines.append("")

    actions = briefing.get("recommended_actions", [])
    if actions:
        lines.append("  Recommended actions:")
        for action in actions:
            lines.append(f"    - {action}")

    return "\n".join(lines)


def cmd_recover(args: argparse.Namespace) -> None:
    """Auto-recover session state from an active mission (read-only)."""
    mission_dir: Path | None = None

    raw_dir = getattr(args, "mission_dir", None)
    if raw_dir:
        mission_dir = Path(raw_dir)
        if not mission_dir.is_dir():
            _die(f"Error: mission directory does not exist: {mission_dir}")
    else:
        missions_dir = Path(args.missions_dir if args.missions_dir else ".nelson/missions")
        mission_dir = _find_active_mission(missions_dir)

    if mission_dir is None:
        print("[nelson-data] No active mission found")
        return

    fleet_status = _read_json_optional(mission_dir / "fleet-status.json")
    handoff_packets = _read_handoff_packets(mission_dir)
    battle_plan = _read_json_optional(mission_dir / "battle-plan.json") or {}

    briefing = _build_recovery_briefing(mission_dir, fleet_status, handoff_packets, battle_plan)

    output_format = getattr(args, "format", "json")
    if output_format == "text":
        print(_format_recovery_text(briefing))
    else:
        print(json.dumps(briefing, indent=JSON_INDENT))
