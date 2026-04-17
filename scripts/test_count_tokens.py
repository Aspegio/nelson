"""Tests for count-tokens.py — token counting and damage reports."""

from __future__ import annotations

import json
from pathlib import Path


# ---------------------------------------------------------------------------
# count_tokens_from_jsonl
# ---------------------------------------------------------------------------


class TestCountTokensFromJsonl:
    def test_returns_none_when_no_assistant_turns(self, tmp_path: Path, count_tokens):
        path = tmp_path / "session.jsonl"
        path.write_text(
            '{"type":"user","message":{"content":"hi"}}\n',
            encoding="utf-8",
        )
        assert count_tokens.count_tokens_from_jsonl(path) is None

    def test_returns_none_on_empty_file(self, tmp_path: Path, count_tokens):
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        assert count_tokens.count_tokens_from_jsonl(path) is None

    def test_sums_last_assistant_usage(self, tmp_path: Path, count_tokens):
        lines = [
            {"type": "user", "message": {"content": "a"}},
            {
                "type": "assistant",
                "message": {
                    "usage": {
                        "input_tokens": 100,
                        "cache_creation_input_tokens": 10,
                        "cache_read_input_tokens": 5,
                        "output_tokens": 42,
                    }
                },
            },
            {
                "type": "assistant",
                "message": {
                    "usage": {
                        "input_tokens": 200,
                        "cache_creation_input_tokens": 20,
                        "cache_read_input_tokens": 30,
                        "output_tokens": 7,
                    }
                },
            },
        ]
        path = tmp_path / "session.jsonl"
        path.write_text(
            "\n".join(json.dumps(line) for line in lines) + "\n",
            encoding="utf-8",
        )
        # uses the LAST usage record, sums the three input-side fields,
        # ignoring output_tokens
        assert count_tokens.count_tokens_from_jsonl(path) == 250

    def test_skips_malformed_json_lines(self, tmp_path: Path, count_tokens):
        path = tmp_path / "session.jsonl"
        path.write_text(
            "not json\n"
            + json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "usage": {
                            "input_tokens": 1,
                            "cache_creation_input_tokens": 2,
                            "cache_read_input_tokens": 3,
                            "output_tokens": 4,
                        }
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        assert count_tokens.count_tokens_from_jsonl(path) == 6

    def test_skips_assistant_records_without_usage(self, tmp_path: Path, count_tokens):
        path = tmp_path / "session.jsonl"
        path.write_text(
            json.dumps({"type": "assistant", "message": {"content": "no usage"}})
            + "\n",
            encoding="utf-8",
        )
        assert count_tokens.count_tokens_from_jsonl(path) is None

    def test_treats_missing_usage_fields_as_zero(self, tmp_path: Path, count_tokens):
        path = tmp_path / "session.jsonl"
        path.write_text(
            json.dumps(
                {"type": "assistant", "message": {"usage": {"input_tokens": 50}}}
            )
            + "\n",
            encoding="utf-8",
        )
        assert count_tokens.count_tokens_from_jsonl(path) == 50


# ---------------------------------------------------------------------------
# count_tokens_heuristic
# ---------------------------------------------------------------------------


class TestCountTokensHeuristic:
    def test_char_count_divided_by_four(self, tmp_path: Path, count_tokens):
        path = tmp_path / "plain.txt"
        path.write_text("a" * 40, encoding="utf-8")
        assert count_tokens.count_tokens_heuristic(path) == 10

    def test_rounds_down(self, tmp_path: Path, count_tokens):
        path = tmp_path / "plain.txt"
        path.write_text("a" * 7, encoding="utf-8")  # 7 // 4 == 1
        assert count_tokens.count_tokens_heuristic(path) == 1

    def test_empty_file_is_zero(self, tmp_path: Path, count_tokens):
        path = tmp_path / "empty.txt"
        path.write_text("", encoding="utf-8")
        assert count_tokens.count_tokens_heuristic(path) == 0


# ---------------------------------------------------------------------------
# hull_integrity_status
# ---------------------------------------------------------------------------


class TestHullIntegrityStatus:
    def test_green_at_or_above_75(self, count_tokens):
        assert count_tokens.hull_integrity_status(100) == "Green"
        assert count_tokens.hull_integrity_status(75) == "Green"

    def test_amber_between_60_and_74(self, count_tokens):
        assert count_tokens.hull_integrity_status(74) == "Amber"
        assert count_tokens.hull_integrity_status(60) == "Amber"

    def test_red_between_40_and_59(self, count_tokens):
        assert count_tokens.hull_integrity_status(59) == "Red"
        assert count_tokens.hull_integrity_status(40) == "Red"

    def test_critical_below_40(self, count_tokens):
        assert count_tokens.hull_integrity_status(39) == "Critical"
        assert count_tokens.hull_integrity_status(0) == "Critical"


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------


class TestBuildReport:
    def test_green_status_does_not_request_relief(self, count_tokens):
        report = count_tokens.build_report(
            "HMS Victory", 50_000, 200_000, "jsonl_usage"
        )
        assert report["ship_name"] == "HMS Victory"
        assert report["token_count"] == 50_000
        assert report["token_limit"] == 200_000
        assert report["hull_integrity_pct"] == 75
        assert report["hull_integrity_status"] == "Green"
        assert report["relief_requested"] is False
        assert report["method"] == "jsonl_usage"
        # timestamp is present and ISO-8601-ish
        assert "T" in report["timestamp"]

    def test_red_status_requests_relief(self, count_tokens):
        report = count_tokens.build_report("HMS Kent", 130_000, 200_000, "heuristic")
        assert report["hull_integrity_pct"] == 35
        assert report["hull_integrity_status"] == "Critical"
        assert report["relief_requested"] is True

    def test_zero_limit_yields_zero_pct(self, count_tokens):
        report = count_tokens.build_report("HMS Edge", 100, 0, "heuristic")
        assert report["hull_integrity_pct"] == 0
        assert report["hull_integrity_status"] == "Critical"

    def test_count_exceeding_limit_clamps_to_zero_remaining(self, count_tokens):
        report = count_tokens.build_report("HMS Overrun", 300_000, 200_000, "jsonl_usage")
        assert report["hull_integrity_pct"] == 0
        assert report["hull_integrity_status"] == "Critical"
        assert report["relief_requested"] is True


# ---------------------------------------------------------------------------
# scan_squadron
# ---------------------------------------------------------------------------


class TestScanSquadron:
    def _write_assistant_jsonl(self, path: Path, input_tokens: int) -> None:
        path.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "usage": {
                            "input_tokens": input_tokens,
                            "cache_creation_input_tokens": 0,
                            "cache_read_input_tokens": 0,
                            "output_tokens": 0,
                        }
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_flagship_only(self, tmp_path: Path, count_tokens):
        session_dir = tmp_path / "session-abc"
        session_dir.mkdir()
        flagship = tmp_path / "session-abc.jsonl"
        self._write_assistant_jsonl(flagship, 100)

        reports = count_tokens.scan_squadron(str(session_dir), 200_000)

        assert len(reports) == 1
        assert reports[0]["ship_name"] == "Flagship"
        assert reports[0]["token_count"] == 100

    def test_flagship_and_subagents(self, tmp_path: Path, count_tokens):
        session_dir = tmp_path / "session-xyz"
        (session_dir / "subagents").mkdir(parents=True)
        flagship = tmp_path / "session-xyz.jsonl"
        self._write_assistant_jsonl(flagship, 50)
        self._write_assistant_jsonl(
            session_dir / "subagents" / "agent-first.jsonl", 77
        )
        self._write_assistant_jsonl(
            session_dir / "subagents" / "agent-second.jsonl", 99
        )

        reports = count_tokens.scan_squadron(str(session_dir), 200_000)
        ships = [r["ship_name"] for r in reports]

        assert "Flagship" in ships
        assert "agent-first" in ships
        assert "agent-second" in ships
        assert len(reports) == 3

    def test_missing_flagship_and_subagents_returns_empty(
        self, tmp_path: Path, count_tokens
    ):
        session_dir = tmp_path / "session-empty"
        session_dir.mkdir()
        assert count_tokens.scan_squadron(str(session_dir), 200_000) == []

    def test_trailing_slash_on_session_dir_is_handled(
        self, tmp_path: Path, count_tokens
    ):
        session_dir = tmp_path / "session-slash"
        session_dir.mkdir()
        self._write_assistant_jsonl(tmp_path / "session-slash.jsonl", 25)

        reports = count_tokens.scan_squadron(str(session_dir) + "/", 200_000)

        assert len(reports) == 1
        assert reports[0]["token_count"] == 25
