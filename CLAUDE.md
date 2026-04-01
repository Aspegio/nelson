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
  fleet-dashboard/          — Live web dashboard for mission visualisation
    index.html
    css/main.css
    css/components.css
    js/utils.js
    js/data-loader.js
    js/renderer.js
    js/app.js
    test/fixture.json
agents/                   — Agent interface definitions
demos/                    — Example applications built with Nelson
scripts/                  — Maintenance & utility scripts
  check-references.sh       — Cross-reference validation for documentation links
  count-tokens.py           — Token counter for hull integrity damage reports
  nelson-data.py            — Structured data capture for Nelson missions
  test_nelson_data.py       — Python tests for nelson-data.py
```

## Mission artifacts (runtime)

Each Nelson mission creates a timestamped directory for its artifacts:

```
.nelson/missions/{YYYY-MM-DD_HHMMSS}/
  captains-log.md         — Written at stand-down
  quarterdeck-report.md   — Updated at every checkpoint
  damage-reports/         — Ship damage reports (JSON)
  turnover-briefs/        — Ship turnover briefs (markdown)
```

Previous missions are preserved — each run gets its own directory.

## No build system

This is a documentation-driven skill with zero runtime dependencies. There is no package manager and no build step. The `nelson-data.py` script uses Python stdlib only. Tests run via `pytest skills/nelson/scripts/test_nelson_data.py -v`.

## Testing changes

Install the plugin and run a mission to verify:

```
/plugin install harrymunro/nelson
```

Or add the marketplace first, then install:

```
/plugin marketplace add harrymunro/nelson
/plugin install nelson
```

For local development in this repo, the symlink at `.claude/skills/nelson` → `../../skills/nelson` means `/nelson` works automatically.

Then invoke `/nelson` in Claude Code.

## Code style

- Keep instructions simple and clear
- Follow the existing Royal Navy tone and terminology
- Markdown for all documentation; YAML for agent interfaces
- The battleships demo (`demos/battleships/index.html`) uses vanilla HTML/CSS/JS with no dependencies

## Git workflow

- Branch from `main`
- Commit messages: imperative mood, concise summary line
- Open a PR for review

## Releasing

After merging to `main`:

1. Bump the `version` field in both `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` to match the new release tag.
2. Commit and push the version bump to `main`.
3. Create a GitHub release with `gh release create vX.Y.Z --target main`.
4. Update the file tree in this file and in `README.md` if new files were added.

Plugin installs are cached snapshots — they do not auto-update. Users must re-install to pick up a new version:

```
/plugin install harrymunro/nelson
```

## Environment

`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` must be set to enable the `agent-team` execution mode (configured in `.claude/settings.local.json`).
