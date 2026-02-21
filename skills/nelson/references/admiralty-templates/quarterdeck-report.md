# Quarterdeck Report Template

Scannable checkpoint report for the admiral. The entire report should be readable in 30 seconds.

```text
STATUS: [ON TRACK / AT RISK / BLOCKED] — [X/Y] tasks complete, [N blockers / no blockers]

Progress:
| Ship           | Task                  | Status      | % Complete |
|----------------|-----------------------|-------------|------------|
| HMS [name]     | [task summary]        | [status]    | [XX]%      |
| HMS [name]     | [task summary]        | [status]    | [XX]%      |

Hull Integrity:
| Ship           | Condition | Hull % | Relief? |
|----------------|-----------|--------|---------|
| HMS [name]     | [XRAY]    | [XX]%  | No      |
| HMS [name]     | [YOKE]    | [XX]%  | No      |

Blockers: [omit section if none]
- [blocker description] — owner: [name], ETA: [time]

Budget: [spent] / [remaining] tokens — burn rate [X]% per checkpoint

Admiral Decision: [continue / rescope / stop] — [brief rationale]

Signal Flags: [omit section if no recognition warranted]
- [recognition]
```

## Usage Notes

- **STATUS line** is the first thing the admiral reads. State the headline, not the detail.
- **Progress table** replaces the flat list. One row per task, sortable by status.
- **Hull Integrity board** gives material condition at a glance. Refer to `references/damage-control/hull-integrity.md` for condition definitions (XRAY, YOKE, ZEBRA, ZEBRA Critical).
- **Blockers** appear only when they exist. Each blocker fits on a single line with owner and ETA.
- **Budget** is a single line. Burn rate lets the admiral project whether the budget will hold.
- **Admiral Decision** is a single line. The rationale should be one sentence.
- **Signal Flags** appear only when recognition is warranted. Omit the section entirely if there is nothing to report.
