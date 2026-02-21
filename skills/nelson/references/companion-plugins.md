# Companion Plugin Ecosystem

Nelson core provides the operational framework — sailing orders, squadron composition, quarterdeck rhythm, action stations, and damage control. Companion plugins extend this framework for specific domains, organisations, or workflows without modifying core files. The core stays lean; extensibility lives in the fleet auxiliary.

## Core Principle

Nelson follows a ship-and-shore model. The core skill is the ship: self-contained, seaworthy, and opinionated about how missions are run. Companion plugins are the shore establishment: they supply provisions, specialist personnel, and intelligence that the ship draws upon as needed.

A companion plugin may add references, templates, standing orders, and hook scripts. It must not alter or override core Nelson files. If a companion plugin conflicts with a core instruction, the core instruction prevails.

## Planned Companion Plugins

### nelson-templates

Pre-built battle plans for common mission types. Each template provides a ready-made battle plan structure — sailing orders, squadron composition, crew assignments, and verification criteria — that the admiral can adopt or adapt.

**Included templates:**

- **API Development** — Endpoint-per-ship decomposition with contract-first crew roles.
- **Refactoring** — Incremental transformation with red-cell verification at each stage.
- **Documentation** — Parallel authoring with cross-reference consistency checks.
- **Migration** — Phased cutover with rollback checkpoints and compatibility verification.

### nelson-crew-library

Organisation-specific crew roles and standing orders. Extends the base crew roles from `crew-roles.md` with domain-specific definitions, custom anti-patterns, and tailored standing orders.

**Use cases:**

- Define custom crew roles for specialised domains (e.g., ML Engineer, Data Steward, Security Analyst).
- Add organisation-specific standing orders that reflect internal coding standards or review practices.
- Package domain-specific anti-patterns so captains receive relevant warnings without cluttering the core standing orders.

### nelson-integrations

Hooks for external tools that connect Nelson's operational rhythm to existing project management and communication systems.

**Planned integrations:**

- **Jira** — Sync battle plan tasks to Jira issues. Update issue status when captains mark tasks complete.
- **GitHub Projects** — Mirror the battle plan as a GitHub Project board. Link ships to project columns.
- **Slack** — Post quarterdeck reports to a designated channel. Surface damage reports and blocker alerts.

Integration hooks run as companion hook scripts (see `event-driven-hooks.md`) and write to external APIs. They do not alter Nelson's internal coordination model.

### nelson-metrics

Dashboard generation from captain's logs. Aggregates the squadron metrics defined in `squadron-metrics.md` across multiple missions to build a longitudinal performance picture.

**Capabilities:**

- Parse captain's log entries and extract metric values.
- Generate per-mission and cross-mission summary reports.
- Identify trends in coal consumption, homecoming rate, and seaworthiness index over time.
- Output reports as markdown files suitable for inclusion in project documentation.

## Plugin Structure

Each companion plugin follows the standard Claude Code plugin manifest structure. A minimal companion plugin contains:

```
nelson-templates/
  .claude-plugin/
    plugin.json             — Plugin manifest (name, version, description)
    marketplace.json        — Marketplace listing (if published)
  skills/nelson-templates/
    SKILL.md                — Entrypoint describing the plugin's purpose
    references/             — Additional reference documents
    templates/              — Battle plan templates or other assets
```

**Rules for companion plugins:**

1. The plugin manifest must declare Nelson core as a dependency.
2. All files live under the companion plugin's own namespace. No files are placed in Nelson core's directory tree.
3. References added by a companion plugin are loaded on demand, the same as core references.
4. Companion plugins may add hook scripts under their own `.claude/nelson/hooks/` namespace.
5. Standing orders added by a companion plugin must not contradict core standing orders.

## Installation

Companion plugins install via the Claude Code plugin marketplace, the same as Nelson core.

```
/plugin install nelson-templates
/plugin install nelson-crew-library
/plugin install nelson-integrations
/plugin install nelson-metrics
```

To install from a specific repository before marketplace publication:

```
/plugin install <owner>/nelson-templates
```

## Development Guide

To create a new companion plugin:

1. **Scaffold the directory structure** following the layout above. Use the companion plugin's name as the top-level directory.
2. **Write the plugin manifest** in `.claude-plugin/plugin.json`. Include `name`, `version`, `description`, and a `dependencies` field listing `nelson` as a required plugin.
3. **Write the SKILL.md entrypoint.** Describe what the plugin provides and how it extends Nelson core. Reference any new documents in the `references/` directory.
4. **Add references and templates.** Follow the same conventions as Nelson core: H1 title, intro paragraph, H2 sections, Royal Navy tone.
5. **Test locally.** Symlink the plugin into your `.claude/skills/` directory and verify that Nelson can load its references on demand.
6. **Publish.** Create a GitHub repository, add a `marketplace.json`, and register with the Claude Code plugin marketplace.

## Cross-References

- `event-driven-hooks.md` — Hook system that companion plugins can extend with additional hook scripts.
- `squadron-metrics.md` — Metric definitions that nelson-metrics aggregates across missions.
