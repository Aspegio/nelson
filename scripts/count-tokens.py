#!/usr/bin/env python3
"""Count tokens in a Claude Code session and produce a Nelson damage report.

Used by ship agents to monitor context window consumption during a mission.
Reads a Claude Code session JSONL file and extracts exact token counts from
the API usage data embedded in assistant messages. Falls back to a character
heuristic if the file is plain text rather than JSONL.

Usage:
    python scripts/count-tokens.py --session session.jsonl --ship "HMS Victory"
    python scripts/count-tokens.py --file plain.txt --ship "HMS Victory"
    python scripts/count-tokens.py --session session.jsonl --ship "HMS Victory" --output report.json
"""

import argparse
import json
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
    parser.add_argument("--ship", required=True, help="Ship name for the report")
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
    report_json = json.dumps(report, indent=2)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(report_json + "\n")
        except OSError as exc:
            print(f"Error writing output: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        print(report_json)


if __name__ == "__main__":
    main()
