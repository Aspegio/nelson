"""Tests for nelson_hooks.py — hook enforcement script.

Tests the preflight, mode-check, brief-validate, task-complete,
and idle-ship subcommands using temporary mission directories and
monkeypatched stdin.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# Add hooks directory to path for imports
hooks_dir = os.path.dirname(os.path.abspath(__file__))
if hooks_dir not in sys.path:
    sys.path.insert(0, hooks_dir)

from conftest import VALID_FLAGSHIP_BRIEF, VALID_STANDARD_BRIEF  # noqa: E402
from nelson_hooks import (  # noqa: E402
    ROLLBACK_PATTERNS,
    VALIDATION_EVIDENCE_PATTERNS,
    _check_running_plot_nonempty,
    _check_section_present,
    _find_mission_dir,
    _get_mode,
    _get_tasks,
    _has_evidence,
    cmd_brief_validate,
    cmd_idle_ship,
    cmd_mode_check,
    cmd_preflight,
    cmd_task_complete,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mission(
    tmp_path: Path,
    *,
    mode: str = "subagents",
    tasks: list[dict[str, Any]] | None = None,
    fleet_status: dict[str, Any] | None = None,
) -> Path:
    """Create a minimal active Nelson mission directory."""
    nelson_dir = tmp_path / ".nelson"
    nelson_dir.mkdir(exist_ok=True)
    mission_dir = nelson_dir / "missions" / "2026-01-01_120000_test"
    mission_dir.mkdir(parents=True, exist_ok=True)
    (nelson_dir / ".active-test-session").write_text(
        str(mission_dir), encoding="utf-8",
    )
    battle_plan: dict[str, Any] = {
        "version": 1,
        "squadron": {
            "mode": mode,
            "admiral": {"ship_name": "HMS Victory", "model": "opus"},
            "captains": [
                {
                    "ship_name": "HMS Daring",
                    "ship_class": "destroyer",
                    "model": "sonnet",
                    "task_id": "task-1",
                },
            ],
        },
        "tasks": tasks or [],
    }
    (mission_dir / "battle-plan.json").write_text(
        json.dumps(battle_plan), encoding="utf-8",
    )
    if fleet_status is not None:
        (mission_dir / "fleet-status.json").write_text(
            json.dumps(fleet_status), encoding="utf-8",
        )
    return mission_dir


def _stdin(payload: dict[str, Any], cwd: str = ".") -> StringIO:
    return StringIO(json.dumps({"cwd": cwd, **payload}))


def _run(cmd_fn: Any, payload: dict[str, Any], cwd: str = ".") -> int:
    """Run a hook command and return its exit code."""
    with patch("sys.stdin", _stdin(payload, cwd)):
        with pytest.raises(SystemExit) as exc:
            cmd_fn(argparse.Namespace())
    return exc.value.code


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------


class TestFindMissionDir:
    def test_no_nelson_dir(self, tmp_path: Path) -> None:
        assert _find_mission_dir(tmp_path) is None

    def test_no_active_files(self, tmp_path: Path) -> None:
        (tmp_path / ".nelson").mkdir()
        assert _find_mission_dir(tmp_path) is None

    def test_active_mission_found(self, tmp_path: Path) -> None:
        mission_dir = _make_mission(tmp_path)
        assert _find_mission_dir(tmp_path) == mission_dir

    def test_active_file_points_to_missing_dir(self, tmp_path: Path) -> None:
        nelson_dir = tmp_path / ".nelson"
        nelson_dir.mkdir()
        (nelson_dir / ".active-test").write_text("/nonexistent/path", encoding="utf-8")
        assert _find_mission_dir(tmp_path) is None


class TestGetMode:
    def test_default_mode(self) -> None:
        assert _get_mode({}) == "subagents"

    def test_explicit_mode(self) -> None:
        assert _get_mode({"squadron": {"mode": "agent-team"}}) == "agent-team"


class TestGetTasks:
    def test_no_tasks(self) -> None:
        assert _get_tasks({}) == []

    def test_with_tasks(self) -> None:
        tasks = [{"id": "task-1", "name": "Test"}]
        assert _get_tasks({"tasks": tasks}) == tasks


class TestHasEvidence:
    def test_finds_test_keyword(self) -> None:
        assert _has_evidence("All tests passed", VALIDATION_EVIDENCE_PATTERNS)

    def test_finds_rollback(self) -> None:
        assert _has_evidence("Rollback: git revert abc", ROLLBACK_PATTERNS)

    def test_no_match(self) -> None:
        assert not _has_evidence("Hello world", ROLLBACK_PATTERNS)

    def test_case_insensitive(self) -> None:
        assert _has_evidence("VERIFIED output", VALIDATION_EVIDENCE_PATTERNS)


class TestCheckSectionPresent:
    def test_present(self) -> None:
        assert _check_section_present("Ship: HMS Daring\n", "Ship:")

    def test_absent(self) -> None:
        assert not _check_section_present("Role: Captain\n", "Ship:")

    def test_case_insensitive(self) -> None:
        assert _check_section_present("ship: HMS Daring\n", "Ship:")


class TestCheckRunningPlotNonempty:
    def test_nonempty(self) -> None:
        assert _check_running_plot_nonempty(
            "Running plot:\n- Working on auth module\n\nFiles touched:",
        )

    def test_empty_section(self) -> None:
        assert not _check_running_plot_nonempty("Running plot:\n\nFiles touched:")

    def test_missing_section(self) -> None:
        assert not _check_running_plot_nonempty("Progress log:\n- Did stuff\n")

    def test_section_with_only_whitespace(self) -> None:
        assert not _check_running_plot_nonempty("Running plot:\n   \n\nFiles touched:")


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------


def _task(
    tid: str = "task-1",
    name: str = "Build auth",
    tier: int = 0,
    owner: str = "HMS Daring",
    files: list[str] | None = None,
) -> dict[str, Any]:
    """Shorthand for a task dict."""
    return {
        "id": tid,
        "name": name,
        "station_tier": tier,
        "owner": owner,
        "file_ownership": files or [],
    }


class TestPreflight:
    def test_no_mission_allows(self, tmp_path: Path) -> None:
        code = _run(
            cmd_preflight,
            {"tool_name": "Agent", "tool_input": {"subagent_type": "general-purpose"}},
            cwd=str(tmp_path),
        )
        assert code == 0

    def test_missing_station_tier_none_rejects(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, tasks=[{"id": "t1", "name": "X", "station_tier": None}])
        code = _run(
            cmd_preflight,
            {"tool_name": "Agent", "tool_input": {"subagent_type": "general-purpose"}},
            cwd=str(tmp_path),
        )
        assert code == 2

    def test_missing_station_tier_key_absent_rejects(self, tmp_path: Path) -> None:
        """Task dict with no station_tier key at all should also reject."""
        _make_mission(tmp_path, tasks=[{"id": "t1", "name": "X"}])
        code = _run(
            cmd_preflight,
            {"tool_name": "Agent", "tool_input": {"subagent_type": "general-purpose"}},
            cwd=str(tmp_path),
        )
        assert code == 2

    def test_all_tiers_set_allows(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, tasks=[_task(files=["src/auth.py"])])
        code = _run(
            cmd_preflight,
            {"tool_name": "Agent", "tool_input": {"subagent_type": "general-purpose"}},
            cwd=str(tmp_path),
        )
        assert code == 0

    def test_duplicate_file_ownership_rejects(self, tmp_path: Path) -> None:
        _make_mission(
            tmp_path,
            tasks=[
                _task(tid="t1", owner="HMS Daring", files=["src/shared.py"]),
                _task(tid="t2", owner="HMS Diamond", files=["src/shared.py"]),
            ],
        )
        code = _run(
            cmd_preflight,
            {"tool_name": "Agent", "tool_input": {"subagent_type": "general-purpose"}},
            cwd=str(tmp_path),
        )
        assert code == 2

    def test_subagent_type_in_agent_team_rejects(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, mode="agent-team", tasks=[_task(files=["src/auth.py"])])
        code = _run(
            cmd_preflight,
            {
                "tool_name": "Agent",
                "tool_input": {
                    "subagent_type": "general-purpose",
                    "prompt": "Build the auth module",
                },
            },
            cwd=str(tmp_path),
        )
        assert code == 2

    def test_team_name_in_subagents_rejects(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, mode="subagents", tasks=[_task(files=["src/auth.py"])])
        code = _run(
            cmd_preflight,
            {
                "tool_name": "Agent",
                "tool_input": {
                    "team_name": "squadron",
                    "name": "hms-daring",
                    "prompt": "Build the auth module",
                },
            },
            cwd=str(tmp_path),
        )
        assert code == 2

    def test_marine_subagent_in_agent_team_allows(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, mode="agent-team", tasks=[_task(files=["src/auth.py"])])
        code = _run(
            cmd_preflight,
            {
                "tool_name": "Agent",
                "tool_input": {
                    "subagent_type": "general-purpose",
                    "prompt": "Deploy Royal Marine to check test coverage",
                },
            },
            cwd=str(tmp_path),
        )
        assert code == 0


# ---------------------------------------------------------------------------
# Mode-check
# ---------------------------------------------------------------------------


class TestModeCheck:
    def test_no_mission_allows(self, tmp_path: Path) -> None:
        assert _run(cmd_mode_check, {"tool_name": "TaskCreate", "tool_input": {}}, str(tmp_path)) == 0

    def test_subagents_mode_rejects(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, mode="subagents")
        assert _run(cmd_mode_check, {"tool_name": "TaskCreate", "tool_input": {}}, str(tmp_path)) == 2

    def test_single_session_rejects(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, mode="single-session")
        assert _run(cmd_mode_check, {"tool_name": "TaskCreate", "tool_input": {}}, str(tmp_path)) == 2

    def test_agent_team_allows(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, mode="agent-team")
        assert _run(cmd_mode_check, {"tool_name": "TaskCreate", "tool_input": {}}, str(tmp_path)) == 0


# ---------------------------------------------------------------------------
# Brief-validate
# ---------------------------------------------------------------------------


class TestBriefValidate:
    def test_non_turnover_path_allows(self, tmp_path: Path) -> None:
        code = _run(cmd_brief_validate, {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "src" / "main.py")},
        })
        assert code == 0

    def test_valid_standard_brief_allows(self, tmp_path: Path) -> None:
        brief_dir = tmp_path / "turnover-briefs"
        brief_dir.mkdir()
        p = brief_dir / "hms-daring.md"
        p.write_text(VALID_STANDARD_BRIEF, encoding="utf-8")
        assert _run(cmd_brief_validate, {"tool_name": "Write", "tool_input": {"file_path": str(p)}}) == 0

    def test_missing_sections_rejects(self, tmp_path: Path) -> None:
        brief_dir = tmp_path / "turnover-briefs"
        brief_dir.mkdir()
        p = brief_dir / "hms-daring.md"
        p.write_text("== TURNOVER BRIEF ==\nShip: HMS Daring\nRole: Captain\n", encoding="utf-8")
        assert _run(cmd_brief_validate, {"tool_name": "Write", "tool_input": {"file_path": str(p)}}) == 2

    def test_empty_running_plot_rejects(self, tmp_path: Path) -> None:
        brief_dir = tmp_path / "turnover-briefs"
        brief_dir.mkdir()
        p = brief_dir / "hms-daring.md"
        content = VALID_STANDARD_BRIEF.replace(
            "Running plot:\n- Working on refresh token rotation\n"
            "- Current state: halfway through implementation",
            "Running plot:\n",
        )
        p.write_text(content, encoding="utf-8")
        assert _run(cmd_brief_validate, {"tool_name": "Write", "tool_input": {"file_path": str(p)}}) == 2

    def test_valid_flagship_brief_allows(self, tmp_path: Path) -> None:
        brief_dir = tmp_path / "turnover-briefs"
        brief_dir.mkdir()
        p = brief_dir / "hms-victory.md"
        p.write_text(VALID_FLAGSHIP_BRIEF, encoding="utf-8")
        assert _run(cmd_brief_validate, {"tool_name": "Write", "tool_input": {"file_path": str(p)}}) == 0

    def test_flagship_missing_sections_rejects(self, tmp_path: Path) -> None:
        brief_dir = tmp_path / "turnover-briefs"
        brief_dir.mkdir()
        p = brief_dir / "hms-victory.md"
        content = VALID_FLAGSHIP_BRIEF.replace(
            "Battle plan status:\n"
            "- Task task-1: Build auth | Owner: HMS Daring | "
            "Status: in_progress | Notes: on track\n",
            "",
        )
        p.write_text(content, encoding="utf-8")
        assert _run(cmd_brief_validate, {"tool_name": "Write", "tool_input": {"file_path": str(p)}}) == 2

    def test_empty_file_rejects(self, tmp_path: Path) -> None:
        brief_dir = tmp_path / "turnover-briefs"
        brief_dir.mkdir()
        p = brief_dir / "empty.md"
        p.write_text("", encoding="utf-8")
        assert _run(cmd_brief_validate, {"tool_name": "Write", "tool_input": {"file_path": str(p)}}) == 2


# ---------------------------------------------------------------------------
# Task-complete
# ---------------------------------------------------------------------------

_EVIDENCE_S0 = "All tests passed and output verified"
_EVIDENCE_S1 = "Tests passed. Rollback: git revert abc123. Failure case: invalid token returns 401."
_EVIDENCE_S2 = _EVIDENCE_S1 + " Red-cell navigator reviewed and approved."
_EVIDENCE_S3 = _EVIDENCE_S2 + " Human confirmation received. Contingency plan documented."


class TestTaskComplete:
    def test_no_mission_allows(self, tmp_path: Path) -> None:
        code = _run(cmd_task_complete, {"task_id": "t1", "task_subject": "Build auth"}, str(tmp_path))
        assert code == 0

    def test_station_0_with_evidence_allows(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, tasks=[{"id": "t1", "name": "Build auth", "station_tier": 0}])
        code = _run(cmd_task_complete, {
            "task_id": "t1", "task_subject": "Build auth", "task_description": _EVIDENCE_S0,
        }, str(tmp_path))
        assert code == 0

    def test_station_1_missing_rollback_rejects(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, tasks=[{"id": "t1", "name": "Build auth", "station_tier": 1}])
        code = _run(cmd_task_complete, {
            "task_id": "t1", "task_subject": "Build auth",
            "task_description": "Tests passed and verified. Error case checked.",
        }, str(tmp_path))
        assert code == 2

    def test_station_1_with_all_evidence_allows(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, tasks=[{"id": "t1", "name": "Build auth", "station_tier": 1}])
        code = _run(cmd_task_complete, {
            "task_id": "t1", "task_subject": "Build auth", "task_description": _EVIDENCE_S1,
        }, str(tmp_path))
        assert code == 0

    def test_station_2_missing_red_cell_rejects(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, tasks=[{"id": "t1", "name": "Build auth", "station_tier": 2}])
        code = _run(cmd_task_complete, {
            "task_id": "t1", "task_subject": "Build auth", "task_description": _EVIDENCE_S1,
        }, str(tmp_path))
        assert code == 2

    def test_station_2_with_red_cell_allows(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, tasks=[{"id": "t1", "name": "Build auth", "station_tier": 2}])
        code = _run(cmd_task_complete, {
            "task_id": "t1", "task_subject": "Build auth", "task_description": _EVIDENCE_S2,
        }, str(tmp_path))
        assert code == 0

    def test_station_3_missing_human_confirmation_rejects(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, tasks=[{"id": "t1", "name": "Drop table", "station_tier": 3}])
        code = _run(cmd_task_complete, {
            "task_id": "t1", "task_subject": "Drop table", "task_description": _EVIDENCE_S2,
        }, str(tmp_path))
        assert code == 2

    def test_station_3_with_all_evidence_allows(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, tasks=[{"id": "t1", "name": "Drop table", "station_tier": 3}])
        code = _run(cmd_task_complete, {
            "task_id": "t1", "task_subject": "Drop table", "task_description": _EVIDENCE_S3,
        }, str(tmp_path))
        assert code == 0

    def test_unmatched_task_allows(self, tmp_path: Path) -> None:
        _make_mission(tmp_path, tasks=[{"id": "t1", "name": "Build auth", "station_tier": 2}])
        code = _run(cmd_task_complete, {
            "task_id": "t999", "task_subject": "Unknown", "task_description": "No evidence",
        }, str(tmp_path))
        assert code == 0


# ---------------------------------------------------------------------------
# Idle-ship
# ---------------------------------------------------------------------------


class TestIdleShip:
    def test_no_mission_allows(self, tmp_path: Path) -> None:
        assert _run(cmd_idle_ship, {"teammate_name": "hms-daring"}, str(tmp_path)) == 0

    def test_complete_no_dependents_advises_paid_off(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        _make_mission(
            tmp_path,
            mode="agent-team",
            tasks=[{"id": "t1", "name": "Auth", "station_tier": 0, "dependents": []}],
            fleet_status={"squadron": [{
                "ship_name": "HMS Daring", "task_id": "t1",
                "task_status": "completed", "hull_integrity_status": "Green",
            }]},
        )
        _run(cmd_idle_ship, {"teammate_name": "HMS Daring"}, str(tmp_path))
        assert "paid-off" in capsys.readouterr().err.lower()

    def test_complete_with_pending_dependents(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        _make_mission(
            tmp_path,
            mode="agent-team",
            tasks=[
                {"id": "t1", "name": "Auth", "station_tier": 0, "dependents": ["t2"]},
                {"id": "t2", "name": "API", "station_tier": 0, "status": "pending"},
            ],
            fleet_status={"squadron": [{
                "ship_name": "HMS Daring", "task_id": "t1",
                "task_status": "completed", "hull_integrity_status": "Green",
            }]},
        )
        _run(cmd_idle_ship, {"teammate_name": "HMS Daring"}, str(tmp_path))
        assert "pending dependent" in capsys.readouterr().err.lower()

    def test_incomplete_task_advises_check(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        _make_mission(
            tmp_path,
            tasks=[],
            fleet_status={"squadron": [{
                "ship_name": "HMS Daring", "task_id": "t1",
                "task_status": "in_progress", "hull_integrity_status": "Amber",
            }]},
        )
        _run(cmd_idle_ship, {"teammate_name": "HMS Daring"}, str(tmp_path))
        assert "in_progress" in capsys.readouterr().err

    def test_unknown_ship_advises_check(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        _make_mission(tmp_path, fleet_status={"squadron": []})
        _run(cmd_idle_ship, {"teammate_name": "HMS Unknown"}, str(tmp_path))
        assert "not found" in capsys.readouterr().err.lower()
