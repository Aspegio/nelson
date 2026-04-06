# Session Resumption: Picking Up Mid-Mission

Use when a session is interrupted (context limit, crash, timeout) and work must continue.

1. If you know the SESSION_ID for this session, read `.nelson/.active-{SESSION_ID}` to recover the mission directory path and set it as `{mission-dir}`. If you cannot determine your SESSION_ID (e.g., after a full restart), list `.nelson/missions/` and present the options to the user for selection. Set the chosen directory as `{mission-dir}`.
2. **Recover state from structured data (preferred):**
   - If `{mission-dir}/fleet-status.json` exists, read it for quick state recovery (task progress, hull status, budget, blockers).
   - If `{mission-dir}/mission-log.json` exists, read it for full event history — task completions, relief chains, standing order violations, and admiral decisions.
   - These JSON files provide faster, more reliable state recovery than re-parsing quarterdeck report prose.
   - **Fallback:** If neither JSON file is present, read `{mission-dir}/quarterdeck-report.md` to establish last known state.
   - **Sub-fallback:** If the canonical `quarterdeck-report.md` is also missing (e.g. crash during report rotation), check for `{mission-dir}/quarterdeck-report-N.md` files (where N is a number). Use the file with the highest N value — it contains the most recent checkpoint data. The same fallback applies to `captains-log.md` / `captains-log-N.md`.
3. List all tasks and their statuses: `pending`, `in_progress`, `completed`.
4. For each `in_progress` task, verify partial outputs against the task deliverable.
5. Discard any unverified or incomplete outputs that cannot be confirmed correct.
6. Re-issue sailing orders with the original mission outcome and updated scope reflecting completed work.
7. Re-form the squadron at the minimum size needed for remaining tasks.
8. Resume quarterdeck rhythm from the next scheduled checkpoint.
