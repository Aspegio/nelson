# Nelson

Nelson is a Claude Code skill for coordinating agent work using Royal Navy terminology. It provides a six-step operational framework: Sailing Orders, Form the Squadron, Battle Plan, Quarterdeck Rhythm, Action Stations, and Stand Down.

## Project structure

```
.claude-plugin/
  plugin.json             — Plugin manifest
  marketplace.json        — Marketplace definition (self-hosted)
settings.json             — Plugin default settings (enables agent teams)
skills/nelson/
  SKILL.md                — Main entrypoint (what Claude reads)
  references/             — Supporting docs loaded on demand
    action-stations.md      — Risk tier definitions (Station 0–3)
    admiralty-templates/     — One file per template, loaded on demand
      damage-report.md        — JSON template for hull integrity damage reports
      turnover-brief.md       — Handover brief for relief on station
    commendations.md        — Recognition signals & graduated correction
    crew-roles.md           — Crew role definitions, ship names & sizing rules
    damage-control/         — One file per procedure, loaded on demand
      comms-failure.md        — Agent team infrastructure failure recovery
      crew-overrun.md         — Ship crew consuming disproportionate resources
      escalation.md           — Issue exceeds current authority or needs clarification
      hull-integrity.md       — Threshold definitions & squadron readiness board
      man-overboard.md        — Stuck agent replacement procedure
      partial-rollback.md     — Completed task found faulty, other tasks sound
      relief-on-station.md    — Planned ship replacement for context exhaustion
      scuttle-and-reform.md   — Mission cannot succeed, abort and reform
      session-hygiene.md      — Clean start procedure for new sessions
      session-resumption.md   — Resuming an interrupted session
    model-selection.md      — Cost-optimized model assignment for agents
    royal-marines.md        — Royal Marines deployment rules & specialisations
    squadron-composition.md — Mode selection & team sizing rules
    structured-data.md      — Structured fleet data capture reference
    tool-mapping.md         — Nelson-to-Claude Code tool reference
    standing-orders/        — One file per anti-pattern, loaded on demand
.nelson/
  memory/                   — Cross-mission memory store (auto-created)
    patterns.json             — Accumulated pattern library (adopt/avoid)
    standing-order-stats.json — Violation frequency and correlation data
agents/                   — Agent interface definitions
demos/                    — Example applications built with Nelson
scripts/                  — Maintenance & utility scripts
  check-references.sh       — Cross-reference validation for documentation links
  count-tokens.py           — Token counter for hull integrity damage reports
  nelson-data.py            — CLI entry point for Nelson data capture
  nelson_data_utils.py      — Shared I/O, validation, and constants
  nelson_data_memory.py     — Cross-mission memory store and pattern library
  nelson_data_lifecycle.py  — Mission lifecycle commands (init through status)
  nelson_data_fleet.py      — Fleet intelligence and analytics commands
  conftest.py               — Shared test helpers (pytest auto-discovery)
  test_nelson_data.py       — Lifecycle command tests
  test_nelson_data_fleet.py — Fleet intelligence and analytics tests
  test_nelson_data_memory.py — Memory store and I/O tests
```
