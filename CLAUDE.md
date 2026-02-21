# Nelson

Nelson is a Claude Code skill for coordinating agent work using Royal Navy terminology. It provides a six-step operational framework: Sailing Orders, Form the Squadron, Battle Plan, Quarterdeck Rhythm, Action Stations, and Stand Down.

## Project structure

```
.claude-plugin/
  plugin.json             — Plugin manifest
  marketplace.json        — Marketplace definition (self-hosted)
skills/nelson/
  SKILL.md                — Main entrypoint (what Claude reads)
  references/             — Supporting docs loaded on demand
    action-stations.md      — Risk tier definitions (Station 0–3)
    admiralty-templates/     — One file per template, loaded on demand
      battle-plan.md          — Task assignment template
      captains-log.md         — End-of-mission log with plan-vs-reality delta
      crew-briefing.md        — Teammate briefing template
      damage-report.md        — JSON template for hull integrity damage reports
      marine-deployment-brief.md — Royal Marines deployment brief
      quarterdeck-report.md   — Headline-format checkpoint report
      red-cell-review.md      — Red-cell review template
      sailing-orders.md       — Mission sailing orders template
      ship-manifest.md        — Ship crew manifest template
      turnover-brief.md       — Handover brief for relief on station
    broadside-quality-gates.md — Synchronised quality gates across all ships
    commendations.md        — Recognition signals & graduated correction
    companion-plugins.md    — Companion plugin ecosystem specification
    crew-roles.md           — Crew role definitions, ship names & sizing rules
    damage-control/         — One file per procedure, loaded on demand
      bulkhead-doctrine.md    — Per-ship token budgets & cascading failure containment
      colours-struck.md       — Graceful degradation between success and abort
      crew-overrun.md         — Crew consuming disproportionate resources
      escalation.md           — Authority escalation procedure
      hull-integrity.md       — Material conditions (XRAY/YOKE/ZEBRA) & readiness board
      man-overboard.md        — Unresponsive or looping agent recovery
      partial-rollback.md     — Rolling back a single faulty task
      relief-on-station.md    — Planned ship replacement for context exhaustion
      scuttle-and-reform.md   — Full mission abort and reform
      session-hygiene.md      — Clean start procedure for new sessions
      session-resumption.md   — Resuming an interrupted session
      soundings.md            — Proactive budget cliff detection between checkpoints
    dynamic-task-ledger.md  — Living battle plan (Magentic-One pattern)
    event-driven-hooks.md   — Claude Code hooks for automated damage control
    red-cell-challenge-library.md — Domain-specific failure patterns for reviews
    royal-marines.md        — Royal Marines deployment rules & specialisations
    sailing-orders-wizard.md — Interactive sailing order creation guide
    squadron-composition.md — Mode selection & team sizing rules
    squadron-metrics.md     — Six RN-themed performance metrics
    standing-order-troubleshooter.md — Decision tree for identifying standing orders
    standing-orders/        — One file per anti-pattern, loaded on demand
      admiral-at-the-helm.md  — Admiral must not implement
      all-hands-on-deck.md    — Do not over-crew
      battalion-ashore.md     — Marines are not crew
      becalmed-fleet.md       — Do not parallelise sequential work
      captain-at-the-capstan.md — Captain must not implement when crewed
      chain-break.md          — Authority ambiguity
      circular-tides.md       — Circular dependencies / deadlock
      crew-without-canvas.md  — Do not add unnecessary agents
      crossing-signals.md     — Ambiguous orders
      cutting-the-line.md     — Bypassing low-priority blockers (tactical)
      drifting-anchorage.md   — Scope drift from sailing orders
      fraying-tether.md       — Silent quality degradation
      ghost-crews.md          — Duplicate work across agents
      press-ganged-navigator.md — Red-cell must not implement
      pressed-crew.md         — Crew working outside their role
      silent-watch.md         — Stale context
      skeleton-crew.md        — Do not spawn one crew for atomic tasks
      split-keel.md           — Do not share files between agents
      storm-surge.md          — Poor task decomposition
      tidal-pull.md           — Memory loss across handoffs
      unclassified-engagement.md — Tasks without risk tier classification
agents/                   — Agent interface definitions
demos/                    — Example applications built with Nelson
scripts/                  — Maintenance & utility scripts
  count-tokens.py           — Token counter for hull integrity damage reports
```

## No build system

This is a documentation-driven skill with zero runtime dependencies. There is no package manager, no build step, and no test suite.

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

## This Project Uses Beans to Manage Issues
**IMPORTANT**: before you do anything else, run the `beans prime` command and heed its output.