# Worktree + Team Name Conflict

Use when a captain spawned with both `team_name` and `isolation: "worktree"`
appears to be running in the main repository instead of an isolated worktree.

This is a known upstream bug — see
[claude-code#37549](https://github.com/anthropics/claude-code/issues/37549).
The combination silently lands the captain in the main repo with no error
raised, defeating the isolation guarantee. The bug is open as of April
2026.

## Symptoms

- Multiple captains spawned with `isolation: "worktree"` write to the same
  files and produce merge-style conflicts where none should be possible.
- `git worktree list` shows fewer worktrees than captains spawned.
- Captain logs reference paths in the main repo rather than under
  `.claude/worktrees/`.

## Procedure

1. Detect: after spawning the squadron, run
   `git worktree list` and compare the count to the number of captains
   intended to be isolated. Mismatch confirms the bug.
2. If captains have already started writing, pause them via
   `SendMessage(type="message")` instructing them to stop and report
   current state.
3. Choose one of two recovery paths:
   - **Path A (preferred): drop worktree isolation, enforce file ownership.**
     Update the battle plan so each captain owns disjoint files
     (`split-keel.md`). Re-run `nelson_conflict_scan.py` to confirm no
     overlap. Continue in `agent-team` mode without isolation.
   - **Path B: drop `agent-team` mode, keep worktrees.** Stand down the
     team via `TeamDelete`. Switch `squadron.mode` to `subagents` (which
     spawns via `subagent_type` and supports worktree isolation correctly).
     Re-spawn each captain with `isolation: "worktree"` only.
4. Log the bug and chosen recovery path in the captain's log.

## Prevention

- Until #37549 is fixed, do not combine `team_name` with `isolation:
  "worktree"` in the same `Agent` call. Choose one or the other:
  `agent-team` mode without worktrees, or `subagents` mode with worktrees.
- The squadron-composition reference now reflects this constraint.

## Related

- `references/squadron-composition.md` — Worktree Isolation guidance.
- `references/standing-orders/split-keel.md` — file ownership as the
  primary conflict-prevention mechanism.
- `references/damage-control/agent-team-spawn-broken.md` — companion bug
  in the same surface area (#40270).
