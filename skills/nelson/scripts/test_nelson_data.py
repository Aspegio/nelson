"""Tests for nelson-data.py — mission lifecycle commands.

Tests for init, squadron, task, plan-approved, event, checkpoint,
stand-down, status, form, headless, handoff, recover, and edge cases.
Uses subprocess to black-box test the CLI interface.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from conftest import (
    add_squadron,
    add_task,
    create_completed_mission,
    init_mission,
    read_json,
    run,
)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_mission_directory(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        assert mission_dir.is_dir()
        assert (mission_dir / "damage-reports").is_dir()
        assert (mission_dir / "turnover-briefs").is_dir()

    def test_creates_sailing_orders(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        so = read_json(mission_dir / "sailing-orders.json")
        assert so["version"] == 1
        assert so["outcome"] == "Test mission"
        assert so["success_metric"] == "All tests pass"
        assert so["deadline"] == "this_session"
        assert so["budget"]["token_limit"] == 100000

    def test_creates_empty_mission_log(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        log = read_json(mission_dir / "mission-log.json")
        assert log["version"] == 1
        assert log["events"] == []

    def test_optional_constraints(self, tmp_path: Path) -> None:
        result = run(
            "init",
            "--outcome", "Test",
            "--metric", "Pass",
            "--deadline", "now",
            "--constraints", "No breaking changes",
            "--constraints", "Keep it simple",
            "--out-of-scope", "UI changes",
            cwd=tmp_path,
        )
        mission_dir = tmp_path / result.stdout.strip()
        so = read_json(mission_dir / "sailing-orders.json")
        assert so["constraints"] == ["No breaking changes", "Keep it simple"]
        assert so["out_of_scope"] == ["UI changes"]

    def test_auto_generates_session_id_in_dirname(self, tmp_path: Path) -> None:
        """Without --session-id, init embeds an 8-hex-char session id in the dir name."""
        mission_dir = init_mission(tmp_path)
        # Expected dir name: {YYYY-MM-DD_HHMMSS}_{8-hex}
        name = mission_dir.name
        parts = name.rsplit("_", 1)
        assert len(parts) == 2, f"Expected '<stamp>_<session_id>', got: {name}"
        session_id = parts[1]
        assert len(session_id) == 8, f"Expected 8-char session id, got: {session_id!r}"
        assert all(c in "0123456789abcdef" for c in session_id), (
            f"Expected lowercase hex session id, got: {session_id!r}"
        )

    def test_accepts_explicit_session_id(self, tmp_path: Path) -> None:
        """--session-id is respected verbatim in the dir name suffix."""
        result = run(
            "init",
            "--outcome", "Test",
            "--metric", "Pass",
            "--deadline", "now",
            "--session-id", "deadbeef",
            cwd=tmp_path,
        )
        mission_dir = tmp_path / result.stdout.strip()
        assert mission_dir.name.endswith("_deadbeef"), (
            f"Expected dir name to end with _deadbeef, got: {mission_dir.name}"
        )

    def test_writes_active_sidecar(self, tmp_path: Path) -> None:
        """init writes .nelson/.active-{session_id} pointing at the mission dir."""
        mission_dir = init_mission(tmp_path)
        session_id = mission_dir.name.rsplit("_", 1)[1]
        sidecar = tmp_path / ".nelson" / f".active-{session_id}"
        assert sidecar.is_file(), f"Expected sidecar at {sidecar}"
        recorded = sidecar.read_text(encoding="utf-8").strip()
        # Sidecar should resolve to the same directory (relative or absolute)
        assert (tmp_path / recorded).resolve() == mission_dir.resolve(), (
            f"Sidecar points to {recorded!r}, expected {mission_dir}"
        )

    def test_rejects_invalid_session_id(self, tmp_path: Path) -> None:
        """Non-hex or wrongly-sized session ids are rejected (prevents path injection)."""
        result = run(
            "init",
            "--outcome", "Test",
            "--metric", "Pass",
            "--deadline", "now",
            "--session-id", "../etc",
            cwd=tmp_path,
            expect_fail=True,
        )
        assert "session-id" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Squadron
# ---------------------------------------------------------------------------

class TestSquadron:
    def test_records_squadron(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir, captains=[
            "HMS Argyll:frigate:sonnet:1",
            "HMS Kent:destroyer:sonnet:2",
        ])
        bp = read_json(mission_dir / "battle-plan.json")
        assert bp["squadron"]["admiral"]["ship_name"] == "HMS Victory"
        assert len(bp["squadron"]["captains"]) == 2
        assert bp["squadron"]["captains"][0]["ship_name"] == "HMS Argyll"
        assert bp["squadron"]["captains"][1]["ship_class"] == "destroyer"

    def test_includes_standing_order_check_in_event(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        log = read_json(mission_dir / "mission-log.json")
        sq_events = [e for e in log["events"] if e["type"] == "squadron_formed"]
        assert len(sq_events) == 1
        assert "standing_order_check" in sq_events[0]["data"]
        assert sq_events[0]["data"]["standing_order_check"] == {
            "triggered": [],
            "remedies": [],
        }

    def test_creates_fleet_status(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["version"] == 1
        assert fs["mission"]["status"] == "forming"

    def test_records_red_cell(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        run(
            "squadron",
            "--mission-dir", str(mission_dir),
            "--admiral", "HMS Victory",
            "--admiral-model", "opus",
            "--captain", "HMS Argyll:frigate:sonnet:1",
            "--red-cell", "HMS Astute",
            "--red-cell-model", "haiku",
            "--mode", "agent-team",
        )
        bp = read_json(mission_dir / "battle-plan.json")
        assert bp["squadron"]["red_cell"]["ship_name"] == "HMS Astute"

    def test_invalid_captain_spec_fails(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        run(
            "squadron",
            "--mission-dir", str(mission_dir),
            "--admiral", "HMS Victory",
            "--admiral-model", "opus",
            "--captain", "HMS Argyll",  # Missing colon-delimited fields
            "--mode", "subagents",
            expect_fail=True,
        )


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class TestTask:
    def test_adds_task_to_battle_plan(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir, task_id=1, name="Auth refactor", station_tier=1)
        bp = read_json(mission_dir / "battle-plan.json")
        assert len(bp["tasks"]) == 1
        assert bp["tasks"][0]["id"] == 1
        assert bp["tasks"][0]["name"] == "Auth refactor"
        assert bp["tasks"][0]["station_tier"] == 1

    def test_multiple_tasks(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir, captains=[
            "HMS Argyll:frigate:sonnet:1",
            "HMS Kent:destroyer:sonnet:2",
        ])
        add_task(mission_dir, task_id=1, name="Task A", owner="HMS Argyll")
        add_task(mission_dir, task_id=2, name="Task B", owner="HMS Kent", deps="1")
        bp = read_json(mission_dir / "battle-plan.json")
        assert len(bp["tasks"]) == 2
        assert bp["tasks"][1]["dependencies"] == [1]

    def test_task_with_files(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        run(
            "task",
            "--mission-dir", str(mission_dir),
            "--id", "1",
            "--name", "Code review",
            "--owner", "HMS Argyll",
            "--deliverable", "Review report",
            "--deps", "",
            "--station-tier", "1",
            "--files", "src/auth/**,src/utils/**",
        )
        bp = read_json(mission_dir / "battle-plan.json")
        assert bp["tasks"][0]["file_ownership"] == ["src/auth/**", "src/utils/**"]


# ---------------------------------------------------------------------------
# Plan Approved
# ---------------------------------------------------------------------------

class TestPlanApproved:
    def test_computes_dag_metrics(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir, captains=[
            "HMS Argyll:frigate:sonnet:1",
            "HMS Kent:destroyer:sonnet:2",
            "HMS Lancaster:frigate:sonnet:3",
        ])
        add_task(mission_dir, task_id=1, name="Independent A")
        add_task(mission_dir, task_id=2, name="Independent B", owner="HMS Kent")
        add_task(mission_dir, task_id=3, name="Depends on A", owner="HMS Lancaster", deps="1")
        run("plan-approved", "--mission-dir", str(mission_dir))

        log = read_json(mission_dir / "mission-log.json")
        bp_events = [e for e in log["events"] if e["type"] == "battle_plan_approved"]
        assert len(bp_events) == 1
        data = bp_events[0]["data"]
        assert data["task_count"] == 3
        assert data["parallel_tracks"] == 2  # Tasks 1 and 2 have no deps
        assert data["critical_path_length"] == 2  # Task 3 depends on 1

    def test_cycle_detection(self, tmp_path: Path) -> None:
        """Cyclic dependencies must produce a clear error, not a crash."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir, captains=[
            "HMS Argyll:frigate:sonnet:1",
            "HMS Kent:destroyer:sonnet:2",
        ])
        add_task(mission_dir, task_id=1, name="Task A", deps="2")
        add_task(mission_dir, task_id=2, name="Task B", owner="HMS Kent", deps="1")
        result = run("plan-approved", "--mission-dir", str(mission_dir), expect_fail=True)
        assert "Cycle detected" in result.stderr

    def test_self_referencing_dependency(self, tmp_path: Path) -> None:
        """A task depending on itself is a cycle."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir, task_id=1, name="Self-ref", deps="1")
        result = run("plan-approved", "--mission-dir", str(mission_dir), expect_fail=True)
        assert "Cycle detected" in result.stderr

    def test_no_tasks_rejects_plan(self, tmp_path: Path) -> None:
        """plan-approved should fail if no tasks have been added."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        result = run("plan-approved", "--mission-dir", str(mission_dir), expect_fail=True)
        assert "no tasks" in result.stderr.lower() or "task" in result.stderr.lower()


# ---------------------------------------------------------------------------
# SkipEstimate
# ---------------------------------------------------------------------------

class TestSkipEstimate:
    def test_writes_flag_and_reason(self, tmp_path: Path) -> None:
        """skip-estimate writes estimate_skipped and estimate_skip_reason."""
        mission_dir = init_mission(tmp_path)
        run(
            "skip-estimate",
            "--mission-dir", str(mission_dir),
            "--reason", "trivial scope",
        )

        so = read_json(mission_dir / "sailing-orders.json")
        assert so["estimate_skipped"] is True
        assert so["estimate_skip_reason"] == "trivial scope"

    def test_logs_event(self, tmp_path: Path) -> None:
        """skip-estimate appends an estimate_skipped event to mission-log.json."""
        mission_dir = init_mission(tmp_path)
        run(
            "skip-estimate",
            "--mission-dir", str(mission_dir),
            "--reason", "hotfix, no estimate warranted",
        )

        log = read_json(mission_dir / "mission-log.json")
        events = [e for e in log["events"] if e["type"] == "estimate_skipped"]
        assert len(events) == 1
        assert events[0]["data"]["reason"] == "hotfix, no estimate warranted"

    def test_preserves_other_fields(self, tmp_path: Path) -> None:
        """skip-estimate does not alter other sailing-orders fields."""
        mission_dir = init_mission(tmp_path)
        before = read_json(mission_dir / "sailing-orders.json")
        run(
            "skip-estimate",
            "--mission-dir", str(mission_dir),
            "--reason", "trivial scope",
        )
        after = read_json(mission_dir / "sailing-orders.json")

        for key in ("outcome", "success_metric", "deadline", "budget", "created_at"):
            assert after[key] == before[key]

    def test_empty_reason_rejected(self, tmp_path: Path) -> None:
        """skip-estimate rejects an empty --reason value."""
        mission_dir = init_mission(tmp_path)
        result = run(
            "skip-estimate",
            "--mission-dir", str(mission_dir),
            "--reason", "   ",
            expect_fail=True,
        )
        assert "reason" in result.stderr.lower()

    def test_missing_sailing_orders_rejected(self, tmp_path: Path) -> None:
        """skip-estimate fails if sailing-orders.json is absent."""
        mission_dir = tmp_path / "bare-mission"
        mission_dir.mkdir(parents=True)
        result = run(
            "skip-estimate",
            "--mission-dir", str(mission_dir),
            "--reason", "whatever",
            expect_fail=True,
        )
        assert "sailing-orders.json" in result.stderr


# ---------------------------------------------------------------------------
# EstimateOutcome
# ---------------------------------------------------------------------------


def _record_outcome(
    mission_dir: Path,
    *,
    effect_id: str = "auth-jwt",
    criterion_id: str = "C1",
    status: str = "pass",
    method: str = "test",
    evidence: str = "pytest output attached",
    recorded_by: str = "HMS Argyll",
    expect_fail: bool = False,
) -> subprocess.CompletedProcess[str]:
    return run(
        "estimate-outcome",
        "--mission-dir", str(mission_dir),
        "--effect-id", effect_id,
        "--criterion-id", criterion_id,
        "--status", status,
        "--method", method,
        "--evidence", evidence,
        "--recorded-by", recorded_by,
        expect_fail=expect_fail,
    )


class TestEstimateOutcome:
    def test_creates_outcomes_file_on_first_record(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        _record_outcome(mission_dir)

        outcomes = read_json(mission_dir / "estimate-outcomes.json")
        assert outcomes["version"] == 1
        assert len(outcomes["outcomes"]) == 1
        recorded = outcomes["outcomes"][0]
        assert recorded["effect_id"] == "auth-jwt"
        assert recorded["criterion_id"] == "C1"
        assert recorded["status"] == "pass"
        assert recorded["method"] == "test"
        assert recorded["recorded_by"] == "HMS Argyll"
        assert "recorded_at" in recorded

    def test_appends_to_existing_outcomes(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        _record_outcome(mission_dir, criterion_id="C1")
        _record_outcome(mission_dir, criterion_id="C2", status="fail", method="review")

        outcomes = read_json(mission_dir / "estimate-outcomes.json")
        assert len(outcomes["outcomes"]) == 2
        assert outcomes["outcomes"][1]["criterion_id"] == "C2"
        assert outcomes["outcomes"][1]["status"] == "fail"
        assert outcomes["outcomes"][1]["method"] == "review"

    def test_logs_event(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        _record_outcome(mission_dir)

        log = read_json(mission_dir / "mission-log.json")
        events = [e for e in log["events"] if e["type"] == "estimate_outcome_recorded"]
        assert len(events) == 1
        assert events[0]["data"]["effect_id"] == "auth-jwt"
        assert events[0]["data"]["status"] == "pass"

    def test_rejects_invalid_status(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        # argparse rejects before our code sees it (choices enforced)
        result = _record_outcome(mission_dir, status="almost-pass", expect_fail=True)
        # either argparse stderr or our _die message
        assert "almost-pass" in result.stderr or "invalid choice" in result.stderr

    def test_rejects_invalid_method(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        result = _record_outcome(mission_dir, method="astrology", expect_fail=True)
        assert "astrology" in result.stderr or "invalid choice" in result.stderr

    def test_rejects_empty_required_fields(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        result = _record_outcome(mission_dir, effect_id="   ", expect_fail=True)
        assert "required" in result.stderr.lower() or "non-empty" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class TestEvent:
    def test_logs_valid_event(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        run(
            "event",
            "--mission-dir", str(mission_dir),
            "--type", "task_completed",
            "--checkpoint", "1",
            "--task-id", "1",
            "--task-name", "Auth refactor",
            "--owner", "HMS Argyll",
        )
        log = read_json(mission_dir / "mission-log.json")
        events = [e for e in log["events"] if e["type"] == "task_completed"]
        assert len(events) == 1
        assert events[0]["data"]["task_name"] == "Auth refactor"

    def test_rejects_invalid_event_type(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        result = run(
            "event",
            "--mission-dir", str(mission_dir),
            "--type", "made_up_event",
            expect_fail=True,
        )
        assert "Invalid event type" in result.stderr or "made_up_event" in result.stderr

    def test_multiple_events_append(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        for i in range(3):
            run(
                "event",
                "--mission-dir", str(mission_dir),
                "--type", "task_started",
                "--task-id", str(i),
                "--task-name", f"Task {i}",
            )
        log = read_json(mission_dir / "mission-log.json")
        started = [e for e in log["events"] if e["type"] == "task_started"]
        assert len(started) == 3


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

class TestCheckpoint:
    def test_total_does_not_double_count_blocked(self, tmp_path: Path) -> None:
        """Blocked tasks are a subset of in_progress — total must not include them separately."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "1",
            "--in-progress", "2",
            "--completed", "2",
            "--blocked", "1",
            "--tokens-spent", "50000",
            "--tokens-remaining", "50000",
            "--hull-green", "2",
            "--hull-amber", "0",
            "--hull-red", "0",
            "--hull-critical", "0",
            "--decision", "continue",
            "--rationale", "On track",
        )
        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["progress"]["total"] == 5  # 1+2+2, NOT 1+2+2+1

    def test_auto_increments_checkpoint_number(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        checkpoint_args = [
            "--pending", "2", "--in-progress", "1", "--completed", "0", "--blocked", "0",
            "--tokens-spent", "10000", "--tokens-remaining", "90000",
            "--hull-green", "1", "--hull-amber", "0", "--hull-red", "0", "--hull-critical", "0",
            "--decision", "continue", "--rationale", "Starting",
        ]
        run("checkpoint", "--mission-dir", str(mission_dir), *checkpoint_args)
        run("checkpoint", "--mission-dir", str(mission_dir), *checkpoint_args)
        log = read_json(mission_dir / "mission-log.json")
        cp_events = [e for e in log["events"] if e["type"] == "checkpoint"]
        assert cp_events[0]["checkpoint"] == 1
        assert cp_events[1]["checkpoint"] == 2

    def test_computes_budget_percentage(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "0", "--in-progress", "0", "--completed", "3", "--blocked", "0",
            "--tokens-spent", "75000", "--tokens-remaining", "25000",
            "--hull-green", "3", "--hull-amber", "0", "--hull-red", "0", "--hull-critical", "0",
            "--decision", "continue", "--rationale", "Almost done",
        )
        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["budget"]["pct_consumed"] == 75.0

    def test_writes_hull_summary(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "0", "--in-progress", "2", "--completed", "1", "--blocked", "0",
            "--tokens-spent", "30000", "--tokens-remaining", "70000",
            "--hull-green", "1", "--hull-amber", "1", "--hull-red", "1", "--hull-critical", "0",
            "--decision", "continue", "--rationale", "Mixed hull",
        )
        log = read_json(mission_dir / "mission-log.json")
        cp = [e for e in log["events"] if e["type"] == "checkpoint"][0]
        hull = cp["data"]["hull_summary"]
        assert hull == {"green": 1, "amber": 1, "red": 1, "critical": 0}


# ---------------------------------------------------------------------------
# Stand Down
# ---------------------------------------------------------------------------

class TestStandDown:
    def test_avg_blocker_duration_is_null(self, tmp_path: Path) -> None:
        """avg_blocker_duration_minutes must be null (not 0) to signal 'not computed'."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir)
        run("plan-approved", "--mission-dir", str(mission_dir))
        run(
            "stand-down",
            "--mission-dir", str(mission_dir),
            "--outcome-achieved",
            "--actual-outcome", "All done",
            "--metric-result", "Passed",
        )
        sd = read_json(mission_dir / "stand-down.json")
        assert sd["quality"]["avg_blocker_duration_minutes"] is None

    def test_records_outcome(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir)
        run("plan-approved", "--mission-dir", str(mission_dir))
        run(
            "stand-down",
            "--mission-dir", str(mission_dir),
            "--outcome-achieved",
            "--actual-outcome", "Refactored auth",
            "--metric-result", "47/47 tests pass",
        )
        sd = read_json(mission_dir / "stand-down.json")
        assert sd["outcome_achieved"] is True
        assert sd["actual_outcome"] == "Refactored auth"
        assert sd["success_metric_result"] == "47/47 tests pass"

    def test_appends_mission_complete_event(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir)
        run("plan-approved", "--mission-dir", str(mission_dir))
        run(
            "stand-down",
            "--mission-dir", str(mission_dir),
            "--outcome-achieved",
            "--actual-outcome", "Done",
            "--metric-result", "Pass",
        )
        log = read_json(mission_dir / "mission-log.json")
        complete_events = [e for e in log["events"] if e["type"] == "mission_complete"]
        assert len(complete_events) == 1

    def test_writes_final_fleet_status(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir)
        run("plan-approved", "--mission-dir", str(mission_dir))
        run(
            "stand-down",
            "--mission-dir", str(mission_dir),
            "--outcome-achieved",
            "--actual-outcome", "Done",
            "--metric-result", "Pass",
        )
        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["status"] == "complete"


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_after_checkpoint(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "1", "--in-progress", "1", "--completed", "1", "--blocked", "0",
            "--tokens-spent", "30000", "--tokens-remaining", "70000",
            "--hull-green", "2", "--hull-amber", "0", "--hull-red", "0", "--hull-critical", "0",
            "--decision", "continue", "--rationale", "Test",
        )
        result = run("status", "--mission-dir", str(mission_dir))
        assert "Status:" in result.stdout or "nelson-data" in result.stdout

    def test_status_no_fleet_data_is_silent(self, tmp_path: Path) -> None:
        """Status on a non-existent mission dir is a silent no-op (rc=0)."""
        # Use a path that doesn't exist to trigger silent no-op
        result = run("status", "--mission-dir", str(tmp_path / "nonexistent"))
        # Silent no-op — no output, no error
        assert result.stdout.strip() == ""

    def test_status_auto_detects_latest_mission(self, tmp_path: Path) -> None:
        """Status without --mission-dir auto-detects the latest mission."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "1", "--in-progress", "1", "--completed", "1", "--blocked", "0",
            "--tokens-spent", "30000", "--tokens-remaining", "70000",
            "--hull-green", "2", "--hull-amber", "0", "--hull-red", "0", "--hull-critical", "0",
            "--decision", "continue", "--rationale", "Test",
        )
        result = run("status", "--mission-dir", "", cwd=tmp_path)
        assert "Status:" in result.stdout or "nelson-data" in result.stdout

    def test_status_no_missions_dir_prints_message(self, tmp_path: Path) -> None:
        """Status without --mission-dir and no .nelson/missions/ prints message."""
        result = run("status", "--mission-dir", "", cwd=tmp_path)
        assert "No active missions" in result.stdout


# ---------------------------------------------------------------------------
# Form (composite command)
# ---------------------------------------------------------------------------


def write_plan_json(path: Path, plan: dict) -> None:
    """Write a plan JSON file for the form command."""
    path.write_text(json.dumps(plan), encoding="utf-8")


def make_plan(
    captains: list[dict] | None = None,
    tasks: list[dict] | None = None,
    admiral: dict | None = None,
    mode: str = "subagents",
    red_cell: dict | None = None,
) -> dict:
    """Build a plan dict suitable for the form command."""
    default_captains = [
        {"ship_name": "HMS Argyll", "ship_class": "frigate", "model": "sonnet", "task_id": 1},
    ] if captains is None else captains
    default_tasks = [
        {
            "id": 1,
            "name": "Auth refactor",
            "owner": "HMS Argyll",
            "deliverable": "JWT-based auth module",
            "dependencies": [],
            "station_tier": 0,
            "file_ownership": [],
        },
    ] if tasks is None else tasks
    squadron: dict = {
        "admiral": admiral or {"ship_name": "HMS Victory", "model": "opus"},
        "captains": default_captains,
    }
    if red_cell:
        squadron["red_cell"] = red_cell
    return {"squadron": squadron, "tasks": default_tasks, "mode": mode}


class TestForm:
    def test_form_registers_tasks(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        plan = make_plan()
        plan_path = tmp_path / "plan.json"
        write_plan_json(plan_path, plan)
        run("form", "--mission-dir", str(mission_dir), "--plan", str(plan_path))
        bp = read_json(mission_dir / "battle-plan.json")
        assert len(bp["tasks"]) == 1
        assert bp["tasks"][0]["name"] == "Auth refactor"
        assert bp["tasks"][0]["owner"] == "HMS Argyll"

    def test_form_records_squadron(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        plan = make_plan()
        plan_path = tmp_path / "plan.json"
        write_plan_json(plan_path, plan)
        run("form", "--mission-dir", str(mission_dir), "--plan", str(plan_path))
        bp = read_json(mission_dir / "battle-plan.json")
        assert bp["squadron"]["admiral"]["ship_name"] == "HMS Victory"
        assert len(bp["squadron"]["captains"]) == 1
        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["status"] == "underway"

    def test_form_computes_dag_metrics(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        plan = make_plan(
            captains=[
                {"ship_name": "HMS Argyll", "ship_class": "frigate", "model": "sonnet", "task_id": 1},
                {"ship_name": "HMS Kent", "ship_class": "destroyer", "model": "sonnet", "task_id": 2},
                {"ship_name": "HMS Lancaster", "ship_class": "frigate", "model": "sonnet", "task_id": 3},
            ],
            tasks=[
                {"id": 1, "name": "A", "owner": "HMS Argyll", "deliverable": "D1",
                 "dependencies": [], "station_tier": 0, "file_ownership": []},
                {"id": 2, "name": "B", "owner": "HMS Kent", "deliverable": "D2",
                 "dependencies": [], "station_tier": 0, "file_ownership": []},
                {"id": 3, "name": "C", "owner": "HMS Lancaster", "deliverable": "D3",
                 "dependencies": [1], "station_tier": 1, "file_ownership": []},
            ],
        )
        plan_path = tmp_path / "plan.json"
        write_plan_json(plan_path, plan)
        result = run("form", "--mission-dir", str(mission_dir), "--plan", str(plan_path))
        summary = json.loads(result.stdout)
        assert summary["dag_metrics"]["parallel_tracks"] == 2
        assert summary["dag_metrics"]["critical_path_length"] == 2

    def test_form_outputs_json_summary(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        plan = make_plan()
        plan_path = tmp_path / "plan.json"
        write_plan_json(plan_path, plan)
        result = run("form", "--mission-dir", str(mission_dir), "--plan", str(plan_path))
        summary = json.loads(result.stdout)
        assert summary["status"] == "ok"
        assert summary["tasks_registered"] == 1
        assert summary["squadron"]["admiral"] == "HMS Victory"
        assert summary["squadron"]["captains"] == 1
        assert summary["squadron"]["mode"] == "subagents"
        assert "conflict_scan" in summary

    def test_form_missing_plan_fails(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        run(
            "form", "--mission-dir", str(mission_dir),
            "--plan", str(tmp_path / "nonexistent.json"),
            expect_fail=True,
        )

    def test_form_empty_tasks_fails(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        plan = make_plan(tasks=[])
        plan_path = tmp_path / "plan.json"
        write_plan_json(plan_path, plan)
        run(
            "form", "--mission-dir", str(mission_dir), "--plan", str(plan_path),
            expect_fail=True,
        )

    def test_form_missing_squadron_fails(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        plan = {"tasks": [{"id": 1, "name": "T", "owner": "X", "deliverable": "D",
                           "dependencies": [], "station_tier": 0, "file_ownership": []}]}
        plan_path = tmp_path / "plan.json"
        write_plan_json(plan_path, plan)
        run(
            "form", "--mission-dir", str(mission_dir), "--plan", str(plan_path),
            expect_fail=True,
        )

    def test_form_with_dependencies(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        plan = make_plan(
            captains=[
                {"ship_name": "HMS Argyll", "ship_class": "frigate", "model": "sonnet", "task_id": 1},
                {"ship_name": "HMS Kent", "ship_class": "destroyer", "model": "sonnet", "task_id": 2},
            ],
            tasks=[
                {"id": 1, "name": "A", "owner": "HMS Argyll", "deliverable": "D1",
                 "dependencies": [], "station_tier": 0, "file_ownership": []},
                {"id": 2, "name": "B", "owner": "HMS Kent", "deliverable": "D2",
                 "dependencies": [1], "station_tier": 1, "file_ownership": []},
            ],
        )
        plan_path = tmp_path / "plan.json"
        write_plan_json(plan_path, plan)
        run("form", "--mission-dir", str(mission_dir), "--plan", str(plan_path))
        bp = read_json(mission_dir / "battle-plan.json")
        assert bp["tasks"][0]["dependents"] == [2]
        assert bp["tasks"][1]["dependencies"] == [1]

    def test_form_with_red_cell(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        plan = make_plan(red_cell={"ship_name": "HMS Astute", "model": "haiku"})
        plan_path = tmp_path / "plan.json"
        write_plan_json(plan_path, plan)
        result = run("form", "--mission-dir", str(mission_dir), "--plan", str(plan_path))
        summary = json.loads(result.stdout)
        assert summary["squadron"]["has_red_cell"] is True
        bp = read_json(mission_dir / "battle-plan.json")
        assert bp["squadron"]["red_cell"]["ship_name"] == "HMS Astute"

    def test_form_runs_conflict_scan(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        plan = make_plan()
        plan_path = tmp_path / "plan.json"
        write_plan_json(plan_path, plan)
        result = run("form", "--mission-dir", str(mission_dir), "--plan", str(plan_path))
        summary = json.loads(result.stdout)
        assert "conflict_scan" in summary
        assert isinstance(summary["conflict_scan"]["clean"], bool)


# ---------------------------------------------------------------------------
# Headless (init + form)
# ---------------------------------------------------------------------------


def write_sailing_orders_json(path: Path, orders: dict) -> None:
    """Write a sailing orders JSON file."""
    path.write_text(json.dumps(orders), encoding="utf-8")


def make_sailing_orders(
    outcome: str = "Test mission",
    metric: str = "All tests pass",
    deadline: str = "this_session",
    token_budget: int | None = 100000,
) -> dict:
    """Build sailing orders suitable for headless command."""
    result: dict = {
        "outcome": outcome,
        "metric": metric,
        "deadline": deadline,
    }
    if token_budget is not None:
        result["budget"] = {"token_limit": token_budget}
    return result


class TestHeadless:
    def test_headless_creates_mission(self, tmp_path: Path) -> None:
        so = make_sailing_orders()
        plan = make_plan()
        so_path = tmp_path / "sailing-orders.json"
        plan_path = tmp_path / "plan.json"
        write_sailing_orders_json(so_path, so)
        write_plan_json(plan_path, plan)
        result = run(
            "headless",
            "--sailing-orders", str(so_path),
            "--battle-plan", str(plan_path),
            "--mode", "subagents",
            "--auto-approve",
            cwd=tmp_path,
        )
        summary = json.loads(result.stdout)
        assert summary["status"] == "ok"
        mission_dir = tmp_path / summary["mission_dir"]
        assert mission_dir.is_dir()
        assert (mission_dir / "sailing-orders.json").exists()
        assert (mission_dir / "battle-plan.json").exists()
        assert (mission_dir / "fleet-status.json").exists()

    def test_headless_outputs_json(self, tmp_path: Path) -> None:
        so = make_sailing_orders()
        plan = make_plan()
        so_path = tmp_path / "sailing-orders.json"
        plan_path = tmp_path / "plan.json"
        write_sailing_orders_json(so_path, so)
        write_plan_json(plan_path, plan)
        result = run(
            "headless",
            "--sailing-orders", str(so_path),
            "--battle-plan", str(plan_path),
            "--mode", "subagents",
            "--auto-approve",
            cwd=tmp_path,
        )
        summary = json.loads(result.stdout)
        assert "mission_dir" in summary
        assert "sailing_orders" in summary
        assert summary["sailing_orders"]["outcome"] == "Test mission"
        assert "formation" in summary

    def test_headless_missing_sailing_orders_fails(self, tmp_path: Path) -> None:
        plan = make_plan()
        plan_path = tmp_path / "plan.json"
        write_plan_json(plan_path, plan)
        run(
            "headless",
            "--sailing-orders", str(tmp_path / "nonexistent.json"),
            "--battle-plan", str(plan_path),
            "--mode", "subagents",
            "--auto-approve",
            cwd=tmp_path,
            expect_fail=True,
        )

    def test_headless_missing_battle_plan_fails(self, tmp_path: Path) -> None:
        so = make_sailing_orders()
        so_path = tmp_path / "sailing-orders.json"
        write_sailing_orders_json(so_path, so)
        run(
            "headless",
            "--sailing-orders", str(so_path),
            "--battle-plan", str(tmp_path / "nonexistent.json"),
            "--mode", "subagents",
            "--auto-approve",
            cwd=tmp_path,
            expect_fail=True,
        )


# ---------------------------------------------------------------------------
# Full Lifecycle Integration
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_full_mission_lifecycle(self, tmp_path: Path) -> None:
        """init -> squadron -> task(s) -> plan-approved -> event -> checkpoint -> stand-down -> status"""
        # Step 1: Init
        mission_dir = init_mission(tmp_path)
        assert (mission_dir / "sailing-orders.json").exists()
        assert (mission_dir / "mission-log.json").exists()

        # Step 2: Tasks + plan-approved
        add_task(mission_dir, task_id=1, name="Code review", owner="HMS Daring", station_tier=1)
        add_task(mission_dir, task_id=2, name="Doc review", owner="HMS Argyll", deps="")
        run("plan-approved", "--mission-dir", str(mission_dir))

        # Step 3: Squadron
        add_squadron(mission_dir, captains=[
            "HMS Daring:destroyer:sonnet:1",
            "HMS Argyll:frigate:sonnet:2",
        ])
        assert (mission_dir / "battle-plan.json").exists()
        assert (mission_dir / "fleet-status.json").exists()

        # Step 4: Events + checkpoint
        run(
            "event",
            "--mission-dir", str(mission_dir),
            "--type", "task_started",
            "--task-id", "1",
            "--task-name", "Code review",
            "--owner", "HMS Daring",
        )
        run(
            "event",
            "--mission-dir", str(mission_dir),
            "--type", "task_completed",
            "--checkpoint", "1",
            "--task-id", "1",
            "--task-name", "Code review",
            "--owner", "HMS Daring",
            "--station-tier", "1",
            "--verification", "passed",
        )
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "0", "--in-progress", "1", "--completed", "1", "--blocked", "0",
            "--tokens-spent", "60000", "--tokens-remaining", "40000",
            "--hull-green", "2", "--hull-amber", "0", "--hull-red", "0", "--hull-critical", "0",
            "--decision", "continue", "--rationale", "One down, one to go",
        )

        # Step 6: Stand down
        run(
            "stand-down",
            "--mission-dir", str(mission_dir),
            "--outcome-achieved",
            "--actual-outcome", "Both reviews complete",
            "--metric-result", "2/2 tasks done",
        )

        # Verify final state
        sd = read_json(mission_dir / "stand-down.json")
        assert sd["outcome_achieved"] is True
        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["status"] == "complete"
        log = read_json(mission_dir / "mission-log.json")
        event_types = [e["type"] for e in log["events"]]
        assert "squadron_formed" in event_types
        assert "battle_plan_approved" in event_types
        assert "task_started" in event_types
        assert "task_completed" in event_types
        assert "checkpoint" in event_types
        assert "mission_complete" in event_types

        # Status check
        result = run("status", "--mission-dir", str(mission_dir))
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_missing_mission_dir(self, tmp_path: Path) -> None:
        """Commands requiring --mission-dir should fail if it doesn't exist."""
        result = run(
            "squadron",
            "--mission-dir", str(tmp_path / "nonexistent"),
            "--admiral", "HMS Victory",
            "--admiral-model", "opus",
            "--captain", "HMS Argyll:frigate:sonnet:1",
            "--mode", "subagents",
            expect_fail=True,
        )
        assert "does not exist" in result.stderr

    def test_corrupt_json_backs_up_file(self, tmp_path: Path) -> None:
        """Corrupt JSON is detected, backed up, and the error is reported.

        Note: the current recovery renames the corrupt file to .bak but does
        not recreate it, so subsequent reads of the same path fail. This is
        a known limitation — the backup itself works correctly.
        """
        mission_dir = init_mission(tmp_path)
        log_path = mission_dir / "mission-log.json"
        log_path.write_text("NOT VALID JSON{{{", encoding="utf-8")
        result = run(
            "event",
            "--mission-dir", str(mission_dir),
            "--type", "task_started",
            "--task-id", "1",
            "--task-name", "Recovery test",
            expect_fail=True,
        )
        # The corrupt file was backed up
        assert (mission_dir / "mission-log.json.bak").exists()
        assert "corrupt JSON" in result.stderr or "backed up" in result.stderr

    def test_no_subcommand_shows_help(self) -> None:
        """Running with no subcommand should exit non-zero."""
        result = run(expect_fail=True)
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# Stand-Down Patterns (--adopt / --avoid)
# ---------------------------------------------------------------------------


class TestStandDownPatterns:
    def test_adopt_avoid_args(self, tmp_path: Path) -> None:
        """--adopt and --avoid flags populate reusable_patterns in stand-down.json."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir)
        run("plan-approved", "--mission-dir", str(mission_dir))
        run(
            "stand-down",
            "--mission-dir", str(mission_dir),
            "--outcome-achieved",
            "--actual-outcome", "Done",
            "--metric-result", "Pass",
            "--adopt", "Station tier 1 for migrations",
            "--adopt", "Dedicated destroyer for DB work",
            "--avoid", "Assigning DB work to frigates",
        )
        sd = read_json(mission_dir / "stand-down.json")
        assert sd["reusable_patterns"]["adopt"] == [
            "Station tier 1 for migrations",
            "Dedicated destroyer for DB work",
        ]
        assert sd["reusable_patterns"]["avoid"] == [
            "Assigning DB work to frigates",
        ]

    def test_adopt_avoid_default_empty(self, tmp_path: Path) -> None:
        """No --adopt/--avoid args produce empty lists (regression check)."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir)
        run("plan-approved", "--mission-dir", str(mission_dir))
        run(
            "stand-down",
            "--mission-dir", str(mission_dir),
            "--outcome-achieved",
            "--actual-outcome", "Done",
            "--metric-result", "Pass",
        )
        sd = read_json(mission_dir / "stand-down.json")
        assert sd["reusable_patterns"]["adopt"] == []
        assert sd["reusable_patterns"]["avoid"] == []


# ---------------------------------------------------------------------------
# Handoff helpers
# ---------------------------------------------------------------------------


def setup_mission_with_task(
    tmp_path: Path,
    station_tier: int = 1,
) -> Path:
    """Create a mission with squadron + task, ready for handoff testing."""
    mission_dir = init_mission(tmp_path)
    add_squadron(mission_dir)
    add_task(mission_dir, task_id=1, name="Test task", station_tier=station_tier)
    run("plan-approved", "--mission-dir", str(mission_dir))
    return mission_dir


def write_handoff(
    mission_dir: Path,
    ship_name: str = "HMS Argyll",
    task_id: int = 1,
    task_name: str = "Test task",
    handoff_type: str = "relief_on_station",
    next_steps: list[str] | None = None,
    file_ownership: list[str] | None = None,
    relief_entries: list[str] | None = None,
    extra_args: list[str] | None = None,
    expect_fail: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run the handoff subcommand and return the result."""
    args = [
        "handoff",
        "--mission-dir", str(mission_dir),
        "--ship-name", ship_name,
        "--task-id", str(task_id),
        "--task-name", task_name,
        "--handoff-type", handoff_type,
        "--hull-at-handoff", "38",
        "--tokens-consumed", "145000",
    ]
    for step in (next_steps or ["Complete remaining work"]):
        args.extend(["--next-step", step])
    for fo in (file_ownership or ["src/main.py"]):
        args.extend(["--file-ownership", fo])
    for entry in (relief_entries or []):
        args.extend(["--relief-entry", entry])
    if extra_args:
        args.extend(extra_args)
    return run(*args, expect_fail=expect_fail)


# ---------------------------------------------------------------------------
# Handoff
# ---------------------------------------------------------------------------


class TestHandoff:
    def test_writes_handoff_packet(self, tmp_path: Path) -> None:
        mission_dir = setup_mission_with_task(tmp_path)
        write_handoff(mission_dir)
        packets = list((mission_dir / "turnover-briefs").glob("*.json"))
        assert len(packets) == 1

    def test_handoff_packet_schema(self, tmp_path: Path) -> None:
        mission_dir = setup_mission_with_task(tmp_path)
        write_handoff(
            mission_dir,
            extra_args=[
                "--completed-subtask", "Schema design",
                "--completed-subtask", "GET endpoint",
                "--key-finding", "Rate limiting needs middleware",
            ],
        )
        packets = list((mission_dir / "turnover-briefs").glob("*.json"))
        packet = read_json(packets[0])
        assert packet["version"] == 1
        assert packet["ship_name"] == "HMS Argyll"
        assert packet["task_id"] == 1
        assert packet["task_name"] == "Test task"
        assert packet["handoff_type"] == "relief_on_station"
        assert packet["state"]["completed_subtasks"] == ["Schema design", "GET endpoint"]
        assert packet["state"]["next_steps"] == ["Complete remaining work"]
        assert packet["state"]["file_ownership"] == ["src/main.py"]
        assert packet["context"]["hull_at_handoff"] == 38
        assert packet["context"]["tokens_consumed"] == 145000
        assert packet["context"]["key_findings"] == ["Rate limiting needs middleware"]
        assert "created_at" in packet

    def test_handoff_appends_relief_event(self, tmp_path: Path) -> None:
        mission_dir = setup_mission_with_task(tmp_path)
        write_handoff(mission_dir, extra_args=["--incoming-ship", "HMS Kent"])
        log = read_json(mission_dir / "mission-log.json")
        relief_events = [
            e for e in log["events"] if e["type"] == "relief_on_station"
        ]
        assert len(relief_events) == 1
        data = relief_events[0]["data"]
        assert data["outgoing_ship"] == "HMS Argyll"
        assert data["incoming_ship"] == "HMS Kent"
        assert data["reason"] == "relief_on_station"
        assert "handoff_packet_path" in data

    def test_handoff_validates_handoff_type(self, tmp_path: Path) -> None:
        mission_dir = setup_mission_with_task(tmp_path)
        result = write_handoff(
            mission_dir, handoff_type="invalid_type", expect_fail=True,
        )
        assert "handoff-type" in result.stderr.lower() or "handoff_type" in result.stderr.lower()

    def test_handoff_requires_next_steps(self, tmp_path: Path) -> None:
        mission_dir = setup_mission_with_task(tmp_path)
        result = run(
            "handoff",
            "--mission-dir", str(mission_dir),
            "--ship-name", "HMS Argyll",
            "--task-id", "1",
            "--task-name", "Test task",
            "--handoff-type", "relief_on_station",
            "--hull-at-handoff", "38",
            "--tokens-consumed", "145000",
            "--file-ownership", "src/main.py",
            expect_fail=True,
        )
        assert "next-step" in result.stderr.lower() or "next_step" in result.stderr.lower()

    def test_handoff_validates_relief_chain_max_3(self, tmp_path: Path) -> None:
        mission_dir = setup_mission_with_task(tmp_path)
        result = write_handoff(
            mission_dir,
            relief_entries=[
                "HMS Argyll:context_exhaustion:2026-04-01T10:00:00Z",
                "HMS Kent:context_exhaustion:2026-04-01T11:00:00Z",
                "HMS Lancaster:context_exhaustion:2026-04-01T12:00:00Z",
                "HMS Richmond:context_exhaustion:2026-04-01T13:00:00Z",
            ],
            expect_fail=True,
        )
        assert "relief chain" in result.stderr.lower()

    def test_handoff_validates_file_ownership_for_implementation(
        self, tmp_path: Path,
    ) -> None:
        mission_dir = setup_mission_with_task(tmp_path, station_tier=1)
        result = run(
            "handoff",
            "--mission-dir", str(mission_dir),
            "--ship-name", "HMS Argyll",
            "--task-id", "1",
            "--task-name", "Test task",
            "--handoff-type", "relief_on_station",
            "--hull-at-handoff", "38",
            "--tokens-consumed", "145000",
            "--next-step", "Finish work",
            expect_fail=True,
        )
        assert "file-ownership" in result.stderr.lower() or "file_ownership" in result.stderr.lower()

    def test_handoff_allows_empty_file_ownership_for_tier_0(
        self, tmp_path: Path,
    ) -> None:
        mission_dir = setup_mission_with_task(tmp_path, station_tier=0)
        run(
            "handoff",
            "--mission-dir", str(mission_dir),
            "--ship-name", "HMS Argyll",
            "--task-id", "1",
            "--task-name", "Test task",
            "--handoff-type", "relief_on_station",
            "--hull-at-handoff", "38",
            "--tokens-consumed", "145000",
            "--next-step", "Finish work",
        )
        packets = list((mission_dir / "turnover-briefs").glob("*.json"))
        assert len(packets) == 1

    def test_handoff_partial_outputs_parsing(self, tmp_path: Path) -> None:
        mission_dir = setup_mission_with_task(tmp_path)
        write_handoff(
            mission_dir,
            extra_args=[
                "--partial-output", "POST endpoint:60%:Validation logic pending",
                "--partial-output", "Auth module:80%:JWT token: RS256 signing done",
            ],
        )
        packets = list((mission_dir / "turnover-briefs").glob("*.json"))
        packet = read_json(packets[0])
        po = packet["state"]["partial_outputs"]
        assert len(po) == 2
        assert po[0] == {
            "subtask": "POST endpoint",
            "progress": "60%",
            "notes": "Validation logic pending",
        }
        # Notes can contain colons
        assert po[1]["notes"] == "JWT token: RS256 signing done"

    def test_handoff_relief_chain_parsing(self, tmp_path: Path) -> None:
        mission_dir = setup_mission_with_task(tmp_path)
        write_handoff(
            mission_dir,
            relief_entries=[
                "HMS Argyll:context_exhaustion:2026-04-08T14:30:00Z",
            ],
        )
        packets = list((mission_dir / "turnover-briefs").glob("*.json"))
        packet = read_json(packets[0])
        chain = packet["relief_chain"]
        assert len(chain) == 1
        assert chain[0] == {
            "ship": "HMS Argyll",
            "reason": "context_exhaustion",
            "handoff_time": "2026-04-08T14:30:00Z",
        }

    def test_handoff_auto_detects_checkpoint(self, tmp_path: Path) -> None:
        mission_dir = setup_mission_with_task(tmp_path)
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "0", "--in-progress", "1", "--completed", "0",
            "--blocked", "0",
            "--tokens-spent", "50000", "--tokens-remaining", "50000",
            "--hull-green", "1", "--hull-amber", "0",
            "--hull-red", "0", "--hull-critical", "0",
            "--decision", "continue", "--rationale", "On track",
        )
        write_handoff(mission_dir)
        packets = list((mission_dir / "turnover-briefs").glob("*.json"))
        packet = read_json(packets[0])
        assert packet["context"]["checkpoint_number"] == 1

    def test_handoff_multiple_packets_coexist(self, tmp_path: Path) -> None:
        import time
        mission_dir = setup_mission_with_task(tmp_path)
        write_handoff(mission_dir, ship_name="HMS Argyll")
        time.sleep(1.1)  # ensure different timestamp
        write_handoff(mission_dir, ship_name="HMS Kent")
        packets = list((mission_dir / "turnover-briefs").glob("*.json"))
        assert len(packets) == 2
        names = {read_json(p)["ship_name"] for p in packets}
        assert names == {"HMS Argyll", "HMS Kent"}


# ---------------------------------------------------------------------------
# Recover
# ---------------------------------------------------------------------------


class TestRecover:
    def test_recover_reads_fleet_status(self, tmp_path: Path) -> None:
        mission_dir = setup_mission_with_task(tmp_path)
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "0", "--in-progress", "1", "--completed", "0",
            "--blocked", "0",
            "--tokens-spent", "50000", "--tokens-remaining", "50000",
            "--hull-green", "1", "--hull-amber", "0",
            "--hull-red", "0", "--hull-critical", "0",
            "--decision", "continue", "--rationale", "On track",
        )
        result = run("recover", "--mission-dir", str(mission_dir))
        briefing = json.loads(result.stdout)
        assert briefing["fleet_status"] is not None
        assert briefing["fleet_status"]["mission"]["status"] == "underway"

    def test_recover_reads_handoff_packets(self, tmp_path: Path) -> None:
        mission_dir = setup_mission_with_task(tmp_path)
        write_handoff(mission_dir)
        result = run("recover", "--mission-dir", str(mission_dir))
        briefing = json.loads(result.stdout)
        assert len(briefing["handoff_packets"]) == 1
        assert briefing["handoff_packets"][0]["ship_name"] == "HMS Argyll"

    def test_recover_auto_discovers_active_mission(self, tmp_path: Path) -> None:
        mission_dir = setup_mission_with_task(tmp_path)
        write_handoff(mission_dir)
        nelson_dir = mission_dir.parent.parent  # .nelson
        active_file = nelson_dir / ".active-test123"
        active_file.write_text(str(mission_dir), encoding="utf-8")
        result = run(
            "recover", "--missions-dir", str(mission_dir.parent),
            cwd=tmp_path,
        )
        briefing = json.loads(result.stdout)
        assert briefing["mission_dir"] == str(mission_dir)
        assert len(briefing["handoff_packets"]) == 1

    def test_recover_json_output(self, tmp_path: Path) -> None:
        mission_dir = setup_mission_with_task(tmp_path)
        result = run("recover", "--mission-dir", str(mission_dir), "--format", "json")
        briefing = json.loads(result.stdout)
        assert "mission_dir" in briefing
        assert "fleet_status" in briefing
        assert "handoff_packets" in briefing
        assert "pending_tasks" in briefing
        assert "recommended_actions" in briefing

    def test_recover_text_output(self, tmp_path: Path) -> None:
        mission_dir = setup_mission_with_task(tmp_path)
        write_handoff(mission_dir)
        result = run("recover", "--mission-dir", str(mission_dir), "--format", "text")
        assert "[nelson-data] Recovery briefing" in result.stdout
        assert "HMS Argyll" in result.stdout

    def test_recover_no_active_mission_silent(self, tmp_path: Path) -> None:
        missions_dir = tmp_path / ".nelson" / "missions"
        missions_dir.mkdir(parents=True)
        result = run("recover", "--missions-dir", str(missions_dir), cwd=tmp_path)
        assert "No active mission" in result.stdout

    def test_recover_skips_completed_missions(self, tmp_path: Path) -> None:
        create_completed_mission(tmp_path, mission_id="2026-04-01_100000")
        missions_dir = tmp_path / ".nelson" / "missions"
        result = run("recover", "--missions-dir", str(missions_dir), cwd=tmp_path)
        assert "No active mission" in result.stdout


# ---------------------------------------------------------------------------
# Handoff Lifecycle
# ---------------------------------------------------------------------------


class TestHandoffLifecycle:
    def test_full_handoff_lifecycle(self, tmp_path: Path) -> None:
        """init -> squadron -> task -> plan-approved -> checkpoint -> handoff -> recover -> stand-down."""
        mission_dir = setup_mission_with_task(tmp_path)

        # Checkpoint
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "0", "--in-progress", "1", "--completed", "0",
            "--blocked", "0",
            "--tokens-spent", "50000", "--tokens-remaining", "50000",
            "--hull-green", "1", "--hull-amber", "0",
            "--hull-red", "0", "--hull-critical", "0",
            "--decision", "continue", "--rationale", "On track",
        )

        # Handoff
        write_handoff(
            mission_dir,
            extra_args=[
                "--completed-subtask", "Schema design",
                "--incoming-ship", "HMS Kent",
                "--relief-entry", "HMS Argyll:context_exhaustion:2026-04-08T14:30:00Z",
            ],
        )

        # Recover
        result = run("recover", "--mission-dir", str(mission_dir))
        briefing = json.loads(result.stdout)
        assert len(briefing["handoff_packets"]) == 1
        assert briefing["recommended_actions"][0].startswith("Resume task")

        # Stand down
        run(
            "stand-down",
            "--mission-dir", str(mission_dir),
            "--outcome-achieved",
            "--actual-outcome", "Task completed after handoff",
            "--metric-result", "All tests pass",
        )

        # Verify relief was counted
        sd = read_json(mission_dir / "stand-down.json")
        assert sd["fleet"]["reliefs"] == 1
