"""Cross-mission trust calibration learned from admiralty decisions.

Aggregates per-(task_type, ship_class) decision outcomes (approved /
modified / rejected) from completed missions into a calibration store.
Emits advisory stderr notices at plan-approved time so the admiral can
weigh historical override rates when setting station_tier.

v1 is advisory-only: no station_tier mutation, no significance gating.
Backwards compatible — every schema addition is optional.

No external dependencies — stdlib only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from nelson_data_memory import _find_completed_missions, _resolve_memory_dir
from nelson_data_utils import (
    JSON_INDENT,
    VALID_DECISION_TYPES,
    _err,
    _file_lock,
    _now_iso,
    _read_json_optional,
    _write_json,
)


CALIBRATION_FILENAME = "trust-calibration.json"
CALIBRATION_LOCK_FILENAME = ".trust-calibration.lock"
MIN_DECISIONS_FOR_ADVISORY = 3


# ---------------------------------------------------------------------------
# Store helpers
# ---------------------------------------------------------------------------


def _empty_calibration() -> dict[str, Any]:
    """Return an empty calibration store structure."""
    return {
        "version": 1,
        "updated_at": None,
        "buckets": {},
        "by_task_type": {},
        "_tracked_missions": [],
    }


def _bucket_key(task_type: str, ship_class: str) -> str:
    """Return the flat key used in the buckets map."""
    return f"{task_type}::{ship_class}"


def _override_rate(approved: int, modified: int, rejected: int) -> float:
    """Compute the override rate (modified + rejected) / total decisions."""
    total = approved + modified + rejected
    if total == 0:
        return 0.0
    return round((modified + rejected) / total, 4)


def _build_squadron_index(fleet_status: dict | None) -> dict[str, str]:
    """Return a map of ship_name -> ship_class from fleet-status.json data."""
    if not fleet_status:
        return {}
    squadron = fleet_status.get("squadron", []) or []
    return {
        ship.get("ship_name", ""): ship.get("ship_class", "")
        for ship in squadron
        if ship.get("ship_name")
    }


def _build_task_index(battle_plan: dict | None) -> dict[int, dict]:
    """Return a map of task_id -> task dict from battle-plan.json data."""
    if not battle_plan:
        return {}
    return {t["id"]: t for t in battle_plan.get("tasks", []) if "id" in t}


# ---------------------------------------------------------------------------
# Decision extraction
# ---------------------------------------------------------------------------


def _extract_decisions_from_mission(mission_dir: Path) -> list[dict]:
    """Return all admiralty_action_completed events that carry decision_type.

    Each returned dict has keys: task_id, decision_type, task_type, ship_class.
    Events missing decision_type, task_type, or ship_class are skipped — only
    fully-attributed decisions feed the calibration store.
    """
    mission_log = _read_json_optional(mission_dir / "mission-log.json") or {}
    events = mission_log.get("events", [])

    battle_plan = _read_json_optional(mission_dir / "battle-plan.json")
    fleet_status = _read_json_optional(mission_dir / "fleet-status.json")
    task_index = _build_task_index(battle_plan)
    squadron_index = _build_squadron_index(fleet_status)

    decisions: list[dict] = []
    for ev in events:
        if ev.get("type") != "admiralty_action_completed":
            continue
        data = ev.get("data", {}) or {}
        decision_type = data.get("decision_type")
        if decision_type not in VALID_DECISION_TYPES:
            continue

        task_type = data.get("task_type")
        ship_class = data.get("ship_class")

        if (not task_type or not ship_class):
            task_id = data.get("task_id")
            task = task_index.get(task_id) if task_id is not None else None
            if task is not None:
                task_type = task_type or task.get("task_type")
                owner = task.get("owner")
                if not ship_class and owner:
                    ship_class = squadron_index.get(owner)

        if not task_type or not ship_class:
            continue

        decisions.append({
            "task_id": data.get("task_id"),
            "decision_type": decision_type,
            "task_type": task_type,
            "ship_class": ship_class,
        })

    return decisions


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _apply_decision_to_bucket(
    bucket: dict[str, Any],
    decision_type: str,
    task_type: str,
    ship_class: str,
    now: str,
) -> dict[str, Any]:
    """Return a new bucket dict with *decision_type* applied."""
    approved = bucket.get("approved", 0) + (1 if decision_type == "approved" else 0)
    modified = bucket.get("modified", 0) + (1 if decision_type == "modified" else 0)
    rejected = bucket.get("rejected", 0) + (1 if decision_type == "rejected" else 0)
    total = approved + modified + rejected
    return {
        "task_type": task_type,
        "ship_class": ship_class,
        "total_decisions": total,
        "approved": approved,
        "modified": modified,
        "rejected": rejected,
        "override_rate": _override_rate(approved, modified, rejected),
        "last_updated": now,
    }


def _apply_decision_to_rollup(
    rollup: dict[str, Any],
    decision_type: str,
) -> dict[str, Any]:
    """Return a new by_task_type rollup with *decision_type* applied."""
    approved = rollup.get("approved", 0) + (1 if decision_type == "approved" else 0)
    modified = rollup.get("modified", 0) + (1 if decision_type == "modified" else 0)
    rejected = rollup.get("rejected", 0) + (1 if decision_type == "rejected" else 0)
    total = approved + modified + rejected
    return {
        "total_decisions": total,
        "approved": approved,
        "modified": modified,
        "rejected": rejected,
        "override_rate": _override_rate(approved, modified, rejected),
    }


def _apply_decisions(
    calibration: dict[str, Any],
    decisions: list[dict],
) -> dict[str, Any]:
    """Return a new calibration dict with all *decisions* applied."""
    now = _now_iso()
    buckets = dict(calibration.get("buckets", {}))
    by_task_type = dict(calibration.get("by_task_type", {}))

    for d in decisions:
        task_type = d["task_type"]
        ship_class = d["ship_class"]
        decision_type = d["decision_type"]
        key = _bucket_key(task_type, ship_class)
        buckets[key] = _apply_decision_to_bucket(
            buckets.get(key, {}),
            decision_type,
            task_type,
            ship_class,
            now,
        )
        by_task_type[task_type] = _apply_decision_to_rollup(
            by_task_type.get(task_type, {}),
            decision_type,
        )

    return {
        **calibration,
        "version": 1,
        "updated_at": now,
        "buckets": buckets,
        "by_task_type": by_task_type,
    }


# ---------------------------------------------------------------------------
# Incremental update at stand-down
# ---------------------------------------------------------------------------


def _update_override_calibration(mission_dir: Path) -> None:
    """Append calibration data from *mission_dir* to the persistent store.

    Idempotent via ``_tracked_missions``; safe to invoke twice per mission.
    Uses file locking to handle concurrent stand-down calls safely.
    """
    missions_dir = mission_dir.parent
    memory_dir = _resolve_memory_dir(missions_dir)
    calibration_path = memory_dir / CALIBRATION_FILENAME
    lock_path = memory_dir / CALIBRATION_LOCK_FILENAME

    mission_id = mission_dir.name

    with _file_lock(lock_path):
        existing = _read_json_optional(calibration_path) or _empty_calibration()
        tracked = list(existing.get("_tracked_missions", []))
        if mission_id in tracked:
            return

        decisions = _extract_decisions_from_mission(mission_dir)
        # Even when there are no decisions, mark the mission tracked so we
        # do not re-scan it on every subsequent stand-down.
        updated = _apply_decisions(existing, decisions)
        updated = {
            **updated,
            "_tracked_missions": tracked + [mission_id],
        }
        _write_json(calibration_path, updated)


# ---------------------------------------------------------------------------
# Full rebuild from indexed missions
# ---------------------------------------------------------------------------


def _sync_calibration_from_missions(missions_dir: Path) -> None:
    """Backfill the calibration store from missions not yet tracked.

    Called from ``cmd_index`` so missions that predate the calibration store
    can still contribute. Mirrors ``_sync_memory_from_index``.
    """
    memory_dir = _resolve_memory_dir(missions_dir)
    calibration_path = memory_dir / CALIBRATION_FILENAME
    lock_path = memory_dir / CALIBRATION_LOCK_FILENAME

    with _file_lock(lock_path):
        existing = _read_json_optional(calibration_path) or _empty_calibration()
        tracked = list(existing.get("_tracked_missions", []))

        completed = _find_completed_missions(missions_dir)
        new_dirs = [d for d in completed if d.name not in tracked]
        if not new_dirs:
            return

        updated = existing
        new_tracked = list(tracked)
        for mission_dir in new_dirs:
            decisions = _extract_decisions_from_mission(mission_dir)
            updated = _apply_decisions(updated, decisions)
            new_tracked.append(mission_dir.name)

        updated = {**updated, "_tracked_missions": new_tracked}
        _write_json(calibration_path, updated)


# ---------------------------------------------------------------------------
# Advisory printer (called from cmd_plan_approved)
# ---------------------------------------------------------------------------


def _lookup_advisory(
    calibration: dict[str, Any],
    task_type: str,
    ship_class: str,
    min_decisions: int,
) -> dict[str, Any] | None:
    """Return the bucket or rollup to advise from, or None if below threshold.

    Prefers the precise ``(task_type, ship_class)`` bucket; falls back to the
    ``by_task_type`` rollup when the bucket has fewer than *min_decisions*.
    """
    buckets = calibration.get("buckets", {}) or {}
    rollups = calibration.get("by_task_type", {}) or {}

    bucket = buckets.get(_bucket_key(task_type, ship_class))
    if bucket and bucket.get("total_decisions", 0) >= min_decisions:
        return {
            "scope": "bucket",
            "task_type": task_type,
            "ship_class": ship_class,
            "total_decisions": bucket["total_decisions"],
            "override_rate": bucket["override_rate"],
        }

    rollup = rollups.get(task_type)
    if rollup and rollup.get("total_decisions", 0) >= min_decisions:
        return {
            "scope": "task_type",
            "task_type": task_type,
            "ship_class": ship_class,
            "total_decisions": rollup["total_decisions"],
            "override_rate": rollup["override_rate"],
        }
    return None


def _print_calibration_advisories(
    mission_dir: Path,
    tasks: list[dict],
) -> None:
    """Print one advisory per task with a high-override history (stderr only).

    No-op when the calibration file is missing. Tasks without ``task_type``
    are skipped silently. Each advisory falls back from the bucket to the
    task-type rollup when the bucket has too few samples.
    """
    if not tasks:
        return

    missions_dir = mission_dir.parent
    # Read-only path: do not create the memory directory just to look up
    # advisory data. Stand-down's writer is responsible for creating it.
    memory_dir = missions_dir.parent / "memory"
    calibration_path = memory_dir / CALIBRATION_FILENAME
    if not calibration_path.exists():
        return
    calibration = _read_json_optional(calibration_path)
    if not calibration:
        return

    fleet_status = _read_json_optional(mission_dir / "fleet-status.json")
    squadron_index = _build_squadron_index(fleet_status)

    for task in tasks:
        task_type = task.get("task_type")
        if not task_type:
            continue
        owner = task.get("owner")
        ship_class = squadron_index.get(owner) if owner else None
        if not ship_class:
            continue

        advisory = _lookup_advisory(
            calibration,
            task_type,
            ship_class,
            MIN_DECISIONS_FOR_ADVISORY,
        )
        if advisory is None:
            continue

        rate_pct = round(advisory["override_rate"] * 100)
        n = advisory["total_decisions"]
        scope_note = (
            f"{task_type} on {ship_class}"
            if advisory["scope"] == "bucket"
            else f"{task_type} (all ship classes)"
        )
        _err(
            f"[nelson-data] Trust advisory: task {task.get('id')} "
            f"({scope_note}) — historical override rate {rate_pct}% "
            f"(n={n}). Consider raising station_tier."
        )


# ---------------------------------------------------------------------------
# CLI: trust-report
# ---------------------------------------------------------------------------


def _resolve_missions_dir(args: argparse.Namespace) -> Path:
    """Return the missions directory from args, defaulting to .nelson/missions."""
    raw = getattr(args, "missions_dir", None)
    if raw:
        return Path(raw)
    return Path(".nelson/missions")


def _format_trust_report_text(
    rows: list[dict],
    rollups: list[dict],
    min_decisions: int,
) -> str:
    """Return the human-readable trust report."""
    lines: list[str] = []
    lines.append(
        f"Trust calibration — {len(rows)} bucket(s) with >= {min_decisions} decision(s)"
    )
    lines.append("")
    if not rows:
        lines.append("  No buckets meet the sample threshold yet.")
    else:
        header = (
            f"  {'task_type':<24} {'ship_class':<12} "
            f"{'n':>4}  {'over%':>6}  approved/modified/rejected"
        )
        lines.append(header)
        lines.append("  " + "-" * (len(header) - 2))
        for r in rows:
            rate_pct = round(r["override_rate"] * 100, 1)
            lines.append(
                f"  {r['task_type']:<24.24} {r['ship_class']:<12.12} "
                f"{r['total_decisions']:>4}  {rate_pct:>5}%  "
                f"{r['approved']}/{r['modified']}/{r['rejected']}"
            )
    lines.append("")

    if rollups:
        lines.append("By task type:")
        for r in rollups:
            rate_pct = round(r["override_rate"] * 100, 1)
            lines.append(
                f"  {r['task_type']:<24.24} "
                f"n={r['total_decisions']:<4} over%={rate_pct:>5}%  "
                f"{r['approved']}/{r['modified']}/{r['rejected']}"
            )

    return "\n".join(lines)


def cmd_trust_report(args: argparse.Namespace) -> None:
    """Print the trust calibration store sorted by override rate."""
    missions_dir = _resolve_missions_dir(args)
    memory_dir = _resolve_memory_dir(missions_dir)
    calibration_path = memory_dir / CALIBRATION_FILENAME
    min_decisions = max(0, int(getattr(args, "min_decisions", MIN_DECISIONS_FOR_ADVISORY)))

    calibration = _read_json_optional(calibration_path) or _empty_calibration()
    buckets = calibration.get("buckets", {}) or {}
    rollups = calibration.get("by_task_type", {}) or {}

    rows = [
        b for b in buckets.values()
        if b.get("total_decisions", 0) >= min_decisions
    ]
    rows.sort(key=lambda b: (-b.get("override_rate", 0.0), -b.get("total_decisions", 0)))

    rollup_rows = [
        {"task_type": tt, **data}
        for tt, data in rollups.items()
        if data.get("total_decisions", 0) >= min_decisions
    ]
    rollup_rows.sort(
        key=lambda b: (-b.get("override_rate", 0.0), -b.get("total_decisions", 0))
    )

    if getattr(args, "json_output", False):
        payload = {
            "version": calibration.get("version", 1),
            "updated_at": calibration.get("updated_at"),
            "min_decisions": min_decisions,
            "buckets": rows,
            "by_task_type": rollup_rows,
        }
        print(json.dumps(payload, indent=JSON_INDENT))
        return

    print(_format_trust_report_text(rows, rollup_rows, min_decisions))
