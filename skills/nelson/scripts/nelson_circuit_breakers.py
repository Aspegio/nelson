"""Automated budget circuit breakers for Nelson missions.

Evaluates a set of configurable thresholds against mission state and returns
a list of ``BreakerTrip`` records describing which thresholds were crossed
and which damage control procedures are recommended. This module is pure —
callers are responsible for appending events, updating fleet status, or
surfacing advisories.

Thresholds implemented:

* ``hull_integrity_breach``   — any ship's hull_integrity_pct <= threshold
* ``budget_alarm``            — tokens_spent/budget >= ratio AND
                                completed/total < completion ratio
* ``cost_per_task_overrun``   — burn rate per task >= multiplier * rolling
                                median of previous checkpoints
* ``consecutive_failures``    — consecutive ``blocker_raised`` events without
                                an intervening ``blocker_resolved`` >= N
* ``time_limit``              — mission duration_minutes >= configured limit
* ``idle_timeout``            — evaluated by the TeammateIdle hook via
                                ``evaluate_idle_timeout``; tracks first-seen
                                idle time per ship in ``idle-tracker.json``

Circuit breakers are **advisory** in this iteration: they emit events and
surface alarms, but do not abort ships or auto-trigger damage control. A
future ``strict`` mode is out of scope.

No external dependencies — stdlib only.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Defaults & config
# ---------------------------------------------------------------------------


DEFAULT_THRESHOLDS: dict[str, Any] = {
    "enabled": True,
    "hull_integrity_threshold": 80,
    "budget_alarm_ratio": 0.7,
    "budget_alarm_completion_ratio": 0.4,
    "cost_per_task_multiplier": 3.0,
    "cost_per_task_min_history": 3,
    "consecutive_failures": 2,
    "idle_timeout_minutes": 10,
    "time_limit_grace_minutes": 0,
}


def load_config(sailing_orders: dict[str, Any] | None) -> dict[str, Any]:
    """Merge user-supplied circuit breaker config with defaults.

    Unknown keys from *sailing_orders* are dropped so typos do not silently
    override defaults.
    """
    merged = dict(DEFAULT_THRESHOLDS)
    if not sailing_orders:
        return merged
    user = sailing_orders.get("circuit_breakers") or {}
    for key, value in user.items():
        if key in DEFAULT_THRESHOLDS:
            merged[key] = value
    return merged


# ---------------------------------------------------------------------------
# Trip record
# ---------------------------------------------------------------------------


@dataclass
class BreakerTrip:
    """Structured record of a threshold crossing."""

    type: str
    value: Any
    threshold: Any
    action: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_event_data(self) -> dict[str, Any]:
        """Serialise for appending to mission-log.json."""
        return {
            "type": self.type,
            "value": self.value,
            "threshold": self.threshold,
            "action": self.action,
            "message": self.message,
            "context": self.context,
        }


# ---------------------------------------------------------------------------
# Evaluator — called at checkpoint time
# ---------------------------------------------------------------------------


def evaluate(
    fleet_status: dict[str, Any],
    sailing_orders: dict[str, Any] | None,
    mission_log_events: list[dict[str, Any]],
    now_iso: str,
) -> list[BreakerTrip]:
    """Evaluate all checkpoint-time thresholds and return any trips.

    *fleet_status* is the freshly-written fleet-status.json dict.
    *sailing_orders* is the sailing-orders.json dict (may be None).
    *mission_log_events* is the full events list from mission-log.json.
    *now_iso* is the current time stamp in ISO 8601 UTC.
    """
    config = load_config(sailing_orders)
    if not config.get("enabled", True):
        return []

    trips: list[BreakerTrip] = []

    trips.extend(_check_hull_integrity(fleet_status, config))
    trips.extend(_check_budget_alarm(fleet_status, sailing_orders, config))
    trips.extend(_check_cost_per_task_overrun(mission_log_events, config))
    trips.extend(_check_consecutive_failures(mission_log_events, config))
    trips.extend(_check_time_limit(fleet_status, sailing_orders, config, now_iso))

    return trips


def _check_hull_integrity(
    fleet_status: dict[str, Any], config: dict[str, Any]
) -> list[BreakerTrip]:
    """Any ship at or below the hull integrity threshold trips the breaker."""
    threshold = config["hull_integrity_threshold"]
    trips: list[BreakerTrip] = []
    for ship in fleet_status.get("squadron", []):
        pct = ship.get("hull_integrity_pct")
        if pct is None:
            continue
        if pct <= threshold:
            name = ship.get("ship_name", "unknown")
            trips.append(
                BreakerTrip(
                    type="hull_integrity_breach",
                    value=pct,
                    threshold=threshold,
                    action="hull-integrity",
                    message=(
                        f"{name} hull integrity {pct}% <= threshold {threshold}%. "
                        f"See damage-control/hull-integrity.md."
                    ),
                    context={"ship_name": name},
                )
            )
    return trips


def _check_budget_alarm(
    fleet_status: dict[str, Any],
    sailing_orders: dict[str, Any] | None,
    config: dict[str, Any],
) -> list[BreakerTrip]:
    """Trip when tokens are burning faster than tasks are completing."""
    if not sailing_orders:
        return []
    token_limit = (sailing_orders.get("budget") or {}).get("token_limit")
    if not token_limit or token_limit <= 0:
        return []

    budget = fleet_status.get("budget") or {}
    tokens_spent = budget.get("tokens_spent", 0)
    progress = fleet_status.get("progress") or {}
    completed = progress.get("completed", 0)
    total = progress.get("total", 0)
    if total <= 0:
        return []

    spent_ratio = tokens_spent / token_limit
    completion_ratio = completed / total

    alarm_ratio = config["budget_alarm_ratio"]
    completion_threshold = config["budget_alarm_completion_ratio"]

    if spent_ratio >= alarm_ratio and completion_ratio < completion_threshold:
        return [
            BreakerTrip(
                type="budget_alarm",
                value={
                    "spent_ratio": round(spent_ratio, 3),
                    "completion_ratio": round(completion_ratio, 3),
                },
                threshold={
                    "spent_ratio": alarm_ratio,
                    "completion_ratio": completion_threshold,
                },
                action="admiral-review",
                message=(
                    f"Budget alarm: {spent_ratio:.0%} of tokens spent with only "
                    f"{completion_ratio:.0%} of tasks complete. Elevate to Station 2 "
                    f"and review scope."
                ),
                context={
                    "tokens_spent": tokens_spent,
                    "token_limit": token_limit,
                    "completed": completed,
                    "total": total,
                },
            )
        ]
    return []


def _check_cost_per_task_overrun(
    events: list[dict[str, Any]], config: dict[str, Any]
) -> list[BreakerTrip]:
    """Trip when the latest burn-rate-per-task is N times the rolling median."""
    min_history = config["cost_per_task_min_history"]
    multiplier = config["cost_per_task_multiplier"]

    checkpoints = [e for e in events if e.get("type") == "checkpoint"]
    if len(checkpoints) < min_history:
        return []

    rates: list[float] = []
    for cp in checkpoints:
        data = cp.get("data") or {}
        budget = data.get("budget") or {}
        progress = data.get("progress") or {}
        completed = progress.get("completed", 0)
        burn = budget.get("burn_rate_per_checkpoint", 0) or 0
        if completed <= 0 or burn <= 0:
            continue
        rates.append(burn / completed)

    if len(rates) < min_history:
        return []

    latest = rates[-1]
    baseline = statistics.median(rates[:-1])
    if baseline <= 0:
        return []

    if latest >= multiplier * baseline:
        return [
            BreakerTrip(
                type="cost_per_task_overrun",
                value=round(latest, 2),
                threshold=round(multiplier * baseline, 2),
                action="crew-overrun",
                message=(
                    f"Cost per task {latest:.0f} tokens/task is >= "
                    f"{multiplier:.1f}x baseline ({baseline:.0f}). "
                    f"See damage-control/crew-overrun.md."
                ),
                context={"baseline_median": round(baseline, 2)},
            )
        ]
    return []


def _check_consecutive_failures(
    events: list[dict[str, Any]], config: dict[str, Any]
) -> list[BreakerTrip]:
    """Trip on N consecutive blockers without resolution."""
    threshold = config["consecutive_failures"]
    run_length = 0
    for event in events:
        etype = event.get("type")
        if etype == "blocker_raised":
            run_length += 1
        elif etype == "blocker_resolved":
            run_length = 0
    if run_length >= threshold:
        return [
            BreakerTrip(
                type="consecutive_failures",
                value=run_length,
                threshold=threshold,
                action="scuttle-and-reform",
                message=(
                    f"{run_length} unresolved blockers in a row (>= {threshold}). "
                    f"Consider scuttle-and-reform. "
                    f"See damage-control/scuttle-and-reform.md."
                ),
                context={},
            )
        ]
    return []


def _check_time_limit(
    fleet_status: dict[str, Any],
    sailing_orders: dict[str, Any] | None,
    config: dict[str, Any],
    now_iso: str,
) -> list[BreakerTrip]:
    """Trip when elapsed mission minutes >= configured time_limit_minutes."""
    if not sailing_orders:
        return []
    budget = sailing_orders.get("budget") or {}
    limit = budget.get("time_limit_minutes")
    if not limit or limit <= 0:
        return []

    started_at = (fleet_status.get("mission") or {}).get("started_at")
    if not started_at:
        return []

    try:
        start_dt = datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        now_dt = datetime.strptime(now_iso, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        return []

    elapsed_minutes = (now_dt - start_dt).total_seconds() / 60.0
    grace = config.get("time_limit_grace_minutes", 0) or 0
    if elapsed_minutes >= (limit + grace):
        return [
            BreakerTrip(
                type="time_limit",
                value=round(elapsed_minutes, 1),
                threshold=limit,
                action="admiral-review",
                message=(
                    f"Mission duration {elapsed_minutes:.0f} min >= "
                    f"time limit {limit} min. Review scope or declare stand-down."
                ),
                context={"grace_minutes": grace},
            )
        ]
    return []


# ---------------------------------------------------------------------------
# Idle timeout — evaluated by the TeammateIdle hook (not at checkpoint)
# ---------------------------------------------------------------------------


def evaluate_idle_timeout(
    mission_dir: Path,
    ship_name: str,
    now_iso: str,
    config: dict[str, Any] | None = None,
) -> BreakerTrip | None:
    """Check whether *ship_name* has been idle longer than the configured threshold.

    Reads and writes ``mission_dir/idle-tracker.json`` to record the first-idle
    timestamp per ship. Returns a BreakerTrip if the threshold is crossed,
    otherwise None. The caller is responsible for surfacing the advisory.
    """
    cfg = config or DEFAULT_THRESHOLDS
    timeout_minutes = cfg.get("idle_timeout_minutes", 10)

    tracker_path = mission_dir / "idle-tracker.json"
    tracker: dict[str, str] = {}
    if tracker_path.exists():
        try:
            import json

            tracker = json.loads(tracker_path.read_text(encoding="utf-8"))
            if not isinstance(tracker, dict):
                tracker = {}
        except (OSError, ValueError):
            tracker = {}

    first_seen = tracker.get(ship_name)
    if first_seen is None:
        # First idle event for this ship — record and return.
        tracker[ship_name] = now_iso
        _write_tracker(tracker_path, tracker)
        return None

    try:
        start_dt = datetime.strptime(first_seen, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        now_dt = datetime.strptime(now_iso, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        # Bad tracker state — reset.
        tracker[ship_name] = now_iso
        _write_tracker(tracker_path, tracker)
        return None

    elapsed_minutes = (now_dt - start_dt).total_seconds() / 60.0
    if elapsed_minutes < timeout_minutes:
        return None

    return BreakerTrip(
        type="idle_timeout",
        value=round(elapsed_minutes, 1),
        threshold=timeout_minutes,
        action="man-overboard",
        message=(
            f"{ship_name} idle for {elapsed_minutes:.0f} min "
            f"(threshold {timeout_minutes} min). "
            f"Consider man-overboard. See damage-control/man-overboard.md."
        ),
        context={"ship_name": ship_name, "first_idle_at": first_seen},
    )


def clear_idle_tracker(mission_dir: Path, ship_name: str | None = None) -> None:
    """Remove tracker entries. If *ship_name* is None, clear all entries."""
    tracker_path = mission_dir / "idle-tracker.json"
    if not tracker_path.exists():
        return

    import json

    try:
        tracker = json.loads(tracker_path.read_text(encoding="utf-8"))
        if not isinstance(tracker, dict):
            return
    except (OSError, ValueError):
        return

    if ship_name is None:
        tracker = {}
    else:
        tracker.pop(ship_name, None)

    _write_tracker(tracker_path, tracker)


def _write_tracker(tracker_path: Path, tracker: dict[str, str]) -> None:
    """Write the idle tracker atomically (best effort — non-fatal on error)."""
    import json

    try:
        tracker_path.parent.mkdir(parents=True, exist_ok=True)
        tracker_path.write_text(
            json.dumps(tracker, indent=2) + "\n", encoding="utf-8"
        )
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Fleet-status augmentation
# ---------------------------------------------------------------------------


def compute_budget_metrics(
    tokens_spent: int,
    tokens_remaining: int | None,
    completed: int,
    total: int,
) -> dict[str, Any]:
    """Compute burn_rate_per_task and projected_budget_at_completion.

    * ``burn_rate_per_task`` is integer tokens per completed task, or None
      when no tasks are yet completed.
    * ``projected_budget_at_completion`` is a simple linear extrapolation:
      ``burn_rate_per_task * total``. None when burn rate is unknown.
    """
    if completed <= 0 or tokens_spent <= 0:
        return {
            "burn_rate_per_task": None,
            "projected_budget_at_completion": None,
        }
    burn_rate = tokens_spent / completed
    projected = None
    if total > 0:
        projected = int(round(burn_rate * total))
    return {
        "burn_rate_per_task": int(round(burn_rate)),
        "projected_budget_at_completion": projected,
    }


def format_alarm_line(trip: BreakerTrip) -> str:
    """Format a single trip for display at the admiral's quarterdeck."""
    return f"[CIRCUIT BREAKER: {trip.type}] {trip.message}"
