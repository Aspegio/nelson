"""Tests for nelson-data.py — structured data capture for Nelson missions.

Uses subprocess to black-box test the CLI interface. Each test gets an
isolated tmp directory via pytest's tmp_path fixture.
"""

from __future__ import annotations

import json
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
        assert "Status:" in result.stdout or "nelson-data" in result.stdout

    def test_status_no_fleet_data_is_silent(self, tmp_path: Path) -> None:
        """Status on a mission with no fleet-status.json is a silent no-op (rc=0)."""
        mission_dir = init_mission(tmp_path)
        # No squadron or checkpoint — no fleet-status.json exists
        result = run("status", "--mission-dir", str(mission_dir))
        # Silent no-op — no output, no error
        assert result.stdout.strip() == ""


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

        # Step 2: Squadron
        add_squadron(mission_dir, captains=[
            "HMS Daring:destroyer:sonnet:1",
            "HMS Argyll:frigate:sonnet:2",
        ])
        assert (mission_dir / "battle-plan.json").exists()
        assert (mission_dir / "fleet-status.json").exists()

        # Step 3: Tasks + plan-approved
        add_task(mission_dir, task_id=1, name="Code review", owner="HMS Daring", station_tier=1)
        add_task(mission_dir, task_id=2, name="Doc review", owner="HMS Argyll", deps="")
        run("plan-approved", "--mission-dir", str(mission_dir))

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
