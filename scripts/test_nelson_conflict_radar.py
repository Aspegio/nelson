"""Tests for nelson_conflict_radar.py — runtime conflict detection.

Tests the path matching, git status parsing, and radar scan logic.
Uses monkeypatching for subprocess calls to avoid real git operations.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from nelson_conflict_radar import _paths_match, get_git_changes, radar_scan


# ---------------------------------------------------------------------------
# _paths_match
# ---------------------------------------------------------------------------

class TestPathsMatch:
    """Test the path component-aligned matching logic."""

    def test_exact_match(self) -> None:
        assert _paths_match(Path("src/utils/app.py"), Path("src/utils/app.py"))

    def test_suffix_match_subpath(self) -> None:
        assert _paths_match(Path("src/utils/app.py"), Path("utils/app.py"))

    def test_suffix_match_filename_only(self) -> None:
        assert _paths_match(Path("src/utils/app.py"), Path("app.py"))

    def test_no_substring_false_positive(self) -> None:
        """'app.py' must not match 'application.py' — different filename."""
        assert not _paths_match(Path("src/webapp/application.py"), Path("app.py"))

    def test_no_partial_component_match(self) -> None:
        """Owned path components must align exactly with tail components."""
        assert not _paths_match(Path("src/foobar/baz.py"), Path("bar/baz.py"))

    def test_owned_longer_than_changed(self) -> None:
        assert not _paths_match(Path("app.py"), Path("src/utils/app.py"))

    def test_both_single_component(self) -> None:
        assert _paths_match(Path("README.md"), Path("README.md"))

    def test_both_single_component_mismatch(self) -> None:
        assert not _paths_match(Path("README.md"), Path("CHANGELOG.md"))


# ---------------------------------------------------------------------------
# get_git_changes
# ---------------------------------------------------------------------------

class TestGetGitChanges:
    """Test git status parsing with -z (NUL-separated) output."""

    @staticmethod
    def _make_porcelain_z(*entries: str) -> str:
        """Build NUL-separated porcelain output from entry strings."""
        return "\0".join(entries) + "\0"

    def test_modified_files(self) -> None:
        stdout = self._make_porcelain_z(
            " M src/main.py",
            "M  src/utils.py",
        )
        with patch("nelson_conflict_radar.subprocess.run") as mock_run:
            mock_run.return_value.stdout = stdout
            mock_run.return_value.returncode = 0
            result = get_git_changes(Path("."))
        assert result == {"src/main.py", "src/utils.py"}

    def test_untracked_files_excluded(self) -> None:
        stdout = self._make_porcelain_z(
            " M src/main.py",
            "?? scratch.txt",
            "?? tmp/output.log",
        )
        with patch("nelson_conflict_radar.subprocess.run") as mock_run:
            mock_run.return_value.stdout = stdout
            mock_run.return_value.returncode = 0
            result = get_git_changes(Path("."))
        assert result == {"src/main.py"}

    def test_renamed_file_uses_destination(self) -> None:
        # With -z, renames are: "R  new.py\0old.py"
        stdout = "R  new.py\0old.py\0"
        with patch("nelson_conflict_radar.subprocess.run") as mock_run:
            mock_run.return_value.stdout = stdout
            mock_run.return_value.returncode = 0
            result = get_git_changes(Path("."))
        assert result == {"new.py"}

    def test_empty_output(self) -> None:
        with patch("nelson_conflict_radar.subprocess.run") as mock_run:
            mock_run.return_value.stdout = ""
            mock_run.return_value.returncode = 0
            result = get_git_changes(Path("."))
        assert result == set()

    def test_added_files(self) -> None:
        stdout = self._make_porcelain_z("A  new_file.py")
        with patch("nelson_conflict_radar.subprocess.run") as mock_run:
            mock_run.return_value.stdout = stdout
            mock_run.return_value.returncode = 0
            result = get_git_changes(Path("."))
        assert result == {"new_file.py"}

    def test_git_failure_returns_empty(self) -> None:
        import subprocess as sp

        with patch(
            "nelson_conflict_radar.subprocess.run",
            side_effect=sp.CalledProcessError(128, "git"),
        ):
            result = get_git_changes(Path("."))
        assert result == set()


# ---------------------------------------------------------------------------
# radar_scan
# ---------------------------------------------------------------------------

class TestRadarScan:
    """Test the ownership scan logic."""

    def test_all_files_owned(self) -> None:
        ownership = {"HMS Victory": {"src/main.py", "src/utils.py"}}
        changed = {"src/main.py"}
        alerts = radar_scan(ownership, changed)
        assert alerts == []

    def test_unowned_file_raises_alert(self) -> None:
        ownership = {"HMS Victory": {"src/main.py"}}
        changed = {"src/unknown.py"}
        alerts = radar_scan(ownership, changed)
        assert len(alerts) == 1
        assert "src/unknown.py" in alerts[0]

    def test_suffix_matching_finds_owner(self) -> None:
        ownership = {"HMS Victory": {"main.py"}}
        changed = {"src/main.py"}
        alerts = radar_scan(ownership, changed)
        assert alerts == []

    def test_no_false_positive_substring(self) -> None:
        """'app.py' ownership must not match 'application.py'."""
        ownership = {"HMS Victory": {"app.py"}}
        changed = {"src/application.py"}
        alerts = radar_scan(ownership, changed)
        assert len(alerts) == 1
        assert "src/application.py" in alerts[0]

    def test_multiple_ships(self) -> None:
        ownership = {
            "HMS Victory": {"src/api.py"},
            "HMS Defiant": {"src/db.py"},
        }
        changed = {"src/api.py", "src/db.py", "src/rogue.py"}
        alerts = radar_scan(ownership, changed)
        assert len(alerts) == 1
        assert "src/rogue.py" in alerts[0]

    def test_empty_changed_files(self) -> None:
        ownership = {"HMS Victory": {"src/main.py"}}
        alerts = radar_scan(ownership, set())
        assert alerts == []

    def test_empty_ownership(self) -> None:
        alerts = radar_scan({}, {"src/main.py"})
        assert len(alerts) == 1
