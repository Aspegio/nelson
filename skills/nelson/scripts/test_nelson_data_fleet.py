"""Tests for fleet intelligence and analytics commands.

Tests for index, history, analytics, and brief subcommands of nelson-data.py.
Uses subprocess to black-box test the CLI interface.
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import (
    create_completed_mission,
    read_json,
    run,
)


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


# ---------------------------------------------------------------------------
# Brief
# ---------------------------------------------------------------------------


class TestBrief:
    def _missions_dir(self, tmp_path: Path) -> str:
        return str(tmp_path / ".nelson" / "missions")

    def _setup_missions(
        self, tmp_path: Path, count: int = 2, adopt: list[str] | None = None,
    ) -> None:
        """Create, index, and populate memory for *count* missions."""
        from conftest import add_squadron, add_task, init_mission

        for i in range(count):
            adopt_args: list[str] = []
            for a in (adopt or []):
                adopt_args.extend(["--adopt", a])
            mission_dir = init_mission(tmp_path)
            add_squadron(mission_dir)
            add_task(mission_dir)
            run("plan-approved", "--mission-dir", str(mission_dir))
            run(
                "checkpoint",
                "--mission-dir", str(mission_dir),
                "--pending", "0", "--in-progress", "0", "--completed", "1",
                "--blocked", "0",
                "--tokens-spent", "50000", "--tokens-remaining", "50000",
                "--hull-green", "1", "--hull-amber", "0",
                "--hull-red", "0", "--hull-critical", "0",
                "--decision", "continue", "--rationale", "OK",
            )
            run(
                "stand-down",
                "--mission-dir", str(mission_dir),
                "--outcome-achieved",
                "--actual-outcome", f"Mission {i} done",
                "--metric-result", "Pass",
                *adopt_args,
            )
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)

    def test_brief_no_missions(self, tmp_path: Path) -> None:
        """Brief with no data shows empty state."""
        missions_dir = tmp_path / ".nelson" / "missions"
        missions_dir.mkdir(parents=True)
        result = run("brief", "--missions-dir", str(missions_dir), cwd=tmp_path)
        assert "0 missions" in result.stdout

    def test_brief_with_missions(self, tmp_path: Path) -> None:
        """Brief with indexed missions shows win rate."""
        self._setup_missions(tmp_path, count=3, adopt=["Use TDD"])
        result = run(
            "brief", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path,
        )
        assert "Intelligence Brief" in result.stdout
        assert "win rate" in result.stdout
        assert "Use TDD" in result.stdout

    def test_brief_json_output(self, tmp_path: Path) -> None:
        """--json outputs valid JSON with expected keys."""
        self._setup_missions(tmp_path, count=2, adopt=["Good pattern"])
        result = run(
            "brief", "--missions-dir", self._missions_dir(tmp_path),
            "--json", cwd=tmp_path,
        )
        data = json.loads(result.stdout)
        assert "total_missions" in data
        assert "win_rate" in data
        assert "top_adopt" in data
        assert "top_avoid" in data
        assert "standing_order_hot_spots" in data

    def test_brief_with_context_matching(self, tmp_path: Path) -> None:
        """--context surfaces relevant precedents."""
        from conftest import add_squadron, add_task, init_mission

        # Create a mission with a specific outcome
        mission_dir = init_mission(
            tmp_path, **{"--outcome": "Refactor auth module to use JWT tokens"}
        )
        add_squadron(mission_dir)
        add_task(mission_dir)
        run("plan-approved", "--mission-dir", str(mission_dir))
        run(
            "checkpoint",
            "--mission-dir", str(mission_dir),
            "--pending", "0", "--in-progress", "0", "--completed", "1",
            "--blocked", "0",
            "--tokens-spent", "50000", "--tokens-remaining", "50000",
            "--hull-green", "1", "--hull-amber", "0",
            "--hull-red", "0", "--hull-critical", "0",
            "--decision", "continue", "--rationale", "OK",
        )
        run(
            "stand-down",
            "--mission-dir", str(mission_dir),
            "--outcome-achieved",
            "--actual-outcome", "Auth module refactored with JWT",
            "--metric-result", "All tests pass",
            "--adopt", "JWT rotation tested separately",
        )
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        result = run(
            "brief",
            "--missions-dir", self._missions_dir(tmp_path),
            "--context", "auth module refactor",
            cwd=tmp_path,
        )
        assert "Relevant precedents" in result.stdout
        assert "auth" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class TestAnalyticsCommand:
    def _missions_dir(self, tmp_path: Path) -> str:
        return str(tmp_path / ".nelson" / "missions")

    def _setup_indexed(self, tmp_path: Path, count: int = 3) -> None:
        """Create and index *count* completed missions."""
        for i in range(count):
            create_completed_mission(
                tmp_path,
                mission_id=f"2026-04-{i + 1:02d}_100000",
                outcome_achieved=(i % 3 != 2),
            )
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)

    def test_success_rate_metric(self, tmp_path: Path) -> None:
        self._setup_indexed(tmp_path, count=3)
        result = run(
            "analytics",
            "--missions-dir", self._missions_dir(tmp_path),
            "--metric", "success-rate",
            cwd=tmp_path,
        )
        assert "Success Rate" in result.stdout
        assert "Win rate" in result.stdout

    def test_standing_orders_metric(self, tmp_path: Path) -> None:
        self._setup_indexed(tmp_path, count=2)
        result = run(
            "analytics",
            "--missions-dir", self._missions_dir(tmp_path),
            "--metric", "standing-orders",
            cwd=tmp_path,
        )
        assert "Standing Orders" in result.stdout

    def test_efficiency_metric(self, tmp_path: Path) -> None:
        self._setup_indexed(tmp_path, count=2)
        result = run(
            "analytics",
            "--missions-dir", self._missions_dir(tmp_path),
            "--metric", "efficiency",
            cwd=tmp_path,
        )
        assert "Efficiency" in result.stdout

    def test_all_metrics(self, tmp_path: Path) -> None:
        self._setup_indexed(tmp_path, count=2)
        result = run(
            "analytics",
            "--missions-dir", self._missions_dir(tmp_path),
            "--metric", "all",
            cwd=tmp_path,
        )
        assert "Success Rate" in result.stdout
        assert "Standing Orders" in result.stdout
        assert "Efficiency" in result.stdout

    def test_analytics_json_output(self, tmp_path: Path) -> None:
        self._setup_indexed(tmp_path, count=2)
        result = run(
            "analytics",
            "--missions-dir", self._missions_dir(tmp_path),
            "--metric", "success-rate",
            "--json",
            cwd=tmp_path,
        )
        data = json.loads(result.stdout)
        assert "total" in data
        assert "win_rate" in data

    def test_analytics_all_json(self, tmp_path: Path) -> None:
        """--metric all --json returns all three metric groups."""
        self._setup_indexed(tmp_path, count=2)
        result = run(
            "analytics",
            "--missions-dir", self._missions_dir(tmp_path),
            "--metric", "all",
            "--json",
            cwd=tmp_path,
        )
        data = json.loads(result.stdout)
        assert "success_rate" in data
        assert "standing_orders" in data
        assert "efficiency" in data

    def test_analytics_last_flag(self, tmp_path: Path) -> None:
        """--last limits the number of missions analyzed."""
        self._setup_indexed(tmp_path, count=4)
        result = run(
            "analytics",
            "--missions-dir", self._missions_dir(tmp_path),
            "--metric", "success-rate",
            "--json",
            "--last", "2",
            cwd=tmp_path,
        )
        data = json.loads(result.stdout)
        assert data["total"] == 2

    def test_estimate_outcomes_metric(self, tmp_path: Path) -> None:
        """Analytics reports pass/fail/not-verified totals across missions."""
        create_completed_mission(
            tmp_path,
            mission_id="2026-04-01_100000",
            estimate_outcomes=[
                {"effect_id": "E1", "criterion_id": "C1", "status": "pass", "method": "test"},
                {"effect_id": "E1", "criterion_id": "C2", "status": "fail", "method": "test"},
                {"effect_id": "E1", "criterion_id": "C3", "status": "pass", "method": "review"},
            ],
        )
        create_completed_mission(
            tmp_path,
            mission_id="2026-04-02_100000",
            estimate_outcomes=[
                {"effect_id": "E1", "criterion_id": "C1", "status": "pass", "method": "type-check"},
                {"effect_id": "E1", "criterion_id": "C2", "status": "not-verified", "method": "visual"},
            ],
        )
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)

        result = run(
            "analytics",
            "--missions-dir", self._missions_dir(tmp_path),
            "--metric", "estimate-outcomes",
            "--json",
            cwd=tmp_path,
        )
        data = json.loads(result.stdout)
        assert data["total"] == 5
        assert data["pass"] == 3
        assert data["fail"] == 1
        assert data["not_verified"] == 1
        assert data["missions_with_outcomes"] == 2
        assert data["pass_rate"] == 60.0

        by_method = data["by_method"]
        assert by_method["test"]["total"] == 2
        assert by_method["test"]["pass"] == 1
        assert by_method["test"]["pass_rate"] == 50.0
        assert by_method["review"]["total"] == 1
        assert by_method["review"]["pass_rate"] == 100.0
        assert by_method["visual"]["total"] == 1
        assert by_method["visual"]["pass_rate"] == 0.0
        assert by_method["lint"]["total"] == 0
        assert by_method["lint"]["pass_rate"] is None

        assert len(data["by_mission"]) == 2

    def test_estimate_outcomes_text_format(self, tmp_path: Path) -> None:
        """Human-readable output shows overall pass rate and method breakdown."""
        create_completed_mission(
            tmp_path,
            mission_id="2026-04-01_100000",
            estimate_outcomes=[
                {"effect_id": "E1", "criterion_id": "C1", "status": "pass", "method": "test"},
                {"effect_id": "E1", "criterion_id": "C2", "status": "fail", "method": "review"},
            ],
        )
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        result = run(
            "analytics",
            "--missions-dir", self._missions_dir(tmp_path),
            "--metric", "estimate-outcomes",
            cwd=tmp_path,
        )
        assert "Estimate outcomes" in result.stdout
        assert "50.0% pass" in result.stdout
        assert "By method" in result.stdout
        assert "test:" in result.stdout
        assert "review:" in result.stdout

    def test_estimate_outcomes_empty_when_no_data(self, tmp_path: Path) -> None:
        """Metric works even when no mission recorded outcomes."""
        self._setup_indexed(tmp_path, count=2)
        result = run(
            "analytics",
            "--missions-dir", self._missions_dir(tmp_path),
            "--metric", "estimate-outcomes",
            "--json",
            cwd=tmp_path,
        )
        data = json.loads(result.stdout)
        assert data["total"] == 0
        assert data["missions_with_outcomes"] == 0
        assert data["pass_rate"] is None

    def test_estimate_outcomes_in_all_metric(self, tmp_path: Path) -> None:
        """--metric all includes the estimate_outcomes group."""
        create_completed_mission(
            tmp_path,
            mission_id="2026-04-01_100000",
            estimate_outcomes=[
                {"effect_id": "E1", "criterion_id": "C1", "status": "pass", "method": "test"},
            ],
        )
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)
        result = run(
            "analytics",
            "--missions-dir", self._missions_dir(tmp_path),
            "--metric", "all",
            "--json",
            cwd=tmp_path,
        )
        data = json.loads(result.stdout)
        assert "estimate_outcomes" in data
        assert data["estimate_outcomes"]["total"] == 1

    def test_analytics_no_index_fails(self, tmp_path: Path) -> None:
        """analytics without an index fails gracefully."""
        missions_dir = tmp_path / ".nelson" / "missions"
        missions_dir.mkdir(parents=True)
        result = run(
            "analytics",
            "--missions-dir", str(missions_dir),
            "--metric", "success-rate",
            cwd=tmp_path,
            expect_fail=True,
        )
        assert "No fleet intelligence index" in result.stderr


# ---------------------------------------------------------------------------
# Index Memory Sync
# ---------------------------------------------------------------------------


class TestIndexMemorySync:
    def _missions_dir(self, tmp_path: Path) -> str:
        return str(tmp_path / ".nelson" / "missions")

    def test_index_populates_memory_store(self, tmp_path: Path) -> None:
        """Running index backfills the memory store from completed missions.

        Note: stand-down already creates pattern entries, but the dir rename
        used by create_completed_mission changes the mission_id, so index
        sync adds entries for the renamed IDs. This test verifies the memory
        store is populated (by stand-down + index sync).
        """
        create_completed_mission(tmp_path, mission_id="2026-04-01_100000")
        create_completed_mission(tmp_path, mission_id="2026-04-02_100000")
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)

        patterns_path = tmp_path / ".nelson" / "memory" / "patterns.json"
        assert patterns_path.exists()
        data = read_json(patterns_path)
        # 2 from stand-down (original IDs) + 2 from index sync (renamed IDs)
        assert data["pattern_count"] >= 2
        # Verify both renamed mission IDs are present
        mission_ids = {p["mission_id"] for p in data["patterns"]}
        assert "2026-04-01_100000" in mission_ids
        assert "2026-04-02_100000" in mission_ids

    def test_index_incremental_sync(self, tmp_path: Path) -> None:
        """Re-indexing after new missions only adds new patterns for unseen IDs."""
        create_completed_mission(tmp_path, mission_id="2026-04-01_100000")
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)

        patterns = read_json(tmp_path / ".nelson" / "memory" / "patterns.json")
        count_after_first = patterns["pattern_count"]

        create_completed_mission(tmp_path, mission_id="2026-04-02_100000")
        run("index", "--missions-dir", self._missions_dir(tmp_path), cwd=tmp_path)

        patterns = read_json(tmp_path / ".nelson" / "memory" / "patterns.json")
        # At least one more pattern added for the new mission
        assert patterns["pattern_count"] > count_after_first
        mission_ids = {p["mission_id"] for p in patterns["patterns"]}
        assert "2026-04-02_100000" in mission_ids
