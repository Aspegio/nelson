#!/usr/bin/env python3
"""Structured data capture for Nelson missions.

Single script with subcommands for every data operation during a Nelson
mission lifecycle.  The admiral calls these via Bash; the script handles
JSON schema compliance, validation, timestamps, and file I/O.

Usage examples:

    python3 nelson-data.py init --outcome "Refactor auth" --metric "Tests pass" --deadline this_session
    python3 nelson-data.py squadron --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 ...
    python3 nelson-data.py task --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 ...
    python3 nelson-data.py plan-approved --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4
    python3 nelson-data.py event --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 --type task_completed ...
    python3 nelson-data.py checkpoint --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 ...
    python3 nelson-data.py stand-down --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 ...
    python3 nelson-data.py status --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4
    python3 nelson-data.py index
    python3 nelson-data.py index --missions-dir .nelson/missions --rebuild
    python3 nelson-data.py history
    python3 nelson-data.py history --json --last 5

No external dependencies — stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile

try:
    import fcntl
except ImportError:
    fcntl = None
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_EVENT_TYPES = frozenset(
    {
        "task_started",
        "task_completed",
        "blocker_raised",
        "blocker_resolved",
        "hull_threshold_crossed",
        "relief_on_station",
        "standing_order_violation",
        "commendation",
        "admiralty_action_required",
        "admiralty_action_completed",
        "battle_plan_amended",
    }
)

VALID_DECISIONS = frozenset({"continue", "rescope", "stop"})
VALID_MODES = frozenset({"single-session", "subagents", "agent-team"})
JSON_INDENT = 2


# ---------------------------------------------------------------------------
# Helpers — pure functions (no side effects)
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mission_dir_stamp() -> str:
    """Return a timestamped directory name fragment."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")


def _read_json(path: Path) -> dict | list:
    """Read and parse a JSON file.  Returns the parsed object."""
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except json.JSONDecodeError:
        # Back up the corrupt file and return a fresh structure
        backup = path.with_suffix(".json.bak")
        try:
            if backup.exists():
                backup.unlink()
            path.rename(backup)
            _err(f"Warning: corrupt JSON at {path}, backed up to {backup}")
        except OSError as e:
            _err(f"Warning: corrupt JSON at {path}, could not back up: {e}")
        if "mission-log" in path.name:
            return {"version": 1, "events": []}
        return {}
    except FileNotFoundError:
        _err(f"Error: file not found: {path}")
        sys.exit(1)


def _write_json(path: Path, data: Any) -> None:
    """Write *data* as formatted JSON.  Creates parent directories.

    Uses a temporary file + os.replace() for atomic writes so a crash
    mid-write cannot corrupt the target file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=JSON_INDENT) + "\n"
    try:
        existing_mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        existing_mode = None
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        if existing_mode is not None:
            os.chmod(tmp, existing_mode)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _append_event(mission_dir: Path, event: dict) -> None:
    """Append *event* to mission-log.json using read-modify-write."""
    log_path = mission_dir / "mission-log.json"
    lock_path = mission_dir / ".mission-log.lock"

    lock_file = open(lock_path, "w")
    try:
        if fcntl:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
        log = _read_json(log_path)
        new_events = list(log.get("events", [])) + [event]
        new_log = {**log, "events": new_events}
        _write_json(log_path, new_log)
    finally:
        if fcntl:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def _err(msg: str) -> None:
    """Print an error/warning message to stderr."""
    print(msg, file=sys.stderr)


def _die(msg: str) -> None:
    """Print error to stderr and exit 1."""
    _err(msg)
    sys.exit(1)


def _require_mission_dir(args: argparse.Namespace) -> Path:
    """Validate and return the mission directory as a Path."""
    raw = getattr(args, "mission_dir", None)
    if not raw:
        _die("Error: --mission-dir is required")
    p = Path(raw)
    if not p.is_dir():
        _die(f"Error: mission directory does not exist: {p}")
    return p


def _parse_extra_kv(extra: list[str]) -> dict[str, Any]:
    """Turn a list of ['--key', 'value', ...] into {'key': 'value', ...}.

    Keys that look like ``--some-key`` are normalised to ``some_key``.
    Values that look like ints or floats are converted; 'true'/'false'
    become booleans.
    """
    result: dict[str, Any] = {}
    i = 0
    while i < len(extra):
        token = extra[i]
        if token.startswith("--"):
            key = token.lstrip("-").replace("-", "_")
            if i + 1 < len(extra) and not extra[i + 1].startswith("--"):
                result[key] = _coerce_value(extra[i + 1])
                i += 2
            else:
                # Flag with no value
                result[key] = True
                i += 1
        else:
            i += 1
    return result


def _coerce_value(val: str) -> Any:
    """Attempt to convert a string to int, float, bool, or list."""
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    # Comma-separated lists (e.g. blocked_task_ids "1,2,3")
    if "," in val:
        parts = [_coerce_value(v.strip()) for v in val.split(",")]
        return parts
    return val


def _read_battle_plan(mission_dir: Path) -> dict:
    """Read battle-plan.json, returning an empty dict if absent."""
    bp_path = mission_dir / "battle-plan.json"
    if not bp_path.exists():
        return {}
    return _read_json(bp_path)


def _read_damage_reports(mission_dir: Path) -> list[dict]:
    """Read all damage report JSON files from the mission directory."""
    dr_dir = mission_dir / "damage-reports"
    if not dr_dir.is_dir():
        return []
    reports: list[dict] = []
    for p in sorted(dr_dir.glob("*.json")):
        try:
            reports.append(_read_json(p))
        except SystemExit:
            # _read_json calls sys.exit on missing files; skip bad ones
            continue
    return reports


def _count_events_of_type(events: list[dict], event_type: str) -> int:
    """Count events matching the given type."""
    return sum(1 for e in events if e.get("type") == event_type)


def _get_last_checkpoint_number(events: list[dict]) -> int:
    """Return the highest checkpoint number seen in events, or 0."""
    nums = [e.get("checkpoint", 0) for e in events if e.get("type") == "checkpoint"]
    return max(nums) if nums else 0


# ---------------------------------------------------------------------------
# Fleet Intelligence — Helpers
# ---------------------------------------------------------------------------


def _read_json_optional(path: Path) -> dict | None:
    """Read and parse a JSON file, returning None if it doesn't exist.

    FileNotFoundError is silent; corrupt JSON and OS errors emit a warning.
    """
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        _err(f"Warning: corrupt JSON at {path}, skipping")
        return None
    except OSError as exc:
        _err(f"Warning: could not read {path}: {exc}")
        return None


def _safe_mean(values: list[float | int]) -> float | None:
    """Return the mean of *values*, or None if the list is empty."""
    if not values:
        return None
    return sum(values) / len(values)


def _build_empty_index() -> dict:
    """Return an empty fleet intelligence index structure."""
    return {
        "version": 1,
        "indexed_at": None,
        "mission_count": 0,
        "missions": [],
    }


# ---------------------------------------------------------------------------
# Cross-Mission Memory Store
# ---------------------------------------------------------------------------


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

    lock_file = open(lock_path, "w")
    try:
        if fcntl:
            fcntl.flock(lock_file, fcntl.LOCK_EX)

        existing = _read_json_optional(patterns_path) or {
            "version": 1,
            "updated_at": None,
            "pattern_count": 0,
            "patterns": [],
        }

        new_patterns = list(existing.get("patterns", [])) + [record]
        updated = {
            "version": 1,
            "updated_at": _now_iso(),
            "pattern_count": len(new_patterns),
            "patterns": new_patterns,
        }
        _write_json(patterns_path, updated)
    finally:
        if fcntl:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


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

    lock_file = open(lock_path, "w")
    try:
        if fcntl:
            fcntl.flock(lock_file, fcntl.LOCK_EX)

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
        }

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
        }
        _write_json(stats_path, updated)
    finally:
        if fcntl:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def _sync_memory_from_index(missions_dir: Path) -> None:
    """Backfill the memory store from missions not yet captured in patterns.json.

    Called at the end of ``cmd_index()`` to ensure the memory store covers
    all completed missions, including those that predate the memory store.
    """
    memory_dir = _resolve_memory_dir(missions_dir)
    patterns_path = memory_dir / "patterns.json"
    stats_path = memory_dir / "standing-order-stats.json"

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

    # Rebuild standing order stats from scratch for consistency
    all_missions_count = 0
    all_violations_count = 0
    by_order: dict[str, dict] = {}
    corr = {
        "missions_with_violations": 0,
        "failures_with_violations": 0,
        "successes_with_violations": 0,
    }

    for p in all_patterns:
        all_missions_count += 1
        violations = p.get("standing_order_violations", [])
        outcome = p.get("outcome_achieved", False)
        had_violations = len(violations) > 0

        all_violations_count += len(violations)

        if had_violations:
            corr["missions_with_violations"] += 1
            if outcome:
                corr["successes_with_violations"] += 1
            else:
                corr["failures_with_violations"] += 1

        for v in violations:
            order = v.get("order", "unknown")
            entry = by_order.get(order, {"count": 0, "missions": []})
            missions_list = list(entry.get("missions", []))
            mid = p["mission_id"]
            if mid not in missions_list:
                missions_list.append(mid)
            by_order[order] = {
                "count": entry.get("count", 0) + 1,
                "missions": missions_list,
            }

    vpm = (
        round(all_violations_count / all_missions_count, 2)
        if all_missions_count > 0
        else 0.0
    )
    updated_stats = {
        "version": 1,
        "updated_at": _now_iso(),
        "total_missions": all_missions_count,
        "total_violations": all_violations_count,
        "violations_per_mission": vpm,
        "by_order": by_order,
        "correlation": corr,
    }
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


# ---------------------------------------------------------------------------
# Subcommand: index
# ---------------------------------------------------------------------------


def _resolve_fleet_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """Return (missions_dir, index_path) from parsed arguments."""
    missions_dir = (
        Path(args.missions_dir) if args.missions_dir else Path(".nelson/missions")
    )
    index_path = missions_dir.parent / "fleet-intelligence.json"
    return missions_dir, index_path


def cmd_index(args: argparse.Namespace) -> None:
    """Build or update the fleet intelligence index."""
    missions_dir, index_path = _resolve_fleet_paths(args)
    rebuild = bool(getattr(args, "rebuild", False))

    lock_path = index_path.with_suffix(".lock")
    lock_file = open(lock_path, "w")
    try:
        if fcntl:
            fcntl.flock(lock_file, fcntl.LOCK_EX)

        # Load existing index or start fresh
        if rebuild:
            index = _build_empty_index()
        else:
            index = _read_json_optional(index_path) or _build_empty_index()

        # Guard against future version bumps
        if not rebuild and index.get("version") is not None and index["version"] != 1:
            _err(f"Warning: index version {index['version']} != 1, rebuilding")
            index = _build_empty_index()
            rebuild = True

        indexed_ids = {m["mission_id"] for m in index.get("missions", [])}

        # Discover completed missions
        completed = _find_completed_missions(missions_dir)

        # Filter to new missions only (unless rebuilding)
        new_dirs = (
            completed
            if rebuild
            else [d for d in completed if d.name not in indexed_ids]
        )

        # Build records (skip missions with unreadable stand-down.json)
        new_records = [
            r for r in (_build_mission_record(d) for d in new_dirs) if r is not None
        ]

        # Merge and sort
        all_missions = (
            new_records if rebuild else list(index.get("missions", [])) + new_records
        )
        all_missions.sort(key=lambda m: m["mission_id"])

        updated_index = {
            "version": 1,
            "indexed_at": _now_iso(),
            "mission_count": len(all_missions),
            "missions": all_missions,
        }
        _write_json(index_path, updated_index)
    finally:
        if fcntl:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()

    print(
        f"[nelson-data] Fleet intelligence indexed: "
        f"{len(all_missions)} missions ({len(new_records)} new)"
    )

    # Sync memory store from indexed missions (best-effort)
    try:
        _sync_memory_from_index(missions_dir)
    except Exception as exc:
        _err(f"Warning: failed to sync memory store: {exc}")


# ---------------------------------------------------------------------------
# Subcommand: history
# ---------------------------------------------------------------------------


def _collect_ship_class_counts(missions: list[dict]) -> dict[str, int]:
    """Count ship class usage across missions, descending by count."""
    counts: dict[str, int] = {}
    for m in missions:
        for cls in m.get("fleet", {}).get("ship_classes", []):
            counts[cls] = counts.get(cls, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def _collect_station_tier_totals(missions: list[dict]) -> dict[str, int]:
    """Accumulate task counts by station tier (0-3 only)."""
    totals: dict[str, int] = {"0": 0, "1": 0, "2": 0, "3": 0}
    for m in missions:
        tiers = m.get("tasks", {}).get("by_station_tier", {})
        for tier, count in tiers.items():
            if tier in totals:
                totals[tier] += count
    return totals


def _compute_analytics(missions: list[dict]) -> dict:
    """Compute aggregate analytics across all mission records."""
    if not missions:
        return {
            "mission_count": 0,
            "achieved": 0,
            "not_achieved": 0,
            "win_rate": None,
            "avg_duration": None,
            "min_duration": None,
            "max_duration": None,
            "avg_tokens_consumed": None,
            "avg_budget_pct": None,
            "avg_ships": None,
            "avg_tasks": None,
            "violations_per_mission": None,
            "blockers_per_mission": None,
            "ship_class_counts": {},
            "station_tier_totals": {"0": 0, "1": 0, "2": 0, "3": 0},
        }

    achieved = sum(1 for m in missions if m.get("outcome_achieved"))
    not_achieved = len(missions) - achieved
    win_rate = round(achieved / len(missions) * 100, 1)

    durations = [
        m["duration_minutes"] for m in missions if m.get("duration_minutes") is not None
    ]
    tokens = [
        v
        for m in missions
        if (v := m.get("budget", {}).get("tokens_consumed")) is not None
    ]
    budget_pcts = [
        v
        for m in missions
        if (v := m.get("budget", {}).get("pct_consumed")) is not None
    ]
    ships = [
        v for m in missions if (v := m.get("fleet", {}).get("ships_used")) is not None
    ]
    task_totals = [
        v for m in missions if (v := m.get("tasks", {}).get("total")) is not None
    ]
    violations = [
        v
        for m in missions
        if (v := m.get("quality", {}).get("standing_order_violations")) is not None
    ]
    blockers = [
        v
        for m in missions
        if (v := m.get("quality", {}).get("blockers_raised")) is not None
    ]

    ship_class_counts = _collect_ship_class_counts(missions)
    station_tier_totals = _collect_station_tier_totals(missions)

    avg_dur = _safe_mean(durations)
    avg_tok = _safe_mean(tokens)
    avg_bpct = _safe_mean(budget_pcts)
    avg_shp = _safe_mean(ships)
    avg_tsk = _safe_mean(task_totals)
    avg_viol = _safe_mean(violations)
    avg_blk = _safe_mean(blockers)

    return {
        "mission_count": len(missions),
        "achieved": achieved,
        "not_achieved": not_achieved,
        "win_rate": win_rate,
        "avg_duration": round(avg_dur, 1) if avg_dur is not None else None,
        "min_duration": min(durations) if durations else None,
        "max_duration": max(durations) if durations else None,
        "avg_tokens_consumed": int(round(avg_tok)) if avg_tok is not None else None,
        "avg_budget_pct": round(avg_bpct, 1) if avg_bpct is not None else None,
        "avg_ships": round(avg_shp, 1) if avg_shp is not None else None,
        "avg_tasks": round(avg_tsk, 1) if avg_tsk is not None else None,
        "violations_per_mission": round(avg_viol, 2) if avg_viol is not None else None,
        "blockers_per_mission": round(avg_blk, 2) if avg_blk is not None else None,
        "ship_class_counts": ship_class_counts,
        "station_tier_totals": station_tier_totals,
    }


def _format_history_text(
    analytics: dict,
    missions: list[dict],
    last_n: int,
) -> str:
    """Format fleet intelligence as human-readable text."""
    lines: list[str] = []
    mc = analytics["mission_count"]
    lines.append(f"Fleet Intelligence \u2014 {mc} missions indexed")
    lines.append("")

    if mc == 0:
        lines.append("  No missions to display.")
        return "\n".join(lines)

    # Outcome
    lines.append(
        f"  Outcome    {mc} missions: {analytics['achieved']} achieved, "
        f"{analytics['not_achieved']} not achieved ({analytics['win_rate']}% win rate)"
    )

    # Duration
    avg_d = analytics["avg_duration"]
    if avg_d is not None:
        lines.append(
            f"  Duration   avg {avg_d} min "
            f"(range: {analytics['min_duration']}\u2013{analytics['max_duration']})"
        )

    # Tokens
    avg_t = analytics["avg_tokens_consumed"]
    if avg_t is not None:
        token_str = f"{round(avg_t / 1000)}K" if avg_t >= 1000 else str(avg_t)
        lines.append(
            f"  Tokens     avg {token_str} consumed, "
            f"avg {analytics['avg_budget_pct']}% of budget"
        )

    # Squadron
    avg_s = analytics["avg_ships"]
    if avg_s is not None:
        lines.append(
            f"  Squadron   avg {avg_s} ships, "
            f"avg {analytics['avg_tasks']} tasks per mission"
        )

    # Quality
    vpm = analytics["violations_per_mission"]
    if vpm is not None:
        lines.append(
            f"  Quality    {vpm} violations/mission, "
            f"{analytics['blockers_per_mission']} blockers/mission"
        )

    lines.append("")

    # Ship classes
    scc = analytics["ship_class_counts"]
    if scc:
        parts = [f"{cls} ({count})" for cls, count in scc.items()]
        lines.append(f"  Ship classes   {', '.join(parts)}")

    # Station tiers
    stt = analytics["station_tier_totals"]
    tier_parts = [f"{k}: {v} tasks" for k, v in sorted(stt.items())]
    lines.append(f"  Station tiers  {', '.join(tier_parts)}")

    lines.append("")

    lines.extend(_format_recent_missions(missions, last_n))

    return "\n".join(lines)


def _format_recent_missions(missions: list[dict], last_n: int) -> list[str]:
    """Format the recent missions section (most recent first)."""
    recent = list(reversed(missions))[:last_n]
    if not recent:
        return []
    lines: list[str] = []
    lines.append("  Recent missions")
    lines.append("  " + "\u2500" * 62)
    for m in recent:
        mid = m["mission_id"]
        date_str = mid[:10] if len(mid) >= 10 else mid
        marker = "\u2713" if m.get("outcome_achieved") else "\u2717"
        outcome = m.get("actual_outcome") or m.get("planned_outcome", "")
        if len(outcome) > 50:
            outcome = outcome[:47] + "..."
        lines.append(f"  {date_str}  {marker}  {outcome}")
    return lines


def _format_history_json(analytics: dict, missions: list[dict]) -> str:
    """Format fleet intelligence as machine-readable JSON."""
    return json.dumps(
        {"analytics": analytics, "missions": missions},
        indent=JSON_INDENT,
    )


def cmd_history(args: argparse.Namespace) -> None:
    """Display fleet intelligence analytics from the index."""
    missions_dir, index_path = _resolve_fleet_paths(args)
    last_n = max(0, args.last)

    if not index_path.exists():
        _die("No fleet intelligence index found. Run 'nelson-data index' first.")

    index = _read_json_optional(index_path)
    if index is None:
        _die("Failed to read fleet intelligence index.")

    missions = index.get("missions", [])
    analytics = _compute_analytics(missions)

    if args.json_output:
        recent = list(reversed(missions))[:last_n]
        print(_format_history_json(analytics, recent))
    else:
        print(_format_history_text(analytics, missions, last_n))


# ---------------------------------------------------------------------------
# Subcommand: brief
# ---------------------------------------------------------------------------


def _keyword_overlap(context: str, text: str) -> int:
    """Count shared keywords between *context* and *text* (case-insensitive).

    Returns the number of overlapping words (length >= 3 to skip noise).
    """
    ctx_words = {w.lower() for w in context.split() if len(w) >= 3}
    txt_words = {w.lower() for w in text.split() if len(w) >= 3}
    return len(ctx_words & txt_words)


def _aggregate_patterns(
    patterns: list[dict],
) -> tuple[dict[str, int], dict[str, int]]:
    """Aggregate adopt and avoid patterns across missions.

    Returns (adopt_counts, avoid_counts) — dicts of pattern text to occurrence count.
    """
    adopt_counts: dict[str, int] = {}
    avoid_counts: dict[str, int] = {}
    for p in patterns:
        for text in p.get("adopt", []):
            adopt_counts[text] = adopt_counts.get(text, 0) + 1
        for text in p.get("avoid", []):
            avoid_counts[text] = avoid_counts.get(text, 0) + 1
    return adopt_counts, avoid_counts


def _build_intelligence_brief(
    patterns: list[dict],
    stats: dict,
    index_missions: list[dict],
    context: str,
) -> dict:
    """Build a structured intelligence brief from memory store data.

    Returns a dict suitable for JSON output or text formatting.
    """
    total = len(index_missions)
    achieved = sum(1 for m in index_missions if m.get("outcome_achieved"))
    win_rate = round(achieved / total * 100, 1) if total > 0 else None

    # Last-5 trend
    recent_5 = list(reversed(index_missions))[:5]
    r5_achieved = sum(1 for m in recent_5 if m.get("outcome_achieved"))
    recent_win_rate = (
        round(r5_achieved / len(recent_5) * 100, 1) if recent_5 else None
    )

    # Aggregate patterns
    adopt_counts, avoid_counts = _aggregate_patterns(patterns)
    top_adopt = sorted(adopt_counts.items(), key=lambda x: -x[1])[:5]
    top_avoid = sorted(avoid_counts.items(), key=lambda x: -x[1])[:5]

    # Standing order hot spots
    by_order = stats.get("by_order", {})
    hot_spots = sorted(
        [
            {
                "order": order,
                "count": data.get("count", 0),
                "missions_affected": len(data.get("missions", [])),
            }
            for order, data in by_order.items()
        ],
        key=lambda x: -x["count"],
    )[:5]

    # Context-relevant precedents
    precedents: list[dict] = []
    if context:
        scored = []
        for m in index_missions:
            outcome_text = m.get("actual_outcome", "") or m.get(
                "planned_outcome", ""
            )
            score = _keyword_overlap(context, outcome_text)
            if score > 0:
                scored.append((score, m))
        scored.sort(key=lambda x: -x[0])
        for _score, m in scored[:3]:
            # Find matching pattern data
            matching_patterns = [
                p
                for p in patterns
                if p.get("mission_id") == m.get("mission_id")
            ]
            mp = matching_patterns[0] if matching_patterns else {}
            precedents.append({
                "mission_id": m.get("mission_id", ""),
                "outcome_achieved": m.get("outcome_achieved", False),
                "planned_outcome": m.get("planned_outcome", ""),
                "duration_minutes": m.get("duration_minutes"),
                "ships_used": m.get("fleet", {}).get("ships_used"),
                "adopt": mp.get("adopt", []),
                "avoid": mp.get("avoid", []),
            })

    return {
        "total_missions": total,
        "win_rate": win_rate,
        "recent_win_rate": recent_win_rate,
        "top_adopt": [{"pattern": p, "count": c} for p, c in top_adopt],
        "top_avoid": [{"pattern": p, "count": c} for p, c in top_avoid],
        "standing_order_hot_spots": hot_spots,
        "precedents": precedents,
    }


def _format_brief_text(brief: dict, context: str) -> str:
    """Format an intelligence brief as compact text for context injection."""
    lines: list[str] = []
    total = brief["total_missions"]
    wr = brief["win_rate"]
    rwr = brief["recent_win_rate"]

    header = f"Intelligence Brief \u2014 {total} missions"
    if wr is not None:
        header += f", {wr}% win rate"
        if rwr is not None:
            header += f" (last 5: {rwr}%)"
    lines.append(header)
    lines.append("")

    if total == 0:
        lines.append("  No mission data available.")
        return "\n".join(lines)

    # Patterns to adopt
    top_adopt = brief.get("top_adopt", [])
    if top_adopt:
        lines.append("Patterns to adopt:")
        for item in top_adopt:
            lines.append(f"  - {item['pattern']} ({item['count']} missions)")
        lines.append("")

    # Patterns to avoid
    top_avoid = brief.get("top_avoid", [])
    if top_avoid:
        lines.append("Patterns to avoid:")
        for item in top_avoid:
            lines.append(f"  - {item['pattern']} ({item['count']} missions)")
        lines.append("")

    # Standing order hot spots
    hot_spots = brief.get("standing_order_hot_spots", [])
    if hot_spots:
        lines.append("Standing order hot spots:")
        for i, hs in enumerate(hot_spots, 1):
            lines.append(
                f"  {i}. {hs['order']}: "
                f"{hs['count']} violations across {hs['missions_affected']} missions"
            )
        lines.append("")

    # Context-relevant precedents
    precedents = brief.get("precedents", [])
    if precedents:
        lines.append(f'Relevant precedents (context: "{context}"):')
        for p in precedents:
            date = p["mission_id"][:10] if len(p["mission_id"]) >= 10 else p["mission_id"]
            marker = "\u2713" if p["outcome_achieved"] else "\u2717"
            outcome = p.get("planned_outcome", "")
            if len(outcome) > 50:
                outcome = outcome[:47] + "..."
            detail = f"  {date}  {marker}  {outcome}"
            if p.get("duration_minutes"):
                detail += f", {p['duration_minutes']}min"
            if p.get("ships_used"):
                detail += f", {p['ships_used']} ships"
            lines.append(detail)
            for a in p.get("adopt", []):
                lines.append(f"    adopt: {a}")
            for a in p.get("avoid", []):
                lines.append(f"    avoid: {a}")
        lines.append("")

    return "\n".join(lines)


def cmd_brief(args: argparse.Namespace) -> None:
    """Generate an intelligence brief from past missions."""
    missions_dir, index_path = _resolve_fleet_paths(args)
    context = args.context or ""

    # Read fleet intelligence index
    index = _read_json_optional(index_path)
    index_missions = index.get("missions", []) if index else []

    # Read memory store
    memory_dir = missions_dir.parent / "memory"
    patterns_data = _read_json_optional(memory_dir / "patterns.json")
    patterns = patterns_data.get("patterns", []) if patterns_data else []

    stats = _read_json_optional(memory_dir / "standing-order-stats.json") or {}

    brief = _build_intelligence_brief(patterns, stats, index_missions, context)

    if args.json_output:
        print(json.dumps(brief, indent=JSON_INDENT))
    else:
        print(_format_brief_text(brief, context))


# ---------------------------------------------------------------------------
# Subcommand: analytics
# ---------------------------------------------------------------------------


VALID_METRICS = frozenset({"success-rate", "standing-orders", "efficiency", "all"})


def _compute_success_rate_analytics(missions: list[dict]) -> dict:
    """Compute success rate analytics across missions."""
    total = len(missions)
    if total == 0:
        return {"total": 0, "achieved": 0, "win_rate": None, "recent_trend": None}

    achieved = sum(1 for m in missions if m.get("outcome_achieved"))
    win_rate = round(achieved / total * 100, 1)

    # Trend: last-5 vs overall
    recent = list(reversed(missions))[:5]
    r_achieved = sum(1 for m in recent if m.get("outcome_achieved"))
    recent_rate = round(r_achieved / len(recent) * 100, 1) if recent else None

    # Win rate by fleet size buckets
    by_size: dict[str, dict] = {}
    for m in missions:
        ships = m.get("fleet", {}).get("ships_used", 0)
        bucket = "1" if ships <= 1 else "2-3" if ships <= 3 else "4+"
        entry = by_size.get(bucket, {"total": 0, "achieved": 0})
        by_size[bucket] = {
            "total": entry["total"] + 1,
            "achieved": entry["achieved"] + (1 if m.get("outcome_achieved") else 0),
        }

    size_rates = {}
    for bucket, data in by_size.items():
        rate = round(data["achieved"] / data["total"] * 100, 1) if data["total"] else 0
        size_rates[bucket] = {"total": data["total"], "win_rate": rate}

    return {
        "total": total,
        "achieved": achieved,
        "not_achieved": total - achieved,
        "win_rate": win_rate,
        "recent_trend": recent_rate,
        "by_fleet_size": size_rates,
    }


def _compute_standing_order_analytics(
    missions: list[dict], stats: dict
) -> dict:
    """Compute standing order violation analytics."""
    by_order = stats.get("by_order", {})
    total_violations = stats.get("total_violations", 0)
    total_missions = stats.get("total_missions", 0)
    vpm = stats.get("violations_per_mission", 0.0)

    # Top offenders sorted by count
    top_offenders = sorted(
        [
            {
                "order": order,
                "count": data.get("count", 0),
                "missions_affected": len(data.get("missions", [])),
            }
            for order, data in by_order.items()
        ],
        key=lambda x: -x["count"],
    )

    corr = stats.get("correlation", {})

    return {
        "total_missions": total_missions,
        "total_violations": total_violations,
        "violations_per_mission": vpm,
        "top_offenders": top_offenders,
        "correlation": corr,
    }


def _compute_efficiency_analytics(missions: list[dict]) -> dict:
    """Compute efficiency analytics across missions."""
    if not missions:
        return {
            "mission_count": 0,
            "tokens_per_task": None,
            "duration_per_task": None,
            "avg_budget_utilization": None,
            "avg_ships_per_mission": None,
            "tasks_per_ship": None,
        }

    # Tokens per task
    tokens_per_task_values: list[float] = []
    duration_per_task_values: list[float] = []
    budget_utils: list[float] = []
    ships_list: list[int] = []
    tasks_per_ship_values: list[float] = []

    for m in missions:
        budget = m.get("budget", {})
        tasks = m.get("tasks", {})
        fleet = m.get("fleet", {})
        total_tasks = tasks.get("total", 0)
        tokens = budget.get("tokens_consumed")
        duration = m.get("duration_minutes")
        pct = budget.get("pct_consumed")
        ships = fleet.get("ships_used")

        if tokens is not None and total_tasks > 0:
            tokens_per_task_values.append(tokens / total_tasks)
        if duration is not None and total_tasks > 0:
            duration_per_task_values.append(duration / total_tasks)
        if pct is not None:
            budget_utils.append(pct)
        if ships is not None:
            ships_list.append(ships)
            if total_tasks > 0:
                tasks_per_ship_values.append(total_tasks / ships)

    tpt = _safe_mean(tokens_per_task_values)
    dpt = _safe_mean(duration_per_task_values)
    abu = _safe_mean(budget_utils)
    aspm = _safe_mean(ships_list)
    tps = _safe_mean(tasks_per_ship_values)

    return {
        "mission_count": len(missions),
        "tokens_per_task": int(round(tpt)) if tpt is not None else None,
        "duration_per_task": round(dpt, 1) if dpt is not None else None,
        "avg_budget_utilization": round(abu, 1) if abu is not None else None,
        "avg_ships_per_mission": round(aspm, 1) if aspm is not None else None,
        "tasks_per_ship": round(tps, 1) if tps is not None else None,
    }


def _format_analytics_text(metric: str, data: dict) -> str:
    """Format analytics results as human-readable text."""
    lines: list[str] = []

    if metric in ("success-rate", "all"):
        sr = data.get("success_rate", {})
        lines.append(f"Success Rate \u2014 {sr['total']} missions")
        if sr.get("win_rate") is not None:
            lines.append(
                f"  Win rate: {sr['win_rate']}% "
                f"({sr['achieved']} achieved, {sr['not_achieved']} not)"
            )
            if sr.get("recent_trend") is not None:
                lines.append(f"  Recent trend (last 5): {sr['recent_trend']}%")
            by_size = sr.get("by_fleet_size", {})
            if by_size:
                lines.append("  By fleet size:")
                for bucket in sorted(by_size.keys()):
                    info = by_size[bucket]
                    lines.append(
                        f"    {bucket} ships: {info['win_rate']}% "
                        f"({info['total']} missions)"
                    )
        lines.append("")

    if metric in ("standing-orders", "all"):
        so = data.get("standing_orders", {})
        lines.append(
            f"Standing Orders \u2014 {so['total_violations']} violations "
            f"across {so['total_missions']} missions "
            f"({so['violations_per_mission']}/mission)"
        )
        for item in so.get("top_offenders", []):
            lines.append(
                f"  {item['order']}: {item['count']} violations "
                f"({item['missions_affected']} missions)"
            )
        corr = so.get("correlation", {})
        if corr:
            lines.append(
                f"  Correlation: {corr.get('failures_with_violations', 0)} failures "
                f"and {corr.get('successes_with_violations', 0)} successes "
                f"had violations"
            )
        lines.append("")

    if metric in ("efficiency", "all"):
        ef = data.get("efficiency", {})
        lines.append(f"Efficiency \u2014 {ef['mission_count']} missions")
        if ef.get("tokens_per_task") is not None:
            tok_str = (
                f"{round(ef['tokens_per_task'] / 1000)}K"
                if ef["tokens_per_task"] >= 1000
                else str(ef["tokens_per_task"])
            )
            lines.append(f"  Tokens per task: {tok_str}")
        if ef.get("duration_per_task") is not None:
            lines.append(f"  Duration per task: {ef['duration_per_task']} min")
        if ef.get("avg_budget_utilization") is not None:
            lines.append(f"  Budget utilization: {ef['avg_budget_utilization']}%")
        if ef.get("avg_ships_per_mission") is not None:
            lines.append(f"  Ships per mission: {ef['avg_ships_per_mission']}")
        if ef.get("tasks_per_ship") is not None:
            lines.append(f"  Tasks per ship: {ef['tasks_per_ship']}")
        lines.append("")

    return "\n".join(lines)


def cmd_analytics(args: argparse.Namespace) -> None:
    """Compute and display cross-mission analytics."""
    missions_dir, index_path = _resolve_fleet_paths(args)
    metric = args.metric

    if not index_path.exists():
        _die("No fleet intelligence index found. Run 'nelson-data index' first.")

    index = _read_json_optional(index_path)
    if index is None:
        _die("Failed to read fleet intelligence index.")

    missions = index.get("missions", [])

    # Apply --last filter
    last_n = max(0, args.last)
    if last_n > 0:
        missions = list(reversed(missions))[:last_n]
        missions = list(reversed(missions))  # restore chronological order

    # Read standing order stats for the standing-orders metric
    memory_dir = missions_dir.parent / "memory"
    stats = _read_json_optional(memory_dir / "standing-order-stats.json") or {}

    result: dict[str, Any] = {}
    if metric in ("success-rate", "all"):
        result["success_rate"] = _compute_success_rate_analytics(missions)
    if metric in ("standing-orders", "all"):
        result["standing_orders"] = _compute_standing_order_analytics(missions, stats)
    if metric in ("efficiency", "all"):
        result["efficiency"] = _compute_efficiency_analytics(missions)

    if args.json_output:
        # For single metrics, unwrap the wrapper key
        output = result if metric == "all" else result.get(metric.replace("-", "_"), result)
        print(json.dumps(output, indent=JSON_INDENT))
    else:
        print(_format_analytics_text(metric if metric != "all" else "all", result))


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="nelson-data",
        description="Structured data capture for Nelson missions.",
    )
    subs = parser.add_subparsers(dest="command", help="Subcommand")

    # --- init ---
    p_init = subs.add_parser("init", help="Create mission directory and sailing orders")
    p_init.add_argument("--outcome", required=True, help="Mission outcome statement")
    p_init.add_argument("--metric", required=True, help="Success metric")
    p_init.add_argument(
        "--deadline", required=True, help="Deadline (e.g. this_session)"
    )
    p_init.add_argument("--token-budget", type=int, default=None, help="Token budget")
    p_init.add_argument(
        "--time-limit", type=int, default=None, help="Time limit in minutes"
    )
    p_init.add_argument(
        "--constraints", action="append", help="Constraint (repeatable)"
    )
    p_init.add_argument(
        "--out-of-scope", action="append", help="Out of scope item (repeatable)"
    )
    p_init.add_argument(
        "--stop-criteria", action="append", help="Stop criterion (repeatable)"
    )
    p_init.add_argument(
        "--handoff-artifacts", action="append", help="Handoff artifact (repeatable)"
    )

    # --- squadron ---
    p_sq = subs.add_parser("squadron", help="Record squadron formation")
    p_sq.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_sq.add_argument("--admiral", required=True, help="Admiral ship name")
    p_sq.add_argument("--admiral-model", required=True, help="Admiral model")
    p_sq.add_argument(
        "--captain",
        action="append",
        help="Captain spec: name:class:model:task_id (repeatable)",
    )
    p_sq.add_argument("--red-cell", default=None, help="Red cell ship name")
    p_sq.add_argument("--red-cell-model", default=None, help="Red cell model")
    p_sq.add_argument(
        "--mode",
        default="subagents",
        help="Execution mode: single-session, subagents, agent-team",
    )

    # --- task ---
    p_task = subs.add_parser("task", help="Add task to battle plan")
    p_task.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_task.add_argument("--id", required=True, type=int, help="Task ID")
    p_task.add_argument("--name", required=True, help="Task name")
    p_task.add_argument("--owner", required=True, help="Owning ship name")
    p_task.add_argument("--deliverable", required=True, help="Task deliverable")
    p_task.add_argument("--deps", default="", help="Comma-separated dependency IDs")
    p_task.add_argument(
        "--station-tier",
        required=True,
        type=int,
        choices=[0, 1, 2, 3],
        help="Station tier (0-3)",
    )
    p_task.add_argument(
        "--files", default="", help="Comma-separated file glob patterns"
    )
    p_task.add_argument("--validation", default=None, help="Validation criteria")
    p_task.add_argument(
        "--rollback-note", action="store_true", help="Rollback note required"
    )
    p_task.add_argument(
        "--admiralty-action", action="store_true", help="Admiralty action required"
    )

    # --- plan-approved ---
    p_pa = subs.add_parser("plan-approved", help="Finalize battle plan")
    p_pa.add_argument("--mission-dir", required=True, help="Mission directory path")

    # --- event ---
    p_ev = subs.add_parser("event", help="Log a mission event")
    p_ev.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_ev.add_argument("--type", required=True, help="Event type")
    p_ev.add_argument("--checkpoint", type=int, default=None, help="Checkpoint number")
    # Additional key-value pairs handled via parse_known_args

    # --- checkpoint ---
    p_cp = subs.add_parser("checkpoint", help="Record a quarterdeck checkpoint")
    p_cp.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_cp.add_argument("--pending", required=True, type=int, help="Pending task count")
    p_cp.add_argument(
        "--in-progress", required=True, type=int, help="In-progress task count"
    )
    p_cp.add_argument(
        "--completed", required=True, type=int, help="Completed task count"
    )
    p_cp.add_argument("--blocked", type=int, default=0, help="Blocked task count")
    p_cp.add_argument(
        "--tokens-spent", required=True, type=int, help="Tokens spent so far"
    )
    p_cp.add_argument(
        "--tokens-remaining", required=True, type=int, help="Tokens remaining"
    )
    p_cp.add_argument(
        "--hull-green", required=True, type=int, help="Ships at green hull"
    )
    p_cp.add_argument(
        "--hull-amber", required=True, type=int, help="Ships at amber hull"
    )
    p_cp.add_argument("--hull-red", required=True, type=int, help="Ships at red hull")
    p_cp.add_argument(
        "--hull-critical", required=True, type=int, help="Ships at critical hull"
    )
    p_cp.add_argument(
        "--decision",
        required=True,
        help="Admiral decision: continue, rescope, or stop",
    )
    p_cp.add_argument("--rationale", required=True, help="Decision rationale")

    # --- stand-down ---
    p_sd = subs.add_parser("stand-down", help="Record mission completion")
    p_sd.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_sd.add_argument(
        "--outcome-achieved", action="store_true", help="Was the outcome achieved?"
    )
    p_sd.add_argument("--actual-outcome", default="", help="Actual outcome description")
    p_sd.add_argument("--metric-result", default="", help="Success metric result")
    p_sd.add_argument(
        "--adopt", action="append", default=None, help="Pattern to adopt (repeatable)"
    )
    p_sd.add_argument(
        "--avoid", action="append", default=None, help="Pattern to avoid (repeatable)"
    )

    # --- status ---
    p_st = subs.add_parser("status", help="Print current fleet status")
    p_st.add_argument("--mission-dir", required=True, help="Mission directory path")

    # --- index ---
    p_idx = subs.add_parser("index", help="Build fleet intelligence index")
    p_idx.add_argument("--missions-dir", default=None, help="Missions directory path")
    # Alias: --mission-dir accepted for consistency with other subcommands
    p_idx.add_argument("--mission-dir", dest="missions_dir", help=argparse.SUPPRESS)
    p_idx.add_argument("--rebuild", action="store_true", help="Force full re-index")

    # --- history ---
    p_hist = subs.add_parser("history", help="Display fleet intelligence analytics")
    p_hist.add_argument("--missions-dir", default=None, help="Missions directory path")
    # Alias: --mission-dir accepted for consistency with other subcommands
    p_hist.add_argument("--mission-dir", dest="missions_dir", help=argparse.SUPPRESS)
    p_hist.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output as JSON",
    )
    p_hist.add_argument("--last", type=int, default=10, help="Recent missions to show")

    # --- brief ---
    p_brief = subs.add_parser("brief", help="Intelligence brief from past missions")
    p_brief.add_argument("--missions-dir", default=None, help="Missions directory path")
    p_brief.add_argument("--mission-dir", dest="missions_dir", help=argparse.SUPPRESS)
    p_brief.add_argument(
        "--context", default="", help="Context for upcoming mission"
    )
    p_brief.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output as JSON",
    )

    # --- analytics ---
    p_an = subs.add_parser("analytics", help="Cross-mission analytics")
    p_an.add_argument("--missions-dir", default=None, help="Missions directory path")
    p_an.add_argument("--mission-dir", dest="missions_dir", help=argparse.SUPPRESS)
    p_an.add_argument(
        "--metric",
        required=True,
        choices=sorted(VALID_METRICS),
        help="Metric to analyze",
    )
    p_an.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output as JSON",
    )
    p_an.add_argument(
        "--last", type=int, default=0, help="Limit to last N missions (0=all)"
    )

    return parser


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse arguments and dispatch to the correct subcommand."""
    parser = build_parser()

    # Use parse_known_args so the 'event' subcommand can accept arbitrary
    # --key value pairs beyond the defined arguments.
    args, extra = parser.parse_known_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "init": lambda: cmd_init(args),
        "squadron": lambda: cmd_squadron(args),
        "task": lambda: cmd_task(args),
        "plan-approved": lambda: cmd_plan_approved(args),
        "event": lambda: cmd_event(args, extra),
        "checkpoint": lambda: cmd_checkpoint(args),
        "stand-down": lambda: cmd_stand_down(args),
        "status": lambda: cmd_status(args),
        "index": lambda: cmd_index(args),
        "history": lambda: cmd_history(args),
        "brief": lambda: cmd_brief(args),
        "analytics": lambda: cmd_analytics(args),
    }

    handler = dispatch.get(args.command)
    if handler is None:
        _die(f"Error: unknown command '{args.command}'")
    else:
        handler()


if __name__ == "__main__":
    main()
