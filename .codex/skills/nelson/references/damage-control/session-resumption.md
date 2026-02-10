# Session Resumption: Picking Up Mid-Mission

Use when a session is interrupted (context limit, crash, timeout) and work must continue.

1. Read the most recent quarterdeck report to establish last known state.
2. List all tasks and their statuses: `pending`, `in_progress`, `completed`.
3. For each `in_progress` task, verify partial outputs against the task deliverable.
4. Discard any unverified or incomplete outputs that cannot be confirmed correct.
5. Re-issue sailing orders with the original mission outcome and updated scope reflecting completed work.
6. Re-form the squadron at the minimum size needed for remaining tasks.
7. Resume quarterdeck rhythm from the next scheduled checkpoint.
