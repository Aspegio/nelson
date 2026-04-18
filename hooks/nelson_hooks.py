#!/usr/bin/env python3
"""
Nelson Hook Enforcement Script.

Enforces Nelson's structural guarantees at the tool level via Claude Code
hooks. Each subcommand maps to a hook event type:

  preflight      — PreToolUse on Agent: station tier gate, file ownership
                   conflicts, mode-tool consistency
  mode-check     — PreToolUse on TaskCreate: reject in non-agent-team modes
  brief-validate — PostToolUse on Write/Edit: turnover brief quality gate
  task-complete  — TaskCompleted: validation evidence and station controls
  idle-ship      — TeammateIdle: paid-off standing order advisory

Exit codes:
  0 — allow (action proceeds)
  2 — reject (action blocked, stderr feedback sent to agent)

All hooks degrade gracefully: if no active Nelson mission is found, they
exit 0 and do not interfere with non-Nelson workflows.

Requires only Python stdlib (no pip dependencies).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, NoReturn


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------


def _read_stdin() -> dict[str, Any]:
    """Parse JSON from stdin (Claude Code hook payload)."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return {}


def _find_mission_dir(cwd: Path) -> Path | None:
    """Find the active Nelson mission directory.

    Scans for ``.nelson/.active-*`` marker files in the working directory.
    Returns the mission directory path if exactly one active session exists,
    or None if no active mission is found.
    """
    nelson_dir = cwd / ".nelson"
    if not nelson_dir.is_dir():
        return None

    active_files = sorted(nelson_dir.glob(".active-*"))
    if not active_files:
        return None

    try:
        mission_path = active_files[0].read_text(encoding="utf-8").strip()
        mission_dir = Path(mission_path)
        if mission_dir.is_dir():
            return mission_dir
    except OSError:
        pass

    return None


def _read_json(path: Path) -> dict[str, Any]:
    """Read and parse a JSON file. Returns empty dict on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _reject(message: str) -> NoReturn:
    """Print rejection feedback to stderr and exit with code 2."""
    print(message, file=sys.stderr)
    sys.exit(2)


def _allow() -> NoReturn:
    """Exit successfully — action proceeds."""
    sys.exit(0)


def _get_mode(battle_plan: dict[str, Any]) -> str:
    """Extract execution mode from battle plan."""
    return battle_plan.get("squadron", {}).get("mode", "subagents")


def _get_tasks(battle_plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract tasks list from battle plan."""
    return battle_plan.get("tasks", [])


def _load_mission_context(
    payload: dict[str, Any],
) -> tuple[Path, dict[str, Any]] | None:
    """Load battle plan from the active mission. Returns None if unavailable."""
    cwd = Path(payload.get("cwd", "."))
    mission_dir = _find_mission_dir(cwd)
    if mission_dir is None:
        return None
    bp = _read_json(mission_dir / "battle-plan.json")
    if not bp:
        return None
    return mission_dir, bp


# ---------------------------------------------------------------------------
# Team config helpers
# ---------------------------------------------------------------------------


def _read_team_config(teams_dir: Path, team_name: str) -> dict[str, Any]:
    """Read a team's config.json. Returns empty dict on failure or invalid name."""
    if not team_name or "/" in team_name or team_name.startswith("."):
        return {}
    return _read_json(teams_dir / team_name / "config.json")


def _check_team_enrollment(
    team_config: dict[str, Any], tool_input: dict[str, Any],
) -> str | None:
    """Return rejection message if the agent's name conflicts with an existing member."""
    team_name = tool_input.get("team_name")
    member_name = tool_input.get("name")
    if not team_name or not member_name:
        return None
    members = team_config.get("members", [])
    existing_names = {m.get("name") for m in members if isinstance(m, dict)}
    if member_name in existing_names:
        return (
            f"Team enrollment violation: agent name '{member_name}' is "
            f"already a member of team '{team_name}'. Spawning would "
            f"create a duplicate. Choose a different ship name from "
            f"references/crew-roles.md."
        )
    return None


# ---------------------------------------------------------------------------
# Preflight helpers
# ---------------------------------------------------------------------------


def _check_station_tiers(tasks: list[dict[str, Any]]) -> str | None:
    """Return rejection message if any task lacks a station tier."""
    unclassified = [t for t in tasks if t.get("station_tier") is None]
    if not unclassified:
        return None
    names = ", ".join(
        f"'{t.get('name', t.get('id', 'unknown'))}'" for t in unclassified
    )
    return (
        f"Standing order violation (unclassified-engagement): "
        f"Tasks without station tier: {names}. "
        f"Classify all tasks via references/action-stations.md before "
        f"spawning agents."
    )


def _check_file_ownership(tasks: list[dict[str, Any]]) -> str | None:
    """Return rejection message if any file is owned by multiple captains."""
    file_owners: dict[str, list[str]] = {}
    for task in tasks:
        owner = task.get("owner", "unknown")
        for filepath in task.get("file_ownership", []):
            file_owners.setdefault(filepath, []).append(owner)

    conflicts = {
        fp: owners for fp, owners in file_owners.items() if len(set(owners)) > 1
    }
    if not conflicts:
        return None
    details = "; ".join(
        f"'{fp}' owned by {', '.join(sorted(set(owners)))}"
        for fp, owners in conflicts.items()
    )
    return (
        f"Standing order violation (split-keel): "
        f"File ownership conflicts detected: {details}. "
        f"Assign exclusive file ownership or use worktree isolation."
    )


def _check_mode_tool_consistency(
    mode: str, tool_input: dict[str, Any],
) -> str | None:
    """Return rejection message if tool input mismatches execution mode."""
    has_subagent_type = "subagent_type" in tool_input
    has_team_name = "team_name" in tool_input

    if mode == "agent-team" and has_subagent_type and not has_team_name:
        # Marines legitimately use subagent_type in agent-team mode
        prompt_text = str(tool_input.get("prompt", "")).lower()
        name_text = str(tool_input.get("name", "")).lower()
        desc_text = str(tool_input.get("description", "")).lower()
        is_marine = any("marine" in t for t in (prompt_text, name_text, desc_text))
        if not is_marine:
            return (
                "Standing order violation (wrong-ensign): "
                "In agent-team mode, spawn captains with team_name + name, "
                "not subagent_type. Marines may still use subagent_type. "
                "See references/tool-mapping.md."
            )

    if mode == "subagents" and has_team_name:
        return (
            "Standing order violation (wrong-ensign): "
            "In subagents mode, do not use team_name. "
            "Spawn captains with subagent_type instead. "
            "See references/tool-mapping.md."
        )

    return None


# ---------------------------------------------------------------------------
# Subcommand: preflight (PreToolUse on Agent)
# ---------------------------------------------------------------------------


def cmd_preflight(args: argparse.Namespace) -> None:
    """Pre-flight standing order gate check before agent spawn."""
    payload = _read_stdin()
    ctx = _load_mission_context(payload)
    if ctx is None:
        _allow()

    _, battle_plan = ctx
    tasks = _get_tasks(battle_plan)
    tool_input = payload.get("tool_input", {})

    teams_dir = Path.home() / ".claude" / "teams"
    team_name = tool_input.get("team_name", "")
    team_config = _read_team_config(teams_dir, team_name)

    for check in (
        lambda: _check_station_tiers(tasks),
        lambda: _check_file_ownership(tasks),
        lambda: _check_mode_tool_consistency(_get_mode(battle_plan), tool_input),
        lambda: _check_team_enrollment(team_config, tool_input),
    ):
        msg = check()
        if msg:
            _reject(msg)

    _allow()


# ---------------------------------------------------------------------------
# Subcommand: mode-check (PreToolUse on TaskCreate)
# ---------------------------------------------------------------------------


def cmd_mode_check(args: argparse.Namespace) -> None:
    """Reject TaskCreate in non-agent-team execution modes."""
    payload = _read_stdin()
    ctx = _load_mission_context(payload)
    if ctx is None:
        _allow()

    _, battle_plan = ctx
    mode = _get_mode(battle_plan)
    if mode in ("subagents", "single-session"):
        _reject(
            f"Standing order violation (wrong-ensign): "
            f"TaskCreate is not available in {mode} mode. "
            f"Track work in the admiral's conversation context. "
            f"See references/tool-mapping.md."
        )

    _allow()


# ---------------------------------------------------------------------------
# Subcommand: brief-validate (PostToolUse on Write/Edit)
# ---------------------------------------------------------------------------

# Required sections for standard turnover briefs
STANDARD_BRIEF_SECTIONS: tuple[str, ...] = (
    "Ship:",
    "Role:",
    "Timestamp:",
    "Reason for relief:",
    "Mission context:",
    "Task assignment:",
    "Progress log:",
    "Running plot",
    "Files touched:",
    "Key decisions made:",
    "Hazards and blockers:",
    "Recommended course of action:",
    "Relief chain:",
)

# Required sections for flagship turnover briefs
FLAGSHIP_BRIEF_SECTIONS: tuple[str, ...] = (
    "Ship:",
    "Role:",
    "Timestamp:",
    "Reason for relief:",
    "Sailing orders:",
    "Battle plan status:",
    "Squadron state:",
    "Key decisions made:",
    "Active blockers and risks:",
    "Pending escalations:",
    "Quarterdeck rhythm:",
    "Relief chain:",
    "Recommended course of action:",
)


def _check_section_present(content: str, section: str) -> bool:
    """Check if a section header is present in the brief content."""
    return bool(re.search(re.escape(section), content, re.IGNORECASE))


def _check_running_plot_nonempty(content: str) -> bool:
    """Check that the Running plot section has at least one bullet point."""
    match = re.search(
        r"Running plot.*?\n(.*?)(?=\n[A-Z][\w ]*:|\n==|\Z)",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return False
    return bool(re.search(r"^\s*-\s+\S", match.group(1), re.MULTILINE))


def cmd_brief_validate(args: argparse.Namespace) -> None:
    """Validate turnover brief quality after file write."""
    payload = _read_stdin()
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Fast path: skip files not in turnover-briefs/
    if "turnover-briefs/" not in file_path and "turnover-briefs\\" not in file_path:
        _allow()

    brief_path = Path(file_path)
    if not brief_path.is_file():
        _allow()

    try:
        content = brief_path.read_text(encoding="utf-8")
    except OSError:
        _allow()

    if not content.strip():
        _reject(
            "Turnover brief quality gate failed: File is empty. "
            "See references/admiralty-templates/turnover-brief.md for the template."
        )

    is_flagship = "== FLAGSHIP TURNOVER BRIEF ==" in content
    sections = FLAGSHIP_BRIEF_SECTIONS if is_flagship else STANDARD_BRIEF_SECTIONS
    brief_type = "Flagship turnover" if is_flagship else "Turnover"

    missing = [s for s in sections if not _check_section_present(content, s)]
    if missing:
        missing_list = ", ".join(f"'{s}'" for s in missing)
        _reject(
            f"{brief_type} brief quality gate failed. "
            f"Missing required sections: {missing_list}. "
            f"See references/admiralty-templates/turnover-brief.md for the template."
        )

    if not is_flagship and not _check_running_plot_nonempty(content):
        _reject(
            "Turnover brief quality gate failed. "
            "Running plot section is empty — the replacement ship needs "
            "to know what was in progress when relief occurred."
        )

    _allow()


# ---------------------------------------------------------------------------
# Subcommand: task-complete (TaskCompleted)
# ---------------------------------------------------------------------------

# Evidence keywords by category
VALIDATION_EVIDENCE_PATTERNS: tuple[str, ...] = (
    r"\btest(s|ed|ing)?\b",
    r"\bpass(es|ed|ing)?\b",
    r"\bverif(y|ied|ication)\b",
    r"\bvalidat(e|ed|ion)\b",
    r"\bconfirm(s|ed)?\b",
    r"\bcheck(s|ed)?\b",
    r"\boutput\b",
    r"\bresult(s)?\b",
)

ROLLBACK_PATTERNS: tuple[str, ...] = (
    r"\brollback\b",
    r"\brevert\b",
    r"\bundo\b",
    r"\brestore\b",
    r"\broll back\b",
)

FAILURE_CASE_PATTERNS: tuple[str, ...] = (
    r"\bfailure\b",
    r"\bfail(s|ed)?\b",
    r"\berror case\b",
    r"\bnegative test\b",
    r"\bedge case\b",
    r"\bboundary\b",
    r"\binvalid\b",
)

RED_CELL_PATTERNS: tuple[str, ...] = (
    r"\bred.?cell\b",
    r"\badversarial review\b",
    r"\bnavigator review\b",
    r"\bfailure.mode checklist\b",
)

HUMAN_CONFIRMATION_PATTERNS: tuple[str, ...] = (
    r"\bhuman confirm(ed|ation)?\b",
    r"\badmiralty confirm(ed|ation)?\b",
    r"\bexplicit.*confirm(ed|ation)\b",
    r"\bcontingency plan\b",
    r"\btwo.step verif",
)


def _has_evidence(text: str, patterns: tuple[str, ...]) -> bool:
    """Check if text contains any of the given evidence patterns."""
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def _read_transcript_tail(path: str, tail_bytes: int = 51200) -> str:
    """Read the tail of a transcript file without loading it all into memory."""
    tp = Path(path)
    if not tp.is_file():
        return ""
    try:
        size = tp.stat().st_size
        with tp.open(encoding="utf-8") as f:
            if size > tail_bytes:
                f.seek(size - tail_bytes)
                f.readline()  # skip partial line
            return f.read()
    except OSError:
        return ""


def _gather_evidence(payload: dict[str, Any]) -> str:
    """Collect evidence text from payload fields and transcript."""
    parts = [
        str(payload.get("task_subject", "")),
        str(payload.get("task_description", "")),
    ]
    transcript = payload.get("transcript_path")
    if transcript:
        parts.append(_read_transcript_tail(transcript))
    return " ".join(parts)


def _check_tier_controls(
    tier: int, task_name: str, evidence: str,
) -> str | None:
    """Return rejection message if station tier controls are unsatisfied."""
    if not _has_evidence(evidence, VALIDATION_EVIDENCE_PATTERNS):
        return (
            f"Quality gate failed: No validation evidence detected for "
            f"task '{task_name}'. Include test results, validation output, "
            f"or verification evidence before marking complete."
        )

    if tier >= 1 and not _has_evidence(evidence, ROLLBACK_PATTERNS):
        return (
            f"Quality gate failed: Station {tier} task '{task_name}' "
            f"requires an explicit rollback note. Describe how to revert "
            f"this change before marking complete."
        )

    if tier >= 1 and not _has_evidence(evidence, FAILURE_CASE_PATTERNS):
        return (
            f"Quality gate failed: Station {tier} task '{task_name}' "
            f"requires failure case or negative test evidence. Document "
            f"what could go wrong and how it was tested."
        )

    if tier >= 2 and not _has_evidence(evidence, RED_CELL_PATTERNS):
        return (
            f"Quality gate failed: Station {tier} task '{task_name}' "
            f"requires red-cell or adversarial review evidence. Ensure a "
            f"red-cell navigator has reviewed this work."
        )

    # Station 3 (Trafalgar): explicit human confirmation + contingency plan
    if tier >= 3 and not _has_evidence(evidence, HUMAN_CONFIRMATION_PATTERNS):
        return (
            f"Quality gate failed: Station {tier} task '{task_name}' "
            f"requires explicit human confirmation and a documented "
            f"contingency plan. See references/action-stations.md."
        )

    return None


def cmd_task_complete(args: argparse.Namespace) -> None:
    """Verify task completion quality against station tier controls."""
    payload = _read_stdin()
    ctx = _load_mission_context(payload)
    if ctx is None:
        _allow()

    _, battle_plan = ctx
    task_id = payload.get("task_id", "")
    task_subject = payload.get("task_subject", "")
    tasks = _get_tasks(battle_plan)

    matched = next(
        (t for t in tasks
         if t.get("id") == task_id or t.get("name") == task_subject),
        None,
    )
    if matched is None:
        _allow()

    tier = matched.get("station_tier", 0)
    name = matched.get("name", task_subject or task_id)
    evidence = _gather_evidence(payload)

    msg = _check_tier_controls(tier, name, evidence)
    if msg:
        _reject(msg)
    _allow()


# ---------------------------------------------------------------------------
# Idle ship helpers
# ---------------------------------------------------------------------------


def _find_ship(
    squadron: list[dict[str, Any]], teammate_name: str,
) -> dict[str, Any] | None:
    """Find a ship in the squadron by exact or partial name match."""
    name_lower = teammate_name.lower()
    # Exact match first
    for ship in squadron:
        if ship.get("ship_name", "").lower() == name_lower:
            return ship
    # Partial match fallback
    for ship in squadron:
        if name_lower in ship.get("ship_name", "").lower():
            return ship
    return None


def _has_pending_dependents(
    task_id: str, tasks: list[dict[str, Any]],
) -> bool:
    """Check whether a task has incomplete dependent tasks."""
    for task in tasks:
        if task.get("id") == task_id:
            for dep_id in task.get("dependents", []):
                dep = next((t for t in tasks if t.get("id") == dep_id), None)
                if dep and dep.get("status") != "completed":
                    return True
    return False


# ---------------------------------------------------------------------------
# Subcommand: idle-ship (TeammateIdle — advisory only)
# ---------------------------------------------------------------------------


def cmd_idle_ship(args: argparse.Namespace) -> None:
    """Check idle ship status and advise on paid-off standing order."""
    payload = _read_stdin()
    cwd = Path(payload.get("cwd", "."))
    mission_dir = _find_mission_dir(cwd)
    if mission_dir is None:
        _allow()

    teammate_name = payload.get("teammate_name", "")
    fleet_status = _read_json(mission_dir / "fleet-status.json")
    battle_plan = _read_json(mission_dir / "battle-plan.json")
    if not fleet_status or not battle_plan:
        _allow()

    ship = _find_ship(fleet_status.get("squadron", []), teammate_name)
    if ship is None:
        print(
            f"Ship '{teammate_name}' idle — not found in fleet status. "
            f"Check hull integrity and task status.",
            file=sys.stderr,
        )
        _check_idle_circuit_breaker(mission_dir, teammate_name)
        _allow()

    ship_name = ship.get("ship_name", teammate_name)
    task_status = ship.get("task_status", "unknown")

    if task_status == "completed":
        task_id = ship.get("task_id", "")
        if not _has_pending_dependents(task_id, _get_tasks(battle_plan)):
            print(
                f"Standing order (paid-off): {ship_name} task is complete "
                f"with no pending dependents. Send shutdown_request. "
                f"See references/standing-orders/paid-off.md.",
                file=sys.stderr,
            )
            # Completed ships don't need an idle-timeout advisory — clear tracker.
            _clear_idle_tracker(mission_dir, ship_name)
        else:
            print(
                f"{ship_name} task is complete but has pending dependent "
                f"tasks. Hold position until dependents are evaluated.",
                file=sys.stderr,
            )
            _check_idle_circuit_breaker(mission_dir, ship_name)
    else:
        hull = ship.get("hull_integrity_status", "unknown")
        print(
            f"{ship_name} idle but task status is '{task_status}' "
            f"(hull: {hull}). Check hull integrity and task progress.",
            file=sys.stderr,
        )
        _check_idle_circuit_breaker(mission_dir, ship_name)

    _allow()


def _check_idle_circuit_breaker(mission_dir: Path, ship_name: str) -> None:
    """Run the idle-timeout circuit breaker and surface an advisory if tripped.

    Imports are local so the hook stays fast and has no hard dependency on
    the scripts directory being importable (the hook degrades gracefully).
    """
    if not ship_name:
        return
    try:
        sys.path.insert(
            0, str(Path(__file__).resolve().parent.parent / "skills" / "nelson" / "scripts")
        )
        from nelson_circuit_breakers import (  # type: ignore[import-not-found]
            evaluate_idle_timeout,
            load_config,
        )
    except ImportError:
        return

    sailing_orders = _read_json(mission_dir / "sailing-orders.json") or None
    config = load_config(sailing_orders)
    if not config.get("enabled", True):
        return

    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    trip = evaluate_idle_timeout(mission_dir, ship_name, now_iso, config)
    if trip is None:
        return

    print(
        f"[CIRCUIT BREAKER: {trip.type}] {trip.message}",
        file=sys.stderr,
    )


def _clear_idle_tracker(mission_dir: Path, ship_name: str) -> None:
    """Best-effort: clear the idle tracker entry for a completed ship."""
    try:
        sys.path.insert(
            0, str(Path(__file__).resolve().parent.parent / "skills" / "nelson" / "scripts")
        )
        from nelson_circuit_breakers import clear_idle_tracker  # type: ignore[import-not-found]
    except ImportError:
        return
    clear_idle_tracker(mission_dir, ship_name)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Nelson hook enforcement script.",
        prog="nelson-hooks",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "preflight",
        help="Pre-flight standing order gate (PreToolUse on Agent)",
    )
    subparsers.add_parser(
        "mode-check",
        help="Mode-tool consistency check (PreToolUse on TaskCreate)",
    )
    subparsers.add_parser(
        "brief-validate",
        help="Turnover brief quality gate (PostToolUse on Write/Edit)",
    )
    subparsers.add_parser(
        "task-complete",
        help="Task completion quality gate (TaskCompleted)",
    )
    subparsers.add_parser(
        "idle-ship",
        help="Idle ship advisory (TeammateIdle)",
    )

    args = parser.parse_args()

    dispatch = {
        "preflight": cmd_preflight,
        "mode-check": cmd_mode_check,
        "brief-validate": cmd_brief_validate,
        "task-complete": cmd_task_complete,
        "idle-ship": cmd_idle_ship,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.error(f"Unknown command: {args.command}")
    handler(args)


if __name__ == "__main__":
    main()
