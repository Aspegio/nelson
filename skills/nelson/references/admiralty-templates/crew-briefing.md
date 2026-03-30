# Crew Briefing Template

When spawning each captain, use the `Agent` tool (see `references/tool-mapping.md` for parameters by mode). Include this briefing in their prompt. Teammates do not inherit the lead's conversation context — they start with a clean slate and need explicit mission context to operate independently.

Target size: ~500 tokens. Enough for the teammate to work without asking clarifying questions, but not so much that it wastes their context window.

```text
== CREW BRIEFING ==
[Admiral — if this captain is assigned haiku: before sending, read
 references/model-selection.md and insert the three haiku briefing
 enhancement blocks here, then apply haiku tasking discipline to the
 task description below]
Mission: [mission name from sailing orders]
Your Role: Captain [N] — [role description]
Ship: [ship name from battle plan]
Your Task: [specific task from battle plan]
Deliverable: [what you must produce]
Action Station: [0-3] — [Patrol / Caution / Action / Trafalgar]
File Ownership: [files you own — no other agent should edit these]
Dependencies: [tasks that must complete before yours / tasks waiting on yours]
Mission Directory: [{mission-dir} absolute path — use for damage reports and turnover briefs]
Marine Capacity: [0-2, from ship manifest — omit line if 0]
Standing Orders:
- Do NOT implement work outside your assigned task scope
- Do NOT edit files not assigned to you
- If any part of your task is ambiguous, signal the admiral before implementing
- Report blockers to admiral immediately with options and one recommendation
- When done, report: deliverable, validation evidence, failure modes, rollback note
- File a damage report to {mission-dir}/damage-reports/{ship-name}.json when your task
  is complete or when hull integrity crosses a threshold (Green → Amber → Red → Critical).
  Use the JSON template from references/admiralty-templates/damage-report.md (fields: ship_name,
  timestamp, hull_integrity_pct, hull_integrity_status, relief_requested, context_summary).
  Estimate hull_integrity_pct from your token usage.
- You may deploy Royal Marines (short-lived sub-agents) for focused sorties.
  Deploy by calling the `Agent` tool with `subagent_type` (see `references/tool-mapping.md`).
  Recce Marine: `Agent` tool with `subagent_type=`"Explore" (read-only recon).
  Assault Marine / Sapper: `Agent` tool with `subagent_type=`"general-purpose".
  Include a deployment brief in the `Agent` prompt (template below).
  Station 2+ marine deployments require admiral approval first.
  Max 2 marines at a time. Marines cannot deploy marines.
- Marines are under your command: deploy at your discretion for Station 0-1 sorties.
  Station 2+: signal admiral and await approval before deploying. Do NOT use marines
  as a substitute for crew on sustained work.
- To muster or pay off crew mid-task, request admiral approval with a brief rationale
  before acting.
- If you reach a step requiring human action (admiralty-action-required: yes), invoke
  the awaiting-admiralty standing order: references/standing-orders/awaiting-admiralty.md
Marine Deployment Brief: use the full template at
  references/admiralty-templates/marine-deployment-brief.md — it includes model
  assignment guidance and haiku briefing requirements.
== END BRIEFING ==
```

## Field notes

- **Mission** — Copy verbatim from sailing orders so the teammate shares the same outcome/metric framing.
- **Ship** — From the ship manifest in the battle plan. Gives the teammate identity and signals task weight (frigate, destroyer, etc.).
- **File Ownership** — Critical for preventing merge conflicts when multiple agents work in parallel. If no files are assigned, note "No file ownership — research/analysis only."
- **Dependencies** — List both blocking (what must finish first) and blocked-by (what waits on this task). If none, note "Independent — no dependencies."
- **Mission Directory** — The absolute path to the current mission directory. Captains use this path when writing damage reports and turnover briefs.
- **Marine Capacity** — From the ship manifest. Tells the captain how many marines they may deploy (max 2). Omit if 0.
- **Standing Orders** — Keep these to 4-5 lines. Project-specific standing orders can be appended here. The marine standing order tells captains they CAN deploy marines and where to find the rules — without this, captains have no knowledge of marines.
