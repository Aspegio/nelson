# Session Hygiene: Clean Start Procedure

Use at the start of a new Nelson session to prepare the mission directory before any ships are launched.

## Directory Structure

Nelson stores each mission's data in a timestamped directory under `.claude/nelson/missions/`:

```
.claude/nelson/missions/{YYYY-MM-DD_HHMMSS}/
  captains-log.md         — Written at stand-down
  quarterdeck-report.md   — Updated at every checkpoint
  damage-reports/         — Ship damage reports (JSON)
  turnover-briefs/        — Ship turnover briefs (markdown)
```

Each mission gets its own directory. Previous missions are preserved automatically — there is no need to archive or delete old data.

## Responsibility

The admiral executes session hygiene at Step 1 (Issue Sailing Orders), before forming the squadron or launching any ships.

## Procedure: New Session

1. Confirm this is a genuinely new session, not a resumption. If resuming, skip this procedure entirely and follow the Resumed Session procedure below.
2. Verify the mission directory created by Step 1's "Establish Mission Directory" exists and contains `damage-reports/` and `turnover-briefs/` subdirectories.
3. Note that session hygiene is complete. Proceed to form the squadron.

## Procedure: Resumed Session

1. List `.claude/nelson/missions/` sorted by name. The most recent directory is the active mission. Set it as `{mission-dir}`.
2. Read existing damage reports from `{mission-dir}/damage-reports/` to establish hull integrity for each ship.
3. Read existing turnover briefs from `{mission-dir}/turnover-briefs/` to recover task state.
4. Follow `damage-control/session-resumption.md` for the full resumption procedure.

## Browsing Previous Missions

Previous missions remain on disk at `.claude/nelson/missions/`. To review past mission logs, list the directory contents sorted by name (which sorts chronologically by date/time).
