"""Tests for the goal-condition command and its composer.

Covers the pure ``compose_goal_condition`` function and the ``goal-condition``
CLI subcommand (plain output, JSON, --record persistence, --max-turns, the
4,000-char limit warning, and schema preservation of the recorded field).
Black-box CLI tests go through the same subprocess harness as the other
nelson-data tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import init_mission, read_json, run
from nelson_data_goal import GOAL_CONDITION_MAX_CHARS, compose_goal_condition
from nelson_data_utils import VALID_EVENT_TYPES

# ---------------------------------------------------------------------------
# Pure composer
# ---------------------------------------------------------------------------


class TestComposeGoalCondition:
    def test_includes_outcome_and_metric(self) -> None:
        condition = compose_goal_condition({"outcome": "Ship the auth refactor", "success_metric": "47 tests pass"})
        assert "Ship the auth refactor" in condition
        assert "47 tests pass" in condition

    def test_includes_stop_criteria_when_present(self) -> None:
        condition = compose_goal_condition(
            {
                "outcome": "X",
                "success_metric": "M",
                "stop_criteria": ["All tests pass", "No regressions"],
            }
        )
        assert "All tests pass" in condition
        assert "No regressions" in condition
        assert "every stop criterion" in condition

    def test_omits_stop_criteria_clause_when_absent(self) -> None:
        condition = compose_goal_condition({"outcome": "X", "success_metric": "M"})
        assert "every stop criterion" not in condition

    def test_always_requires_captains_log_and_stand_down(self) -> None:
        """The transcript-verifiable Stand Down evidence is always required."""
        condition = compose_goal_condition({"outcome": "X"})
        assert "captain's log" in condition
        assert "stand-down" in condition.lower()

    def test_includes_scuttle_escape_path(self) -> None:
        """A formally abandoned mission is a legitimate stop, not a trap."""
        condition = compose_goal_condition({"outcome": "X"})
        assert "scuttle-and-reform" in condition

    def test_max_turns_appended(self) -> None:
        condition = compose_goal_condition({"outcome": "X"}, max_turns=25)
        assert "stop after 25 turns" in condition

    def test_max_turns_ignored_when_zero_or_none(self) -> None:
        assert "stop after" not in compose_goal_condition({"outcome": "X"})
        assert "stop after" not in compose_goal_condition({"outcome": "X"}, max_turns=0)

    def test_missing_outcome_uses_placeholder(self) -> None:
        condition = compose_goal_condition({})
        assert "the stated mission outcome" in condition

    def test_collapses_whitespace_in_free_text(self) -> None:
        condition = compose_goal_condition({"outcome": "line one\n  line two\ttab"})
        assert "line one line two tab" in condition
        assert "\n" not in condition

    def test_does_not_mutate_input(self) -> None:
        orders = {"outcome": "X", "success_metric": "M", "stop_criteria": ["a"]}
        snapshot = json.dumps(orders, sort_keys=True)
        compose_goal_condition(orders)
        assert json.dumps(orders, sort_keys=True) == snapshot


# ---------------------------------------------------------------------------
# CLI: goal-condition
# ---------------------------------------------------------------------------


class TestGoalConditionCommand:
    def test_plain_output_is_a_goal_command(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        result = run("goal-condition", "--mission-dir", str(mission_dir))
        assert result.stdout.startswith("/goal ")
        assert "Test mission" in result.stdout
        assert "All tests pass" in result.stdout

    def test_json_output_shape(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        result = run("goal-condition", "--mission-dir", str(mission_dir), "--json")
        payload = json.loads(result.stdout)
        assert payload["command"] == f"/goal {payload['condition']}"
        assert payload["char_count"] == len(payload["condition"])
        assert payload["within_limit"] is True
        assert payload["recorded"] is False

    def test_max_turns_flows_through(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        result = run("goal-condition", "--mission-dir", str(mission_dir), "--max-turns", "40")
        assert "stop after 40 turns" in result.stdout

    def test_record_persists_field_and_logs_event(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        run("goal-condition", "--mission-dir", str(mission_dir), "--record")

        so = read_json(mission_dir / "sailing-orders.json")
        assert "goal_condition" in so
        assert so["goal_condition"].startswith("The Nelson mission is complete")

        log = read_json(mission_dir / "mission-log.json")
        assert [e["type"] for e in log["events"]] == ["goal_set"]
        assert log["events"][0]["data"]["goal_condition"] == so["goal_condition"]

    def test_recorded_field_survives_later_write(self, tmp_path: Path) -> None:
        """goal_condition must persist through subsequent sailing-orders writes."""
        mission_dir = init_mission(tmp_path)
        run("goal-condition", "--mission-dir", str(mission_dir), "--record")
        run("skip-estimate", "--mission-dir", str(mission_dir), "--reason", "trivial scope")

        so = read_json(mission_dir / "sailing-orders.json")
        assert "goal_condition" in so
        assert so["estimate_skipped"] is True

    def test_missing_sailing_orders_fails(self, tmp_path: Path) -> None:
        (tmp_path / "empty").mkdir()
        result = run(
            "goal-condition",
            "--mission-dir",
            str(tmp_path / "empty"),
            cwd=tmp_path,
            expect_fail=True,
        )
        assert "sailing-orders.json" in result.stderr

    def test_over_limit_metric_warns(self, tmp_path: Path) -> None:
        huge = "x" * (GOAL_CONDITION_MAX_CHARS + 100)
        mission_dir = init_mission(tmp_path, **{"--metric": huge})
        result = run("goal-condition", "--mission-dir", str(mission_dir), "--json")
        payload = json.loads(result.stdout)
        assert payload["within_limit"] is False
        assert "over the" in result.stderr


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class TestGoalEventTypes:
    def test_goal_events_are_valid(self) -> None:
        assert "goal_set" in VALID_EVENT_TYPES
        assert "goal_cleared" in VALID_EVENT_TYPES

    def test_goal_cleared_event_accepted(self, tmp_path: Path) -> None:
        mission_dir = init_mission(tmp_path)
        run(
            "event",
            "--mission-dir",
            str(mission_dir),
            "--type",
            "goal_cleared",
            "--reason",
            "mission complete",
        )
        log = read_json(mission_dir / "mission-log.json")
        assert log["events"][-1]["type"] == "goal_cleared"
        assert log["events"][-1]["data"]["reason"] == "mission complete"
