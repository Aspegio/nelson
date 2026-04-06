#!/usr/bin/env python3
"""
Pre-flight Conflict Scan for Nelson Missions.

This script parses a Nelson battle plan (a Markdown or JSON file)
to extract file ownership for each task/captain, and builds a simple
dependency graph of the codebase to check if any two captains own files
that import each other. This flags "split-keel" violations before execution.
"""

import sys
import re
import argparse
from pathlib import Path


def parse_battle_plan(path: Path) -> dict:
    """Parse battle-plan.md to extract file ownership per captain."""
    if not path.exists():
        print(f"Error: Battle plan not found at {path}", file=sys.stderr)
        sys.exit(1)

    content = path.read_text(encoding="utf-8")

    ownership = {}  # Map of captain/ship -> set of files
    current_ship = None

    # We look for lines like "- Ship (if crewed): HMS Victory"
    # and "- File ownership (if code): src/main.py, src/utils.py"
    for line in content.splitlines():
        line = line.strip()

        ship_match = re.match(
            r"^-\s*Ship(?:\s*\(if crewed\))?:\s*(.+)$", line, re.IGNORECASE
        )
        if ship_match:
            ship_name = ship_match.group(1).strip()
            # Handle placeholder "[assigned at Step 3 — Formation]"
            if not ship_name.startswith("["):
                current_ship = ship_name
            continue

        file_match = re.match(
            r"^-\s*File ownership(?:\s*\(if code\))?:\s*(.+)$", line, re.IGNORECASE
        )
        if file_match and current_ship:
            files_str = file_match.group(1).strip()
            # Ignore placeholder
            if not files_str.startswith("["):
                files = [f.strip() for f in files_str.split(",") if f.strip()]
                if current_ship not in ownership:
                    ownership[current_ship] = set()
                ownership[current_ship].update(files)
            # Reset current ship after capturing files so we don't accidentally carry it over
            current_ship = None

    return ownership


def parse_imports(filepath: Path) -> set:
    """Extract imports from a file using simple regex.
    Currently supports Python, JS/TS."""
    imports = set()
    if not filepath.exists():
        return imports

    content = filepath.read_text(encoding="utf-8")

    if filepath.suffix == ".py":
        # import foo
        # from foo import bar
        for line in content.splitlines():
            line = line.strip()
            match = re.match(
                r"^(?:from\s+([a-zA-Z0-9_\.]+)\s+)?import\s+([a-zA-Z0-9_\.,\s]+)", line
            )
            if match:
                module = match.group(1) or match.group(2).split(",")[0].strip()
                imports.add(module.split(".")[0])

    elif filepath.suffix in (".js", ".ts", ".jsx", ".tsx"):
        # import ... from 'foo'
        # require('foo')
        for match in re.finditer(
            r'(?:import.*from\s+[\'"]([^\'"]+)[\'"]|require\([\'"]([^\'"]+)[\'"]\))',
            content,
        ):
            module = match.group(1) or match.group(2)
            imports.add(module)

    return imports


def build_dependency_graph(files: set, project_root: Path) -> dict:
    """Build a graph mapping a file to its imports."""
    graph = {}
    for f in files:
        filepath = project_root / f
        graph[f] = parse_imports(filepath)
    return graph


def detect_conflicts(ownership: dict, graph: dict) -> list:
    """Detect if files owned by different captains import each other."""
    conflicts = []

    # Create a reverse map from file to owner
    file_to_owner = {}
    for owner, files in ownership.items():
        for f in files:
            file_to_owner[f] = owner

    # For each file, check its imports
    for file, owner in file_to_owner.items():
        if file not in graph:
            continue

        imports = graph[file]
        for other_file, other_owner in file_to_owner.items():
            if owner == other_owner:
                continue

            # Check if `file` imports `other_file`.
            # This is a very simplistic check that tries to match the module name
            # to the file name. It's language-dependent and brittle, but a start.

            # Extract basic module names from the paths
            file_module = Path(file).stem
            other_module = Path(other_file).stem

            # Simple heuristic: if the module name is in the imports
            # OR if it's a relative path match for JS/TS
            for imp in imports:
                if other_module in imp or imp in str(Path(other_file)):
                    conflicts.append((owner, file, other_owner, other_file))

    return conflicts


def main():
    parser = argparse.ArgumentParser(
        description="Pre-flight conflict scan for Nelson battle plans."
    )
    parser.add_argument("--plan", required=True, help="Path to battle-plan.md")
    parser.add_argument("--root", default=".", help="Project root directory")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    project_root = Path(args.root)

    ownership = parse_battle_plan(plan_path)

    if not ownership:
        print("No file ownership declarations found in battle plan.")
        sys.exit(0)

    print("File Ownership detected:")
    for owner, files in ownership.items():
        print(f"  {owner}: {', '.join(files)}")

    # Gather all files
    all_files = set()
    for files in ownership.values():
        all_files.update(files)

    graph = build_dependency_graph(all_files, project_root)

    conflicts = detect_conflicts(ownership, graph)

    if conflicts:
        print("\n[!] WARNING: Split-keel violations detected!")
        for c in conflicts:
            print(
                f"  Captain {c[0]} owns {c[1]} which appears to import {c[3]} owned by Captain {c[2]}."
            )
        print("\nRemedy: Re-assign files to eliminate cross-captain dependencies.")
        sys.exit(1)
    else:
        print("\n[+] Pre-flight scan clean: No obvious split-keel violations detected.")
        sys.exit(0)


if __name__ == "__main__":
    main()
