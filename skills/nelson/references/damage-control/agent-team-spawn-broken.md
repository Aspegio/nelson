# Agent Team Spawn Broken

Use when spawning a captain via `Agent(team_name=..., name=...)` returns
`[Tool result missing due to internal error]` or otherwise silently fails to
produce a teammate.

This is a known upstream regression — see
[claude-code#40270](https://github.com/anthropics/claude-code/issues/40270).
The `team_name` parameter on the `Agent` tool currently triggers an internal
error in the teammate spawn path even when `TeamCreate` and `TaskCreate`
succeed first. The issue is open as of April 2026.

## Symptoms

- `Agent(team_name="...", name="...")` returns `[Tool result missing due to
  internal error]` or empty content with no captain spawned.
- `TeamCreate` succeeded but the team has no enrolled members afterwards.
- The admiral cannot reach any captain via `SendMessage` because no captains
  exist.

## Procedure

1. Confirm the failure is the `#40270` regression by retrying once. If the
   second `Agent(team_name=...)` call returns the same error, treat the
   experimental Agent Teams spawn path as unavailable for this session.
2. Stand down the empty team if `TeamCreate` succeeded but no members
   enrolled:
   ```
   TeamDelete(team_name="<name>")
   ```
3. Fall back to `subagents` mode for the rest of the mission:
   - Update `battle-plan.json` `squadron.mode` to `subagents`.
   - Re-run the conflict scan: `python3 .claude/skills/nelson/scripts/nelson_conflict_scan.py --plan {mission-dir}/battle-plan.json`.
   - Re-spawn captains with `Agent(subagent_type="general-purpose", ...)`
     instead of `Agent(team_name=..., name=...)`.
   - Reassign captain visibility tracking via the admiral's
     `TaskCreate`/`TaskUpdate` calls (admiral exception, not captain
     coordination).
4. Log the regression and mode change in the captain's log so future
   missions know to check #40270 status before selecting `agent-team`.

## Prevention

- At the start of every `agent-team` mission, the admiral should make ONE
  test spawn before assigning the full squadron. If that spawn fails with
  the #40270 symptom, abort `agent-team` mode and select `subagents`
  instead before any tasks are committed.
- When upstream confirms a fix, remove this damage-control entry and the
  preflight check. Track the issue's status when planning new missions.

## Related

- `references/standing-orders/wrong-ensign.md` — mode/tool consistency.
- `references/damage-control/comms-failure.md` — broader infrastructure
  failure recovery.
- `references/squadron-composition.md` — mode selection (which now warns
  about #40270).
