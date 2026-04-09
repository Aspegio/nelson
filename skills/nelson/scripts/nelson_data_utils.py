"""Shared I/O, validation, and constants for Nelson data capture.

This module provides the foundational utilities used by all other
nelson_data_* modules: JSON I/O with atomic writes, error handling,
argument parsing helpers, and shared constants.

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


def _safe_mean(values: list[float | int]) -> float | None:
    """Return the mean of *values*, or None if the list is empty."""
    if not values:
        return None
    return sum(values) / len(values)


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
