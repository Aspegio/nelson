"""Tests for nelson_circuit_breakers and checkpoint integration."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from conftest import (
    add_squadron,
    add_task,
    init_mission,
    read_json,
    run,
)

from nelson_circuit_breakers import (
    BreakerTrip,
    DEFAULT_THRESHOLDS,
    clear_idle_tracker,
    compute_budget_metrics,
    evaluate,
    evaluate_idle_timeout,
    load_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_iso() -> str:
    return _iso(datetime.now(timezone.utc))


def _fleet_status(
    *,
    tokens_spent: int = 0,
    completed: int = 0,
    total: int = 4,
    squadron: list[dict] | None = None,
    started_at: str | None = None,
) -> dict:
    return {
        "version": 1,
        "mission": {
            "outcome": "Test",
            "status": "underway",
            "phase": "ACTION_STATIONS",
            "started_at": started_at or _now_iso(),
            "checkpoint_number": 1,
        },
        "progress": {
            "pending": max(total - completed, 0),
            "in_progress": 0,
            "completed": completed,
            "blocked": 0,
            "total": total,
        },
        "budget": {
            "tokens_spent": tokens_spent,
            "tokens_remaining": 0,
            "pct_consumed": 0.0,
            "burn_rate_per_checkpoint": 0,
        },
        "squadron": squadron or [],
    }


def _sailing_orders(
    token_limit: int | None = 100_000,
    time_limit_minutes: int | None = None,
    circuit_breakers: dict | None = None,
) -> dict:
    return {
        "version": 1,
        "outcome": "Test",
        "budget": {
            "token_limit": token_limit,
            "time_limit_minutes": time_limit_minutes,
        },
        "circuit_breakers": circuit_breakers or {},
    }


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_defaults_when_no_sailing_orders(self) -> None:
        config = load_config(None)
        assert config == DEFAULT_THRESHOLDS
        # Returned object must be an independent copy
        config["enabled"] = False
        assert DEFAULT_THRESHOLDS["enabled"] is True

    def test_user_overrides_applied(self) -> None:
        so = _sailing_orders(
            circuit_breakers={
                "hull_integrity_threshold": 50,
                "budget_alarm_ratio": 0.9,
            }
        )
        config = load_config(so)
        assert config["hull_integrity_threshold"] == 50
        assert config["budget_alarm_ratio"] == 0.9
        # Unmodified keys retain defaults
        assert config["idle_timeout_minutes"] == DEFAULT_THRESHOLDS["idle_timeout_minutes"]

    def test_unknown_keys_dropped(self) -> None:
        so = _sailing_orders(circuit_breakers={"not_a_real_key": 999})
        config = load_config(so)
        assert "not_a_real_key" not in config


# ---------------------------------------------------------------------------
# Hull integrity
# ---------------------------------------------------------------------------


class TestHullIntegrityBreaker:
    def test_clean_state_no_trips(self) -> None:
        fs = _fleet_status(
            squadron=[{"ship_name": "HMS Argyll", "hull_integrity_pct": 90}]
        )
        trips = evaluate(fs, _sailing_orders(), [], _now_iso())
        assert trips == []

    def test_equals_threshold_trips(self) -> None:
        fs = _fleet_status(
            squadron=[{"ship_name": "HMS Argyll", "hull_integrity_pct": 80}]
        )
        trips = evaluate(fs, _sailing_orders(), [], _now_iso())
        assert len(trips) == 1
        assert trips[0].type == "hull_integrity_breach"
        assert trips[0].action == "hull-integrity"
        assert "HMS Argyll" in trips[0].message

    def test_below_threshold_trips(self) -> None:
        fs = _fleet_status(
            squadron=[
                {"ship_name": "HMS Argyll", "hull_integrity_pct": 95},
                {"ship_name": "HMS Kent", "hull_integrity_pct": 45},
            ]
        )
        trips = evaluate(fs, _sailing_orders(), [], _now_iso())
        breach = [t for t in trips if t.type == "hull_integrity_breach"]
        assert len(breach) == 1
        assert breach[0].context["ship_name"] == "HMS Kent"

    def test_missing_pct_skipped(self) -> None:
        fs = _fleet_status(
            squadron=[{"ship_name": "HMS Argyll", "hull_integrity_pct": None}]
        )
        trips = evaluate(fs, _sailing_orders(), [], _now_iso())
        assert trips == []


# ---------------------------------------------------------------------------
# Budget alarm
# ---------------------------------------------------------------------------


class TestBudgetAlarmBreaker:
    def test_clean_state_no_trips(self) -> None:
        fs = _fleet_status(tokens_spent=50_000, completed=3, total=4)
        trips = evaluate(fs, _sailing_orders(token_limit=100_000), [], _now_iso())
        assert not any(t.type == "budget_alarm" for t in trips)

    def test_over_spent_ratio_but_tasks_ahead_no_trip(self) -> None:
        # 70% spent but 75% complete — fine
        fs = _fleet_status(tokens_spent=70_000, completed=3, total=4)
        trips = evaluate(fs, _sailing_orders(token_limit=100_000), [], _now_iso())
        assert not any(t.type == "budget_alarm" for t in trips)

    def test_alarm_when_spent_ahead_of_completion(self) -> None:
        # 70% spent, 25% complete — tripwire
        fs = _fleet_status(tokens_spent=70_000, completed=1, total=4)
        trips = evaluate(fs, _sailing_orders(token_limit=100_000), [], _now_iso())
        alarms = [t for t in trips if t.type == "budget_alarm"]
        assert len(alarms) == 1
        assert alarms[0].action == "admiral-review"
        assert alarms[0].context["tokens_spent"] == 70_000

    def test_no_token_limit_skipped(self) -> None:
        fs = _fleet_status(tokens_spent=70_000, completed=1, total=4)
        trips = evaluate(fs, _sailing_orders(token_limit=None), [], _now_iso())
        assert not any(t.type == "budget_alarm" for t in trips)

    def test_zero_total_skipped(self) -> None:
        fs = _fleet_status(tokens_spent=70_000, completed=0, total=0)
        trips = evaluate(fs, _sailing_orders(token_limit=100_000), [], _now_iso())
        assert not any(t.type == "budget_alarm" for t in trips)


# ---------------------------------------------------------------------------
# Cost per task overrun
# ---------------------------------------------------------------------------


def _cp(completed: int, burn: int) -> dict:
    return {
        "type": "checkpoint",
        "data": {
            "progress": {"completed": completed},
            "budget": {"burn_rate_per_checkpoint": burn},
        },
    }


class TestCostPerTaskOverrun:
    def test_insufficient_history_no_trip(self) -> None:
        events = [_cp(1, 5000), _cp(2, 5000)]  # only 2 < min_history 3
        trips = evaluate(_fleet_status(), _sailing_orders(), events, _now_iso())
        assert not any(t.type == "cost_per_task_overrun" for t in trips)

    def test_stable_burn_no_trip(self) -> None:
        events = [_cp(1, 5000), _cp(2, 5000), _cp(3, 5000)]
        trips = evaluate(_fleet_status(), _sailing_orders(), events, _now_iso())
        assert not any(t.type == "cost_per_task_overrun" for t in trips)

    def test_spike_trips(self) -> None:
        # First three checkpoints: ~5000 tokens/task.
        # Fourth: 60000 tokens/task — clearly a spike.
        events = [
            _cp(1, 5000),  # rate 5000
            _cp(2, 5000),  # rate 2500
            _cp(3, 5000),  # rate 1666
            _cp(1, 60000),  # rate 60000 — > 3x baseline median 2500
        ]
        trips = evaluate(_fleet_status(), _sailing_orders(), events, _now_iso())
        overrun = [t for t in trips if t.type == "cost_per_task_overrun"]
        assert len(overrun) == 1
        assert overrun[0].action == "crew-overrun"


# ---------------------------------------------------------------------------
# Consecutive failures
# ---------------------------------------------------------------------------


class TestConsecutiveFailures:
    def test_zero_blockers_no_trip(self) -> None:
        trips = evaluate(_fleet_status(), _sailing_orders(), [], _now_iso())
        assert not any(t.type == "consecutive_failures" for t in trips)

    def test_single_blocker_no_trip(self) -> None:
        events = [{"type": "blocker_raised"}]
        trips = evaluate(_fleet_status(), _sailing_orders(), events, _now_iso())
        assert not any(t.type == "consecutive_failures" for t in trips)

    def test_two_blockers_trips(self) -> None:
        events = [{"type": "blocker_raised"}, {"type": "blocker_raised"}]
        trips = evaluate(_fleet_status(), _sailing_orders(), events, _now_iso())
        failures = [t for t in trips if t.type == "consecutive_failures"]
        assert len(failures) == 1
        assert failures[0].action == "scuttle-and-reform"

    def test_resolution_resets_counter(self) -> None:
        events = [
            {"type": "blocker_raised"},
            {"type": "blocker_resolved"},
            {"type": "blocker_raised"},
        ]
        trips = evaluate(_fleet_status(), _sailing_orders(), events, _now_iso())
        assert not any(t.type == "consecutive_failures" for t in trips)


# ---------------------------------------------------------------------------
# Time limit
# ---------------------------------------------------------------------------


class TestTimeLimit:
    def test_within_limit_no_trip(self) -> None:
        started = _iso(datetime.now(timezone.utc) - timedelta(minutes=5))
        fs = _fleet_status(started_at=started)
        trips = evaluate(fs, _sailing_orders(time_limit_minutes=60), [], _now_iso())
        assert not any(t.type == "time_limit" for t in trips)

    def test_over_limit_trips(self) -> None:
        started = _iso(datetime.now(timezone.utc) - timedelta(minutes=120))
        fs = _fleet_status(started_at=started)
        trips = evaluate(fs, _sailing_orders(time_limit_minutes=60), [], _now_iso())
        time_trips = [t for t in trips if t.type == "time_limit"]
        assert len(time_trips) == 1
        assert time_trips[0].threshold == 60


# ---------------------------------------------------------------------------
# Disabled
# ---------------------------------------------------------------------------


class TestDisabled:
    def test_disabled_skips_all_checks(self) -> None:
        fs = _fleet_status(
            tokens_spent=90_000,
            completed=0,
            total=4,
            squadron=[{"ship_name": "HMS Argyll", "hull_integrity_pct": 20}],
        )
        so = _sailing_orders(circuit_breakers={"enabled": False})
        events = [{"type": "blocker_raised"}, {"type": "blocker_raised"}]
        trips = evaluate(fs, so, events, _now_iso())
        assert trips == []


# ---------------------------------------------------------------------------
# Idle timeout
# ---------------------------------------------------------------------------


class TestIdleTimeout:
    def test_first_idle_records_no_trip(self, tmp_path: Path) -> None:
        trip = evaluate_idle_timeout(tmp_path, "HMS Argyll", _now_iso())
        assert trip is None
        tracker = json.loads((tmp_path / "idle-tracker.json").read_text())
        assert "HMS Argyll" in tracker

    def test_under_threshold_no_trip(self, tmp_path: Path) -> None:
        first = datetime.now(timezone.utc)
        evaluate_idle_timeout(tmp_path, "HMS Argyll", _iso(first))
        later = _iso(first + timedelta(minutes=5))
        trip = evaluate_idle_timeout(tmp_path, "HMS Argyll", later)
        assert trip is None

    def test_over_threshold_trips(self, tmp_path: Path) -> None:
        first = datetime.now(timezone.utc)
        evaluate_idle_timeout(tmp_path, "HMS Argyll", _iso(first))
        later = _iso(first + timedelta(minutes=15))
        trip = evaluate_idle_timeout(tmp_path, "HMS Argyll", later)
        assert trip is not None
        assert trip.type == "idle_timeout"
        assert trip.action == "man-overboard"
        assert trip.context["ship_name"] == "HMS Argyll"

    def test_custom_threshold(self, tmp_path: Path) -> None:
        first = datetime.now(timezone.utc)
        config = dict(DEFAULT_THRESHOLDS)
        config["idle_timeout_minutes"] = 1
        evaluate_idle_timeout(tmp_path, "HMS Argyll", _iso(first), config)
        later = _iso(first + timedelta(minutes=2))
        trip = evaluate_idle_timeout(tmp_path, "HMS Argyll", later, config)
        assert trip is not None

    def test_clear_removes_entry(self, tmp_path: Path) -> None:
        evaluate_idle_timeout(tmp_path, "HMS Argyll", _now_iso())
        clear_idle_tracker(tmp_path, "HMS Argyll")
        tracker = json.loads((tmp_path / "idle-tracker.json").read_text())
        assert "HMS Argyll" not in tracker


# ---------------------------------------------------------------------------
# Budget metric computation
# ---------------------------------------------------------------------------


class TestBudgetMetrics:
    def test_no_progress_returns_none(self) -> None:
        metrics = compute_budget_metrics(
            tokens_spent=5000, tokens_remaining=None, completed=0, total=4
        )
        assert metrics["burn_rate_per_task"] is None
        assert metrics["projected_budget_at_completion"] is None

    def test_linear_projection(self) -> None:
        metrics = compute_budget_metrics(
            tokens_spent=10_000, tokens_remaining=None, completed=2, total=8
        )
        assert metrics["burn_rate_per_task"] == 5000
        assert metrics["projected_budget_at_completion"] == 40_000

    def test_total_zero_projection_none(self) -> None:
        metrics = compute_budget_metrics(
            tokens_spent=10_000, tokens_remaining=None, completed=2, total=0
        )
        assert metrics["burn_rate_per_task"] == 5000
        assert metrics["projected_budget_at_completion"] is None


# ---------------------------------------------------------------------------
# End-to-end checkpoint integration
# ---------------------------------------------------------------------------


class TestCheckpointIntegration:
    def test_sailing_orders_persists_circuit_breakers_key(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        sailing = read_json(mission_dir / "sailing-orders.json")
        assert "circuit_breakers" in sailing
        assert sailing["circuit_breakers"] == {}

    def test_checkpoint_writes_burn_rate_per_task(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir)
        run("plan-approved", "--mission-dir", str(mission_dir))
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "0",
            "--in-progress", "0",
            "--completed", "2",
            "--blocked", "0",
            "--tokens-spent", "20000",
            "--tokens-remaining", "80000",
            "--hull-green", "1",
            "--hull-amber", "0",
            "--hull-red", "0",
            "--hull-critical", "0",
            "--decision", "continue",
            "--rationale", "All good",
        )
        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["budget"]["burn_rate_per_task"] == 10000
        # total comes from pending+in_progress+completed = 2
        assert fs["budget"]["projected_budget_at_completion"] == 20000

    def test_checkpoint_emits_circuit_breaker_event_on_budget_alarm(
        self, tmp_path: Path
    ) -> None:
        mission_dir = init_mission(tmp_path, **{"--token-budget": "100000"})
        add_squadron(
            mission_dir,
            captains=[
                "HMS Argyll:frigate:sonnet:1",
                "HMS Kent:frigate:sonnet:2",
                "HMS Warspite:destroyer:sonnet:3",
                "HMS Defiance:frigate:sonnet:4",
            ],
        )
        for i, owner in enumerate(
            ["HMS Argyll", "HMS Kent", "HMS Warspite", "HMS Defiance"]
        ):
            add_task(mission_dir, task_id=i + 1, owner=owner)
        run("plan-approved", "--mission-dir", str(mission_dir))

        # 80% spent but 25% complete — trips budget alarm.
        result = run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "3",
            "--in-progress", "0",
            "--completed", "1",
            "--blocked", "0",
            "--tokens-spent", "80000",
            "--tokens-remaining", "20000",
            "--hull-green", "4",
            "--hull-amber", "0",
            "--hull-red", "0",
            "--hull-critical", "0",
            "--decision", "continue",
            "--rationale", "Pressing on",
        )
        assert "CIRCUIT BREAKER: budget_alarm" in result.stdout

        log = read_json(mission_dir / "mission-log.json")
        trips = [
            e for e in log["events"] if e.get("type") == "circuit_breaker_tripped"
        ]
        assert len(trips) >= 1
        assert any(
            t["data"]["type"] == "budget_alarm" for t in trips
        )

    def test_clean_checkpoint_no_breakers(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path, **{"--token-budget": "100000"})
        add_squadron(mission_dir)
        add_task(mission_dir)
        run("plan-approved", "--mission-dir", str(mission_dir))
        result = run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "0",
            "--in-progress", "0",
            "--completed", "1",
            "--blocked", "0",
            "--tokens-spent", "10000",
            "--tokens-remaining", "90000",
            "--hull-green", "1",
            "--hull-amber", "0",
            "--hull-red", "0",
            "--hull-critical", "0",
            "--decision", "continue",
            "--rationale", "All good",
        )
        assert "CIRCUIT BREAKER" not in result.stdout
        log = read_json(mission_dir / "mission-log.json")
        assert not any(
            e.get("type") == "circuit_breaker_tripped" for e in log["events"]
        )
