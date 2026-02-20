#!/usr/bin/env python3
"""Count tokens in a Claude Code session and produce a Nelson damage report.

The admiral uses this script to monitor hull integrity across the squadron.
Reads Claude Code session JSONL files and extracts exact token counts from
the API usage data embedded in assistant messages. No estimation needed.

Single ship (flagship checks itself):
    python scripts/count-tokens.py --session session.jsonl --ship "HMS Victory"

Squadron readiness board (flagship checks all ships):
    python scripts/count-tokens.py --squadron /path/to/{session-id}/

Plain text fallback (heuristic estimate):
    python scripts/count-tokens.py --file plain.txt --ship "HMS Victory"
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone


def count_tokens_from_jsonl(path):
    """Extract exact token count from the last assistant turn's usage data.

    Claude Code JSONL files contain API usage stats on every assistant message:
    input_tokens, cache_creation_input_tokens, cache_read_input_tokens, and
    output_tokens. The sum of the input fields on the most recent turn gives
    the current context size.
    """
    last_usage = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") != "assistant":
                continue
            msg = record.get("message")
            if not isinstance(msg, dict) or "usage" not in msg:
                continue
            last_usage = msg["usage"]

    if last_usage is None:
        return None

    input_tokens = last_usage.get("input_tokens", 0)
    cache_creation = last_usage.get("cache_creation_input_tokens", 0)
    cache_read = last_usage.get("cache_read_input_tokens", 0)
    return input_tokens + cache_creation + cache_read


def count_tokens_heuristic(path):
    """Estimate token count as character count divided by 4.

    Fallback for plain text files that lack API usage data.
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return len(text) // 4


def hull_integrity_status(pct):
    """Map remaining-capacity percentage to a status label."""
    if pct >= 75:
        return "Green"
    if pct >= 60:
        return "Amber"
    if pct >= 40:
        return "Red"
    return "Critical"


def build_report(ship_name, token_count, token_limit, method):
    """Build a Nelson damage report dict."""
    remaining = max(token_limit - token_count, 0)
    pct = int((remaining / token_limit) * 100) if token_limit > 0 else 0
    status = hull_integrity_status(pct)

    return {
        "ship_name": ship_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "token_count": token_count,
        "token_limit": token_limit,
        "hull_integrity_pct": pct,
        "hull_integrity_status": status,
        "relief_requested": status in ("Red", "Critical"),
        "method": method,
    }


def scan_squadron(session_dir, token_limit):
    """Scan a session directory for the flagship and all subagent JSONL files.

    Returns a readiness board: a list of damage reports for every ship found.

    Directory layout:
        {session-id}/
            subagents/
                agent-{agentId}.jsonl   — one per subagent (ship)
        {session-id}.jsonl              — flagship session (sibling of dir)
    """
    reports = []
    session_dir = session_dir.rstrip("/")
    session_id = os.path.basename(session_dir)

    # Flagship JSONL is the sibling file with matching session ID
    flagship_path = session_dir + ".jsonl"
    if os.path.isfile(flagship_path):
        token_count = count_tokens_from_jsonl(flagship_path)
        if token_count is not None:
            reports.append(
                build_report("Flagship", token_count, token_limit, "jsonl_usage")
            )

    # Subagent JSONLs live in the subagents/ subdirectory
    subagents_dir = os.path.join(session_dir, "subagents")
    if os.path.isdir(subagents_dir):
        for jsonl_path in sorted(glob.glob(os.path.join(subagents_dir, "agent-*.jsonl"))):
            filename = os.path.basename(jsonl_path)
            agent_id = filename.replace("agent-", "").replace(".jsonl", "")
            token_count = count_tokens_from_jsonl(jsonl_path)
            if token_count is not None:
                reports.append(
                    build_report(
                        f"agent-{agent_id}",
                        token_count,
                        token_limit,
                        "jsonl_usage",
                    )
                )

    return reports


def main():
    parser = argparse.ArgumentParser(
        description="Count tokens and produce a Nelson damage report."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--session", help="Path to a Claude Code session JSONL file (exact counts)"
    )
    source.add_argument(
        "--file", help="Path to a plain text file (heuristic estimate)"
    )
    source.add_argument(
        "--squadron",
        help="Path to a session directory to scan flagship + all subagents",
    )
    parser.add_argument(
        "--ship", help="Ship name for the report (required for --session and --file)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200000,
        help="Context window token limit (default: 200000)",
    )
    parser.add_argument(
        "--output", help="Write JSON report to this path instead of stdout"
    )
    args = parser.parse_args()

    if args.squadron:
        if not os.path.isdir(args.squadron):
            print(f"Error: not a directory: {args.squadron}", file=sys.stderr)
            sys.exit(1)
        reports = scan_squadron(args.squadron, args.limit)
        if not reports:
            print("Warning: no usage data found in session directory", file=sys.stderr)
            sys.exit(1)
        result = json.dumps(reports, indent=2)
    else:
        if not args.ship:
            parser.error("--ship is required when using --session or --file")

        path = args.session or args.file
        try:
            if args.session:
                token_count = count_tokens_from_jsonl(path)
                if token_count is None:
                    print(
                        "Warning: no usage data found in JSONL, falling back to heuristic",
                        file=sys.stderr,
                    )
                    token_count = count_tokens_heuristic(path)
                    method = "heuristic"
                else:
                    method = "jsonl_usage"
            else:
                token_count = count_tokens_heuristic(path)
                method = "heuristic"
        except FileNotFoundError:
            print(f"Error: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        except OSError as exc:
            print(f"Error reading file: {exc}", file=sys.stderr)
            sys.exit(1)

        report = build_report(args.ship, token_count, args.limit, method)
        result = json.dumps(report, indent=2)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result + "\n")
        except OSError as exc:
            print(f"Error writing output: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        print(result)


if __name__ == "__main__":
    main()
