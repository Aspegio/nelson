"""Tests for the override-learning trust calibration store.

Covers the admiralty-decision CLI, stand-down aggregation, plan-approved
advisory printer, and the trust-report subcommand.
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import (
    add_squadron,
    add_task,
    init_mission,
    read_json,
    record_admiralty_decision,
    run,
)


def _stand_down(mission_dir: Path, outcome_achieved: bool = True) -> None:
    """Run stand-down with default arguments."""
    args = [
        "stand-down",
        "--mission-dir", str(mission_dir),
        "--actual-outcome", "Done",
        "--metric-result", "Pass",
    ]
    if outcome_achieved:
        args.append("--outcome-achieved")
    run(*args)


def _rename_mission(mission_dir: Path, new_id: str) -> Path:
    """Rename a mission directory to a deterministic id."""
    target = mission_dir.parent / new_id
    mission_dir.rename(target)
    return target


def _calibration_path(tmp_path: Path) -> Path:
    return tmp_path / ".nelson" / "memory" / "trust-calibration.json"


# ---------------------------------------------------------------------------
# admiralty-decision subcommand
# ---------------------------------------------------------------------------


class TestAdmiraltyDecisionCommand:
    def test_writes_event_with_decision_type(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir, task_type="auth_refactor")
        run("plan-approved", "--mission-dir", str(mission_dir))

        record_admiralty_decision(
            mission_dir,
            task_id=1,
            decision_type="modified",
            notes="tightened scope",
        )

        log = read_json(mission_dir / "mission-log.json")
        matching = [
            e for e in log["events"]
            if e.get("type") == "admiralty_action_completed"
        ]
        assert len(matching) == 1
        data = matching[0]["data"]
        assert data["decision_type"] == "modified"
        assert data["task_id"] == 1
        assert data["task_type"] == "auth_refactor"
        assert data["ship_class"] == "frigate"
        assert data["notes"] == "tightened scope"

    def test_rejects_invalid_decision_type(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir, task_type="auth_refactor")
        run("plan-approved", "--mission-dir", str(mission_dir))

        result = run(
            "admiralty-decision",
            "--mission-dir", str(mission_dir),
            "--task-id", "1",
            "--decision-type", "weasel",
            expect_fail=True,
        )
        assert "decision-type" in result.stderr.lower() or "invalid choice" in result.stderr.lower()

    def test_unknown_task_id_fails(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir, task_type="auth_refactor")
        run("plan-approved", "--mission-dir", str(mission_dir))

        result = run(
            "admiralty-decision",
            "--mission-dir", str(mission_dir),
            "--task-id", "999",
            "--decision-type", "approved",
            expect_fail=True,
        )
        assert "999" in result.stderr

    def test_captures_task_type_and_ship_class_from_state(
        self, tmp_path: Path
    ) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir, captains=["HMS Iron Duke:battleship:opus:1"])
        add_task(mission_dir, owner="HMS Iron Duke", task_type="db_migration")
        run("plan-approved", "--mission-dir", str(mission_dir))

        record_admiralty_decision(
            mission_dir, task_id=1, decision_type="rejected"
        )

        log = read_json(mission_dir / "mission-log.json")
        ev = next(
            e for e in log["events"]
            if e.get("type") == "admiralty_action_completed"
        )
        assert ev["data"]["task_type"] == "db_migration"
        assert ev["data"]["ship_class"] == "battleship"


# ---------------------------------------------------------------------------
# Calibration store
# ---------------------------------------------------------------------------


class TestCalibrationStore:
    def test_stand_down_creates_calibration_file(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir, task_type="auth_refactor")
        run("plan-approved", "--mission-dir", str(mission_dir))
        record_admiralty_decision(
            mission_dir, task_id=1, decision_type="modified"
        )
        _stand_down(mission_dir)

        cal_path = _calibration_path(tmp_path)
        assert cal_path.exists()
        data = read_json(cal_path)
        assert data["version"] == 1
        bucket = data["buckets"]["auth_refactor::frigate"]
        assert bucket["total_decisions"] == 1
        assert bucket["modified"] == 1
        assert bucket["approved"] == 0
        assert bucket["rejected"] == 0
        assert bucket["override_rate"] == 1.0
        rollup = data["by_task_type"]["auth_refactor"]
        assert rollup["total_decisions"] == 1
        assert rollup["modified"] == 1
        assert rollup["override_rate"] == 1.0
        assert mission_dir.name in data["_tracked_missions"]

    def test_idempotent_on_re_stand_down(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir, task_type="auth_refactor")
        run("plan-approved", "--mission-dir", str(mission_dir))
        record_admiralty_decision(
            mission_dir, task_id=1, decision_type="approved"
        )
        _stand_down(mission_dir)
        _stand_down(mission_dir)  # second call should not double-count

        data = read_json(_calibration_path(tmp_path))
        bucket = data["buckets"]["auth_refactor::frigate"]
        assert bucket["total_decisions"] == 1
        assert bucket["approved"] == 1

    def test_aggregates_across_missions(self, tmp_path: Path) -> None:
        mission_ids = [
            "2026-04-01_000001_aa11bb22",
            "2026-04-02_000001_cc33dd44",
            "2026-04-03_000001_ee55ff66",
        ]
        decisions = ["approved", "modified", "rejected"]
        for mid, decision in zip(mission_ids, decisions):
            md = init_mission(tmp_path)
            md = _rename_mission(md, mid)
            add_squadron(md)
            add_task(md, task_type="auth_refactor")
            run("plan-approved", "--mission-dir", str(md))
            record_admiralty_decision(md, task_id=1, decision_type=decision)
            _stand_down(md)

        data = read_json(_calibration_path(tmp_path))
        bucket = data["buckets"]["auth_refactor::frigate"]
        assert bucket["total_decisions"] == 3
        assert bucket["approved"] == 1
        assert bucket["modified"] == 1
        assert bucket["rejected"] == 1
        # 2 of 3 overrides
        assert bucket["override_rate"] == round(2 / 3, 4)

    def test_ignores_events_without_decision_type(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir, task_type="auth_refactor")
        run("plan-approved", "--mission-dir", str(mission_dir))
        # Bare event has no decision_type
        run(
            "event",
            "--mission-dir", str(mission_dir),
            "--type", "admiralty_action_completed",
            "--task-id", "1",
        )
        _stand_down(mission_dir)

        cal_path = _calibration_path(tmp_path)
        assert cal_path.exists()
        data = read_json(cal_path)
        assert data["buckets"] == {}
        assert data["by_task_type"] == {}
        assert mission_dir.name in data["_tracked_missions"]

    def test_ignores_tasks_without_task_type(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir)  # no task_type
        run("plan-approved", "--mission-dir", str(mission_dir))
        record_admiralty_decision(
            mission_dir, task_id=1, decision_type="modified"
        )
        _stand_down(mission_dir)

        data = read_json(_calibration_path(tmp_path))
        assert data["buckets"] == {}
        assert data["by_task_type"] == {}

    def test_override_rate_arithmetic(self, tmp_path: Path) -> None:
        # 3 approved + 1 modified + 1 rejected => 2/5 = 0.4
        decisions = [
            "approved",
            "approved",
            "approved",
            "modified",
            "rejected",
        ]
        for i, decision in enumerate(decisions, start=1):
            mid = f"2026-04-{i:02d}_000001_aa{i:02d}{i:02d}bbcc"
            md = init_mission(tmp_path)
            md = _rename_mission(md, mid)
            add_squadron(md)
            add_task(md, task_type="auth_refactor")
            run("plan-approved", "--mission-dir", str(md))
            record_admiralty_decision(md, task_id=1, decision_type=decision)
            _stand_down(md)

        data = read_json(_calibration_path(tmp_path))
        bucket = data["buckets"]["auth_refactor::frigate"]
        assert bucket["total_decisions"] == 5
        assert bucket["approved"] == 3
        assert bucket["modified"] == 1
        assert bucket["rejected"] == 1
        assert bucket["override_rate"] == 0.4


# ---------------------------------------------------------------------------
# plan-approved advisory printer
# ---------------------------------------------------------------------------


def _accrue_history(
    tmp_path: Path,
    decisions: list[str],
    *,
    task_type: str = "auth_refactor",
    captains: list[str] | None = None,
    task_owner: str = "HMS Argyll",
) -> None:
    """Run *len(decisions)* completed missions, each contributing one decision."""
    for i, decision in enumerate(decisions, start=1):
        mid = f"2026-03-{i:02d}_000001_hh{i:02d}{i:02d}gggg"
        md = init_mission(tmp_path)
        md = _rename_mission(md, mid)
        add_squadron(md, captains=captains)
        add_task(md, owner=task_owner, task_type=task_type)
        run("plan-approved", "--mission-dir", str(md))
        record_admiralty_decision(md, task_id=1, decision_type=decision)
        _stand_down(md)


class TestPlanApprovedAdvisory:
    def test_advisory_printed_when_threshold_met(self, tmp_path: Path) -> None:
        _accrue_history(tmp_path, ["modified", "rejected", "modified"])

        # New mission with the same task_type + ship_class
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir, task_type="auth_refactor")
        result = run("plan-approved", "--mission-dir", str(mission_dir))

        assert "Trust advisory" in result.stderr
        assert "auth_refactor" in result.stderr
        assert "frigate" in result.stderr
        assert "task 1" in result.stderr

    def test_suppressed_below_sample_size(self, tmp_path: Path) -> None:
        _accrue_history(tmp_path, ["modified", "modified"])  # n=2 < 3

        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir, task_type="auth_refactor")
        result = run("plan-approved", "--mission-dir", str(mission_dir))

        assert "Trust advisory" not in result.stderr

    def test_no_op_when_calibration_file_missing(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir, task_type="auth_refactor")
        # No prior missions, so no calibration file exists
        result = run("plan-approved", "--mission-dir", str(mission_dir))
        assert "Trust advisory" not in result.stderr

    def test_advisory_uses_rollup_fallback(self, tmp_path: Path) -> None:
        # Three frigate decisions for auth_refactor; new task targets a
        # battleship, so the bucket lookup misses but the by_task_type
        # rollup has enough samples.
        _accrue_history(
            tmp_path,
            ["modified", "rejected", "modified"],
            captains=["HMS Argyll:frigate:sonnet:1"],
        )

        mission_dir = init_mission(tmp_path)
        add_squadron(
            mission_dir,
            captains=["HMS Iron Duke:battleship:opus:1"],
        )
        add_task(
            mission_dir,
            owner="HMS Iron Duke",
            task_type="auth_refactor",
        )
        result = run("plan-approved", "--mission-dir", str(mission_dir))
        assert "Trust advisory" in result.stderr
        # Rollup advisory uses "(all ship classes)" form
        assert "all ship classes" in result.stderr


# ---------------------------------------------------------------------------
# trust-report CLI
# ---------------------------------------------------------------------------


class TestTrustReport:
    def test_text_report_sorted_by_override_rate(self, tmp_path: Path) -> None:
        # auth_refactor frigate: 2/3 override (high)
        _accrue_history(
            tmp_path, ["modified", "rejected", "modified"]
        )
        # db_migration battleship: all approved -> 0% override
        for i in range(3):
            mid = f"2026-05-{i + 1:02d}_000001_kk{i:02d}{i:02d}llmm"
            md = init_mission(tmp_path)
            md = _rename_mission(md, mid)
            add_squadron(md, captains=["HMS Iron Duke:battleship:opus:1"])
            add_task(
                md,
                owner="HMS Iron Duke",
                task_type="db_migration",
            )
            run("plan-approved", "--mission-dir", str(md))
            record_admiralty_decision(md, task_id=1, decision_type="approved")
            _stand_down(md)

        result = run(
            "trust-report",
            "--missions-dir", str(tmp_path / ".nelson" / "missions"),
        )
        out = result.stdout
        # High-override row comes first
        assert out.index("auth_refactor") < out.index("db_migration")
        assert "Trust calibration" in out

    def test_json_report_schema(self, tmp_path: Path) -> None:
        _accrue_history(tmp_path, ["modified", "rejected", "modified"])

        result = run(
            "trust-report",
            "--missions-dir", str(tmp_path / ".nelson" / "missions"),
            "--json",
        )
        payload = json.loads(result.stdout)
        assert payload["version"] == 1
        assert payload["min_decisions"] == 3
        assert isinstance(payload["buckets"], list)
        assert isinstance(payload["by_task_type"], list)
        assert payload["buckets"][0]["task_type"] == "auth_refactor"
        assert payload["buckets"][0]["ship_class"] == "frigate"
        assert payload["buckets"][0]["total_decisions"] == 3

    def test_min_decisions_filter(self, tmp_path: Path) -> None:
        # Only 2 decisions — below default threshold of 3.
        _accrue_history(tmp_path, ["modified", "rejected"])

        result = run(
            "trust-report",
            "--missions-dir", str(tmp_path / ".nelson" / "missions"),
            "--json",
        )
        payload = json.loads(result.stdout)
        assert payload["buckets"] == []

        # Lowering the threshold reveals the bucket.
        result = run(
            "trust-report",
            "--missions-dir", str(tmp_path / ".nelson" / "missions"),
            "--min-decisions", "1",
            "--json",
        )
        payload = json.loads(result.stdout)
        assert len(payload["buckets"]) == 1
        assert payload["buckets"][0]["total_decisions"] == 2
