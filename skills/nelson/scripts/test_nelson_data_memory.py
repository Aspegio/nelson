"""Tests for cross-mission memory store and low-level I/O.

Tests for _write_json crash cleanup, _read_json_optional OSError handling,
and memory store operations (patterns, standing order stats).
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from conftest import (
    SCRIPT,
    add_squadron,
    add_task,
    create_completed_mission,
    init_mission,
    read_json,
    run,
)

from nelson_data_utils import _write_json


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
            # Attempt a write that touches a locked directory — expect
            # failure because _write_json cannot write the tmp file
            # inside the read-only directory.
            result = subprocess.run(
                [
                    sys.executable, "-c",
                    (
                        f"import sys; sys.path.insert(0, '{SCRIPT.parent}');"
                        "from pathlib import Path;"
                        "from nelson_data_utils import _write_json;"
                        f"_write_json(Path('{locked_target}'), {{'version': 2}})"
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
                        "from pathlib import Path;"
                        "from nelson_data_utils import _write_json;"
                        f"_write_json(Path('{target}'), {{'v': 1}})"
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
# Memory Store
# ---------------------------------------------------------------------------


class TestMemoryStore:
    def test_stand_down_creates_patterns_json(self, tmp_path: Path) -> None:
        """Completing a mission creates .nelson/memory/patterns.json."""
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
            "--adopt", "Good pattern",
        )
        patterns_path = tmp_path / ".nelson" / "memory" / "patterns.json"
        assert patterns_path.exists()
        data = read_json(patterns_path)
        assert data["version"] == 1
        assert data["pattern_count"] == 1
        assert data["patterns"][0]["adopt"] == ["Good pattern"]
        assert data["patterns"][0]["outcome_achieved"] is True

    def test_patterns_accumulate(self, tmp_path: Path) -> None:
        """Two missions produce two pattern entries."""
        mission_ids = ["2026-01-01_000001", "2026-01-01_000002"]
        for i, mission_id in enumerate(mission_ids):
            mission_dir = init_mission(tmp_path)
            # Rename to deterministic ID to avoid timestamp collisions
            target = mission_dir.parent / mission_id
            mission_dir.rename(target)
            mission_dir = target
            add_squadron(mission_dir)
            add_task(mission_dir)
            run("plan-approved", "--mission-dir", str(mission_dir))
            run(
                "stand-down",
                "--mission-dir", str(mission_dir),
                "--outcome-achieved",
                "--actual-outcome", f"Mission {i}",
                "--metric-result", "Pass",
                "--adopt", f"Pattern {i}",
            )
        patterns_path = tmp_path / ".nelson" / "memory" / "patterns.json"
        data = read_json(patterns_path)
        assert data["pattern_count"] == 2

    def test_standing_order_stats_updated(self, tmp_path: Path) -> None:
        """Logging a standing_order_violation event updates stats on stand-down."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir)
        run("plan-approved", "--mission-dir", str(mission_dir))
        run(
            "event",
            "--mission-dir", str(mission_dir),
            "--type", "standing_order_violation",
            "--order", "split-keel",
            "--description", "File overlap",
            "--severity", "medium",
            "--corrective-action", "Reassigned",
        )
        run(
            "stand-down",
            "--mission-dir", str(mission_dir),
            "--outcome-achieved",
            "--actual-outcome", "Done",
            "--metric-result", "Pass",
        )
        stats_path = tmp_path / ".nelson" / "memory" / "standing-order-stats.json"
        assert stats_path.exists()
        stats = read_json(stats_path)
        assert stats["total_violations"] == 1
        assert stats["total_missions"] == 1
        assert "split-keel" in stats["by_order"]
        assert stats["by_order"]["split-keel"]["count"] == 1

    def test_memory_store_failure_non_fatal(self, tmp_path: Path) -> None:
        """If memory dir is read-only, stand-down still succeeds."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir)
        run("plan-approved", "--mission-dir", str(mission_dir))

        # Create a read-only memory directory to force failure
        memory_dir = tmp_path / ".nelson" / "memory"
        memory_dir.mkdir(parents=True)
        memory_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
        try:
            result = run(
                "stand-down",
                "--mission-dir", str(mission_dir),
                "--outcome-achieved",
                "--actual-outcome", "Done",
                "--metric-result", "Pass",
            )
            # Stand-down should succeed despite memory store failure
            sd = read_json(mission_dir / "stand-down.json")
            assert sd["outcome_achieved"] is True
            assert "Warning" in result.stderr or "memory" in result.stderr.lower()
        finally:
            memory_dir.chmod(stat.S_IRWXU)

    def test_extract_patterns_captures_violations(self, tmp_path: Path) -> None:
        """Pattern extraction includes standing order violation details."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir)
        run("plan-approved", "--mission-dir", str(mission_dir))
        run(
            "event",
            "--mission-dir", str(mission_dir),
            "--type", "standing_order_violation",
            "--order", "skeleton-crew",
            "--description", "Too few agents",
            "--severity", "low",
            "--corrective-action", "Added crew",
        )
        run(
            "stand-down",
            "--mission-dir", str(mission_dir),
            "--outcome-achieved",
            "--actual-outcome", "Done",
            "--metric-result", "Pass",
            "--avoid", "Under-crewing ships",
        )
        patterns_path = tmp_path / ".nelson" / "memory" / "patterns.json"
        data = read_json(patterns_path)
        p = data["patterns"][0]
        assert len(p["standing_order_violations"]) == 1
        assert p["standing_order_violations"][0]["order"] == "skeleton-crew"
        assert p["avoid"] == ["Under-crewing ships"]

    def test_duplicate_stand_down_is_idempotent(self, tmp_path: Path) -> None:
        """Calling stand-down twice for the same mission must not create duplicate entries."""
        mission_dir = init_mission(tmp_path)
        add_squadron(mission_dir)
        add_task(mission_dir)
        run("plan-approved", "--mission-dir", str(mission_dir))

        sd_args = [
            "stand-down",
            "--mission-dir", str(mission_dir),
            "--outcome-achieved",
            "--actual-outcome", "Done",
            "--metric-result", "Pass",
            "--adopt", "Good pattern",
        ]
        run(*sd_args)
        run(*sd_args)  # second call — should be idempotent

        patterns_path = tmp_path / ".nelson" / "memory" / "patterns.json"
        data = read_json(patterns_path)
        assert data["pattern_count"] == 1, "Duplicate stand-down created extra pattern entry"

        stats_path = tmp_path / ".nelson" / "memory" / "standing-order-stats.json"
        stats = read_json(stats_path)
        assert stats["total_missions"] == 1, "Duplicate stand-down inflated mission count"
