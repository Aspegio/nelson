# Session Hygiene: Clean Start Procedure

Use at the start of a new Nelson session to prepare the mission directory before any ships are launched.

## Directory Structure

Nelson stores each mission's data in a timestamped directory under `.nelson/missions/`:

```
.nelson/missions/{YYYY-MM-DD_HHMMSS}_{SESSION_ID}/
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
2. Verify that `nelson-data.py init` (Step 1, "Structured Data Capture") has been run. It creates the mission directory, the `damage-reports/` and `turnover-briefs/` subdirectories, the three initial JSON files, and the `.nelson/.active-{SESSION_ID}` marker in one step. Confirm `{mission-dir}` is set to the path the script printed.
3. Note that session hygiene is complete. Proceed to form the squadron.

## Procedure: Resumed Session

1. If you know the SESSION_ID for this session, read `.nelson/.active-{SESSION_ID}` to recover the mission directory path and set it as `{mission-dir}`. If you cannot determine your SESSION_ID (e.g., after a full restart), list `.nelson/missions/` and present the options to the user for selection. Set the chosen directory as `{mission-dir}`.
2. Read existing damage reports from `{mission-dir}/damage-reports/` to establish hull integrity for each ship.
3. Read existing turnover briefs from `{mission-dir}/turnover-briefs/` to recover task state.
4. Follow `damage-control/session-resumption.md` for the full resumption procedure.

## Rotated Report Files

Within each mission directory, rotated checkpoint files may be present:

- `quarterdeck-report-0.md`, `quarterdeck-report-1.md`, etc.
- `captains-log-0.md`, `captains-log-1.md`, etc.

These are intentionally preserved as checkpoint history — they record the state of the reports at each checkpoint within that mission. They do not require cleanup because:

1. Each mission has its own timestamped directory (`.nelson/missions/{YYYY-MM-DD_HHMMSS}_{SESSION_ID}/`)
2. Rotated files within a mission directory are historical artifacts of that mission's execution
3. Previous missions are preserved automatically, so the checkpoint history is part of the permanent record for that mission

You may review checkpoint history by reading the rotated files in the mission directory. You should not delete them.

## Browsing Previous Missions

Previous missions remain on disk at `.nelson/missions/`. To review past mission logs, list the directory contents sorted by name (which sorts chronologically by date/time).
