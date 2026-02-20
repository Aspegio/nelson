# Session Hygiene: Clean Start Procedure

Use at the start of a new Nelson session to clear stale damage reports and turnover briefs before any ships are launched.

## Directory Structure

Nelson stores all session data under `.claude/nelson/`:

```
.claude/nelson/
  damage-reports/     — Current session's damage reports (JSON)
  turnover-briefs/    — Current session's turnover briefs (markdown)
  archive/            — Archived data from previous sessions
```

## Responsibility

The admiral executes session hygiene at Step 1 (Issue Sailing Orders), before forming the squadron or launching any ships.

## Procedure: New Session

1. Confirm this is a genuinely new session, not a resumption. If resuming, skip this procedure entirely and follow `damage-control/session-resumption.md`.
2. Check whether `.claude/nelson/damage-reports/` or `.claude/nelson/turnover-briefs/` contain files from a previous session.
3. If previous files exist and the admiral wants to preserve them, archive first:
   - Create `.claude/nelson/archive/{YYYY-MM-DD}/` using the current date.
   - Move all files from `damage-reports/` into the archive directory.
   - Move all files from `turnover-briefs/` into the archive directory.
4. If archiving is not needed, delete all files in `damage-reports/` and `turnover-briefs/`.
5. Ensure the directory structure exists. Create any missing directories:
   - `.claude/nelson/damage-reports/`
   - `.claude/nelson/turnover-briefs/`
6. Record in the captain's log that session hygiene is complete. Proceed to form the squadron.

## Procedure: Resumed Session

1. Do NOT clear or archive any files.
2. Read existing damage reports to establish hull integrity for each ship.
3. Read existing turnover briefs to recover task state.
4. Follow `damage-control/session-resumption.md` for the full resumption procedure.
