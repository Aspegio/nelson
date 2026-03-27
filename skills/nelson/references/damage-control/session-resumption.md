# Session Resumption: Picking Up Mid-Mission

Use when a session is interrupted (context limit, crash, timeout) and work must continue.

1. List `.nelson/missions/` sorted by name. The most recent directory is the active mission. Set it as `{mission-dir}`.
2. **Recover state from structured data (preferred):**
   - If `{mission-dir}/fleet-status.json` exists, read it for quick state recovery (task progress, hull status, budget, blockers).
   - If `{mission-dir}/mission-log.json` exists, read it for full event history — task completions, relief chains, standing order violations, and admiral decisions.
   - These JSON files provide faster, more reliable state recovery than re-parsing quarterdeck report prose.
   - **Fallback:** If neither JSON file is present, read `{mission-dir}/quarterdeck-report.md` to establish last known state.
3. List all tasks and their statuses: `pending`, `in_progress`, `completed`.
4. For each `in_progress` task, verify partial outputs against the task deliverable.
5. Discard any unverified or incomplete outputs that cannot be confirmed correct.
6. Re-issue sailing orders with the original mission outcome and updated scope reflecting completed work.
7. Re-form the squadron at the minimum size needed for remaining tasks.
8. Resume quarterdeck rhythm from the next scheduled checkpoint.
