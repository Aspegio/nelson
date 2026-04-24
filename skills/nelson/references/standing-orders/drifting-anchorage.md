# Standing Order: Drifting Anchorage

Do not allow tasks to expand scope beyond the original sailing orders without re-scoping.

**Symptoms:**
- Captains add features or refactors not in the battle plan.
- Mission metric is no longer connected to active work.
- Token and time budgets overrun without corresponding mission progress.
- Captain creates new functions, files, or environment variables that duplicate existing ones instead of extending them.
- Existing implementation is deprecated, bypassed, or shadowed rather than modified.

**Remedy:** When scope drift is detected during a quarterdeck checkpoint, re-scope the task or split it. Work that falls outside the sailing orders must be deferred or explicitly added with admiral approval.

When a captain creates a parallel implementation instead of extending existing code, direct the captain to remove the duplicate and modify the existing implementation. If the task is already completed, apply partial rollback per `references/damage-control/partial-rollback.md` and re-task with explicit modification targets.
