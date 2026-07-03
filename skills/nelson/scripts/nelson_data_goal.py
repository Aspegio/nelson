"""Goal alignment for Nelson missions.

Composes a Claude Code ``/goal`` condition from a mission's sailing orders so
the harness's session-scoped Stop hook enforces mission completion. The
``/goal`` evaluator judges the condition against the *conversation transcript*
only — it does not read files or run commands — so the composed condition is
phrased in terms of facts the admiral must surface into the conversation
(metric confirmed, captain's log written and its path stated, stand-down
recorded), which is exactly what Nelson's Stand Down step already does.

See ``references/goal-alignment.md`` for the doctrine.

No external dependencies — stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from nelson_data_utils import (
    _append_event,
    _die,
    _err,
    _now_iso,
    _read_json,
    _require_mission_dir,
    _write_json,
)

# Claude Code caps a /goal condition at 4,000 characters.
GOAL_CONDITION_MAX_CHARS = 4000

_WHITESPACE = re.compile(r"\s+")


def _clean(text: str) -> str:
    """Collapse whitespace so free-text fields stay on one line in the condition."""
    return _WHITESPACE.sub(" ", str(text or "")).strip()


def compose_goal_condition(
    sailing_orders: dict[str, Any],
    max_turns: int | None = None,
) -> str:
    """Compose a transcript-verifiable ``/goal`` condition from sailing orders.

    Pure function: never mutates *sailing_orders*. The returned string is the
    condition text (without the leading ``/goal``). It is deliberately worded
    against facts observable in the conversation, because the goal evaluator
    only sees the transcript.
    """
    outcome = _clean(sailing_orders.get("outcome")) or "the stated mission outcome"
    metric = _clean(sailing_orders.get("success_metric"))
    stop_criteria = [_clean(c) for c in sailing_orders.get("stop_criteria", []) if _clean(c)]

    conditions: list[str] = []
    if metric:
        conditions.append(f"the success metric is confirmed met in this conversation ({metric})")
    if stop_criteria:
        conditions.append("every stop criterion is satisfied (" + "; ".join(stop_criteria) + ")")
    conditions.append(
        "the captain's log has been written to disk with its path stated here, and Nelson stand-down has been recorded"
    )

    parts = [
        f"The Nelson mission is complete: {outcome}.",
        "Treat this as met only when the conversation shows all of: " + "; ".join(conditions) + ".",
        (
            "It is also met if the mission has been formally stood down via scuttle-and-reform "
            "with the blocking reason stated in this conversation."
        ),
    ]
    if max_turns is not None and max_turns > 0:
        parts.append(f"Or stop after {max_turns} turns.")

    return " ".join(parts)


def _record_goal_condition(mission_dir: Path, condition: str) -> None:
    """Persist *condition* into sailing-orders.json and log a ``goal_set`` event.

    Immutable update: reads the existing orders, writes a new dict with the
    added field, and never edits the loaded object in place.
    """
    so_path = mission_dir / "sailing-orders.json"
    if not so_path.exists():
        _err("Warning: sailing-orders.json not found — goal condition not recorded.")
        return
    sailing_orders = _read_json(so_path)
    new_sailing_orders = {**sailing_orders, "goal_condition": condition}
    _write_json(so_path, new_sailing_orders)
    _append_event(
        mission_dir,
        {
            "type": "goal_set",
            "checkpoint": 0,
            "timestamp": _now_iso(),
            "data": {"goal_condition": condition},
        },
    )


def cmd_goal_condition(args: argparse.Namespace) -> None:
    """Compose (and optionally record) a ``/goal`` condition from sailing orders."""
    mission_dir = _require_mission_dir(args)

    so_path = mission_dir / "sailing-orders.json"
    if not so_path.exists():
        _die("Error: sailing-orders.json does not exist. Run 'init' before composing a goal.")

    sailing_orders = _read_json(so_path)
    condition = compose_goal_condition(sailing_orders, max_turns=getattr(args, "max_turns", None))

    char_count = len(condition)
    within_limit = char_count <= GOAL_CONDITION_MAX_CHARS
    if not within_limit:
        _err(
            f"Warning: composed condition is {char_count} chars, over the {GOAL_CONDITION_MAX_CHARS}-char "
            "/goal limit. Shorten the outcome, metric, or stop criteria."
        )

    if getattr(args, "record", False):
        _record_goal_condition(mission_dir, condition)

    if getattr(args, "json_output", False):
        print(
            json.dumps(
                {
                    "condition": condition,
                    "command": f"/goal {condition}",
                    "char_count": char_count,
                    "within_limit": within_limit,
                    "recorded": bool(getattr(args, "record", False)),
                },
                indent=2,
            )
        )
    else:
        print(f"/goal {condition}")
