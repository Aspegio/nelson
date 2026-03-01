# Damage Report Template

File a damage report to communicate context window usage to the admiral. Store each report as a JSON file at `.claude/nelson/damage-reports/{ship-name}.json` during a mission.

```json
{
  "ship_name": "",
  "agent_id": "",
  "timestamp": "",
  "token_count": 0,
  "token_limit": 0,
  "hull_integrity_pct": 0,
  "hull_integrity_status": "",
  "relief_requested": false,
  "context_summary": "",
  "report_path": ".claude/nelson/damage-reports/{ship-name}.json"
}
```

## Field Definitions

| Field | Type | Description |
|---|---|---|
| `ship_name` | string | Ship name assigned in the battle plan (e.g. `"HMS Argyll"`) |
| `agent_id` | string | Agent identifier from the team config |
| `timestamp` | string | ISO 8601 timestamp of the report (e.g. `"2026-02-20T14:30:00Z"`) |
| `token_count` | integer | Tokens consumed so far in the current session |
| `token_limit` | integer | Maximum context window size for the agent |
| `hull_integrity_pct` | integer | Remaining capacity as a percentage: `floor((token_limit - token_count) / token_limit * 100)` |
| `hull_integrity_status` | string | One of `"Green"`, `"Amber"`, `"Red"`, `"Critical"` — see thresholds below |
| `relief_requested` | boolean | `true` when status is `"Red"` or `"Critical"`, `false` otherwise |
| `context_summary` | string | One-line description of current work (e.g. `"Implementing API endpoint for user search"`) |
| `report_path` | string | File path where this report is stored |

## Hull Integrity Thresholds

| Status | Remaining Capacity | Meaning |
|---|---|---|
| Green | 75 -- 100% | Operating normally |
| Amber | 60 -- 74% | Monitor closely |
| Red | 40 -- 59% | Relief on station recommended |
| Critical | Below 40% | Relief on station required |

## Notes

- Hull integrity represents remaining capacity, not usage. A ship at 75% hull integrity has used 25% of its context window.
- Set `relief_requested` to `true` when hull integrity drops to Red or Critical. The admiral uses this flag to prioritise relief on station.
- Update the report at each quarterdeck checkpoint or when hull integrity crosses a threshold boundary.
- The admiral reads all damage reports from `.claude/nelson/damage-reports/` to build the squadron readiness board.

## Read-Only Agent Variant

Agents spawned with `subagent_type="Explore"` (Navigating Officer, Coxswain, Recce Marines) are read-only — they cannot write files, including damage reports.

These agents report hull integrity via `SendMessage` to their captain. The captain writes the damage report JSON on their behalf using the same template and field definitions above.

If the read-only agent is a Recce Marine reporting directly to a captain, the captain includes the marine's hull integrity in their own damage report under `context_summary`.
