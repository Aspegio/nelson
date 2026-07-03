#!/usr/bin/env python3
"""Structured data capture for Nelson missions.

Single script with subcommands for every data operation during a Nelson
mission lifecycle.  The admiral calls these via Bash; the script handles
JSON schema compliance, validation, timestamps, and file I/O.

Usage examples:

    python3 nelson-data.py init --outcome "Refactor auth" --metric "Tests pass" --deadline this_session
    python3 nelson-data.py squadron --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 ...
    python3 nelson-data.py task --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 ...
    python3 nelson-data.py plan-approved --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4
    python3 nelson-data.py event --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 --type task_completed ...
    python3 nelson-data.py checkpoint --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 ...
    python3 nelson-data.py stand-down --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4 ...
    python3 nelson-data.py status --mission-dir .nelson/missions/2026-03-27_120000_a1b2c3d4
    python3 nelson-data.py index
    python3 nelson-data.py index --missions-dir .nelson/missions --rebuild
    python3 nelson-data.py history
    python3 nelson-data.py history --json --last 5

No external dependencies — stdlib only.
"""

from __future__ import annotations

import argparse
import sys

from nelson_data_calibration import cmd_trust_report
from nelson_data_fleet import VALID_METRICS, cmd_analytics, cmd_brief, cmd_history, cmd_index
from nelson_data_goal import cmd_goal_condition
from nelson_data_lifecycle import (
    cmd_admiralty_decision,
    cmd_checkpoint,
    cmd_event,
    cmd_form,
    cmd_handoff,
    cmd_headless,
    cmd_init,
    cmd_plan_approved,
    cmd_record_estimate_outcome,
    cmd_recover,
    cmd_skip_estimate,
    cmd_squadron,
    cmd_stand_down,
    cmd_status,
    cmd_task,
)
from nelson_data_patterns import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MIN_MISSIONS,
    cmd_detect_patterns,
    cmd_dismiss_candidate,
    cmd_promote_candidate,
)
from nelson_data_utils import (
    VALID_ADMIRALTY_OUTCOMES,
    VALID_ESTIMATE_OUTCOME_METHODS,
    VALID_ESTIMATE_OUTCOME_STATUSES,
    _die,
)

# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:  # noqa: PLR0915 -- argparse subcommand registration is inherently long; refactor tracked in nelson-e6j
    """Build the top-level argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="nelson-data",
        description="Structured data capture for Nelson missions.",
    )
    subs = parser.add_subparsers(dest="command", help="Subcommand")

    # --- init ---
    p_init = subs.add_parser("init", help="Create mission directory and sailing orders")
    p_init.add_argument("--outcome", required=True, help="Mission outcome statement")
    p_init.add_argument("--metric", required=True, help="Success metric")
    p_init.add_argument("--deadline", required=True, help="Deadline (e.g. this_session)")
    p_init.add_argument("--token-budget", type=int, default=None, help="Token budget")
    p_init.add_argument("--time-limit", type=int, default=None, help="Time limit in minutes")
    p_init.add_argument("--constraints", action="append", help="Constraint (repeatable)")
    p_init.add_argument("--out-of-scope", action="append", help="Out of scope item (repeatable)")
    p_init.add_argument("--stop-criteria", action="append", help="Stop criterion (repeatable)")
    p_init.add_argument("--handoff-artifacts", action="append", help="Handoff artifact (repeatable)")
    p_init.add_argument(
        "--session-id",
        default=None,
        help=(
            "Optional 8-char lowercase hex session id. Auto-generated if omitted. "
            "Embedded in the mission dir name and used for the "
            ".nelson/.active-<id> marker file."
        ),
    )

    # --- squadron ---
    p_sq = subs.add_parser("squadron", help="Record squadron formation")
    p_sq.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_sq.add_argument("--admiral", required=True, help="Admiral ship name")
    p_sq.add_argument("--admiral-model", required=True, help="Admiral model")
    p_sq.add_argument(
        "--captain",
        action="append",
        help="Captain spec: name:class:model:task_id (repeatable)",
    )
    p_sq.add_argument("--red-cell", default=None, help="Red cell ship name")
    p_sq.add_argument("--red-cell-model", default=None, help="Red cell model")
    p_sq.add_argument(
        "--mode",
        default="subagents",
        help="Execution mode: single-session, subagents, agent-team, workflow, hybrid-workflow",
    )

    # --- task ---
    p_task = subs.add_parser("task", help="Add task to battle plan")
    p_task.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_task.add_argument("--id", required=True, type=int, help="Task ID")
    p_task.add_argument("--name", required=True, help="Task name")
    p_task.add_argument("--owner", required=True, help="Owning ship name")
    p_task.add_argument("--deliverable", required=True, help="Task deliverable")
    p_task.add_argument("--deps", default="", help="Comma-separated dependency IDs")
    p_task.add_argument(
        "--station-tier",
        required=True,
        type=int,
        choices=[0, 1, 2, 3],
        help="Station tier (0-3)",
    )
    p_task.add_argument("--files", default="", help="Comma-separated file glob patterns")
    p_task.add_argument(
        "--modification-targets",
        default="",
        help="Comma-separated functions, env vars, or config being extended",
    )
    p_task.add_argument("--validation", default=None, help="Validation criteria")
    p_task.add_argument("--rollback-note", action="store_true", help="Rollback note required")
    p_task.add_argument("--admiralty-action", action="store_true", help="Admiralty action required")
    p_task.add_argument(
        "--task-type",
        default=None,
        help=(
            "Optional free-form task type (e.g. 'auth_refactor') used by the override-learning trust calibration store"
        ),
    )

    # --- plan-approved ---
    p_pa = subs.add_parser("plan-approved", help="Finalize battle plan")
    p_pa.add_argument("--mission-dir", required=True, help="Mission directory path")

    # --- goal-condition ---
    p_goal = subs.add_parser(
        "goal-condition",
        help="Compose a Claude Code /goal condition from sailing orders",
    )
    p_goal.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_goal.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="Optional turn cap appended as 'or stop after N turns'",
    )
    p_goal.add_argument(
        "--record",
        action="store_true",
        help="Persist the condition into sailing-orders.json and log a goal_set event",
    )
    p_goal.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Emit a JSON object (condition, command, char_count, within_limit)",
    )

    # --- skip-estimate ---
    p_se = subs.add_parser("skip-estimate", help="Record that the ESTIMATE phase is being skipped")
    p_se.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_se.add_argument(
        "--reason",
        required=True,
        help="Rationale for skipping the estimate (e.g. 'trivial scope')",
    )

    # --- estimate-outcome ---
    p_eo = subs.add_parser(
        "estimate-outcome",
        help="Record a per-criterion verification outcome for The Estimate",
    )
    p_eo.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_eo.add_argument("--effect-id", required=True, help="Effect identifier from the Estimate")
    p_eo.add_argument(
        "--criterion-id",
        required=True,
        help="Criterion identifier within the effect",
    )
    p_eo.add_argument(
        "--status",
        required=True,
        choices=sorted(VALID_ESTIMATE_OUTCOME_STATUSES),
        help="Verification status",
    )
    p_eo.add_argument(
        "--method",
        required=True,
        choices=sorted(VALID_ESTIMATE_OUTCOME_METHODS),
        help="Verification method used",
    )
    p_eo.add_argument("--evidence", default="", help="Free-text evidence supporting the outcome")
    p_eo.add_argument(
        "--recorded-by",
        required=True,
        help="Ship or role that recorded the outcome",
    )

    # --- event ---
    p_ev = subs.add_parser("event", help="Log a mission event")
    p_ev.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_ev.add_argument("--type", required=True, help="Event type")
    p_ev.add_argument("--checkpoint", type=int, default=None, help="Checkpoint number")
    # Additional key-value pairs handled via parse_known_args

    # --- handoff ---
    p_ho = subs.add_parser("handoff", help="Write a typed handoff packet")
    p_ho.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_ho.add_argument("--ship-name", required=True, help="Outgoing ship name")
    p_ho.add_argument("--task-id", required=True, type=int, help="Task ID")
    p_ho.add_argument("--task-name", required=True, help="Task name")
    p_ho.add_argument(
        "--handoff-type",
        required=True,
        help="Handoff type: relief_on_station, session_resumption, mid_mission_resize",
    )
    p_ho.add_argument(
        "--completed-subtask",
        action="append",
        help="Completed subtask (repeatable)",
    )
    p_ho.add_argument(
        "--partial-output",
        action="append",
        help="Partial output: subtask:progress:notes (repeatable)",
    )
    p_ho.add_argument("--known-blocker", action="append", help="Known blocker (repeatable)")
    p_ho.add_argument("--file-ownership", action="append", help="Owned file path (repeatable)")
    p_ho.add_argument("--next-step", action="append", help="Next step (repeatable, at least one required)")
    p_ho.add_argument("--open-decision", action="append", help="Open decision (repeatable)")
    p_ho.add_argument("--hull-at-handoff", required=True, type=int, help="Hull integrity % at handoff")
    p_ho.add_argument("--tokens-consumed", required=True, type=int, help="Tokens consumed at handoff")
    p_ho.add_argument("--key-finding", action="append", help="Key finding (repeatable)")
    p_ho.add_argument(
        "--relief-entry",
        action="append",
        help="Relief chain entry: ship:reason:time (repeatable, max 3)",
    )
    p_ho.add_argument("--incoming-ship", default=None, help="Replacement ship name")

    # --- checkpoint ---
    p_cp = subs.add_parser("checkpoint", help="Record a quarterdeck checkpoint")
    p_cp.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_cp.add_argument("--pending", required=True, type=int, help="Pending task count")
    p_cp.add_argument("--in-progress", required=True, type=int, help="In-progress task count")
    p_cp.add_argument("--completed", required=True, type=int, help="Completed task count")
    p_cp.add_argument("--blocked", type=int, default=0, help="Blocked task count")
    p_cp.add_argument("--tokens-spent", required=True, type=int, help="Tokens spent so far")
    p_cp.add_argument("--tokens-remaining", required=True, type=int, help="Tokens remaining")
    p_cp.add_argument("--hull-green", required=True, type=int, help="Ships at green hull")
    p_cp.add_argument("--hull-amber", required=True, type=int, help="Ships at amber hull")
    p_cp.add_argument("--hull-red", required=True, type=int, help="Ships at red hull")
    p_cp.add_argument("--hull-critical", required=True, type=int, help="Ships at critical hull")
    p_cp.add_argument(
        "--decision",
        required=True,
        help="Admiral decision: continue, rescope, or stop",
    )
    p_cp.add_argument("--rationale", required=True, help="Decision rationale")

    # --- stand-down ---
    p_sd = subs.add_parser("stand-down", help="Record mission completion")
    p_sd.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_sd.add_argument("--outcome-achieved", action="store_true", help="Was the outcome achieved?")
    p_sd.add_argument("--actual-outcome", default="", help="Actual outcome description")
    p_sd.add_argument("--metric-result", default="", help="Success metric result")
    p_sd.add_argument("--adopt", action="append", default=None, help="Pattern to adopt (repeatable)")
    p_sd.add_argument("--avoid", action="append", default=None, help="Pattern to avoid (repeatable)")

    # --- form ---
    p_form = subs.add_parser("form", help="Composite formation: tasks + squadron + plan")
    p_form.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_form.add_argument("--plan", required=True, help="Path to plan JSON file")
    p_form.add_argument(
        "--mode",
        default="subagents",
        help="Execution mode: single-session, subagents, agent-team, workflow, hybrid-workflow",
    )

    # --- headless ---
    p_hl = subs.add_parser("headless", help="Headless mission: init + form in one step")
    p_hl.add_argument("--sailing-orders", required=True, help="Path to sailing orders JSON file")
    p_hl.add_argument("--battle-plan", required=True, help="Path to battle plan JSON file")
    p_hl.add_argument(
        "--mode",
        default="subagents",
        help="Execution mode: single-session, subagents, agent-team, workflow, hybrid-workflow",
    )
    p_hl.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip interactive approval gate",
    )

    # --- status ---
    p_st = subs.add_parser("status", help="Print current fleet status")
    p_st.add_argument("--mission-dir", default="", help="Mission directory path")

    # --- recover ---
    p_rec = subs.add_parser("recover", help="Auto-recover session state (read-only)")
    p_rec.add_argument("--mission-dir", default=None, help="Mission directory path")
    p_rec.add_argument("--missions-dir", default=None, help="Missions root directory")
    p_rec.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )

    # --- index ---
    p_idx = subs.add_parser("index", help="Build fleet intelligence index")
    p_idx.add_argument("--missions-dir", default=None, help="Missions directory path")
    # Alias: --mission-dir accepted for consistency with other subcommands
    p_idx.add_argument("--mission-dir", dest="missions_dir", help=argparse.SUPPRESS)
    p_idx.add_argument("--rebuild", action="store_true", help="Force full re-index")

    # --- history ---
    p_hist = subs.add_parser("history", help="Display fleet intelligence analytics")
    p_hist.add_argument("--missions-dir", default=None, help="Missions directory path")
    # Alias: --mission-dir accepted for consistency with other subcommands
    p_hist.add_argument("--mission-dir", dest="missions_dir", help=argparse.SUPPRESS)
    p_hist.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output as JSON",
    )
    p_hist.add_argument("--last", type=int, default=10, help="Recent missions to show")

    # --- brief ---
    p_brief = subs.add_parser("brief", help="Intelligence brief from past missions")
    p_brief.add_argument("--missions-dir", default=None, help="Missions directory path")
    p_brief.add_argument("--mission-dir", dest="missions_dir", help=argparse.SUPPRESS)
    p_brief.add_argument("--context", default="", help="Context for upcoming mission")
    p_brief.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output as JSON",
    )

    # --- analytics ---
    p_an = subs.add_parser("analytics", help="Cross-mission analytics")
    p_an.add_argument("--missions-dir", default=None, help="Missions directory path")
    p_an.add_argument("--mission-dir", dest="missions_dir", help=argparse.SUPPRESS)
    p_an.add_argument(
        "--metric",
        required=True,
        choices=sorted(VALID_METRICS),
        help="Metric to analyze",
    )
    p_an.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output as JSON",
    )
    p_an.add_argument("--last", type=int, default=0, help="Limit to last N missions (0=all)")

    # --- detect-patterns ---
    p_dp = subs.add_parser(
        "detect-patterns",
        help="Detect candidate standing orders from mission patterns",
    )
    p_dp.add_argument(
        "--missions-dir",
        default=None,
        help="Missions directory (memory dir derived as {missions_dir}/../memory)",
    )
    p_dp.add_argument(
        "--memory-dir",
        default=None,
        help="Memory directory (overrides --missions-dir derivation)",
    )
    p_dp.add_argument(
        "--standing-orders-dir",
        default=None,
        help="Standing orders directory (default: skill references dir)",
    )
    p_dp.add_argument(
        "--min-missions",
        type=int,
        default=DEFAULT_MIN_MISSIONS,
        help=f"Minimum missions before detection runs (default: {DEFAULT_MIN_MISSIONS})",
    )
    p_dp.add_argument(
        "--confidence-threshold",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
        help=(f"Drop candidates below this confidence (default: {DEFAULT_CONFIDENCE_THRESHOLD})"),
    )
    p_dp.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Emit a JSON summary to stdout instead of a free-text message",
    )

    # --- promote-candidate ---
    p_pc = subs.add_parser(
        "promote-candidate",
        help="Promote a candidate to a real standing order",
    )
    p_pc.add_argument(
        "--candidate-id",
        dest="candidate_id",
        required=True,
        help="Candidate ID (e.g. cand-abc123)",
    )
    p_pc.add_argument(
        "--missions-dir",
        default=None,
        help="Missions directory (memory dir derived as {missions_dir}/../memory)",
    )
    p_pc.add_argument(
        "--memory-dir",
        default=None,
        help="Memory directory (overrides --missions-dir derivation)",
    )

    # --- admiralty-decision ---
    p_ad = subs.add_parser(
        "admiralty-decision",
        help="Record an admiralty action decision (approved/modified/rejected)",
    )
    p_ad.add_argument("--mission-dir", required=True, help="Mission directory path")
    p_ad.add_argument("--task-id", required=True, type=int, help="Task ID the decision applies to")
    p_ad.add_argument(
        "--decision-type",
        required=True,
        choices=sorted(VALID_ADMIRALTY_OUTCOMES),
        help="Decision outcome: approved, modified, or rejected",
    )
    p_ad.add_argument(
        "--recorded-by",
        required=True,
        help="Ship that recorded the decision (e.g. 'Admiral' or captain ship name)",
    )
    p_ad.add_argument("--notes", default="", help="Optional free-text rationale for the decision")

    # --- trust-report ---
    p_tr = subs.add_parser(
        "trust-report",
        help="Print learned trust calibration buckets sorted by override rate",
    )
    p_tr.add_argument("--missions-dir", default=None, help="Missions directory path")
    p_tr.add_argument(
        "--min-decisions",
        type=int,
        default=3,
        help="Hide buckets with fewer than N decisions (default: 3)",
    )
    p_tr.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Emit JSON instead of a text table",
    )

    # --- dismiss-candidate ---
    p_dc = subs.add_parser(
        "dismiss-candidate",
        help="Dismiss a candidate (archived so it is not re-proposed)",
    )
    p_dc.add_argument(
        "--candidate-id",
        dest="candidate_id",
        required=True,
        help="Candidate ID (e.g. cand-abc123)",
    )
    p_dc.add_argument(
        "--reason",
        required=True,
        help="Why this candidate is being dismissed",
    )
    p_dc.add_argument(
        "--missions-dir",
        default=None,
        help="Missions directory (memory dir derived as {missions_dir}/../memory)",
    )
    p_dc.add_argument(
        "--memory-dir",
        default=None,
        help="Memory directory (overrides --missions-dir derivation)",
    )

    return parser


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse arguments and dispatch to the correct subcommand."""
    parser = build_parser()

    # Use parse_known_args so the 'event' subcommand can accept arbitrary
    # --key value pairs beyond the defined arguments.
    args, extra = parser.parse_known_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "init": lambda: cmd_init(args),
        "squadron": lambda: cmd_squadron(args),
        "task": lambda: cmd_task(args),
        "goal-condition": lambda: cmd_goal_condition(args),
        "plan-approved": lambda: cmd_plan_approved(args),
        "skip-estimate": lambda: cmd_skip_estimate(args),
        "estimate-outcome": lambda: cmd_record_estimate_outcome(args),
        "event": lambda: cmd_event(args, extra),
        "handoff": lambda: cmd_handoff(args),
        "checkpoint": lambda: cmd_checkpoint(args),
        "stand-down": lambda: cmd_stand_down(args),
        "form": lambda: cmd_form(args),
        "headless": lambda: cmd_headless(args),
        "status": lambda: cmd_status(args),
        "recover": lambda: cmd_recover(args),
        "index": lambda: cmd_index(args),
        "history": lambda: cmd_history(args),
        "brief": lambda: cmd_brief(args),
        "analytics": lambda: cmd_analytics(args),
        "detect-patterns": lambda: cmd_detect_patterns(args),
        "promote-candidate": lambda: cmd_promote_candidate(args),
        "dismiss-candidate": lambda: cmd_dismiss_candidate(args),
        "admiralty-decision": lambda: cmd_admiralty_decision(args),
        "trust-report": lambda: cmd_trust_report(args),
    }

    handler = dispatch.get(args.command)
    if handler is None:
        _die(f"Error: unknown command '{args.command}'")
    else:
        handler()


if __name__ == "__main__":
    main()
