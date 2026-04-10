"""Cross-mission memory store for Nelson missions.

Manages pattern extraction, standing order statistics, and memory
synchronization from completed missions. Uses file locking for
concurrent access safety.

No external dependencies — stdlib only.
"""

from __future__ import annotations

from pathlib import Path

from nelson_data_utils import (
    _err,
    _file_lock,
    _now_iso,
    _read_json_optional,
    _write_json,
)


# ---------------------------------------------------------------------------
# Cross-Mission Memory Store
# ---------------------------------------------------------------------------


def _build_empty_index() -> dict:
    """Return an empty fleet intelligence index structure."""
    return {
        "version": 1,
        "indexed_at": None,
        "mission_count": 0,
        "missions": [],
    }


def _resolve_memory_dir(missions_dir: Path) -> Path:
    """Return the memory store directory, creating it if needed.

    The memory directory lives alongside the missions directory at
    ``{missions_dir}/../memory/``.
    """
    memory_dir = missions_dir.parent / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


def _extract_patterns_from_mission(mission_dir: Path) -> dict | None:
    """Extract pattern data from a completed mission.

    Returns None if stand-down.json is missing or unreadable.
    """
    stand_down = _read_json_optional(mission_dir / "stand-down.json")
    if stand_down is None:
        return None

    mission_log = _read_json_optional(mission_dir / "mission-log.json") or {}
    sailing_orders = _read_json_optional(mission_dir / "sailing-orders.json") or {}
    events = mission_log.get("events", [])

    # Extract standing order violations
    violations: list[dict] = []
    for ev in events:
        if ev.get("type") == "standing_order_violation":
            data = ev.get("data", {})
            violations.append({
                "order": data.get("order", ""),
                "description": data.get("description", ""),
                "severity": data.get("severity", ""),
                "corrective_action": data.get("corrective_action", ""),
            })

    # Count damage control events
    damage_control_types = frozenset({"relief_on_station", "hull_threshold_crossed"})
    damage_control_events = sum(
        1 for ev in events if ev.get("type") in damage_control_types
    )

    # Quality metrics
    sd_tasks = stand_down.get("tasks", {})
    total_tasks = sd_tasks.get("total", 0)
    completed_tasks = sd_tasks.get("completed", 0)
    task_completion_rate = (
        round(completed_tasks / total_tasks, 2) if total_tasks > 0 else None
    )

    sd_quality = stand_down.get("quality", {})
    reusable = stand_down.get("reusable_patterns", {})

    return {
        "mission_id": mission_dir.name,
        "completed_at": stand_down.get("created_at"),
        "outcome_achieved": stand_down.get("outcome_achieved", False),
        "planned_outcome": stand_down.get(
            "planned_outcome", sailing_orders.get("outcome", "")
        ),
        "adopt": list(reusable.get("adopt", [])),
        "avoid": list(reusable.get("avoid", [])),
        "standing_order_violations": violations,
        "damage_control_events": damage_control_events,
        "quality": {
            "violations": sd_quality.get("standing_order_violations", 0),
            "blockers_raised": sd_quality.get("blockers_raised", 0),
            "blockers_resolved": sd_quality.get("blockers_resolved", 0),
            "task_completion_rate": task_completion_rate,
        },
    }


def _update_patterns_store(mission_dir: Path) -> None:
    """Append pattern data from *mission_dir* to the persistent patterns store.

    Uses file locking to handle concurrent stand-down calls safely.
    """
    missions_dir = mission_dir.parent
    memory_dir = _resolve_memory_dir(missions_dir)
    patterns_path = memory_dir / "patterns.json"
    lock_path = memory_dir / ".patterns.lock"

    record = _extract_patterns_from_mission(mission_dir)
    if record is None:
        return

    with _file_lock(lock_path):
        existing = _read_json_optional(patterns_path) or {
            "version": 1,
            "updated_at": None,
            "pattern_count": 0,
            "patterns": [],
        }

        # Idempotency: skip if this mission already recorded
        existing_ids = {p["mission_id"] for p in existing.get("patterns", [])}
        if record["mission_id"] in existing_ids:
            return

        new_patterns = list(existing.get("patterns", [])) + [record]
        updated = {
            "version": 1,
            "updated_at": _now_iso(),
            "pattern_count": len(new_patterns),
            "patterns": new_patterns,
        }
        _write_json(patterns_path, updated)


def _update_standing_order_stats(mission_dir: Path) -> None:
    """Update standing order violation statistics from *mission_dir*.

    Reads standing_order_violation events from mission-log.json and updates
    the aggregate stats in standing-order-stats.json.
    """
    missions_dir = mission_dir.parent
    memory_dir = _resolve_memory_dir(missions_dir)
    stats_path = memory_dir / "standing-order-stats.json"
    lock_path = memory_dir / ".standing-order-stats.lock"

    stand_down = _read_json_optional(mission_dir / "stand-down.json")
    if stand_down is None:
        return

    mission_log = _read_json_optional(mission_dir / "mission-log.json") or {}
    events = mission_log.get("events", [])

    mission_id = mission_dir.name
    outcome_achieved = stand_down.get("outcome_achieved", False)

    # Extract violations from this mission
    mission_violations: list[str] = []
    for ev in events:
        if ev.get("type") == "standing_order_violation":
            order = ev.get("data", {}).get("order", "unknown")
            mission_violations.append(order)

    with _file_lock(lock_path):
        existing = _read_json_optional(stats_path) or {
            "version": 1,
            "updated_at": None,
            "total_missions": 0,
            "total_violations": 0,
            "violations_per_mission": 0.0,
            "by_order": {},
            "correlation": {
                "missions_with_violations": 0,
                "failures_with_violations": 0,
                "successes_with_violations": 0,
            },
            "_tracked_missions": [],
        }

        # Idempotency: skip if this mission already tracked
        tracked = list(existing.get("_tracked_missions", []))
        if mission_id in tracked:
            return

        total_missions = existing.get("total_missions", 0) + 1
        total_violations = existing.get("total_violations", 0) + len(mission_violations)
        vpm = round(total_violations / total_missions, 2) if total_missions > 0 else 0.0

        by_order = dict(existing.get("by_order", {}))
        for order in mission_violations:
            entry = by_order.get(order, {"count": 0, "missions": []})
            new_missions = list(entry.get("missions", []))
            if mission_id not in new_missions:
                new_missions.append(mission_id)
            by_order[order] = {
                "count": entry.get("count", 0) + 1,
                "missions": new_missions,
            }

        corr = dict(existing.get("correlation", {}))
        had_violations = len(mission_violations) > 0
        missions_with = corr.get("missions_with_violations", 0) + (
            1 if had_violations else 0
        )
        failures_with = corr.get("failures_with_violations", 0) + (
            1 if had_violations and not outcome_achieved else 0
        )
        successes_with = corr.get("successes_with_violations", 0) + (
            1 if had_violations and outcome_achieved else 0
        )

        updated = {
            "version": 1,
            "updated_at": _now_iso(),
            "total_missions": total_missions,
            "total_violations": total_violations,
            "violations_per_mission": vpm,
            "by_order": by_order,
            "correlation": {
                "missions_with_violations": missions_with,
                "failures_with_violations": failures_with,
                "successes_with_violations": successes_with,
            },
            "_tracked_missions": tracked + [mission_id],
        }
        _write_json(stats_path, updated)


def _rebuild_standing_order_stats(all_patterns: list[dict]) -> dict:
    """Rebuild standing order stats from scratch from pattern records.

    Returns a complete stats dict ready for writing.
    """
    all_missions_count = len(all_patterns)
    all_violations = [v for p in all_patterns for v in p.get("standing_order_violations", [])]
    all_violations_count = len(all_violations)

    missions_with = sum(
        1 for p in all_patterns if len(p.get("standing_order_violations", [])) > 0
    )
    failures_with = sum(
        1 for p in all_patterns
        if len(p.get("standing_order_violations", [])) > 0 and not p.get("outcome_achieved", False)
    )
    successes_with = sum(
        1 for p in all_patterns
        if len(p.get("standing_order_violations", [])) > 0 and p.get("outcome_achieved", False)
    )

    by_order: dict[str, dict] = {}
    for p in all_patterns:
        for v in p.get("standing_order_violations", []):
            order = v.get("order", "unknown")
            entry = by_order.get(order, {"count": 0, "missions": []})
            missions_list = list(entry.get("missions", []))
            mid = p["mission_id"]
            if mid not in missions_list:
                missions_list = missions_list + [mid]
            by_order[order] = {
                "count": entry.get("count", 0) + 1,
                "missions": missions_list,
            }

    vpm = (
        round(all_violations_count / all_missions_count, 2)
        if all_missions_count > 0
        else 0.0
    )
    return {
        "version": 1,
        "updated_at": _now_iso(),
        "total_missions": all_missions_count,
        "total_violations": all_violations_count,
        "violations_per_mission": vpm,
        "by_order": by_order,
        "correlation": {
            "missions_with_violations": missions_with,
            "failures_with_violations": failures_with,
            "successes_with_violations": successes_with,
        },
        "_tracked_missions": [p["mission_id"] for p in all_patterns],
    }


def _sync_memory_from_index(missions_dir: Path) -> None:
    """Backfill the memory store from missions not yet captured in patterns.json.

    Called at the end of ``cmd_index()`` to ensure the memory store covers
    all completed missions, including those that predate the memory store.
    Uses file locking to prevent concurrent corruption.
    """
    memory_dir = _resolve_memory_dir(missions_dir)
    patterns_path = memory_dir / "patterns.json"
    stats_path = memory_dir / "standing-order-stats.json"
    patterns_lock_path = memory_dir / ".patterns.lock"
    stats_lock_path = memory_dir / ".standing-order-stats.lock"

    # Lock patterns file for read-modify-write
    with _file_lock(patterns_lock_path):
        existing = _read_json_optional(patterns_path) or {
            "version": 1,
            "updated_at": None,
            "pattern_count": 0,
            "patterns": [],
        }
        indexed_ids = {p["mission_id"] for p in existing.get("patterns", [])}

        completed = _find_completed_missions(missions_dir)
        new_dirs = [d for d in completed if d.name not in indexed_ids]

        if not new_dirs:
            return

        # Build new pattern records
        new_records = [
            r for r in (_extract_patterns_from_mission(d) for d in new_dirs) if r is not None
        ]

        if not new_records:
            return

        # Append to patterns store
        all_patterns = list(existing.get("patterns", [])) + new_records
        updated_patterns = {
            "version": 1,
            "updated_at": _now_iso(),
            "pattern_count": len(all_patterns),
            "patterns": all_patterns,
        }
        _write_json(patterns_path, updated_patterns)

    # Lock stats file and rebuild from scratch for consistency
    with _file_lock(stats_lock_path):
        updated_stats = _rebuild_standing_order_stats(all_patterns)
        _write_json(stats_path, updated_stats)


# ---------------------------------------------------------------------------
# Fleet Intelligence — Record Builders
# ---------------------------------------------------------------------------


def _find_completed_missions(missions_dir: Path) -> list[Path]:
    """Return sorted list of mission dirs that contain a stand-down.json."""
    if not missions_dir.is_dir():
        return []
    return sorted(p.parent for p in missions_dir.glob("*/stand-down.json"))


def _extract_fleet_details(battle_plan: dict) -> dict:
    """Extract squadron metadata from a battle-plan dict."""
    squadron = battle_plan.get("squadron", {})
    admiral = squadron.get("admiral", {})
    captains = squadron.get("captains", [])
    return {
        "admiral_model": admiral.get("model"),
        "captain_count": len(captains),
        "ship_classes": [c.get("ship_class", "unknown") for c in captains],
        "captain_models": [c.get("model", "unknown") for c in captains],
        "had_red_cell": "red_cell" in squadron,
    }


def _build_mission_record(mission_dir: Path) -> dict | None:
    """Build a denormalized mission record from all JSON files in *mission_dir*.

    Returns None if stand-down.json is missing or corrupt.  Enriches from
    battle-plan.json, sailing-orders.json, and mission-log.json when available.
    """
    mission_id = mission_dir.name

    # Stand-down is the gate — return None if unreadable
    stand_down = _read_json_optional(mission_dir / "stand-down.json")
    if stand_down is None:
        return None

    # Optional enrichment sources
    battle_plan = _read_json_optional(mission_dir / "battle-plan.json") or {}
    sailing_orders = _read_json_optional(mission_dir / "sailing-orders.json") or {}
    mission_log = _read_json_optional(mission_dir / "mission-log.json") or {}

    # Fleet details from battle-plan
    fleet_details = _extract_fleet_details(battle_plan)

    # Execution mode from squadron_formed event
    events = mission_log.get("events", [])
    execution_mode = "subagents"
    for ev in events:
        if ev.get("type") == "squadron_formed":
            execution_mode = ev.get("data", {}).get("execution_mode", "subagents")
            break

    # Merge fleet from stand-down + battle-plan enrichment
    sd_fleet = stand_down.get("fleet", {})
    fleet = {
        "ships_used": sd_fleet.get("ships_used", 0),
        "reliefs": sd_fleet.get("reliefs", 0),
        "max_concurrent_ships": sd_fleet.get("max_concurrent_ships", 0),
        "execution_mode": execution_mode,
        **fleet_details,
    }

    # Tasks from stand-down + task names/files from battle-plan
    sd_tasks = stand_down.get("tasks", {})
    bp_tasks = battle_plan.get("tasks", [])
    task_names = [t.get("name", "") for t in bp_tasks]
    file_ownership = [f for t in bp_tasks for f in t.get("file_ownership", [])]

    tasks = {
        "completed": sd_tasks.get("completed", 0),
        "total": sd_tasks.get("total", 0),
        "by_station_tier": sd_tasks.get(
            "by_station_tier", {"0": 0, "1": 0, "2": 0, "3": 0}
        ),
        "task_names": task_names,
        "file_ownership": file_ownership,
    }

    # Timestamps
    created_at = sailing_orders.get("created_at") or stand_down.get("created_at")
    completed_at = stand_down.get("created_at")

    # Event types from mission log
    event_types = sorted({ev["type"] for ev in events if ev.get("type")})

    return {
        "mission_id": mission_id,
        "outcome_achieved": stand_down.get("outcome_achieved", False),
        "planned_outcome": stand_down.get("planned_outcome", ""),
        "actual_outcome": stand_down.get("actual_outcome", ""),
        "success_metric": sailing_orders.get("success_metric", ""),
        "success_metric_result": stand_down.get("success_metric_result", ""),
        "created_at": created_at,
        "completed_at": completed_at,
        "duration_minutes": stand_down.get("duration_minutes"),
        "budget": stand_down.get("budget", {}),
        "fleet": fleet,
        "tasks": tasks,
        "quality": stand_down.get("quality", {}),
        "reusable_patterns": stand_down.get(
            "reusable_patterns", {"adopt": [], "avoid": []}
        ),
        "event_types": event_types,
    }
