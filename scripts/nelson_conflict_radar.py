#!/usr/bin/env python3
"""
Conflict Radar for Nelson Missions.

This script monitors for file conflicts by comparing active git changes
against the `battle-plan.md` file ownership declarations. It raises an
alert if a changed file has no registered owner in the battle plan.

Usage (manual invocation):
  python scripts/nelson_conflict_radar.py --plan .nelson/missions/<your-mission-dir>/battle-plan.md

Opt-in hook configuration (add to settings.json PostToolUse hooks if desired):
  Recommended guard to only run during active Nelson missions:
    if [ -d .nelson/missions ]; then python scripts/nelson_conflict_radar.py --plan <path>; fi

  Note: Running this as a default PostToolUse hook is NOT recommended — it is
  too expensive to run on every tool use and will cause issues in non-Nelson
  projects. Opt in manually by adding the hook command to your settings.json
  and supplying the explicit --plan path.
"""

import sys
import subprocess
import argparse
from pathlib import Path
from nelson_conflict_scan import parse_battle_plan


def get_git_changes(project_root: Path) -> set:
    """Get a list of currently modified/untracked files using git."""
    try:
        # Get unstaged and staged changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running git status: {e}", file=sys.stderr)
        return set()

    changed_files = set()
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        # Status format is usually 'XY filename'
        filename = line[3:].strip()

        # Handle quoted paths (git quotes paths with special chars)
        if filename.startswith('"') and filename.endswith('"'):
            filename = filename[1:-1].encode('utf-8').decode('unicode_escape')

        # Handle renames 'R  old -> new'
        if "->" in filename:
            filename = filename.split("->")[1].strip()

        changed_files.add(filename)

    return changed_files


def radar_scan(ownership: dict, changed_files: set) -> list:
    """Scan changed files against ownership to detect violations."""
    alerts = []

    # Create reverse map of files to their owners
    file_to_owner = {}
    for owner, files in ownership.items():
        for f in files:
            file_to_owner[f] = owner

    # Note: In a real multi-agent hook, we would need to know WHICH agent is making the change
    # to flag "writing to unowned file". Since this runs globally via git status, we can only
    # reliably flag if a changed file is owned by multiple agents in the battle plan (which shouldn't
    # happen due to the pre-flight scan) OR if we check the git reflog/blame, which is complex.

    # For now, we will flag any changed file that has no registered owner
    for changed in changed_files:
        # Is the changed file owned by anyone?
        found_owner = False
        changed_path = Path(changed)
        for f in file_to_owner:
            owned_path = Path(f)
            if changed_path == owned_path or str(changed_path).endswith(str(owned_path)):
                found_owner = True
                break

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
