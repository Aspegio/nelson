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
    commendations.md        — Recognition signals & graduated correction
    crew-roles.md           — Crew role definitions, ship names & sizing rules
    damage-control/         — One file per procedure, loaded on demand
    royal-marines.md        — Royal Marines deployment rules & specialisations
    squadron-composition.md — Mode selection & team sizing rules
    standing-orders/        — One file per anti-pattern, loaded on demand
agents/                   — Agent interface definitions
demos/                    — Example applications built with Nelson
scripts/                  — Maintenance scripts
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

## Environment

`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` must be set to enable the `agent-team` execution mode (configured in `.claude/settings.local.json`).
