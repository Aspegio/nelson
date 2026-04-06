#!/usr/bin/env python3
"""
Pre-flight Conflict Scan for Nelson Missions.

This script parses a Nelson battle plan (a Markdown or JSON file)
to extract file ownership for each task/captain, and builds a simple
dependency graph of the codebase to check if any two captains own files
that import each other. This flags "split-keel" violations before execution.

Known limitations of the regex-based import parser:
  - Python multi-line imports (from x import (\\n y\\n)) are only partially captured
  - Python conditional imports inside try/except blocks are captured but not
    distinguished from top-level imports
  - Python dynamic imports (importlib.import_module) are not detected
  - JS/TS dynamic imports (await import('module')) are not detected
  - JS/TS type-only imports (import type { Foo } from './bar') are not matched
  - JS/TS re-exports (export { default } from './module') are not matched
For production use, consider AST-based parsers or tools like madge/pydeps.
"""

import sys
import re
import json
import argparse
from pathlib import Path

# Common Python stdlib modules that should never be treated as local dependencies
PYTHON_STDLIB = frozenset(
    {
        "abc",
        "argparse",
        "ast",
        "asyncio",
        "base64",
        "bisect",
        "calendar",
        "collections",
        "configparser",
        "contextlib",
        "copy",
        "csv",
        "ctypes",
        "dataclasses",
        "datetime",
        "decimal",
        "difflib",
        "email",
        "enum",
        "errno",
        "fnmatch",
        "fractions",
        "functools",
        "gc",
        "getpass",
        "glob",
        "gzip",
        "hashlib",
        "heapq",
        "hmac",
        "html",
        "http",
        "importlib",
        "inspect",
        "io",
        "itertools",
        "json",
        "keyword",
        "logging",
        "math",
        "mimetypes",
        "multiprocessing",
        "operator",
        "os",
        "pathlib",
        "platform",
        "pprint",
        "queue",
        "re",
        "secrets",
        "select",
        "shelve",
        "shlex",
        "shutil",
        "signal",
        "socket",
        "sqlite3",
        "ssl",
        "statistics",
        "string",
        "struct",
        "subprocess",
        "sys",
        "tempfile",
        "textwrap",
        "threading",
        "time",
        "timeit",
        "traceback",
        "typing",
        "unittest",
        "urllib",
        "uuid",
        "warnings",
        "weakref",
        "xml",
        "zipfile",
        "zlib",
    }
)


def parse_battle_plan(path: Path) -> dict:
    """Parse battle-plan.md or battle-plan.json to extract file ownership per captain."""
    if not path.exists():
        raise FileNotFoundError(f"Battle plan not found at {path}")

    content = path.read_text(encoding="utf-8")
    ownership = {}  # Map of captain/ship -> set of files

    try:
        data = json.loads(content)
        for task in data.get("tasks", []):
            owner = task.get("owner")
            files = task.get("files", [])
            if owner and files:
                if owner not in ownership:
                    ownership[owner] = set()
                ownership[owner].update(files)
        if ownership:
            return ownership
    except json.JSONDecodeError:
        pass

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


def parse_imports(filepath: Path) -> set[str]:
    """Extract imports from a file using simple regex.

    Currently supports Python, JS/TS. See module docstring for known
    limitations of the regex-based approach.
    """
    imports: set[str] = set()
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
                # Skip empty strings (e.g. from relative imports like "from . import x")
                if module:
                    imports.add(module)

    elif filepath.suffix in (".js", ".ts", ".jsx", ".tsx"):
        # import ... from 'foo'
        # require('foo')
        for match in re.finditer(
            r'(?:import.*from\s+[\'"]([^\'"]+)[\'"]|require\([\'"]([^\'"]+)[\'"]\))',
            content,
            re.DOTALL,
        ):
            module = match.group(1) or match.group(2)
            if module:
                imports.add(module)

    return imports


def build_dependency_graph(files: set[str], project_root: Path) -> dict[str, set[str]]:
    """Build a graph mapping a file to its imports.

    Files that resolve outside the project root are skipped to prevent
    path-traversal attacks via crafted battle plans.
    """
    graph: dict[str, set[str]] = {}
    resolved_root = project_root.resolve()
    for f in files:
        filepath = (project_root / f).resolve()
        if not str(filepath).startswith(str(resolved_root)):
            # Path escapes project root — skip silently
            continue
        graph[f] = parse_imports(filepath)
    return graph


def detect_conflicts(
    ownership: dict[str, set[str]], graph: dict[str, set[str]]
) -> list[tuple[str, ...]]:
    """Detect if files owned by different captains import each other.

    Also flags duplicate file ownership (two captains claiming the same
    file), which is itself a split-keel violation.
    """
    conflicts: list[tuple[str, ...]] = []

    # Create a reverse map from file to owner, detecting duplicates
    file_to_owner: dict[str, str] = {}
    for owner, files in ownership.items():
        for f in files:
            if f in file_to_owner:
                conflicts.append((file_to_owner[f], f, owner, f))
            else:
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
            # Match the import against the other file's stem, relative path
            # without extension, or full relative path — exact matches only.
            other_stem = Path(other_file).stem
            other_no_ext = str(Path(other_file).with_suffix(""))
            other_full = str(Path(other_file))

            for imp in imports:
                # Skip Python stdlib modules — they cannot refer to project files
                if imp in PYTHON_STDLIB:
                    continue
                imp_path = imp.replace(".", "/")
                if (
                    imp == other_stem
                    or imp == other_no_ext
                    or imp == other_full
                    or imp_path == other_no_ext
                    or imp_path == other_full
                ):
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

    try:
        ownership = parse_battle_plan(plan_path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

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
        print("\n[!] WARNING: Possible split-keel violations detected!")
        for c in conflicts:
            if c[1] == c[3]:
                # Duplicate ownership — two captains claim the same file
                print(f"  {c[0]} and {c[2]} both claim ownership of {c[1]}.")
            else:
                print(
                    f"  Captain {c[0]} owns {c[1]} which appears to import {c[3]} owned by Captain {c[2]}."
                )
        print("\nRemedy: Re-assign files to eliminate cross-captain dependencies.")
        # Exit 0 — the scan is best-effort; use exit code for parse errors only
        sys.exit(0)
    else:
        print("\n[+] Pre-flight scan clean: No obvious split-keel violations detected.")
        sys.exit(0)


if __name__ == "__main__":
    main()
