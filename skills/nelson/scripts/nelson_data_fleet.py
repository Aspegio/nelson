"""Fleet intelligence and analytics commands for Nelson data capture.

Implements the fleet-wide analysis commands: index, history, brief,
and analytics subcommands.

No external dependencies — stdlib only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from nelson_data_memory import (
    _build_empty_index,
    _build_mission_record,
    _find_completed_missions,
    _sync_memory_from_index,
)
from nelson_data_utils import (
    JSON_INDENT,
    VALID_ESTIMATE_OUTCOME_METHODS,
    VALID_ESTIMATE_OUTCOME_STATUSES,
    _die,
    _err,
    _file_lock,
    _now_iso,
    _read_json_optional,
    _safe_mean,
    _write_json,
)


VALID_METRICS = frozenset(
    {"success-rate", "standing-orders", "efficiency", "estimate-outcomes", "all"}
)


# ---------------------------------------------------------------------------
# Subcommand: index
# ---------------------------------------------------------------------------


def _resolve_fleet_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """Return (missions_dir, index_path) from parsed arguments."""
    missions_dir = (
        Path(args.missions_dir) if args.missions_dir else Path(".nelson/missions")
    )
    index_path = missions_dir.parent / "fleet-intelligence.json"
    return missions_dir, index_path


def cmd_index(args: argparse.Namespace) -> None:
    """Build or update the fleet intelligence index."""
    missions_dir, index_path = _resolve_fleet_paths(args)
    rebuild = bool(getattr(args, "rebuild", False))

    lock_path = index_path.with_suffix(".lock")
    with _file_lock(lock_path):
        # Load existing index or start fresh
        if rebuild:
            index = _build_empty_index()
        else:
            index = _read_json_optional(index_path) or _build_empty_index()

        # Guard against future version bumps
        if not rebuild and index.get("version") is not None and index["version"] != 1:
            _err(f"Warning: index version {index['version']} != 1, rebuilding")
            index = _build_empty_index()
            rebuild = True

        indexed_ids = {m["mission_id"] for m in index.get("missions", [])}

        # Discover completed missions
        completed = _find_completed_missions(missions_dir)

        # Filter to new missions only (unless rebuilding)
        new_dirs = (
            completed
            if rebuild
            else [d for d in completed if d.name not in indexed_ids]
        )

        # Build records (skip missions with unreadable stand-down.json)
        new_records = [
            r for r in (_build_mission_record(d) for d in new_dirs) if r is not None
        ]

        # Merge and sort
        all_missions = (
            new_records if rebuild else list(index.get("missions", [])) + new_records
        )
        all_missions.sort(key=lambda m: m["mission_id"])

        updated_index = {
            "version": 1,
            "indexed_at": _now_iso(),
            "mission_count": len(all_missions),
            "missions": all_missions,
        }
        _write_json(index_path, updated_index)

    print(
        f"[nelson-data] Fleet intelligence indexed: "
        f"{len(all_missions)} missions ({len(new_records)} new)"
    )

    # Sync memory store from indexed missions (best-effort)
    try:
        _sync_memory_from_index(missions_dir)
    except Exception as exc:
        _err(f"Warning: failed to sync memory store: {exc}")


# ---------------------------------------------------------------------------
# Subcommand: history
# ---------------------------------------------------------------------------


def _collect_ship_class_counts(missions: list[dict]) -> dict[str, int]:
    """Count ship class usage across missions, descending by count."""
    counts: dict[str, int] = {}
    for m in missions:
        for cls in m.get("fleet", {}).get("ship_classes", []):
            counts[cls] = counts.get(cls, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def _collect_station_tier_totals(missions: list[dict]) -> dict[str, int]:
    """Accumulate task counts by station tier (0-3 only)."""
    totals: dict[str, int] = {"0": 0, "1": 0, "2": 0, "3": 0}
    for m in missions:
        tiers = m.get("tasks", {}).get("by_station_tier", {})
        for tier, count in tiers.items():
            if tier in totals:
                totals[tier] += count
    return totals


def _compute_analytics(missions: list[dict]) -> dict:
    """Compute aggregate analytics across all mission records."""
    if not missions:
        return {
            "mission_count": 0,
            "achieved": 0,
            "not_achieved": 0,
            "win_rate": None,
            "avg_duration": None,
            "min_duration": None,
            "max_duration": None,
            "avg_tokens_consumed": None,
            "avg_budget_pct": None,
            "avg_ships": None,
            "avg_tasks": None,
            "violations_per_mission": None,
            "blockers_per_mission": None,
            "ship_class_counts": {},
            "station_tier_totals": {"0": 0, "1": 0, "2": 0, "3": 0},
        }

    achieved = sum(1 for m in missions if m.get("outcome_achieved"))
    not_achieved = len(missions) - achieved
    win_rate = round(achieved / len(missions) * 100, 1)

    durations = [
        m["duration_minutes"] for m in missions if m.get("duration_minutes") is not None
    ]
    tokens = [
        v
        for m in missions
        if (v := m.get("budget", {}).get("tokens_consumed")) is not None
    ]
    budget_pcts = [
        v
        for m in missions
        if (v := m.get("budget", {}).get("pct_consumed")) is not None
    ]
    ships = [
        v for m in missions if (v := m.get("fleet", {}).get("ships_used")) is not None
    ]
    task_totals = [
        v for m in missions if (v := m.get("tasks", {}).get("total")) is not None
    ]
    violations = [
        v
        for m in missions
        if (v := m.get("quality", {}).get("standing_order_violations")) is not None
    ]
    blockers = [
        v
        for m in missions
        if (v := m.get("quality", {}).get("blockers_raised")) is not None
    ]

    ship_class_counts = _collect_ship_class_counts(missions)
    station_tier_totals = _collect_station_tier_totals(missions)

    avg_dur = _safe_mean(durations)
    avg_tok = _safe_mean(tokens)
    avg_bpct = _safe_mean(budget_pcts)
    avg_shp = _safe_mean(ships)
    avg_tsk = _safe_mean(task_totals)
    avg_viol = _safe_mean(violations)
    avg_blk = _safe_mean(blockers)

    return {
        "mission_count": len(missions),
        "achieved": achieved,
        "not_achieved": not_achieved,
        "win_rate": win_rate,
        "avg_duration": round(avg_dur, 1) if avg_dur is not None else None,
        "min_duration": min(durations) if durations else None,
        "max_duration": max(durations) if durations else None,
        "avg_tokens_consumed": int(round(avg_tok)) if avg_tok is not None else None,
        "avg_budget_pct": round(avg_bpct, 1) if avg_bpct is not None else None,
        "avg_ships": round(avg_shp, 1) if avg_shp is not None else None,
        "avg_tasks": round(avg_tsk, 1) if avg_tsk is not None else None,
        "violations_per_mission": round(avg_viol, 2) if avg_viol is not None else None,
        "blockers_per_mission": round(avg_blk, 2) if avg_blk is not None else None,
        "ship_class_counts": ship_class_counts,
        "station_tier_totals": station_tier_totals,
    }


def _format_history_text(
    analytics: dict,
    missions: list[dict],
    last_n: int,
) -> str:
    """Format fleet intelligence as human-readable text."""
    lines: list[str] = []
    mc = analytics["mission_count"]
    lines.append(f"Fleet Intelligence \u2014 {mc} missions indexed")
    lines.append("")

    if mc == 0:
        lines.append("  No missions to display.")
        return "\n".join(lines)

    # Outcome
    lines.append(
        f"  Outcome    {mc} missions: {analytics['achieved']} achieved, "
        f"{analytics['not_achieved']} not achieved ({analytics['win_rate']}% win rate)"
    )

    # Duration
    avg_d = analytics["avg_duration"]
    if avg_d is not None:
        lines.append(
            f"  Duration   avg {avg_d} min "
            f"(range: {analytics['min_duration']}\u2013{analytics['max_duration']})"
        )

    # Tokens
    avg_t = analytics["avg_tokens_consumed"]
    if avg_t is not None:
        token_str = f"{round(avg_t / 1000)}K" if avg_t >= 1000 else str(avg_t)
        lines.append(
            f"  Tokens     avg {token_str} consumed, "
            f"avg {analytics['avg_budget_pct']}% of budget"
        )

    # Squadron
    avg_s = analytics["avg_ships"]
    if avg_s is not None:
        lines.append(
            f"  Squadron   avg {avg_s} ships, "
            f"avg {analytics['avg_tasks']} tasks per mission"
        )

    # Quality
    vpm = analytics["violations_per_mission"]
    if vpm is not None:
        lines.append(
            f"  Quality    {vpm} violations/mission, "
            f"{analytics['blockers_per_mission']} blockers/mission"
        )

    lines.append("")

    # Ship classes
    scc = analytics["ship_class_counts"]
    if scc:
        parts = [f"{cls} ({count})" for cls, count in scc.items()]
        lines.append(f"  Ship classes   {', '.join(parts)}")

    # Station tiers
    stt = analytics["station_tier_totals"]
    tier_parts = [f"{k}: {v} tasks" for k, v in sorted(stt.items())]
    lines.append(f"  Station tiers  {', '.join(tier_parts)}")

    lines.append("")

    lines.extend(_format_recent_missions(missions, last_n))

    return "\n".join(lines)


def _format_recent_missions(missions: list[dict], last_n: int) -> list[str]:
    """Format the recent missions section (most recent first)."""
    recent = list(reversed(missions))[:last_n]
    if not recent:
        return []
    lines: list[str] = []
    lines.append("  Recent missions")
    lines.append("  " + "\u2500" * 62)
    for m in recent:
        mid = m["mission_id"]
        date_str = mid[:10] if len(mid) >= 10 else mid
        marker = "\u2713" if m.get("outcome_achieved") else "\u2717"
        outcome = m.get("actual_outcome") or m.get("planned_outcome", "")
        if len(outcome) > 50:
            outcome = outcome[:47] + "..."
        lines.append(f"  {date_str}  {marker}  {outcome}")
    return lines


def _format_history_json(analytics: dict, missions: list[dict]) -> str:
    """Format fleet intelligence as machine-readable JSON."""
    return json.dumps(
        {"analytics": analytics, "missions": missions},
        indent=JSON_INDENT,
    )


def cmd_history(args: argparse.Namespace) -> None:
    """Display fleet intelligence analytics from the index."""
    missions_dir, index_path = _resolve_fleet_paths(args)
    last_n = max(0, args.last)

    if not index_path.exists():
        _die("No fleet intelligence index found. Run 'nelson-data index' first.")

    index = _read_json_optional(index_path)
    if index is None:
        _die("Failed to read fleet intelligence index.")

    missions = index.get("missions", [])
    analytics = _compute_analytics(missions)

    if args.json_output:
        recent = list(reversed(missions))[:last_n]
        print(_format_history_json(analytics, recent))
    else:
        print(_format_history_text(analytics, missions, last_n))


# ---------------------------------------------------------------------------
# Subcommand: brief
# ---------------------------------------------------------------------------


def _keyword_overlap(context: str, text: str) -> int:
    """Count shared keywords between *context* and *text* (case-insensitive).

    Returns the number of overlapping words (length >= 3 to skip noise).
    """
    ctx_words = {w.lower() for w in context.split() if len(w) >= 3}
    txt_words = {w.lower() for w in text.split() if len(w) >= 3}
    return len(ctx_words & txt_words)


def _aggregate_patterns(
    patterns: list[dict],
) -> tuple[dict[str, int], dict[str, int]]:
    """Aggregate adopt and avoid patterns across missions.

    Returns (adopt_counts, avoid_counts) — dicts of pattern text to occurrence count.
    """
    adopt_counts: dict[str, int] = {}
    avoid_counts: dict[str, int] = {}
    for p in patterns:
        for text in p.get("adopt", []):
            adopt_counts[text] = adopt_counts.get(text, 0) + 1
        for text in p.get("avoid", []):
            avoid_counts[text] = avoid_counts.get(text, 0) + 1
    return adopt_counts, avoid_counts


def _build_intelligence_brief(
    patterns: list[dict],
    stats: dict,
    index_missions: list[dict],
    context: str,
) -> dict:
    """Build a structured intelligence brief from memory store data.

    Returns a dict suitable for JSON output or text formatting.
    """
    total = len(index_missions)
    achieved = sum(1 for m in index_missions if m.get("outcome_achieved"))
    win_rate = round(achieved / total * 100, 1) if total > 0 else None

    # Last-5 trend
    recent_5 = list(reversed(index_missions))[:5]
    r5_achieved = sum(1 for m in recent_5 if m.get("outcome_achieved"))
    recent_win_rate = (
        round(r5_achieved / len(recent_5) * 100, 1) if recent_5 else None
    )

    # Aggregate patterns
    adopt_counts, avoid_counts = _aggregate_patterns(patterns)
    top_adopt = sorted(adopt_counts.items(), key=lambda x: -x[1])[:5]
    top_avoid = sorted(avoid_counts.items(), key=lambda x: -x[1])[:5]

    # Standing order hot spots
    by_order = stats.get("by_order", {})
    hot_spots = sorted(
        [
            {
                "order": order,
                "count": data.get("count", 0),
                "missions_affected": len(data.get("missions", [])),
            }
            for order, data in by_order.items()
        ],
        key=lambda x: -x["count"],
    )[:5]

    # Context-relevant precedents
    precedents: list[dict] = []
    if context:
        scored = []
        for m in index_missions:
            outcome_text = m.get("actual_outcome", "") or m.get(
                "planned_outcome", ""
            )
            score = _keyword_overlap(context, outcome_text)
            if score > 0:
                scored.append((score, m))
        scored.sort(key=lambda x: -x[0])
        for _score, m in scored[:3]:
            # Find matching pattern data
            matching_patterns = [
                p
                for p in patterns
                if p.get("mission_id") == m.get("mission_id")
            ]
            mp = matching_patterns[0] if matching_patterns else {}
            precedents.append({
                "mission_id": m.get("mission_id", ""),
                "outcome_achieved": m.get("outcome_achieved", False),
                "planned_outcome": m.get("planned_outcome", ""),
                "duration_minutes": m.get("duration_minutes"),
                "ships_used": m.get("fleet", {}).get("ships_used"),
                "adopt": mp.get("adopt", []),
                "avoid": mp.get("avoid", []),
            })

    return {
        "total_missions": total,
        "win_rate": win_rate,
        "recent_win_rate": recent_win_rate,
        "top_adopt": [{"pattern": p, "count": c} for p, c in top_adopt],
        "top_avoid": [{"pattern": p, "count": c} for p, c in top_avoid],
        "standing_order_hot_spots": hot_spots,
        "precedents": precedents,
    }


def _format_brief_text(brief: dict, context: str) -> str:
    """Format an intelligence brief as compact text for context injection."""
    lines: list[str] = []
    total = brief["total_missions"]
    wr = brief["win_rate"]
    rwr = brief["recent_win_rate"]

    header = f"Intelligence Brief \u2014 {total} missions"
    if wr is not None:
        header += f", {wr}% win rate"
        if rwr is not None:
            header += f" (last 5: {rwr}%)"
    lines.append(header)
    lines.append("")

    if total == 0:
        lines.append("  No mission data available.")
        return "\n".join(lines)

    # Patterns to adopt
    top_adopt = brief.get("top_adopt", [])
    if top_adopt:
        lines.append("Patterns to adopt:")
        for item in top_adopt:
            lines.append(f"  - {item['pattern']} ({item['count']} missions)")
        lines.append("")

    # Patterns to avoid
    top_avoid = brief.get("top_avoid", [])
    if top_avoid:
        lines.append("Patterns to avoid:")
        for item in top_avoid:
            lines.append(f"  - {item['pattern']} ({item['count']} missions)")
        lines.append("")

    # Standing order hot spots
    hot_spots = brief.get("standing_order_hot_spots", [])
    if hot_spots:
        lines.append("Standing order hot spots:")
        for i, hs in enumerate(hot_spots, 1):
            lines.append(
                f"  {i}. {hs['order']}: "
                f"{hs['count']} violations across {hs['missions_affected']} missions"
            )
        lines.append("")

    # Context-relevant precedents
    precedents = brief.get("precedents", [])
    if precedents:
        lines.append(f'Relevant precedents (context: "{context}"):')
        for p in precedents:
            date = p["mission_id"][:10] if len(p["mission_id"]) >= 10 else p["mission_id"]
            marker = "\u2713" if p["outcome_achieved"] else "\u2717"
            outcome = p.get("planned_outcome", "")
            if len(outcome) > 50:
                outcome = outcome[:47] + "..."
            detail = f"  {date}  {marker}  {outcome}"
            if p.get("duration_minutes"):
                detail += f", {p['duration_minutes']}min"
            if p.get("ships_used"):
                detail += f", {p['ships_used']} ships"
            lines.append(detail)
            for a in p.get("adopt", []):
                lines.append(f"    adopt: {a}")
            for a in p.get("avoid", []):
                lines.append(f"    avoid: {a}")
        lines.append("")

    return "\n".join(lines)


def cmd_brief(args: argparse.Namespace) -> None:
    """Generate an intelligence brief from past missions."""
    missions_dir, index_path = _resolve_fleet_paths(args)
    context = args.context or ""

    # Read fleet intelligence index
    index = _read_json_optional(index_path)
    index_missions = index.get("missions", []) if index else []

    # Read memory store
    memory_dir = missions_dir.parent / "memory"
    patterns_data = _read_json_optional(memory_dir / "patterns.json")
    patterns = patterns_data.get("patterns", []) if patterns_data else []

    stats = _read_json_optional(memory_dir / "standing-order-stats.json") or {}

    brief = _build_intelligence_brief(patterns, stats, index_missions, context)

    if args.json_output:
        print(json.dumps(brief, indent=JSON_INDENT))
    else:
        print(_format_brief_text(brief, context))


# ---------------------------------------------------------------------------
# Subcommand: analytics
# ---------------------------------------------------------------------------


def _compute_success_rate_analytics(missions: list[dict]) -> dict:
    """Compute success rate analytics across missions."""
    total = len(missions)
    if total == 0:
        return {"total": 0, "achieved": 0, "win_rate": None, "recent_trend": None}

    achieved = sum(1 for m in missions if m.get("outcome_achieved"))
    win_rate = round(achieved / total * 100, 1)

    # Trend: last-5 vs overall
    recent = list(reversed(missions))[:5]
    r_achieved = sum(1 for m in recent if m.get("outcome_achieved"))
    recent_rate = round(r_achieved / len(recent) * 100, 1) if recent else None

    # Win rate by fleet size buckets
    by_size: dict[str, dict] = {}
    for m in missions:
        ships = m.get("fleet", {}).get("ships_used", 0)
        bucket = "1" if ships <= 1 else "2-3" if ships <= 3 else "4+"
        entry = by_size.get(bucket, {"total": 0, "achieved": 0})
        by_size[bucket] = {
            "total": entry["total"] + 1,
            "achieved": entry["achieved"] + (1 if m.get("outcome_achieved") else 0),
        }

    size_rates = {}
    for bucket, data in by_size.items():
        rate = round(data["achieved"] / data["total"] * 100, 1) if data["total"] else 0
        size_rates[bucket] = {"total": data["total"], "win_rate": rate}

    return {
        "total": total,
        "achieved": achieved,
        "not_achieved": total - achieved,
        "win_rate": win_rate,
        "recent_trend": recent_rate,
        "by_fleet_size": size_rates,
    }


def _compute_standing_order_analytics(
    missions: list[dict], stats: dict
) -> dict:
    """Compute standing order violation analytics."""
    by_order = stats.get("by_order", {})
    total_violations = stats.get("total_violations", 0)
    total_missions = stats.get("total_missions", 0)
    vpm = stats.get("violations_per_mission", 0.0)

    # Top offenders sorted by count
    top_offenders = sorted(
        [
            {
                "order": order,
                "count": data.get("count", 0),
                "missions_affected": len(data.get("missions", [])),
            }
            for order, data in by_order.items()
        ],
        key=lambda x: -x["count"],
    )

    corr = stats.get("correlation", {})

    return {
        "total_missions": total_missions,
        "total_violations": total_violations,
        "violations_per_mission": vpm,
        "top_offenders": top_offenders,
        "correlation": corr,
    }


def _compute_efficiency_analytics(missions: list[dict]) -> dict:
    """Compute efficiency analytics across missions."""
    if not missions:
        return {
            "mission_count": 0,
            "tokens_per_task": None,
            "duration_per_task": None,
            "avg_budget_utilization": None,
            "avg_ships_per_mission": None,
            "tasks_per_ship": None,
        }

    # Tokens per task
    tokens_per_task_values: list[float] = []
    duration_per_task_values: list[float] = []
    budget_utils: list[float] = []
    ships_list: list[int] = []
    tasks_per_ship_values: list[float] = []

    for m in missions:
        budget = m.get("budget", {})
        tasks = m.get("tasks", {})
        fleet = m.get("fleet", {})
        total_tasks = tasks.get("total", 0)
        tokens = budget.get("tokens_consumed")
        duration = m.get("duration_minutes")
        pct = budget.get("pct_consumed")
        ships = fleet.get("ships_used")

        if tokens is not None and total_tasks > 0:
            tokens_per_task_values.append(tokens / total_tasks)
        if duration is not None and total_tasks > 0:
            duration_per_task_values.append(duration / total_tasks)
        if pct is not None:
            budget_utils.append(pct)
        if ships is not None:
            ships_list.append(ships)
            if total_tasks > 0:
                tasks_per_ship_values.append(total_tasks / ships)

    tpt = _safe_mean(tokens_per_task_values)
    dpt = _safe_mean(duration_per_task_values)
    abu = _safe_mean(budget_utils)
    aspm = _safe_mean(ships_list)
    tps = _safe_mean(tasks_per_ship_values)

    return {
        "mission_count": len(missions),
        "tokens_per_task": int(round(tpt)) if tpt is not None else None,
        "duration_per_task": round(dpt, 1) if dpt is not None else None,
        "avg_budget_utilization": round(abu, 1) if abu is not None else None,
        "avg_ships_per_mission": round(aspm, 1) if aspm is not None else None,
        "tasks_per_ship": round(tps, 1) if tps is not None else None,
    }


def _compute_estimate_outcome_analytics(missions: list[dict]) -> dict:
    """Compute estimate acceptance-criterion verification analytics.

    Aggregates per-criterion outcomes recorded via `nelson-data estimate-outcome`
    across missions.  Reports pass / fail / not-verified totals, a per-method
    breakdown with pass rates, and per-mission pass rates so the quarterdeck
    can spot which missions skimped on verification.
    """
    methods = sorted(VALID_ESTIMATE_OUTCOME_METHODS)
    statuses = sorted(VALID_ESTIMATE_OUTCOME_STATUSES)

    totals = {s: 0 for s in statuses}
    by_method: dict[str, dict[str, int]] = {
        m: {s: 0 for s in statuses} for m in methods
    }
    per_mission: list[dict] = []
    missions_with_outcomes = 0

    for m in missions:
        outcomes = m.get("estimate_outcomes", []) or []
        if not outcomes:
            continue
        missions_with_outcomes += 1
        mission_counts = {s: 0 for s in statuses}
        for o in outcomes:
            status = o.get("status")
            method = o.get("method")
            if status in totals:
                totals[status] += 1
                mission_counts[status] += 1
            if method in by_method and status in by_method[method]:
                by_method[method][status] += 1
        m_total = sum(mission_counts.values())
        pass_rate = (
            round(mission_counts["pass"] / m_total * 100, 1) if m_total else None
        )
        per_mission.append(
            {
                "mission_id": m.get("mission_id", ""),
                "total": m_total,
                "pass": mission_counts["pass"],
                "fail": mission_counts["fail"],
                "not_verified": mission_counts["not-verified"],
                "pass_rate": pass_rate,
            }
        )

    total = sum(totals.values())
    overall_pass_rate = (
        round(totals["pass"] / total * 100, 1) if total else None
    )

    method_summary: dict[str, dict] = {}
    for method, counts in by_method.items():
        m_total = sum(counts.values())
        method_summary[method] = {
            "total": m_total,
            "pass": counts["pass"],
            "fail": counts["fail"],
            "not_verified": counts["not-verified"],
            "pass_rate": (
                round(counts["pass"] / m_total * 100, 1) if m_total else None
            ),
        }

    return {
        "mission_count": len(missions),
        "missions_with_outcomes": missions_with_outcomes,
        "total": total,
        "pass": totals["pass"],
        "fail": totals["fail"],
        "not_verified": totals["not-verified"],
        "pass_rate": overall_pass_rate,
        "by_method": method_summary,
        "by_mission": per_mission,
    }


def _format_analytics_text(metric: str, data: dict) -> str:
    """Format analytics results as human-readable text."""
    lines: list[str] = []

    if metric in ("success-rate", "all"):
        sr = data.get("success_rate", {})
        lines.append(f"Success Rate \u2014 {sr['total']} missions")
        if sr.get("win_rate") is not None:
            lines.append(
                f"  Win rate: {sr['win_rate']}% "
                f"({sr['achieved']} achieved, {sr['not_achieved']} not)"
            )
            if sr.get("recent_trend") is not None:
                lines.append(f"  Recent trend (last 5): {sr['recent_trend']}%")
            by_size = sr.get("by_fleet_size", {})
            if by_size:
                lines.append("  By fleet size:")
                for bucket in sorted(by_size.keys()):
                    info = by_size[bucket]
                    lines.append(
                        f"    {bucket} ships: {info['win_rate']}% "
                        f"({info['total']} missions)"
                    )
        lines.append("")

    if metric in ("standing-orders", "all"):
        so = data.get("standing_orders", {})
        lines.append(
            f"Standing Orders \u2014 {so['total_violations']} violations "
            f"across {so['total_missions']} missions "
            f"({so['violations_per_mission']}/mission)"
        )
        for item in so.get("top_offenders", []):
            lines.append(
                f"  {item['order']}: {item['count']} violations "
                f"({item['missions_affected']} missions)"
            )
        corr = so.get("correlation", {})
        if corr:
            lines.append(
                f"  Correlation: {corr.get('failures_with_violations', 0)} failures "
                f"and {corr.get('successes_with_violations', 0)} successes "
                f"had violations"
            )
        lines.append("")

    if metric in ("efficiency", "all"):
        ef = data.get("efficiency", {})
        lines.append(f"Efficiency \u2014 {ef['mission_count']} missions")
        if ef.get("tokens_per_task") is not None:
            tok_str = (
                f"{round(ef['tokens_per_task'] / 1000)}K"
                if ef["tokens_per_task"] >= 1000
                else str(ef["tokens_per_task"])
            )
            lines.append(f"  Tokens per task: {tok_str}")
        if ef.get("duration_per_task") is not None:
            lines.append(f"  Duration per task: {ef['duration_per_task']} min")
        if ef.get("avg_budget_utilization") is not None:
            lines.append(f"  Budget utilization: {ef['avg_budget_utilization']}%")
        if ef.get("avg_ships_per_mission") is not None:
            lines.append(f"  Ships per mission: {ef['avg_ships_per_mission']}")
        if ef.get("tasks_per_ship") is not None:
            lines.append(f"  Tasks per ship: {ef['tasks_per_ship']}")
        lines.append("")

    if metric in ("estimate-outcomes", "all"):
        eo = data.get("estimate_outcomes", {})
        lines.append(
            f"Estimate outcomes \u2014 {eo.get('missions_with_outcomes', 0)} "
            f"of {eo.get('mission_count', 0)} missions recorded outcomes"
        )
        if eo.get("total", 0) > 0:
            lines.append(
                f"  Overall: {eo['pass_rate']}% pass "
                f"({eo['pass']} pass, {eo['fail']} fail, "
                f"{eo['not_verified']} not-verified of {eo['total']})"
            )
            by_method = eo.get("by_method", {})
            method_lines = [
                (method, info)
                for method, info in by_method.items()
                if info.get("total", 0) > 0
            ]
            if method_lines:
                lines.append("  By method:")
                for method, info in method_lines:
                    lines.append(
                        f"    {method}: {info['pass_rate']}% pass "
                        f"({info['pass']}/{info['total']})"
                    )
        lines.append("")

    return "\n".join(lines)


def cmd_analytics(args: argparse.Namespace) -> None:
    """Compute and display cross-mission analytics."""
    missions_dir, index_path = _resolve_fleet_paths(args)
    metric = args.metric

    if not index_path.exists():
        _die("No fleet intelligence index found. Run 'nelson-data index' first.")

    index = _read_json_optional(index_path)
    if index is None:
        _die("Failed to read fleet intelligence index.")

    missions = index.get("missions", [])

    # Apply --last filter
    last_n = max(0, args.last)
    if last_n > 0:
        missions = list(reversed(missions))[:last_n]
        missions = list(reversed(missions))  # restore chronological order

    # Read standing order stats for the standing-orders metric
    memory_dir = missions_dir.parent / "memory"
    stats = _read_json_optional(memory_dir / "standing-order-stats.json") or {}

    result: dict[str, Any] = {}
    if metric in ("success-rate", "all"):
        result["success_rate"] = _compute_success_rate_analytics(missions)
    if metric in ("standing-orders", "all"):
        result["standing_orders"] = _compute_standing_order_analytics(missions, stats)
    if metric in ("efficiency", "all"):
        result["efficiency"] = _compute_efficiency_analytics(missions)
    if metric in ("estimate-outcomes", "all"):
        result["estimate_outcomes"] = _compute_estimate_outcome_analytics(missions)

    if args.json_output:
        # For single metrics, unwrap the wrapper key
        output = result if metric == "all" else result.get(metric.replace("-", "_"), result)
        print(json.dumps(output, indent=JSON_INDENT))
    else:
        print(_format_analytics_text(metric if metric != "all" else "all", result))
