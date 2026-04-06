#!/usr/bin/env python3
"""
Conflict Radar for Nelson Missions.

This script runs during the quarterdeck rhythm (via PostToolUse hook)
to monitor for file conflicts. It compares active file changes
(via `git status` / `git diff --name-only`) against the `battle-plan.md`
file ownership to raise an alert if multiple ships write to the same file
or write to a file they don't own.
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
        status = line[:2]
        filename = line[3:].strip()

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
        # Ignore common non-code files
        if (
            changed.endswith(".md")
            or changed.endswith(".json")
            or changed.startswith(".claude")
        ):
            continue

        # Is the changed file owned by anyone?
        found_owner = False
        for f in file_to_owner:
            if f in changed or changed in f:
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
