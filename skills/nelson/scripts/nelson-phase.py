#!/usr/bin/env python3
"""Deterministic phase engine for Nelson missions.

Tracks the current mission phase, validates phase-appropriate tool usage,
and enforces transition criteria.  The admiral still does all judgment
work inside each phase; this script handles structural transitions only.

Phases:
    SAILING_ORDERS -> BATTLE_PLAN -> FORMATION -> PERMISSION -> UNDERWAY -> STAND_DOWN

Usage examples:

    python3 nelson-phase.py current --mission-dir .nelson/missions/2026-04-09_120000_a1b2c3d4
    python3 nelson-phase.py advance --mission-dir .nelson/missions/2026-04-09_120000_a1b2c3d4
    python3 nelson-phase.py validate-tool --tool Agent
    python3 nelson-phase.py set --mission-dir .nelson/missions/2026-04-09_120000_a1b2c3d4 --phase UNDERWAY

No external dependencies -- stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


try:
    import fcntl
except ImportError:
    fcntl = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PHASES = (
    "SAILING_ORDERS",
    "BATTLE_PLAN",
    "FORMATION",
    "PERMISSION",
    "UNDERWAY",
    "STAND_DOWN",
)

PHASE_SET = frozenset(PHASES)

# Tools blocked per phase.  Tools not listed here are always allowed.
BLOCKED_TOOLS: dict[str, frozenset[str]] = {
    "SAILING_ORDERS": frozenset({"Agent", "TeamCreate", "TaskCreate"}),
    "BATTLE_PLAN": frozenset({"Agent", "TeamCreate", "TaskCreate"}),
    "FORMATION": frozenset({"Agent", "TeamCreate"}),
    "PERMISSION": frozenset({"Agent", "TeamCreate", "TaskCreate"}),
    "UNDERWAY": frozenset(),
    "STAND_DOWN": frozenset({"TeamCreate", "TaskCreate"}),
}

# Human-readable descriptions of exit criteria per phase.
EXIT_CRITERIA_DESC: dict[str, str] = {
    "SAILING_ORDERS": "sailing-orders.json must exist in the mission directory",
    "BATTLE_PLAN": "battle-plan.json must have tasks, all with station_tier assigned",
    "FORMATION": "battle-plan.json must have a squadron section",
    "PERMISSION": "a permission_granted event must exist in mission-log.json",
    "UNDERWAY": "all tasks must be completed or mission aborted",
    "STAND_DOWN": "STAND_DOWN is the terminal phase",
}

JSON_INDENT = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _err(msg: str) -> None:
    """Print a message to stderr."""
    print(msg, file=sys.stderr)


def _die(msg: str) -> None:
    """Print error to stderr and exit 1."""
    _err(msg)
    sys.exit(1)


def _read_json(path: Path) -> dict | list:
    """Read and parse a JSON file."""
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except json.JSONDecodeError:
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
    """Write data as formatted JSON using atomic temp-file + replace."""
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
    """Append an event to mission-log.json using read-modify-write."""
    log_path = mission_dir / "mission-log.json"
    lock_path = mission_dir / ".mission-log.lock"

    lock_file = open(lock_path, "w")
    try:
        if fcntl:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
        if log_path.exists():
            log = _read_json(log_path)
        else:
            log = {"version": 1, "events": []}
        new_events = list(log.get("events", [])) + [event]
        new_log = {**log, "events": new_events}
        _write_json(log_path, new_log)
    finally:
        if fcntl:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def _find_active_mission() -> Path | None:
    """Find the active mission directory from .nelson/.active-* files.

    Returns the mission directory path from the most recently modified
    .active-* file, or None if no active mission exists.
    """
    nelson_dir = Path(".nelson")
    if not nelson_dir.is_dir():
        return None
    active_files = sorted(nelson_dir.glob(".active-*"), key=lambda p: p.stat().st_mtime)
    if not active_files:
        return None
    # Use the most recently modified active file
    mission_path = active_files[-1].read_text(encoding="utf-8").strip()
    mission_dir = Path(mission_path)
    if mission_dir.is_dir():
        return mission_dir
    return None


def _resolve_mission_dir(args: argparse.Namespace) -> Path | None:
    """Resolve mission directory from args or auto-discovery.

    Returns None if no mission can be found (caller decides if this
    is an error or a silent no-op).
    """
    raw = getattr(args, "mission_dir", None)
    if raw:
        p = Path(raw)
        if not p.is_dir():
            _die(f"Error: mission directory does not exist: {p}")
        return p
    return _find_active_mission()


def _get_phase(mission_dir: Path) -> str | None:
    """Read the current phase from fleet-status.json.

    Returns None if fleet-status.json doesn't exist or has no phase field.
    """
    fs_path = mission_dir / "fleet-status.json"
    if not fs_path.exists():
        return None
    fs = _read_json(fs_path)
    return fs.get("mission", {}).get("phase")


def _set_phase(mission_dir: Path, phase: str) -> None:
    """Write the phase to fleet-status.json, preserving other fields."""
    fs_path = mission_dir / "fleet-status.json"
    if fs_path.exists():
        fs = _read_json(fs_path)
    else:
        fs = {"version": 1}
    new_fs = {
        **fs,
        "mission": {
            **fs.get("mission", {}),
            "phase": phase,
        },
        "last_updated": _now_iso(),
    }
    _write_json(fs_path, new_fs)


def _next_phase(current: str) -> str | None:
    """Return the next phase after current, or None if terminal."""
    try:
        idx = PHASES.index(current)
    except ValueError:
        return None
    if idx + 1 >= len(PHASES):
        return None
    return PHASES[idx + 1]


def _get_last_checkpoint_number(events: list[dict]) -> int:
    """Return the highest checkpoint number from events, or 0."""
    nums = [e.get("checkpoint", 0) for e in events if e.get("type") == "checkpoint"]
    return max(nums) if nums else 0


# ---------------------------------------------------------------------------
# Exit Criteria Validators
# ---------------------------------------------------------------------------


def _check_sailing_orders_exit(mission_dir: Path) -> str | None:
    """Check exit criteria for SAILING_ORDERS phase.

    Returns None if criteria met, or an error message if not.
    """
    so_path = mission_dir / "sailing-orders.json"
    if not so_path.exists():
        return "sailing-orders.json does not exist"
    so = _read_json(so_path)
    if not so.get("outcome"):
        return "sailing-orders.json is missing an outcome"
    return None


def _check_battle_plan_exit(mission_dir: Path) -> str | None:
    """Check exit criteria for BATTLE_PLAN phase.

    Returns None if criteria met, or an error message if not.
    """
    bp_path = mission_dir / "battle-plan.json"
    if not bp_path.exists():
        return "battle-plan.json does not exist"
    bp = _read_json(bp_path)
    tasks = bp.get("tasks", [])
    if not tasks:
        return "battle-plan.json has no tasks defined"
    for task in tasks:
        if task.get("station_tier") is None:
            return f"task {task.get('id', '?')} is missing a station_tier"
    return None


def _check_formation_exit(mission_dir: Path) -> str | None:
    """Check exit criteria for FORMATION phase.

    Returns None if criteria met, or an error message if not.
    """
    bp_path = mission_dir / "battle-plan.json"
    if not bp_path.exists():
        return "battle-plan.json does not exist"
    bp = _read_json(bp_path)
    squadron = bp.get("squadron")
    if not squadron:
        return "battle-plan.json has no squadron section"
    if not squadron.get("admiral"):
        return "squadron has no admiral assigned"
    return None


def _check_permission_exit(mission_dir: Path) -> str | None:
    """Check exit criteria for PERMISSION phase.

    Returns None if criteria met, or an error message if not.
    """
    log_path = mission_dir / "mission-log.json"
    if not log_path.exists():
        return "mission-log.json does not exist"
    log = _read_json(log_path)
    events = log.get("events", [])
    for event in events:
        if event.get("type") == "permission_granted":
            return None
    return "no permission_granted event found in mission-log.json"


def _check_underway_exit(mission_dir: Path) -> str | None:
    """Check exit criteria for UNDERWAY phase.

    Returns None if criteria met, or an error message if not.
    """
    bp_path = mission_dir / "battle-plan.json"
    if not bp_path.exists():
        return "battle-plan.json does not exist"
    bp = _read_json(bp_path)
    tasks = bp.get("tasks", [])
    if not tasks:
        return "no tasks defined"

    log_path = mission_dir / "mission-log.json"
    if not log_path.exists():
        return "mission-log.json does not exist"
    log = _read_json(log_path)
    events = log.get("events", [])

    completed_ids: set[int] = set()
    for event in events:
        if event.get("type") == "task_completed":
            task_id = event.get("data", {}).get("task_id")
            if task_id is not None:
                completed_ids.add(int(task_id))

    # Check for mission abort
    for event in events:
        if event.get("type") == "mission_complete":
            return None

    all_task_ids = {int(t["id"]) for t in tasks if "id" in t}
    pending = all_task_ids - completed_ids
    if pending:
        return f"tasks not yet completed: {sorted(pending)}"
    return None


# Map phase -> exit criteria checker
EXIT_VALIDATORS: dict[str, Any] = {
    "SAILING_ORDERS": _check_sailing_orders_exit,
    "BATTLE_PLAN": _check_battle_plan_exit,
    "FORMATION": _check_formation_exit,
    "PERMISSION": _check_permission_exit,
    "UNDERWAY": _check_underway_exit,
}


# ---------------------------------------------------------------------------
# Subcommand: current
# ---------------------------------------------------------------------------


def cmd_current(args: argparse.Namespace) -> None:
    """Print the current mission phase."""
    mission_dir = _resolve_mission_dir(args)
    if mission_dir is None:
        return  # silent no-op: no active mission

    phase = _get_phase(mission_dir)
    if phase is None:
        return  # silent no-op: no phase tracking

    print(phase)


# ---------------------------------------------------------------------------
# Subcommand: advance
# ---------------------------------------------------------------------------


def cmd_advance(args: argparse.Namespace) -> None:
    """Validate exit criteria and advance to the next phase."""
    mission_dir = _resolve_mission_dir(args)
    if mission_dir is None:
        _die("Error: no active mission found")

    current = _get_phase(mission_dir)
    if current is None:
        _die("Error: no phase set in fleet-status.json")

    if current == "STAND_DOWN":
        _die("Error: STAND_DOWN is the terminal phase, cannot advance")

    target = _next_phase(current)
    if target is None:
        _die(f"Error: no phase after {current}")

    # Validate exit criteria
    validator = EXIT_VALIDATORS.get(current)
    if validator:
        error = validator(mission_dir)
        if error:
            _die(
                f"Error: cannot advance from {current} to {target}\n"
                f"Exit criteria not met: {error}\n"
                f"Required: {EXIT_CRITERIA_DESC.get(current, 'unknown')}"
            )

    # Advance
    _set_phase(mission_dir, target)

    # Log the transition
    log_path = mission_dir / "mission-log.json"
    if log_path.exists():
        log = _read_json(log_path)
        events = log.get("events", [])
    else:
        events = []

    event = {
        "type": "phase_transition",
        "checkpoint": _get_last_checkpoint_number(events),
        "timestamp": _now_iso(),
        "data": {
            "from_phase": current,
            "to_phase": target,
        },
    }
    _append_event(mission_dir, event)

    print(f"[nelson-phase] {current} -> {target}")


# ---------------------------------------------------------------------------
# Subcommand: validate-tool
# ---------------------------------------------------------------------------


def cmd_validate_tool(args: argparse.Namespace) -> None:
    """Check if a tool is allowed in the current phase.

    Exits 0 if allowed (or no active mission).
    Exits 1 with a message if blocked.
    """
    tool = args.tool
    mission_dir = _resolve_mission_dir(args)
    if mission_dir is None:
        return  # no active mission -- allow everything

    phase = _get_phase(mission_dir)
    if phase is None:
        return  # no phase tracking -- allow everything (backward compat)

    blocked = BLOCKED_TOOLS.get(phase, frozenset())
    if tool in blocked:
        # Print to stdout so Claude Code can display the blocking reason,
        # and exit 1 so the PreToolUse hook blocks the tool call.
        print(
            f"[nelson-phase] BLOCKED: {tool} is not available during {phase}.\n"
            f"{EXIT_CRITERIA_DESC.get(phase, 'Complete the current phase first.')}"
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Subcommand: set
# ---------------------------------------------------------------------------


def cmd_set(args: argparse.Namespace) -> None:
    """Force-set the mission phase (recovery escape hatch)."""
    phase = args.phase.upper()
    if phase not in PHASE_SET:
        _die(f"Error: invalid phase '{args.phase}'. Valid: {', '.join(PHASES)}")

    raw = getattr(args, "mission_dir", None)
    if not raw:
        _die("Error: --mission-dir is required for set")
    mission_dir = Path(raw)
    if not mission_dir.is_dir():
        _die(f"Error: mission directory does not exist: {mission_dir}")

    old_phase = _get_phase(mission_dir)
    _set_phase(mission_dir, phase)

    old_label = old_phase or "(none)"
    print(f"[nelson-phase] Phase set: {old_label} -> {phase}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Deterministic phase engine for Nelson missions."
    )
    subs = parser.add_subparsers(dest="command")

    # --- current ---
    p_cur = subs.add_parser("current", help="Print current mission phase")
    p_cur.add_argument("--mission-dir", default=None, help="Mission directory path")

    # --- advance ---
    p_adv = subs.add_parser("advance", help="Advance to the next phase")
    p_adv.add_argument("--mission-dir", default=None, help="Mission directory path")

    # --- validate-tool ---
    p_vt = subs.add_parser("validate-tool", help="Check if a tool is allowed")
    p_vt.add_argument("--tool", required=True, help="Tool name to validate")
    p_vt.add_argument("--mission-dir", default=None, help="Mission directory path")

    # --- set ---
    p_set = subs.add_parser("set", help="Force-set the mission phase")
    p_set.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_set.add_argument("--phase", required=True, help="Target phase")

    return parser


def main() -> None:
    """Parse arguments and dispatch to the correct subcommand."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "current": lambda: cmd_current(args),
        "advance": lambda: cmd_advance(args),
        "validate-tool": lambda: cmd_validate_tool(args),
        "set": lambda: cmd_set(args),
    }

    handler = dispatch.get(args.command)
    if handler is None:
        _die(f"Error: unknown command '{args.command}'")
    else:
        handler()


if __name__ == "__main__":
    main()
