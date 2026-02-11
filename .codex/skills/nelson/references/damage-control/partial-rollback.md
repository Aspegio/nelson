# Partial Rollback: Reverting Without Losing Progress

Use when a completed task is found to be faulty but other completed tasks are sound.

1. Admiral identifies the faulty task and its downstream dependents.
2. Admiral marks the faulty task as `in_progress` and all dependents as `pending`.
3. If the faulty task produced code changes, revert those changes using version control.
4. If the faulty task produced non-code artifacts, archive them with a `reverted` label.
5. Re-assign the faulty task to the original owner or a replacement agent.
6. Agent re-executes the task from its original definition with the failure mode documented as a constraint.
7. Once the re-executed task is verified, unblock and resume dependent tasks.
