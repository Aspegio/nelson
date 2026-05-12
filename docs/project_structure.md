# Project Structure

```
.claude-plugin/
  plugin.json             — Plugin manifest
  marketplace.json        — Marketplace definition (self-hosted)
settings.json             — Plugin default settings (enables agent teams)
hooks/
  hooks.json              — Skill-scoped hook configuration (auto-discovered)
  nelson_hooks.py         — Hook enforcement script (preflight, brief, task, idle)
  conftest.py             — Shared test helpers
  test_nelson_hooks.py    — Tests for hook handlers
skills/nelson/
  SKILL.md                — Main entrypoint (what Claude reads)
  references/             — Supporting docs loaded on demand
    action-stations.md      — Risk tier definitions (Station 0–3)
    commendations.md        — Recognition signals & graduated correction
    crew-roles.md           — Crew role definitions, ship names & sizing rules
    model-selection.md      — Cost-optimized model assignment for agents
    royal-marines.md        — Royal Marines deployment rules & specialisations
    squadron-composition.md — Mode selection & team sizing rules
    structured-data.md      — Structured fleet data capture reference
    the-estimate.md         — 7 Question Maritime Tactical Estimate reference
    tool-mapping.md         — Nelson-to-Claude Code tool reference
    admiralty-templates/    — One file per template, loaded on demand
      battle-plan.md            — Battle plan with commander's intent and acceptance criteria
      captains-log.md           — Final mission report
      crew-briefing.md          — Per-captain deployment brief
      damage-report.md          — JSON template for hull integrity damage reports
      estimate.md               — Estimate skeleton (~25-line H2 scaffold)
      marine-deployment-brief.md — Royal Marines detachment briefing
      quarterdeck-report.md     — Checkpoint status report
      red-cell-review.md        — Adversarial review template
      sailing-orders.md         — Mission definition template
      ship-manifest.md          — Captain's crew plan template
      turnover-brief.md         — Handover brief for relief on station
    damage-control/         — One file per procedure, loaded on demand
      circuit-breakers.md       — Automated alarm thresholds for hull, budget, idle, blockers
      comms-failure.md          — Agent team infrastructure failure recovery
      crew-overrun.md           — Ship crew consuming disproportionate resources
      escalation.md             — Issue exceeds current authority or needs clarification
      hull-integrity.md         — Threshold definitions & squadron readiness board
      man-overboard.md          — Stuck agent replacement procedure
      partial-rollback.md       — Completed task found faulty, other tasks sound
      relief-on-station.md      — Planned ship replacement for context exhaustion
      scuttle-and-reform.md     — Mission cannot succeed, abort and reform
      session-hygiene.md        — Clean start procedure for new sessions
      session-resumption.md     — Resuming an interrupted session
    standing-orders/        — One file per anti-pattern, loaded on demand
.nelson/
  memory/                   — Cross-mission memory store (auto-created)
    patterns.json             — Accumulated pattern library (adopt/avoid)
    standing-order-stats.json — Violation frequency and correlation data
agents/                   — Agent interface definitions
demos/                    — Example applications built with Nelson
docs/                     — Project documentation (this file lives here)
scripts/                  — Maintenance & utility scripts
  check-references.sh       — Cross-reference validation for documentation links
  count-tokens.py           — Token counter for hull integrity damage reports
  test_count_tokens.py      — Tests for the token counter
  conftest.py               — Shared test helpers
skills/nelson/scripts/    — Skill-level scripts (run by Nelson itself)
  nelson-data.py            — CLI entry point for Nelson data capture
  nelson-phase.py           — Deterministic phase engine for mission scaffolding
  nelson_data_utils.py      — Shared I/O, validation, and constants
  nelson_data_memory.py     — Cross-mission memory store and pattern library
  nelson_data_lifecycle.py  — Mission lifecycle commands (init through status)
  nelson_data_fleet.py      — Fleet intelligence and analytics commands
  nelson_data_patterns.py   — Learned standing orders pipeline (mine → score → synthesise)
  nelson_circuit_breakers.py — Automated alarm thresholds (hull, budget, idle, blockers)
  nelson_conflict_radar.py  — Cross-ship conflict detection
  nelson_conflict_scan.py   — Conflict scan CLI
  conftest.py               — Shared test helpers (pytest auto-discovery)
  test_nelson_data.py       — Lifecycle command tests
  test_nelson_data_fleet.py — Fleet intelligence and analytics tests
  test_nelson_data_memory.py — Memory store and I/O tests
  test_nelson_data_patterns.py — Learned standing orders pipeline tests
  test_nelson_circuit_breakers.py — Circuit breaker tests
  test_nelson_conflict_radar.py — Conflict radar tests
  test_nelson_conflict_scan.py — Conflict scan tests
  test_nelson_phase.py      — Phase engine tests
```
