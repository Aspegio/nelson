# Session Hygiene: Clean Start Procedure

Use at the start of a new Nelson session to prepare the mission directory before any ships are launched.

## Directory Structure

Nelson stores each mission's data in a timestamped directory under `.claude/nelson/missions/`:

```
.claude/nelson/missions/{YYYY-MM-DD_HHMM}/
  captains-log.md         — Written at stand-down
  quarterdeck-report.md   — Updated at every checkpoint
  damage-reports/         — Ship damage reports (JSON)
  turnover-briefs/        — Ship turnover briefs (markdown)
```

Each mission gets its own directory. Previous missions are preserved automatically — there is no need to archive or delete old data.

## Responsibility

The admiral executes session hygiene at Step 1 (Issue Sailing Orders), before forming the squadron or launching any ships.

## Procedure: New Session

1. Confirm this is a genuinely new session, not a resumption. If resuming, skip this procedure entirely and follow `damage-control/session-resumption.md`.
2. Create the mission directory at `.claude/nelson/missions/{YYYY-MM-DD_HHMM}/` using the current date and 24-hour time.
3. Create the subdirectories `damage-reports/` and `turnover-briefs/` within the mission directory.
4. Record the mission directory path as `{mission-dir}` for the remainder of the mission. All subsequent file references use this path.
5. Record in the captain's log that session hygiene is complete. Proceed to form the squadron.

## Procedure: Resumed Session

1. Do NOT create a new mission directory. Use the existing one from the interrupted session.
2. Read existing damage reports from `{mission-dir}/damage-reports/` to establish hull integrity for each ship.
3. Read existing turnover briefs from `{mission-dir}/turnover-briefs/` to recover task state.
4. Follow `damage-control/session-resumption.md` for the full resumption procedure.

## Browsing Previous Missions

Previous missions remain on disk at `.claude/nelson/missions/`. To review past mission logs, list the directory contents sorted by name (which sorts chronologically by date/time).
