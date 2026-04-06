#!/usr/bin/env python3
"""
Conflict Radar for Nelson Missions.

This script monitors for file conflicts by comparing active git changes
against the `battle-plan.md` file ownership declarations. It raises an
alert if a changed file has no registered owner in the battle plan.

Limitation: This script uses ``git status`` to detect changed files globally.
It cannot determine which agent made a change, so it can only flag files that
have no registered owner — not cross-ship violations (Ship A writing to Ship B's
files). For true cross-ship detection, per-agent change tracking would be needed.

Usage (manual invocation):
  python3 scripts/nelson_conflict_radar.py --plan .nelson/missions/<your-mission-dir>/battle-plan.md

Opt-in hook configuration (add to settings.json PostToolUse hooks if desired):
  Recommended guard to only run during active Nelson missions:
    if [ -d .nelson/missions ]; then python3 scripts/nelson_conflict_radar.py --plan <path>; fi

  Note: Running this as a default PostToolUse hook is NOT recommended — it is
  too expensive to run on every tool use and will cause issues in non-Nelson
  projects. Opt in manually by adding the hook command to your settings.json
  and supplying the explicit --plan path.

Depends on: nelson_conflict_scan.py (shared parse_battle_plan logic from PR #73).
"""

import sys
import subprocess
import argparse
from pathlib import Path
from nelson_conflict_scan import parse_battle_plan


def get_git_changes(project_root: Path) -> set[str]:
    """Get modified/staged files from git, excluding untracked files.

    Uses ``git status --porcelain -z`` for NUL-separated output, which avoids
    quoting issues with paths containing spaces or special characters.
    Untracked files (``??``) are excluded because they are typically scratch
    files or temp outputs that should not trigger ownership alerts.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "-z"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running git status: {e}", file=sys.stderr)
        return set()

    changed_files: set[str] = set()
    # -z output is NUL-separated; split and filter empty strings
    entries = [e for e in result.stdout.split("\0") if e]

    i = 0
    while i < len(entries):
        entry = entries[i]
        if len(entry) < 4:
            i += 1
            continue

        status = entry[:2]
        filename = entry[3:]

        # Skip untracked files
        if status == "??":
            i += 1
            continue

        # Renames/copies have a second entry for the original path
        if status[0] in ("R", "C"):
            # With -z, rename format is: "R  new\0old"
            # We want the new (destination) filename
            i += 1  # skip the old path entry
        changed_files.add(filename)
        i += 1

    return changed_files


def _paths_match(changed: Path, owned: Path) -> bool:
    """Check if a changed file path matches an owned file path.

    Supports exact matches and suffix matches where the owned path is a
    trailing sub-path of the changed path (aligned on path components).
    For example, ``src/utils/app.py`` matches owned path ``src/utils/app.py``
    and ``utils/app.py`` but NOT ``app.py`` matching ``webapp/application.py``.
    """
    if changed == owned:
        return True
    # Suffix match: owned parts must align with the tail of changed parts
    changed_parts = changed.parts
    owned_parts = owned.parts
    if len(owned_parts) > len(changed_parts):
        return False
    return changed_parts[-len(owned_parts):] == owned_parts


def radar_scan(ownership: dict[str, set[str]], changed_files: set[str]) -> list[str]:
    """Scan changed files against ownership to detect unowned modifications.

    Flags any changed file that has no registered owner in the battle plan.
    Cannot detect cross-ship violations (Ship A editing Ship B's files)
    because ``git status`` reports global working-tree state without
    per-agent attribution.
    """
    file_to_owner: dict[str, str] = {}
    for owner, files in ownership.items():
        for f in files:
            file_to_owner[f] = owner

    alerts: list[str] = []
    for changed in changed_files:
        changed_path = Path(changed)
        found_owner = any(
            _paths_match(changed_path, Path(f)) for f in file_to_owner
        )
        if not found_owner:
            alerts.append(
                f"File '{changed}' was modified but has no owner in the battle plan."
            )

    return alerts


def main():
    parser = argparse.ArgumentParser(description="Conflict radar for Nelson.")
    parser.add_argument("--plan", required=True, help="Path to battle-plan.md")
    parser.add_argument("--root", default=".", help="Project root directory")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    project_root = Path(args.root)

    ownership = parse_battle_plan(plan_path)
    if not ownership:
        print("No ownership data found in battle plan.")
        sys.exit(0)

    changed_files = get_git_changes(project_root)
    if not changed_files:
        print("No file changes detected by git.")
        sys.exit(0)

    alerts = radar_scan(ownership, changed_files)

    if alerts:
        print("\n[!] RADAR ALERT: Potential file conflicts detected!")
        for alert in alerts:
            print(f"  - {alert}")
        print("\nRaise a blocker_raised event for these violations.")
        sys.exit(1)
    else:
        print("\n[+] Radar scan clean: Active changes match battle plan ownership.")
        sys.exit(0)


if __name__ == "__main__":
    main()
