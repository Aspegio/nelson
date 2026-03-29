# Session Resumption: Picking Up Mid-Mission

Use when a session is interrupted (context limit, crash, timeout) and work must continue.

1. List `.nelson/missions/` sorted by name. The most recent directory is the active mission. Set it as `{mission-dir}`. Read the latest report to establish last known state:
   - The canonical path is `{mission-dir}/quarterdeck-report.md`.
   - **Fallback:** If the canonical file is missing (e.g. crash during report rotation), check for `{mission-dir}/quarterdeck-report-N.md` files (where N is a number). Use the file with the highest N value — it contains the most recent checkpoint data. The same fallback applies to `captains-log.md` / `captains-log-N.md`.
2. List all tasks and their statuses: `pending`, `in_progress`, `completed`.
3. For each `in_progress` task, verify partial outputs against the task deliverable.
4. Discard any unverified or incomplete outputs that cannot be confirmed correct.
5. Re-issue sailing orders with the original mission outcome and updated scope reflecting completed work.
6. Re-form the squadron at the minimum size needed for remaining tasks.
7. Resume quarterdeck rhythm from the next scheduled checkpoint.
