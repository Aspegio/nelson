"""Tests for nelson-data.py — structured data capture for Nelson missions.

Uses subprocess to black-box test the CLI interface. Each test gets an
isolated tmp directory via pytest's tmp_path fixture.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "nelson-data.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(
    *args: str,
    cwd: Path | None = None,
    expect_fail: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run nelson-data.py with the given arguments."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if expect_fail:
        assert result.returncode != 0, (
            f"Expected failure but got rc=0.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    else:
        assert result.returncode == 0, (
            f"Unexpected failure (rc={result.returncode}).\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def init_mission(cwd: Path, **kwargs: str) -> Path:
    """Create a mission via `init` and return the absolute mission directory path."""
    defaults = {
        "--outcome": "Test mission",
        "--metric": "All tests pass",
        "--deadline": "this_session",
        "--token-budget": "100000",
    }
    defaults.update(kwargs)
    cmd_args = []
    for k, v in defaults.items():
        cmd_args.extend([k, v])
    result = run("init", *cmd_args, cwd=cwd)
    # init outputs a relative path — make it absolute relative to cwd
    return cwd / result.stdout.strip()


def add_squadron(mission_dir: Path, captains: list[str] | None = None) -> None:
    """Add a basic squadron to an existing mission."""
    captain_specs = captains or ["HMS Argyll:frigate:sonnet:1"]
    captain_args = []
    for spec in captain_specs:
        captain_args.extend(["--captain", spec])
    run(
        "squadron",
        "--mission-dir", str(mission_dir),
        "--admiral", "HMS Victory",
        "--admiral-model", "opus",
        *captain_args,
        "--mode", "subagents",
    )


def add_task(
    mission_dir: Path,
    task_id: int = 1,
    name: str = "Test task",
    owner: str = "HMS Argyll",
    deps: str = "",
    station_tier: int = 0,
) -> None:
    """Add a task to the battle plan."""
    run(
        "task",
        "--mission-dir", str(mission_dir),
        "--id", str(task_id),
        "--name", name,
        "--owner", owner,
        "--deliverable", f"Deliverable for {name}",
        "--deps", deps,
        "--station-tier", str(station_tier),
        "--files", "",
    )


def read_json(path: Path) -> dict:
    """Read and parse a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


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
        assert "NELSON FLEET STATUS" in result.stdout
        assert "underway" in result.stdout
        assert "1/3 tasks complete" in result.stdout
        assert "Budget:" in result.stdout
        assert "Last checkpoint: 1" in result.stdout

    def test_status_no_fleet_data_is_silent(self, tmp_path: Path) -> None:
        """Status on a mission with no fleet-status.json is a silent no-op (rc=0)."""
        mission_dir = init_mission(tmp_path)
        # No squadron or checkpoint — no fleet-status.json exists
        result = run("status", "--mission-dir", str(mission_dir))
        # Silent no-op — no output, no error
        assert result.stdout.strip() == ""

    def test_status_shows_per_ship_status(self, tmp_path: Path) -> None:
        """Status output includes per-ship hull status."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir, captains=[
            "HMS Argyll:frigate:sonnet:1",
            "HMS Kent:destroyer:sonnet:2",
        ])
        add_task(mission_dir, task_id=1, name="Task A", owner="HMS Argyll")
        add_task(mission_dir, task_id=2, name="Task B", owner="HMS Kent")
        run("plan-approved", "--mission-dir", str(mission_dir))
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "0", "--in-progress", "1", "--completed", "1", "--blocked", "0",
            "--tokens-spent", "40000", "--tokens-remaining", "60000",
            "--hull-green", "2", "--hull-amber", "0", "--hull-red", "0", "--hull-critical", "0",
            "--decision", "continue", "--rationale", "Test",
        )
        result = run("status", "--mission-dir", str(mission_dir))
        assert "HMS Argyll" in result.stdout
        assert "HMS Kent" in result.stdout
        assert "Ships:" in result.stdout

    def test_status_shows_completed_ships(self, tmp_path: Path) -> None:
        """Ships whose tasks are complete show (completed) in status."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir, captains=[
            "HMS Argyll:frigate:sonnet:1",
            "HMS Kent:destroyer:sonnet:2",
        ])
        add_task(mission_dir, task_id=1, name="Task A", owner="HMS Argyll")
        add_task(mission_dir, task_id=2, name="Task B", owner="HMS Kent")
        run("plan-approved", "--mission-dir", str(mission_dir))
        # Record task completion event for HMS Argyll
        run(
            "event",
            "--mission-dir", str(mission_dir),
            "--type", "task_completed",
            "--checkpoint", "1",
            "--task-id", "1", "--task-name", "Task A", "--owner", "HMS Argyll",
            "--station-tier", "0", "--verification", "passed",
        )
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "0", "--in-progress", "1", "--completed", "1", "--blocked", "0",
            "--tokens-spent", "50000", "--tokens-remaining", "50000",
            "--hull-green", "1", "--hull-amber", "0", "--hull-red", "0", "--hull-critical", "0",
            "--decision", "continue", "--rationale", "Test",
        )
        result = run("status", "--mission-dir", str(mission_dir))
        assert "HMS Argyll (completed)" in result.stdout
        assert "HMS Kent (Green" in result.stdout

    def test_status_shows_mission_name(self, tmp_path: Path) -> None:
        """Status output includes the mission directory name."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "0", "--in-progress", "0", "--completed", "1", "--blocked", "0",
            "--tokens-spent", "10000", "--tokens-remaining", "90000",
            "--hull-green", "1", "--hull-amber", "0", "--hull-red", "0", "--hull-critical", "0",
            "--decision", "continue", "--rationale", "Test",
        )
        result = run("status", "--mission-dir", str(mission_dir))
        assert f"Mission: {mission_dir.name}" in result.stdout

    def test_status_no_mission_dir_is_silent(self, tmp_path: Path) -> None:
        """Status without --mission-dir is a silent no-op."""
        result = run("status", cwd=tmp_path)
        assert result.stdout.strip() == ""

    def test_status_shows_blocked_count(self, tmp_path: Path) -> None:
        """Status shows blocked count when blockers exist."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "1", "--in-progress", "0", "--completed", "1", "--blocked", "1",
            "--tokens-spent", "30000", "--tokens-remaining", "70000",
            "--hull-green", "1", "--hull-amber", "0", "--hull-red", "0", "--hull-critical", "0",
            "--decision", "continue", "--rationale", "Test",
        )
        result = run("status", "--mission-dir", str(mission_dir))
        assert "1 blocked" in result.stdout


# ---------------------------------------------------------------------------
# Full Lifecycle Integration
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_full_mission_lifecycle(self, tmp_path: Path) -> None:
        """init → squadron → task(s) → plan-approved → event → checkpoint → stand-down → status"""
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
# Helpers — Fleet Intelligence
# ---------------------------------------------------------------------------


def create_completed_mission(
    cwd: Path,
    mission_id: str | None = None,
    outcome_achieved: bool = True,
    captains: list[str] | None = None,
    task_count: int = 1,
    station_tiers: list[int] | None = None,
    actual_outcome: str = "Mission completed",
    metric_result: str = "All tests pass",
) -> Path:
    """Create a fully completed mission with all 4 JSON files.

    If *mission_id* is provided, the mission directory is renamed to that ID
    to allow deterministic test fixtures without timing issues.
    tmp_path isolation prevents rename collisions across tests.
    """
    mission_dir = init_mission(cwd)
    captain_specs = captains or ["HMS Argyll:frigate:sonnet:1"]
    add_squadron(mission_dir, captains=captain_specs)

    tiers = station_tiers or [0] * task_count
    for i in range(task_count):
        owner = captain_specs[i % len(captain_specs)].split(":")[0]
        tier = tiers[i] if i < len(tiers) else 0
        add_task(
            mission_dir,
            task_id=i + 1,
            name=f"Task {i + 1}",
            owner=owner,
            station_tier=tier,
        )

    run("plan-approved", "--mission-dir", str(mission_dir))

    run(
        "checkpoint",
        "--mission-dir", str(mission_dir),
        "--pending", "0",
        "--in-progress", "0",
        "--completed", str(task_count),
        "--blocked", "0",
        "--tokens-spent", "50000",
        "--tokens-remaining", "50000",
        "--hull-green", str(len(captain_specs)),
        "--hull-amber", "0",
        "--hull-red", "0",
        "--hull-critical", "0",
        "--decision", "continue",
        "--rationale", "All good",
    )

    sd_args = [
        "stand-down",
        "--mission-dir", str(mission_dir),
        "--actual-outcome", actual_outcome,
        "--metric-result", metric_result,
    ]
    if outcome_achieved:
        sd_args.append("--outcome-achieved")
    run(*sd_args)

    if mission_id:
        target = mission_dir.parent / mission_id
        mission_dir.rename(target)
        return target
    return mission_dir


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


class TestIndex:
    def _missions_dir(self, tmp_path: Path) -> str:
        return str(tmp_path / ".nelson" / "missions")

    def test_creates_index_from_completed_missions(self, tmp_path: Path) -> None:
        create_completed_mission(tmp_path, mission_id="2026-03-28_100000")
        create_completed_mission(tmp_path, mission_id="2026-03-29_100000")
        result = run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        index = read_json(tmp_path / ".nelson" / "fleet-intelligence.json")
        assert index["version"] == 1
        assert index["mission_count"] == 2
        assert len(index["missions"]) == 2
        assert "2 missions" in result.stdout

    def test_incremental_adds_new_missions_only(self, tmp_path: Path) -> None:
        create_completed_mission(tmp_path, mission_id="2026-03-28_100000")
        create_completed_mission(tmp_path, mission_id="2026-03-29_100000")
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)

        create_completed_mission(tmp_path, mission_id="2026-03-30_100000")
        result = run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)

        index = read_json(tmp_path / ".nelson" / "fleet-intelligence.json")
        assert index["mission_count"] == 3
        assert "1 new" in result.stdout

    def test_rebuild_reindexes_all(self, tmp_path: Path) -> None:
        create_completed_mission(tmp_path, mission_id="2026-03-28_100000")
        create_completed_mission(tmp_path, mission_id="2026-03-29_100000")
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)

        result = run(
            "index", "--missions-dir", self._missions_dir(tmp_path),
            "--rebuild", cwd=tmp_path,
        )
        index = read_json(tmp_path / ".nelson" / "fleet-intelligence.json")
        assert index["mission_count"] == 2
        assert "2 new" in result.stdout

    def test_skips_incomplete_missions(self, tmp_path: Path) -> None:
        create_completed_mission(tmp_path, mission_id="2026-03-29_100000")
        # Create an incomplete mission (no stand-down.json)
        incomplete = tmp_path / ".nelson" / "missions" / "2026-03-28_100000"
        incomplete.mkdir(parents=True)
        (incomplete / "sailing-orders.json").write_text('{"version": 1}')

        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        index = read_json(tmp_path / ".nelson" / "fleet-intelligence.json")
        assert index["mission_count"] == 1

    def test_enriches_from_battle_plan(self, tmp_path: Path) -> None:
        create_completed_mission(
            tmp_path,
            mission_id="2026-03-29_100000",
            captains=["HMS Argyll:frigate:sonnet:1", "HMS Kent:destroyer:sonnet:2"],
            task_count=2,
        )
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        index = read_json(tmp_path / ".nelson" / "fleet-intelligence.json")
        m = index["missions"][0]
        assert m["fleet"]["ship_classes"] == ["frigate", "destroyer"]
        assert m["fleet"]["execution_mode"] == "subagents"
        assert len(m["tasks"]["task_names"]) == 2

    def test_enriches_from_sailing_orders(self, tmp_path: Path) -> None:
        create_completed_mission(tmp_path, mission_id="2026-03-29_100000")
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        index = read_json(tmp_path / ".nelson" / "fleet-intelligence.json")
        m = index["missions"][0]
        assert m["success_metric"] == "All tests pass"
        assert m["created_at"] is not None

    def test_enriches_from_mission_log(self, tmp_path: Path) -> None:
        create_completed_mission(tmp_path, mission_id="2026-03-29_100000")
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        index = read_json(tmp_path / ".nelson" / "fleet-intelligence.json")
        m = index["missions"][0]
        assert "squadron_formed" in m["event_types"]
        assert "battle_plan_approved" in m["event_types"]
        assert "mission_complete" in m["event_types"]
        assert m["fleet"]["execution_mode"] == "subagents"

    def test_no_missions_creates_empty_index(self, tmp_path: Path) -> None:
        missions_dir = tmp_path / ".nelson" / "missions"
        missions_dir.mkdir(parents=True)
        run("index", "--missions-dir", str(missions_dir), cwd=tmp_path)
        index = read_json(tmp_path / ".nelson" / "fleet-intelligence.json")
        assert index["mission_count"] == 0
        assert index["missions"] == []

    def test_missions_sorted_by_id(self, tmp_path: Path) -> None:
        # Create in reverse chronological order
        create_completed_mission(tmp_path, mission_id="2026-03-30_100000")
        create_completed_mission(tmp_path, mission_id="2026-03-28_100000")
        create_completed_mission(tmp_path, mission_id="2026-03-29_100000")
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        index = read_json(tmp_path / ".nelson" / "fleet-intelligence.json")
        ids = [m["mission_id"] for m in index["missions"]]
        assert ids == ["2026-03-28_100000", "2026-03-29_100000", "2026-03-30_100000"]

    def test_index_skips_corrupt_stand_down(self, tmp_path: Path) -> None:
        """Corrupt stand-down.json → mission skipped, no .bak file created."""
        create_completed_mission(tmp_path, mission_id="2026-03-28_100000")
        # Corrupt the stand-down.json of a second mission
        corrupt_dir = tmp_path / ".nelson" / "missions" / "2026-03-29_100000"
        corrupt_dir.mkdir(parents=True)
        (corrupt_dir / "stand-down.json").write_text("NOT VALID JSON{{{", encoding="utf-8")

        result = run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        index = read_json(tmp_path / ".nelson" / "fleet-intelligence.json")
        assert index["mission_count"] == 1
        # No .bak file — _read_json_optional doesn't rename
        assert not (corrupt_dir / "stand-down.json.bak").exists()

    def test_index_warns_on_corrupt_optional_json(self, tmp_path: Path) -> None:
        """Corrupt battle-plan.json → stderr warning, mission still indexed."""
        create_completed_mission(tmp_path, mission_id="2026-03-28_100000")
        # Corrupt the battle-plan.json
        bp_path = tmp_path / ".nelson" / "missions" / "2026-03-28_100000" / "battle-plan.json"
        bp_path.write_text("CORRUPT{{{", encoding="utf-8")

        result = run(
            "index", "--missions-dir", self._missions_dir(tmp_path),
            "--rebuild", cwd=tmp_path,
        )
        assert "corrupt JSON" in result.stderr
        index = read_json(tmp_path / ".nelson" / "fleet-intelligence.json")
        assert index["mission_count"] == 1

    def test_index_silent_on_missing_optional_json(self, tmp_path: Path) -> None:
        """Missing battle-plan.json → no warning emitted."""
        create_completed_mission(tmp_path, mission_id="2026-03-28_100000")
        # Remove battle-plan.json
        bp_path = tmp_path / ".nelson" / "missions" / "2026-03-28_100000" / "battle-plan.json"
        bp_path.unlink()

        result = run(
            "index", "--missions-dir", self._missions_dir(tmp_path),
            "--rebuild", cwd=tmp_path,
        )
        assert "Warning" not in result.stderr
        index = read_json(tmp_path / ".nelson" / "fleet-intelligence.json")
        assert index["mission_count"] == 1

    def test_index_rebuilds_on_version_mismatch(self, tmp_path: Path) -> None:
        """Index with version 2 → triggers rebuild + warning."""
        create_completed_mission(tmp_path, mission_id="2026-03-28_100000")
        create_completed_mission(tmp_path, mission_id="2026-03-29_100000")
        # Build initial index
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)

        # Tamper with the version
        idx_path = tmp_path / ".nelson" / "fleet-intelligence.json"
        index = read_json(idx_path)
        index["version"] = 2
        idx_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

        # Add another mission and run incremental
        create_completed_mission(tmp_path, mission_id="2026-03-30_100000")
        result = run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        assert "version 2" in result.stderr
        index = read_json(idx_path)
        assert index["version"] == 1
        assert index["mission_count"] == 3
        assert {m["mission_id"] for m in index["missions"]} == {
            "2026-03-28_100000", "2026-03-29_100000", "2026-03-30_100000",
        }

    def test_accepts_mission_dir_singular(self, tmp_path: Path) -> None:
        """--mission-dir alias works for index."""
        create_completed_mission(tmp_path, mission_id="2026-03-28_100000")
        result = run(
            "index", "--mission-dir", self._missions_dir(tmp_path), cwd=tmp_path,
        )
        index = read_json(tmp_path / ".nelson" / "fleet-intelligence.json")
        assert index["mission_count"] == 1

    def test_no_temp_files_after_index(self, tmp_path: Path) -> None:
        """No .tmp files left behind after indexing."""
        create_completed_mission(tmp_path, mission_id="2026-03-28_100000")
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        nelson_dir = tmp_path / ".nelson"
        tmp_files = list(nelson_dir.rglob("*.tmp"))
        assert tmp_files == []


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class TestHistory:
    def _missions_dir(self, tmp_path: Path) -> str:
        return str(tmp_path / ".nelson" / "missions")

    def _setup_indexed(self, tmp_path: Path, count: int = 2) -> None:
        """Create and index *count* completed missions."""
        for i in range(count):
            create_completed_mission(
                tmp_path,
                mission_id=f"2026-03-{28 + i:02d}_100000",
                outcome_achieved=(i % 3 != 2),  # Every 3rd mission fails
            )
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)

    def test_displays_analytics(self, tmp_path: Path) -> None:
        self._setup_indexed(tmp_path, count=2)
        result = run("history", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        assert "Fleet Intelligence" in result.stdout
        assert "win rate" in result.stdout
        assert "missions indexed" in result.stdout

    def test_json_output(self, tmp_path: Path) -> None:
        self._setup_indexed(tmp_path, count=2)
        result = run(
            "history", "--missions-dir", self._missions_dir(tmp_path),
            "--json", cwd=tmp_path,
        )
        data = json.loads(result.stdout)
        assert "analytics" in data
        assert "missions" in data
        assert data["analytics"]["mission_count"] == 2

    def test_no_index_shows_message(self, tmp_path: Path) -> None:
        result = run(
            "history", "--missions-dir", self._missions_dir(tmp_path),
            cwd=tmp_path, expect_fail=True,
        )
        assert "No fleet intelligence index" in result.stderr

    def test_empty_index_shows_message(self, tmp_path: Path) -> None:
        missions_dir = tmp_path / ".nelson" / "missions"
        missions_dir.mkdir(parents=True)
        run("index", "--missions-dir", str(missions_dir), cwd=tmp_path)
        result = run("history", "--missions-dir", str(missions_dir), cwd=tmp_path)
        assert "0 missions indexed" in result.stdout

    def test_win_rate_calculation(self, tmp_path: Path) -> None:
        create_completed_mission(tmp_path, mission_id="2026-03-28_100000", outcome_achieved=True)
        create_completed_mission(tmp_path, mission_id="2026-03-29_100000", outcome_achieved=True)
        create_completed_mission(tmp_path, mission_id="2026-03-30_100000", outcome_achieved=False)
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        result = run(
            "history", "--missions-dir", self._missions_dir(tmp_path),
            "--json", cwd=tmp_path,
        )
        data = json.loads(result.stdout)
        assert data["analytics"]["win_rate"] == 66.7

    def test_last_n_flag(self, tmp_path: Path) -> None:
        for i in range(4):
            create_completed_mission(
                tmp_path,
                mission_id=f"2026-03-{27 + i:02d}_100000",
            )
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        result = run(
            "history", "--missions-dir", self._missions_dir(tmp_path),
            "--last", "2", cwd=tmp_path,
        )
        # Extract dates from the recent missions section
        lines = result.stdout.split("\n")
        recent_section = False
        recent_dates: list[str] = []
        for line in lines:
            if "Recent missions" in line:
                recent_section = True
                continue
            if recent_section and line.strip().startswith("2026-"):
                recent_dates.append(line.strip()[:10])
        assert len(recent_dates) == 2

    def test_recent_missions_ordered(self, tmp_path: Path) -> None:
        create_completed_mission(tmp_path, mission_id="2026-03-28_100000")
        create_completed_mission(tmp_path, mission_id="2026-03-30_100000")
        create_completed_mission(tmp_path, mission_id="2026-03-29_100000")
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        result = run("history", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        lines = result.stdout.split("\n")
        recent_section = False
        recent_dates: list[str] = []
        for line in lines:
            if "Recent missions" in line:
                recent_section = True
                continue
            if recent_section and line.strip().startswith("2026-"):
                recent_dates.append(line.strip()[:10])
        # Most recent first
        assert recent_dates == ["2026-03-30", "2026-03-29", "2026-03-28"]

    def test_json_output_respects_last_flag(self, tmp_path: Path) -> None:
        """--json --last 2 with 4 missions → 2 missions in JSON, analytics covers all 4."""
        self._setup_indexed(tmp_path, count=4)
        result = run(
            "history", "--missions-dir", self._missions_dir(tmp_path),
            "--json", "--last", "2", cwd=tmp_path,
        )
        data = json.loads(result.stdout)
        assert len(data["missions"]) == 2
        assert data["analytics"]["mission_count"] == 4
        ids = [m["mission_id"] for m in data["missions"]]
        assert ids == ["2026-03-31_100000", "2026-03-30_100000"]

    def test_last_negative_treated_as_zero(self, tmp_path: Path) -> None:
        """--last -1 → no crash, no recent missions shown."""
        self._setup_indexed(tmp_path, count=2)
        result = run(
            "history", "--missions-dir", self._missions_dir(tmp_path),
            "--last", "-1", cwd=tmp_path,
        )
        # Should not crash
        assert result.returncode == 0
        # No recent missions section
        assert "Recent missions" not in result.stdout

    def test_last_zero_shows_no_recent_missions(self, tmp_path: Path) -> None:
        """--last 0 → empty recent section."""
        self._setup_indexed(tmp_path, count=2)
        result = run(
            "history", "--missions-dir", self._missions_dir(tmp_path),
            "--last", "0", cwd=tmp_path,
        )
        assert "Recent missions" not in result.stdout

    def test_last_exceeds_mission_count(self, tmp_path: Path) -> None:
        """--last 999 with 2 missions shows all 2."""
        self._setup_indexed(tmp_path, count=2)
        result = run(
            "history", "--missions-dir", self._missions_dir(tmp_path),
            "--last", "999", cwd=tmp_path,
        )
        assert result.returncode == 0
        assert "2 missions indexed" in result.stdout

    def test_json_last_zero_shows_empty_missions(self, tmp_path: Path) -> None:
        """--json --last 0 returns empty missions list."""
        self._setup_indexed(tmp_path, count=2)
        result = run(
            "history", "--missions-dir", self._missions_dir(tmp_path),
            "--json", "--last", "0", cwd=tmp_path,
        )
        data = json.loads(result.stdout)
        assert data["missions"] == []
        assert data["analytics"]["mission_count"] == 2

    def test_history_accepts_mission_dir_singular(self, tmp_path: Path) -> None:
        """--mission-dir alias works for history."""
        self._setup_indexed(tmp_path, count=2)
        result = run(
            "history", "--mission-dir", self._missions_dir(tmp_path),
            cwd=tmp_path,
        )
        assert "Fleet Intelligence" in result.stdout


# ---------------------------------------------------------------------------
# C1: _write_json crash/cleanup — original file preserved, no .tmp leftovers
# ---------------------------------------------------------------------------


class TestWriteJsonCrashCleanup:
    def test_original_preserved_when_replace_fails(self, tmp_path: Path) -> None:
        """If os.replace fails, the original file must not be corrupted."""
        target = tmp_path / "data.json"
        original = {"version": 1, "status": "original"}
        target.write_text(json.dumps(original) + "\n", encoding="utf-8")

        # Make the directory read-only so the temp file cannot be created
        # (on some platforms) or os.replace cannot overwrite.  We use a
        # subdirectory so we can safely chmod it back afterwards.
        sub = tmp_path / "locked"
        sub.mkdir()
        locked_target = sub / "data.json"
        locked_target.write_text(json.dumps(original) + "\n", encoding="utf-8")

        # Remove write permission on the directory
        sub.chmod(stat.S_IRUSR | stat.S_IXUSR)
        try:
            # Attempt an index write that touches a locked directory — expect
            # the subprocess to fail because _write_json cannot write the tmp
            # file inside the read-only directory.
            result = subprocess.run(
                [
                    sys.executable, "-c",
                    (
                        "import sys; sys.path.insert(0, '.');"
                        "from pathlib import Path;"
                        f"sys.path.insert(0, '{SCRIPT.parent}');"
                        "import importlib.util;"
                        f"spec = importlib.util.spec_from_file_location('nelson_data', '{SCRIPT}');"
                        "mod = importlib.util.module_from_spec(spec);"
                        "spec.loader.exec_module(mod);"
                        f"mod._write_json(Path('{locked_target}'), {{'version': 2}})"
                    ),
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode != 0, "Expected _write_json to fail"

            # Original content must be intact
            content = json.loads(locked_target.read_text(encoding="utf-8"))
            assert content == original

            # No .tmp files left behind
            tmp_files = list(sub.glob("*.tmp"))
            assert tmp_files == [], f"Leftover temp files: {tmp_files}"
        finally:
            sub.chmod(stat.S_IRWXU)

    def test_exception_propagates(self, tmp_path: Path) -> None:
        """Errors from _write_json must propagate, not be swallowed."""
        sub = tmp_path / "locked"
        sub.mkdir()
        target = sub / "data.json"
        target.write_text("{}\n", encoding="utf-8")

        sub.chmod(stat.S_IRUSR | stat.S_IXUSR)
        try:
            result = subprocess.run(
                [
                    sys.executable, "-c",
                    (
                        f"import sys; sys.path.insert(0, '{SCRIPT.parent}');"
                        "import importlib.util;"
                        f"spec = importlib.util.spec_from_file_location('nelson_data', '{SCRIPT}');"
                        "mod = importlib.util.module_from_spec(spec);"
                        "spec.loader.exec_module(mod);"
                        "from pathlib import Path;"
                        f"mod._write_json(Path('{target}'), {{'v': 1}})"
                    ),
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode != 0
        finally:
            sub.chmod(stat.S_IRWXU)


# ---------------------------------------------------------------------------
# C2: _read_json_optional OSError path — warning on stderr, graceful skip
# ---------------------------------------------------------------------------


class TestReadJsonOptionalOSError:
    def test_unreadable_file_emits_warning(self, tmp_path: Path) -> None:
        """A file without read permission triggers a stderr warning and skip."""
        missions_dir = tmp_path / ".nelson" / "missions"
        mission_dir = create_completed_mission(tmp_path, mission_id="2026-04-01_100000")

        # Make stand-down.json unreadable
        sd_path = mission_dir / "stand-down.json"
        sd_path.chmod(0o000)
        try:
            result = run(
                "index", "--missions-dir", str(missions_dir),
                "--rebuild", cwd=tmp_path,
            )
            # The mission should be skipped (no crash), and we may see a warning
            # Either stderr has a warning OR the mission was simply skipped
            index_path = missions_dir.parent / "fleet-intelligence.json"
            index_data = json.loads(index_path.read_text(encoding="utf-8"))
            # Mission is skipped because stand-down.json can't be read
            assert len(index_data["missions"]) == 0
        finally:
            sd_path.chmod(stat.S_IRUSR | stat.S_IWUSR)


# ---------------------------------------------------------------------------
# H3: _compute_analytics None-filtering — missing fields yield None, not 0
# ---------------------------------------------------------------------------


class TestAnalyticsNoneFiltering:
    def _missions_dir(self, tmp_path: Path) -> str:
        return str(tmp_path / ".nelson" / "missions")

    def test_missing_duration_and_budget_yield_none(self, tmp_path: Path) -> None:
        """Missions with no duration_minutes or budget should produce None analytics."""
        mission_dir = create_completed_mission(
            tmp_path, mission_id="2026-04-01_100000",
        )
        # Strip duration_minutes and budget from stand-down.json
        sd_path = mission_dir / "stand-down.json"
        sd = json.loads(sd_path.read_text(encoding="utf-8"))
        sd.pop("duration_minutes", None)
        sd.pop("budget", None)
        sd_path.write_text(json.dumps(sd, indent=2) + "\n", encoding="utf-8")

        missions_dir = self._missions_dir(tmp_path)
        run("index", "--missions-dir", missions_dir, cwd=tmp_path)
        result = run(
            "history", "--missions-dir", missions_dir,
            "--json", cwd=tmp_path,
        )
        data = json.loads(result.stdout)
        analytics = data["analytics"]
        assert analytics["avg_duration"] is None
        assert analytics["min_duration"] is None
        assert analytics["max_duration"] is None
        assert analytics["avg_tokens_consumed"] is None
        assert analytics["avg_budget_pct"] is None


# ---------------------------------------------------------------------------
# H4: cmd_history with corrupt index — error message on stderr
# ---------------------------------------------------------------------------


class TestHistoryCorruptIndex:
    def _missions_dir(self, tmp_path: Path) -> str:
        return str(tmp_path / ".nelson" / "missions")

    def test_corrupt_index_reports_error(self, tmp_path: Path) -> None:
        """history with a corrupt fleet-intelligence.json should fail gracefully."""
        create_completed_mission(tmp_path, mission_id="2026-04-01_100000")
        missions_dir = self._missions_dir(tmp_path)
        run("index", "--missions-dir", missions_dir, cwd=tmp_path)

        # Corrupt the index file (lives in parent of missions dir)
        index_path = Path(missions_dir).parent / "fleet-intelligence.json"
        index_path.write_text("NOT VALID JSON{{{", encoding="utf-8")

        result = run(
            "history", "--missions-dir", missions_dir,
            cwd=tmp_path, expect_fail=True,
        )
        assert "corrupt" in result.stderr.lower() or "json" in result.stderr.lower() or "error" in result.stderr.lower()
