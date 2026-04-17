"""Tests for nelson-phase.py — deterministic phase engine for Nelson missions.

Uses subprocess to black-box test the CLI interface. Each test gets an
isolated tmp directory via pytest's tmp_path fixture.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PHASE_SCRIPT = Path(__file__).parent / "nelson-phase.py"
DATA_SCRIPT = Path(__file__).parent / "nelson-data.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_phase(
    *args: str,
    cwd: Path | None = None,
    expect_fail: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run nelson-phase.py with the given arguments."""
    result = subprocess.run(
        [sys.executable, str(PHASE_SCRIPT), *args],
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


def run_data(
    *args: str,
    cwd: Path | None = None,
    expect_fail: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run nelson-data.py with the given arguments."""
    result = subprocess.run(
        [sys.executable, str(DATA_SCRIPT), *args],
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


def init_mission(cwd: Path) -> Path:
    """Create a mission via nelson-data.py init and return its absolute path."""
    result = run_data(
        "init",
        "--outcome", "Test mission",
        "--metric", "All tests pass",
        "--deadline", "this_session",
        "--token-budget", "100000",
        cwd=cwd,
    )
    mission_dir = cwd / result.stdout.strip()
    assert mission_dir.is_dir()
    return mission_dir


def read_json(path: Path) -> dict:
    """Read a JSON file and return the parsed dict."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    """Write a dict as JSON to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def add_task(cwd: Path, mission_dir: Path, task_id: int = 1, station_tier: int = 1) -> None:
    """Add a task to the battle plan."""
    run_data(
        "task",
        "--mission-dir", str(mission_dir),
        "--id", str(task_id),
        "--name", f"Task {task_id}",
        "--owner", "HMS Argyll",
        "--deliverable", f"Deliverable for task {task_id}",
        "--deps", "",
        "--station-tier", str(station_tier),
        "--files", "src/**",
        cwd=cwd,
    )


def approve_plan(cwd: Path, mission_dir: Path) -> None:
    """Run plan-approved on the mission."""
    run_data("plan-approved", "--mission-dir", str(mission_dir), cwd=cwd)


def write_estimate(mission_dir: Path) -> None:
    """Write a minimal estimate.md to satisfy the ESTIMATE exit criterion."""
    (mission_dir / "estimate.md").write_text(
        "# Estimate\n\n## 1. Reconnaissance\nMinimal test estimate.\n",
        encoding="utf-8",
    )


def form_squadron(cwd: Path, mission_dir: Path) -> None:
    """Record squadron formation."""
    run_data(
        "squadron",
        "--mission-dir", str(mission_dir),
        "--admiral", "HMS Victory",
        "--admiral-model", "opus",
        "--captain", "HMS Argyll:frigate:sonnet:1",
        "--mode", "subagents",
        cwd=cwd,
    )


def log_permission(mission_dir: Path) -> None:
    """Add a permission_granted event to mission-log.json."""
    log_path = mission_dir / "mission-log.json"
    log = read_json(log_path)
    new_events = list(log.get("events", [])) + [
        {
            "type": "permission_granted",
            "checkpoint": 0,
            "timestamp": "2026-04-09T12:00:00Z",
            "data": {},
        }
    ]
    write_json(log_path, {**log, "events": new_events})


def log_task_completed(mission_dir: Path, task_id: int = 1) -> None:
    """Add a task_completed event to mission-log.json."""
    log_path = mission_dir / "mission-log.json"
    log = read_json(log_path)
    new_events = list(log.get("events", [])) + [
        {
            "type": "task_completed",
            "checkpoint": 1,
            "timestamp": "2026-04-09T13:00:00Z",
            "data": {
                "task_id": task_id,
                "task_name": f"Task {task_id}",
                "owner": "HMS Argyll",
                "station_tier": 1,
                "verification": "passed",
            },
        }
    ]
    write_json(log_path, {**log, "events": new_events})


# ---------------------------------------------------------------------------
# TestCurrent
# ---------------------------------------------------------------------------


class TestCurrent:
    """Tests for the 'current' subcommand."""

    def test_nonexistent_mission_dir_fails(self, tmp_path: Path) -> None:
        """When --mission-dir points to a nonexistent directory, current fails."""
        result = run_phase(
            "current", "--mission-dir", str(tmp_path / "nonexistent"),
            expect_fail=True,
        )
        assert "does not exist" in result.stderr

    def test_no_mission_dir_no_active(self, tmp_path: Path) -> None:
        """When no --mission-dir and no .active-* files, silent no-op."""
        result = run_phase("current", cwd=tmp_path)
        assert result.stdout.strip() == ""

    def test_fresh_mission_shows_sailing_orders(self, tmp_path: Path) -> None:
        """After init, current phase is SAILING_ORDERS."""
        mission_dir = init_mission(tmp_path)
        result = run_phase("current", "--mission-dir", str(mission_dir))
        assert result.stdout.strip() == "SAILING_ORDERS"

    def test_auto_discovers_active_mission(self, tmp_path: Path) -> None:
        """current auto-discovers mission from .nelson/.active-* files."""
        mission_dir = init_mission(tmp_path)
        nelson_dir = tmp_path / ".nelson"
        nelson_dir.mkdir(exist_ok=True)
        (nelson_dir / ".active-12345678").write_text(str(mission_dir), encoding="utf-8")
        result = run_phase("current", cwd=tmp_path)
        assert result.stdout.strip() == "SAILING_ORDERS"

    def test_no_phase_field_silent_noop(self, tmp_path: Path) -> None:
        """fleet-status.json without phase field is a silent no-op."""
        mission_dir = tmp_path / "old-mission"
        mission_dir.mkdir(parents=True)
        write_json(mission_dir / "fleet-status.json", {
            "version": 1,
            "mission": {"status": "underway"},
        })
        result = run_phase("current", "--mission-dir", str(mission_dir))
        assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# TestAdvance
# ---------------------------------------------------------------------------


class TestAdvance:
    """Tests for the 'advance' subcommand."""

    def test_sailing_orders_to_estimate(self, tmp_path: Path) -> None:
        """Advance from SAILING_ORDERS to ESTIMATE when sailing-orders.json exists."""
        mission_dir = init_mission(tmp_path)
        result = run_phase("advance", "--mission-dir", str(mission_dir))
        assert "SAILING_ORDERS -> ESTIMATE" in result.stdout

        # Verify phase was updated
        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "ESTIMATE"

    def test_sailing_orders_blocked_without_orders(self, tmp_path: Path) -> None:
        """Cannot advance from SAILING_ORDERS if sailing-orders.json is missing."""
        mission_dir = tmp_path / "bare-mission"
        mission_dir.mkdir(parents=True)
        write_json(mission_dir / "fleet-status.json", {
            "version": 1,
            "mission": {"phase": "SAILING_ORDERS"},
        })
        result = run_phase("advance", "--mission-dir", str(mission_dir), expect_fail=True)
        assert "sailing-orders.json" in result.stderr

    def test_battle_plan_to_formation(self, tmp_path: Path) -> None:
        """Advance from BATTLE_PLAN to FORMATION when tasks are defined with tiers."""
        mission_dir = init_mission(tmp_path)
        add_task(tmp_path, mission_dir, task_id=1, station_tier=1)
        approve_plan(tmp_path, mission_dir)
        # plan-approved sets phase to BATTLE_PLAN

        result = run_phase("advance", "--mission-dir", str(mission_dir))
        assert "BATTLE_PLAN -> FORMATION" in result.stdout

        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "FORMATION"

    def test_battle_plan_blocked_without_tasks(self, tmp_path: Path) -> None:
        """Cannot advance from BATTLE_PLAN without tasks defined."""
        mission_dir = init_mission(tmp_path)
        # Set phase to BATTLE_PLAN without any tasks
        fs = read_json(mission_dir / "fleet-status.json")
        write_json(mission_dir / "fleet-status.json", {
            **fs,
            "mission": {**fs["mission"], "phase": "BATTLE_PLAN"},
        })
        result = run_phase("advance", "--mission-dir", str(mission_dir), expect_fail=True)
        assert "battle-plan.json" in result.stderr

    def test_battle_plan_blocked_without_tiers(self, tmp_path: Path) -> None:
        """Cannot advance from BATTLE_PLAN when tasks lack station_tier."""
        mission_dir = init_mission(tmp_path)
        # Write battle-plan with a task missing station_tier
        write_json(mission_dir / "battle-plan.json", {
            "version": 1,
            "tasks": [{"id": 1, "name": "Test"}],
        })
        fs = read_json(mission_dir / "fleet-status.json")
        write_json(mission_dir / "fleet-status.json", {
            **fs,
            "mission": {**fs["mission"], "phase": "BATTLE_PLAN"},
        })
        result = run_phase("advance", "--mission-dir", str(mission_dir), expect_fail=True)
        assert "station_tier" in result.stderr

    def test_formation_to_permission(self, tmp_path: Path) -> None:
        """Advance from FORMATION to PERMISSION when squadron is assigned."""
        mission_dir = init_mission(tmp_path)
        add_task(tmp_path, mission_dir, task_id=1)
        approve_plan(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))  # BATTLE_PLAN -> FORMATION
        form_squadron(tmp_path, mission_dir)

        result = run_phase("advance", "--mission-dir", str(mission_dir))
        assert "FORMATION -> PERMISSION" in result.stdout

        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "PERMISSION"

    def test_formation_blocked_without_squadron(self, tmp_path: Path) -> None:
        """Cannot advance from FORMATION without squadron section."""
        mission_dir = init_mission(tmp_path)
        add_task(tmp_path, mission_dir, task_id=1)
        approve_plan(tmp_path, mission_dir)
        # plan-approved sets BATTLE_PLAN, no squadron yet
        # Force phase to FORMATION
        fs = read_json(mission_dir / "fleet-status.json")
        write_json(mission_dir / "fleet-status.json", {
            **fs,
            "mission": {**fs["mission"], "phase": "FORMATION"},
        })
        result = run_phase("advance", "--mission-dir", str(mission_dir), expect_fail=True)
        assert "squadron" in result.stderr

    def test_permission_to_underway(self, tmp_path: Path) -> None:
        """Advance from PERMISSION to UNDERWAY when permission_granted event exists."""
        mission_dir = init_mission(tmp_path)
        add_task(tmp_path, mission_dir, task_id=1)
        approve_plan(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))  # BATTLE_PLAN -> FORMATION
        form_squadron(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))  # FORMATION -> PERMISSION

        # Log permission
        log_permission(mission_dir)

        result = run_phase("advance", "--mission-dir", str(mission_dir))
        assert "PERMISSION -> UNDERWAY" in result.stdout

        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "UNDERWAY"

    def test_permission_blocked_without_event(self, tmp_path: Path) -> None:
        """Cannot advance from PERMISSION without permission_granted event."""
        mission_dir = init_mission(tmp_path)
        add_task(tmp_path, mission_dir, task_id=1)
        approve_plan(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))  # BATTLE_PLAN -> FORMATION
        form_squadron(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))  # FORMATION -> PERMISSION

        # Try to advance without permission event
        result = run_phase("advance", "--mission-dir", str(mission_dir), expect_fail=True)
        assert "permission_granted" in result.stderr

    def test_underway_to_stand_down(self, tmp_path: Path) -> None:
        """Advance from UNDERWAY to STAND_DOWN when all tasks are completed."""
        mission_dir = init_mission(tmp_path)
        add_task(tmp_path, mission_dir, task_id=1)
        approve_plan(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))  # BATTLE_PLAN -> FORMATION
        form_squadron(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))  # FORMATION -> PERMISSION
        log_permission(mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))  # PERMISSION -> UNDERWAY

        # Complete the task
        log_task_completed(mission_dir, task_id=1)

        result = run_phase("advance", "--mission-dir", str(mission_dir))
        assert "UNDERWAY -> STAND_DOWN" in result.stdout

        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "STAND_DOWN"

    def test_underway_blocked_with_pending_tasks(self, tmp_path: Path) -> None:
        """Cannot advance from UNDERWAY when tasks are still pending."""
        mission_dir = init_mission(tmp_path)
        add_task(tmp_path, mission_dir, task_id=1)
        approve_plan(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))  # BATTLE_PLAN -> FORMATION
        form_squadron(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))  # FORMATION -> PERMISSION
        log_permission(mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))  # PERMISSION -> UNDERWAY

        # Try to advance without completing tasks
        result = run_phase("advance", "--mission-dir", str(mission_dir), expect_fail=True)
        assert "not yet completed" in result.stderr

    def test_stand_down_cannot_advance(self, tmp_path: Path) -> None:
        """Cannot advance past STAND_DOWN (terminal state)."""
        mission_dir = tmp_path / "terminal-mission"
        mission_dir.mkdir(parents=True)
        write_json(mission_dir / "fleet-status.json", {
            "version": 1,
            "mission": {"phase": "STAND_DOWN"},
        })
        result = run_phase("advance", "--mission-dir", str(mission_dir), expect_fail=True)
        assert "terminal phase" in result.stderr

    def test_advance_logs_phase_transition_event(self, tmp_path: Path) -> None:
        """Advance appends a phase_transition event to mission-log.json."""
        mission_dir = init_mission(tmp_path)
        run_phase("advance", "--mission-dir", str(mission_dir))

        log = read_json(mission_dir / "mission-log.json")
        events = log.get("events", [])
        transition_events = [e for e in events if e.get("type") == "phase_transition"]
        assert len(transition_events) == 1
        assert transition_events[0]["data"]["from_phase"] == "SAILING_ORDERS"
        assert transition_events[0]["data"]["to_phase"] == "ESTIMATE"

    def test_no_active_mission_fails(self, tmp_path: Path) -> None:
        """Advance with no active mission fails with a helpful error."""
        result = run_phase("advance", cwd=tmp_path, expect_fail=True)
        assert "no active mission" in result.stderr
        assert "--mission-dir" in result.stderr


# ---------------------------------------------------------------------------
# TestValidateTool
# ---------------------------------------------------------------------------


class TestValidateTool:
    """Tests for the 'validate-tool' subcommand."""

    def test_no_active_mission_allows_all(self, tmp_path: Path) -> None:
        """When no active mission, all tools are allowed."""
        result = run_phase("validate-tool", "--tool", "Agent", cwd=tmp_path)
        assert result.returncode == 0

    def test_sailing_orders_blocks_agent(self, tmp_path: Path) -> None:
        """Agent is blocked during SAILING_ORDERS phase."""
        mission_dir = init_mission(tmp_path)
        result = run_phase(
            "validate-tool", "--tool", "Agent",
            "--mission-dir", str(mission_dir),
            expect_fail=True,
        )
        assert "BLOCKED" in result.stdout
        assert "SAILING_ORDERS" in result.stdout

    def test_sailing_orders_blocks_team_create(self, tmp_path: Path) -> None:
        """TeamCreate is blocked during SAILING_ORDERS phase."""
        mission_dir = init_mission(tmp_path)
        result = run_phase(
            "validate-tool", "--tool", "TeamCreate",
            "--mission-dir", str(mission_dir),
            expect_fail=True,
        )
        assert "BLOCKED" in result.stdout

    def test_sailing_orders_blocks_task_create(self, tmp_path: Path) -> None:
        """TaskCreate is blocked during SAILING_ORDERS phase."""
        mission_dir = init_mission(tmp_path)
        result = run_phase(
            "validate-tool", "--tool", "TaskCreate",
            "--mission-dir", str(mission_dir),
            expect_fail=True,
        )
        assert "BLOCKED" in result.stdout

    def test_sailing_orders_allows_bash(self, tmp_path: Path) -> None:
        """Bash is allowed during SAILING_ORDERS phase."""
        mission_dir = init_mission(tmp_path)
        result = run_phase(
            "validate-tool", "--tool", "Bash",
            "--mission-dir", str(mission_dir),
        )
        assert result.returncode == 0

    def test_sailing_orders_allows_read(self, tmp_path: Path) -> None:
        """Read is allowed during SAILING_ORDERS phase."""
        mission_dir = init_mission(tmp_path)
        result = run_phase(
            "validate-tool", "--tool", "Read",
            "--mission-dir", str(mission_dir),
        )
        assert result.returncode == 0

    def test_underway_allows_all(self, tmp_path: Path) -> None:
        """All tools are allowed during UNDERWAY phase."""
        mission_dir = tmp_path / "underway-mission"
        mission_dir.mkdir(parents=True)
        write_json(mission_dir / "fleet-status.json", {
            "version": 1,
            "mission": {"phase": "UNDERWAY"},
        })
        for tool in ["Agent", "TeamCreate", "TaskCreate", "Bash", "Read", "Write"]:
            result = run_phase(
                "validate-tool", "--tool", tool,
                "--mission-dir", str(mission_dir),
            )
            assert result.returncode == 0, f"{tool} should be allowed in UNDERWAY"

    def test_stand_down_blocks_team_create(self, tmp_path: Path) -> None:
        """TeamCreate is blocked during STAND_DOWN phase."""
        mission_dir = tmp_path / "standdown-mission"
        mission_dir.mkdir(parents=True)
        write_json(mission_dir / "fleet-status.json", {
            "version": 1,
            "mission": {"phase": "STAND_DOWN"},
        })
        result = run_phase(
            "validate-tool", "--tool", "TeamCreate",
            "--mission-dir", str(mission_dir),
            expect_fail=True,
        )
        assert "BLOCKED" in result.stdout

    def test_stand_down_allows_agent(self, tmp_path: Path) -> None:
        """Agent is allowed during STAND_DOWN phase (for cleanup)."""
        mission_dir = tmp_path / "standdown-mission"
        mission_dir.mkdir(parents=True)
        write_json(mission_dir / "fleet-status.json", {
            "version": 1,
            "mission": {"phase": "STAND_DOWN"},
        })
        result = run_phase(
            "validate-tool", "--tool", "Agent",
            "--mission-dir", str(mission_dir),
        )
        assert result.returncode == 0

    def test_formation_blocks_agent(self, tmp_path: Path) -> None:
        """Agent is blocked during FORMATION phase."""
        mission_dir = tmp_path / "formation-mission"
        mission_dir.mkdir(parents=True)
        write_json(mission_dir / "fleet-status.json", {
            "version": 1,
            "mission": {"phase": "FORMATION"},
        })
        result = run_phase(
            "validate-tool", "--tool", "Agent",
            "--mission-dir", str(mission_dir),
            expect_fail=True,
        )
        assert "BLOCKED" in result.stdout

    def test_formation_allows_task_create(self, tmp_path: Path) -> None:
        """TaskCreate is allowed during FORMATION phase (for creating tasks)."""
        mission_dir = tmp_path / "formation-mission"
        mission_dir.mkdir(parents=True)
        write_json(mission_dir / "fleet-status.json", {
            "version": 1,
            "mission": {"phase": "FORMATION"},
        })
        result = run_phase(
            "validate-tool", "--tool", "TaskCreate",
            "--mission-dir", str(mission_dir),
        )
        assert result.returncode == 0

    def test_old_format_allows_all(self, tmp_path: Path) -> None:
        """fleet-status.json without phase field allows all tools (backward compat)."""
        mission_dir = tmp_path / "old-mission"
        mission_dir.mkdir(parents=True)
        write_json(mission_dir / "fleet-status.json", {
            "version": 1,
            "mission": {"status": "underway"},
        })
        result = run_phase(
            "validate-tool", "--tool", "Agent",
            "--mission-dir", str(mission_dir),
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# TestSet
# ---------------------------------------------------------------------------


class TestSet:
    """Tests for the 'set' subcommand."""

    def test_sets_phase(self, tmp_path: Path) -> None:
        """Set updates the phase in fleet-status.json."""
        mission_dir = init_mission(tmp_path)
        run_phase("set", "--mission-dir", str(mission_dir), "--phase", "UNDERWAY")

        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "UNDERWAY"

    def test_set_output_shows_transition(self, tmp_path: Path) -> None:
        """Set prints the old -> new phase transition."""
        mission_dir = init_mission(tmp_path)
        result = run_phase("set", "--mission-dir", str(mission_dir), "--phase", "UNDERWAY")
        assert "SAILING_ORDERS -> UNDERWAY" in result.stdout

    def test_rejects_invalid_phase(self, tmp_path: Path) -> None:
        """Set rejects invalid phase names."""
        mission_dir = init_mission(tmp_path)
        result = run_phase(
            "set", "--mission-dir", str(mission_dir), "--phase", "INVALID",
            expect_fail=True,
        )
        assert "invalid phase" in result.stderr

    def test_case_insensitive(self, tmp_path: Path) -> None:
        """Set accepts lowercase phase names."""
        mission_dir = init_mission(tmp_path)
        run_phase("set", "--mission-dir", str(mission_dir), "--phase", "underway")

        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "UNDERWAY"

    def test_requires_mission_dir(self, tmp_path: Path) -> None:
        """Set requires --mission-dir."""
        result = run_phase("set", "--phase", "UNDERWAY", expect_fail=True)
        # argparse should reject missing required arg
        assert result.returncode != 0

    def test_logs_phase_override_event(self, tmp_path: Path) -> None:
        """Set logs a phase_override event to mission-log.json."""
        mission_dir = init_mission(tmp_path)
        run_phase("set", "--mission-dir", str(mission_dir), "--phase", "UNDERWAY")

        log = read_json(mission_dir / "mission-log.json")
        events = log.get("events", [])
        override_events = [e for e in events if e.get("type") == "phase_override"]
        assert len(override_events) == 1
        assert override_events[0]["data"]["from_phase"] == "SAILING_ORDERS"
        assert override_events[0]["data"]["to_phase"] == "UNDERWAY"


# ---------------------------------------------------------------------------
# TestBackwardCompatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Tests for backward compatibility with old fleet-status.json format."""

    def test_no_phase_field_validate_allows_all(self, tmp_path: Path) -> None:
        """Old fleet-status.json without phase allows all tools."""
        mission_dir = tmp_path / "old-mission"
        mission_dir.mkdir(parents=True)
        write_json(mission_dir / "fleet-status.json", {
            "version": 1,
            "mission": {"status": "underway", "checkpoint_number": 3},
        })
        result = run_phase(
            "validate-tool", "--tool", "Agent",
            "--mission-dir", str(mission_dir),
        )
        assert result.returncode == 0

    def test_no_phase_field_current_silent(self, tmp_path: Path) -> None:
        """Old fleet-status.json without phase: current is silent no-op."""
        mission_dir = tmp_path / "old-mission"
        mission_dir.mkdir(parents=True)
        write_json(mission_dir / "fleet-status.json", {
            "version": 1,
            "mission": {"status": "underway"},
        })
        result = run_phase("current", "--mission-dir", str(mission_dir))
        assert result.stdout.strip() == ""

    def test_set_on_old_format(self, tmp_path: Path) -> None:
        """Set works on fleet-status.json that had no phase field."""
        mission_dir = tmp_path / "old-mission"
        mission_dir.mkdir(parents=True)
        write_json(mission_dir / "fleet-status.json", {
            "version": 1,
            "mission": {"status": "underway"},
        })
        run_phase("set", "--mission-dir", str(mission_dir), "--phase", "UNDERWAY")
        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "UNDERWAY"
        # Original fields preserved
        assert fs["mission"]["status"] == "underway"


# ---------------------------------------------------------------------------
# TestPhasePreservation
# ---------------------------------------------------------------------------


class TestPhasePreservation:
    """Tests verifying phase is preserved through nelson-data.py operations."""

    def test_init_creates_fleet_status_with_phase(self, tmp_path: Path) -> None:
        """Init creates fleet-status.json with SAILING_ORDERS phase."""
        mission_dir = init_mission(tmp_path)
        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "SAILING_ORDERS"

    def test_plan_approved_sets_battle_plan_phase(self, tmp_path: Path) -> None:
        """plan-approved sets phase to BATTLE_PLAN."""
        mission_dir = init_mission(tmp_path)
        add_task(tmp_path, mission_dir, task_id=1)
        approve_plan(tmp_path, mission_dir)

        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "BATTLE_PLAN"

    def test_squadron_preserves_phase(self, tmp_path: Path) -> None:
        """squadron preserves the existing phase (does not hard-set FORMATION)."""
        mission_dir = init_mission(tmp_path)
        add_task(tmp_path, mission_dir, task_id=1)
        approve_plan(tmp_path, mission_dir)
        # plan-approved sets BATTLE_PLAN, advance to FORMATION via phase engine
        run_phase("advance", "--mission-dir", str(mission_dir))
        form_squadron(tmp_path, mission_dir)

        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "FORMATION"

    def test_stand_down_sets_stand_down_phase(self, tmp_path: Path) -> None:
        """stand-down sets phase to STAND_DOWN."""
        mission_dir = init_mission(tmp_path)
        add_task(tmp_path, mission_dir, task_id=1)
        approve_plan(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))  # BATTLE_PLAN -> FORMATION
        form_squadron(tmp_path, mission_dir)

        # Log task events and stand down
        run_data(
            "event",
            "--mission-dir", str(mission_dir),
            "--type", "task_completed",
            "--checkpoint", "1",
            "--task-id", "1",
            "--task-name", "Task 1",
            "--owner", "HMS Argyll",
            "--station-tier", "1",
            "--verification", "passed",
            cwd=tmp_path,
        )
        run_data(
            "stand-down",
            "--mission-dir", str(mission_dir),
            "--outcome-achieved",
            "--actual-outcome", "Test complete",
            "--metric-result", "All pass",
            cwd=tmp_path,
        )

        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "STAND_DOWN"

    def test_checkpoint_preserves_phase(self, tmp_path: Path) -> None:
        """Checkpoint overwrites fleet-status.json but preserves the phase field."""
        mission_dir = init_mission(tmp_path)
        add_task(tmp_path, mission_dir, task_id=1)
        approve_plan(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))  # BATTLE_PLAN -> FORMATION
        form_squadron(tmp_path, mission_dir)

        # Set phase to UNDERWAY
        run_phase("set", "--mission-dir", str(mission_dir), "--phase", "UNDERWAY")

        # Write a checkpoint
        run_data(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "0",
            "--in-progress", "1",
            "--completed", "0",
            "--blocked", "0",
            "--tokens-spent", "50000",
            "--tokens-remaining", "50000",
            "--hull-green", "1",
            "--hull-amber", "0",
            "--hull-red", "0",
            "--hull-critical", "0",
            "--decision", "continue",
            "--rationale", "On track",
            cwd=tmp_path,
        )

        # Phase should be preserved
        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "UNDERWAY"


# ---------------------------------------------------------------------------
# TestFullLifecycle
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# TestCorruptJSON
# ---------------------------------------------------------------------------


class TestCorruptJSON:
    """Tests for corrupt JSON recovery in the phase engine."""

    def test_corrupt_fleet_status_backs_up(self, tmp_path: Path) -> None:
        """Corrupt fleet-status.json is backed up and treated as empty."""
        mission_dir = tmp_path / "corrupt-mission"
        mission_dir.mkdir(parents=True)
        fs_path = mission_dir / "fleet-status.json"
        fs_path.write_text("{invalid json", encoding="utf-8")

        result = run_phase("current", "--mission-dir", str(mission_dir))
        # Corrupt file is backed up, so phase is None -> silent no-op
        assert result.stdout.strip() == ""
        assert (mission_dir / "fleet-status.json.bak").exists()

    def test_corrupt_mission_log_during_advance(self, tmp_path: Path) -> None:
        """Corrupt mission-log.json is backed up during advance."""
        mission_dir = init_mission(tmp_path)
        # Corrupt the mission log
        log_path = mission_dir / "mission-log.json"
        log_path.write_text("not json!", encoding="utf-8")

        # Advance should still succeed (corrupt log is backed up, fresh one created)
        result = run_phase("advance", "--mission-dir", str(mission_dir))
        assert "SAILING_ORDERS -> ESTIMATE" in result.stdout
        assert (mission_dir / "mission-log.json.bak").exists()


# ---------------------------------------------------------------------------
# TestLockFileCleanup
# ---------------------------------------------------------------------------


class TestLockFileCleanup:
    """Tests that lock files are cleaned up after operations."""

    def test_advance_cleans_up_lock_file(self, tmp_path: Path) -> None:
        """Lock file is removed after advance completes."""
        mission_dir = init_mission(tmp_path)
        run_phase("advance", "--mission-dir", str(mission_dir))
        assert not (mission_dir / ".mission-log.lock").exists()


# ---------------------------------------------------------------------------
# TestFullLifecycle
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """End-to-end test of the full phase lifecycle."""

    def test_full_phase_progression(self, tmp_path: Path) -> None:
        """Walk through all phases from SAILING_ORDERS to STAND_DOWN."""
        # 1. Init mission -> SAILING_ORDERS
        mission_dir = init_mission(tmp_path)
        result = run_phase("current", "--mission-dir", str(mission_dir))
        assert result.stdout.strip() == "SAILING_ORDERS"

        # 2. Advance to ESTIMATE
        run_phase("advance", "--mission-dir", str(mission_dir))
        result = run_phase("current", "--mission-dir", str(mission_dir))
        assert result.stdout.strip() == "ESTIMATE"

        # 3. Write estimate.md, advance to BATTLE_PLAN
        write_estimate(mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))
        result = run_phase("current", "--mission-dir", str(mission_dir))
        assert result.stdout.strip() == "BATTLE_PLAN"

        # 4. Add task, approve plan, advance to FORMATION
        add_task(tmp_path, mission_dir, task_id=1)
        approve_plan(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))
        result = run_phase("current", "--mission-dir", str(mission_dir))
        assert result.stdout.strip() == "FORMATION"

        # 5. Form squadron, advance to PERMISSION
        form_squadron(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))
        result = run_phase("current", "--mission-dir", str(mission_dir))
        assert result.stdout.strip() == "PERMISSION"

        # 6. Grant permission, advance to UNDERWAY
        log_permission(mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))
        result = run_phase("current", "--mission-dir", str(mission_dir))
        assert result.stdout.strip() == "UNDERWAY"

        # 7. Complete task, advance to STAND_DOWN
        log_task_completed(mission_dir, task_id=1)
        run_phase("advance", "--mission-dir", str(mission_dir))
        result = run_phase("current", "--mission-dir", str(mission_dir))
        assert result.stdout.strip() == "STAND_DOWN"

        # 8. Verify all transition events were logged
        log = read_json(mission_dir / "mission-log.json")
        transitions = [e for e in log["events"] if e["type"] == "phase_transition"]
        assert len(transitions) == 6
        expected_transitions = [
            ("SAILING_ORDERS", "ESTIMATE"),
            ("ESTIMATE", "BATTLE_PLAN"),
            ("BATTLE_PLAN", "FORMATION"),
            ("FORMATION", "PERMISSION"),
            ("PERMISSION", "UNDERWAY"),
            ("UNDERWAY", "STAND_DOWN"),
        ]
        for transition, (from_phase, to_phase) in zip(transitions, expected_transitions):
            assert transition["data"]["from_phase"] == from_phase
            assert transition["data"]["to_phase"] == to_phase


# ---------------------------------------------------------------------------
# TestEstimatePhase
# ---------------------------------------------------------------------------


class TestEstimatePhase:
    """Tests for the ESTIMATE phase — exit criteria, opt-out flag, and tool blocks."""

    def test_advance_estimate_to_battle_plan_with_file(self, tmp_path: Path) -> None:
        """Advance from ESTIMATE to BATTLE_PLAN when estimate.md exists."""
        mission_dir = init_mission(tmp_path)
        run_phase("advance", "--mission-dir", str(mission_dir))  # SAILING_ORDERS -> ESTIMATE
        write_estimate(mission_dir)

        result = run_phase("advance", "--mission-dir", str(mission_dir))
        assert "ESTIMATE -> BATTLE_PLAN" in result.stdout

        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "BATTLE_PLAN"

    def test_advance_estimate_to_battle_plan_with_skip_flag(self, tmp_path: Path) -> None:
        """Advance from ESTIMATE to BATTLE_PLAN when sailing-orders.json.estimate_skipped is true."""
        mission_dir = init_mission(tmp_path)
        run_phase("advance", "--mission-dir", str(mission_dir))  # SAILING_ORDERS -> ESTIMATE

        # Set opt-out flag directly on sailing-orders.json
        so_path = mission_dir / "sailing-orders.json"
        so = read_json(so_path)
        write_json(so_path, {
            **so,
            "estimate_skipped": True,
            "estimate_skip_reason": "trivial scope",
        })

        result = run_phase("advance", "--mission-dir", str(mission_dir))
        assert "ESTIMATE -> BATTLE_PLAN" in result.stdout

        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "BATTLE_PLAN"

    def test_advance_estimate_blocked_without_file_or_flag(self, tmp_path: Path) -> None:
        """Cannot advance from ESTIMATE when neither estimate.md nor skip flag is present."""
        mission_dir = init_mission(tmp_path)
        run_phase("advance", "--mission-dir", str(mission_dir))  # SAILING_ORDERS -> ESTIMATE

        result = run_phase("advance", "--mission-dir", str(mission_dir), expect_fail=True)
        assert "estimate.md" in result.stderr
        assert "estimate_skipped" in result.stderr

        fs = read_json(mission_dir / "fleet-status.json")
        assert fs["mission"]["phase"] == "ESTIMATE"

    def test_estimate_allows_agent(self, tmp_path: Path) -> None:
        """Agent is allowed during ESTIMATE phase (Q1 dispatches Explore agents)."""
        mission_dir = init_mission(tmp_path)
        run_phase("advance", "--mission-dir", str(mission_dir))  # SAILING_ORDERS -> ESTIMATE

        result = run_phase(
            "validate-tool", "--tool", "Agent",
            "--mission-dir", str(mission_dir),
        )
        assert result.returncode == 0

    def test_estimate_blocks_team_create(self, tmp_path: Path) -> None:
        """TeamCreate is blocked during ESTIMATE phase."""
        mission_dir = init_mission(tmp_path)
        run_phase("advance", "--mission-dir", str(mission_dir))  # SAILING_ORDERS -> ESTIMATE

        result = run_phase(
            "validate-tool", "--tool", "TeamCreate",
            "--mission-dir", str(mission_dir),
            expect_fail=True,
        )
        assert "BLOCKED" in result.stdout
        assert "ESTIMATE" in result.stdout

    def test_estimate_blocks_task_create(self, tmp_path: Path) -> None:
        """TaskCreate is blocked during ESTIMATE phase."""
        mission_dir = init_mission(tmp_path)
        run_phase("advance", "--mission-dir", str(mission_dir))  # SAILING_ORDERS -> ESTIMATE

        result = run_phase(
            "validate-tool", "--tool", "TaskCreate",
            "--mission-dir", str(mission_dir),
            expect_fail=True,
        )
        assert "BLOCKED" in result.stdout


# ---------------------------------------------------------------------------
# TestSkillMdEstimateStep
# ---------------------------------------------------------------------------


class TestSkillMdEstimateStep:
    """Structural assertions for the SKILL.md surgery that inserts The Estimate."""

    SKILL_MD = Path(__file__).resolve().parents[1] / "SKILL.md"

    def test_conduct_the_estimate_heading_present(self) -> None:
        """SKILL.md contains a 'Conduct The Estimate' step between Sailing Orders and Battle Plan."""
        text = self.SKILL_MD.read_text(encoding="utf-8")
        assert "## 2. Conduct The Estimate" in text

    def test_steps_are_numbered_one_through_eight(self) -> None:
        """All eight step headings appear in order."""
        text = self.SKILL_MD.read_text(encoding="utf-8")
        expected_headings = [
            "## 1. Issue Sailing Orders",
            "## 2. Conduct The Estimate",
            "## 3. Draft Battle Plan",
            "## 4. Form the Squadron",
            "## 5. Get Permission to Sail",
            "## 6. Run Quarterdeck Rhythm",
            "## 7. Set Action Stations",
            "## 8. Stand Down And Log Action",
        ]
        positions = [text.find(h) for h in expected_headings]
        assert all(p >= 0 for p in positions), (
            f"Missing headings: {[h for h, p in zip(expected_headings, positions) if p < 0]}"
        )
        assert positions == sorted(positions), "Step headings are out of order"

    def test_estimate_phase_advance_snippet_present(self) -> None:
        """The SAILING_ORDERS -> ESTIMATE phase-advance snippet appears before Battle Plan."""
        text = self.SKILL_MD.read_text(encoding="utf-8")
        estimate_idx = text.index("## 2. Conduct The Estimate")
        battle_plan_idx = text.index("## 3. Draft Battle Plan")
        between = text[:battle_plan_idx]

        # Step 1 must advance from SAILING_ORDERS to ESTIMATE
        assert "SAILING_ORDERS to ESTIMATE" in text[:estimate_idx]
        # Step 2 must advance from ESTIMATE to BATTLE_PLAN
        assert "ESTIMATE to BATTLE_PLAN" in between

    def test_skip_estimate_subcommand_documented(self) -> None:
        """The skip-estimate opt-out path is documented in Step 1."""
        text = self.SKILL_MD.read_text(encoding="utf-8")
        assert "skip-estimate" in text
        assert "--reason" in text

    def test_battle_plan_step_drops_analytical_bullets(self) -> None:
        """The Battle Plan step no longer contains the pre-Estimate analytical wording."""
        text = self.SKILL_MD.read_text(encoding="utf-8")
        battle_plan_idx = text.index("## 3. Draft Battle Plan")
        next_step_idx = text.index("## 4. Form the Squadron")
        battle_plan_body = text[battle_plan_idx:next_step_idx]

        # These analytical instructions lived in the old Battle Plan step and
        # should now be covered by Q4-Q7 of the Estimate.
        assert "Split mission into independent tasks" not in battle_plan_body
        assert "Map the dependency graph" not in battle_plan_body

    def test_elegant_prose_direction_near_top(self) -> None:
        """A single sentence about elegant writing appears before Step 1."""
        text = self.SKILL_MD.read_text(encoding="utf-8")
        intro = text[: text.index("## 1. Issue Sailing Orders")]
        assert "elegant" in intro.lower()


# ---------------------------------------------------------------------------
# TestEstimateE2E — T9 (happy path) and T10 (opt-out)
# ---------------------------------------------------------------------------


def _full_estimate_body() -> str:
    """Return a minimal but complete 7-section estimate.md body."""
    sections = [
        "# The Estimate",
        "",
        "## 1. Reconnaissance",
        "What do we know?",
        "",
        "## 2. Task analysis",
        "What must we achieve?",
        "",
        "## 3. Environment",
        "What shapes the terrain?",
        "",
        "## 4. Courses of action",
        "Single course: direct refactor.",
        "",
        "## 5. Coordination",
        "One captain, one ship.",
        "",
        "## 6. Execution",
        "Proceed on approved plan.",
        "",
        "## 7. Control",
        "Watch for drift past the hull threshold.",
        "",
    ]
    return "\n".join(sections)


class TestEstimateE2E:
    """End-to-end tests for the full Estimate flow (T9 happy path, T10 opt-out)."""

    def test_happy_path_estimate_with_outcomes_and_analytics(
        self, tmp_path: Path
    ) -> None:
        """Full flow: init -> estimate -> tasks -> outcomes -> stand-down -> analytics."""
        # 1. Init -> SAILING_ORDERS
        mission_dir = init_mission(tmp_path)

        # 2. Advance to ESTIMATE
        run_phase("advance", "--mission-dir", str(mission_dir))
        assert read_json(mission_dir / "fleet-status.json")["mission"]["phase"] == "ESTIMATE"

        # 3. Author a full 7-section estimate.md and advance to BATTLE_PLAN
        (mission_dir / "estimate.md").write_text(
            _full_estimate_body(), encoding="utf-8"
        )
        run_phase("advance", "--mission-dir", str(mission_dir))
        assert read_json(mission_dir / "fleet-status.json")["mission"]["phase"] == "BATTLE_PLAN"

        # 4. Add tasks, approve plan, advance to FORMATION
        add_task(tmp_path, mission_dir, task_id=1, station_tier=1)
        add_task(tmp_path, mission_dir, task_id=2, station_tier=1)
        approve_plan(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))

        # 5. Form squadron, advance to PERMISSION
        form_squadron(tmp_path, mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))

        # 6. Grant permission, advance to UNDERWAY
        log_permission(mission_dir)
        run_phase("advance", "--mission-dir", str(mission_dir))

        # 7. Record estimate outcomes (pass/fail mix, multiple methods)
        outcomes = [
            ("E1", "C1", "pass", "test", "pytest green"),
            ("E1", "C2", "fail", "test", "pytest red — one case off"),
            ("E1", "C3", "pass", "review", "admiral OK'd diff"),
            ("E2", "C1", "not-verified", "visual", "no UI reviewer available"),
        ]
        for effect_id, crit_id, status, method, evidence in outcomes:
            run_data(
                "estimate-outcome",
                "--mission-dir", str(mission_dir),
                "--effect-id", effect_id,
                "--criterion-id", crit_id,
                "--status", status,
                "--method", method,
                "--evidence", evidence,
                "--recorded-by", "HMS Argyll",
                cwd=tmp_path,
            )

        # Outcomes file exists with 4 entries
        outcomes_doc = read_json(mission_dir / "estimate-outcomes.json")
        assert outcomes_doc["version"] == 1
        assert len(outcomes_doc["outcomes"]) == 4

        # 8. Complete both tasks, advance to STAND_DOWN
        log_task_completed(mission_dir, task_id=1)
        log_task_completed(mission_dir, task_id=2)
        run_phase("advance", "--mission-dir", str(mission_dir))
        assert read_json(mission_dir / "fleet-status.json")["mission"]["phase"] == "STAND_DOWN"

        # 9. Run stand-down to persist mission terminal state
        run_data(
            "stand-down",
            "--mission-dir", str(mission_dir),
            "--outcome-achieved",
            "--actual-outcome", "Estimate E2E complete",
            "--metric-result", "All pass",
            cwd=tmp_path,
        )

        # 10. Index the fleet and run analytics on estimate-outcomes
        missions_dir = mission_dir.parent
        run_data("index", "--missions-dir", str(missions_dir), cwd=tmp_path)
        result = run_data(
            "analytics",
            "--missions-dir", str(missions_dir),
            "--metric", "estimate-outcomes",
            "--json",
            cwd=tmp_path,
        )
        data = json.loads(result.stdout)
        assert data["total"] == 4
        assert data["pass"] == 2
        assert data["fail"] == 1
        assert data["not_verified"] == 1
        assert data["missions_with_outcomes"] == 1
        assert data["by_method"]["test"]["total"] == 2
        assert data["by_method"]["review"]["total"] == 1
        assert data["by_method"]["visual"]["total"] == 1

    def test_opt_out_skip_estimate_advances_through(self, tmp_path: Path) -> None:
        """Flow: init -> skip-estimate -> advance SAILING_ORDERS->ESTIMATE->BATTLE_PLAN."""
        mission_dir = init_mission(tmp_path)

        # skip-estimate writes flag + reason on sailing-orders.json
        run_data(
            "skip-estimate",
            "--mission-dir", str(mission_dir),
            "--reason", "trivial scope",
            cwd=tmp_path,
        )

        so = read_json(mission_dir / "sailing-orders.json")
        assert so["estimate_skipped"] is True
        assert so["estimate_skip_reason"] == "trivial scope"

        # Advance SAILING_ORDERS -> ESTIMATE
        run_phase("advance", "--mission-dir", str(mission_dir))
        assert read_json(mission_dir / "fleet-status.json")["mission"]["phase"] == "ESTIMATE"

        # Advance ESTIMATE -> BATTLE_PLAN without estimate.md
        assert not (mission_dir / "estimate.md").exists()
        result = run_phase("advance", "--mission-dir", str(mission_dir))
        assert "ESTIMATE -> BATTLE_PLAN" in result.stdout
        assert read_json(mission_dir / "fleet-status.json")["mission"]["phase"] == "BATTLE_PLAN"

        # An estimate_skipped event was logged by skip-estimate
        log = read_json(mission_dir / "mission-log.json")
        skip_events = [e for e in log["events"] if e.get("type") == "estimate_skipped"]
        assert len(skip_events) == 1
        assert skip_events[0]["data"]["reason"] == "trivial scope"
