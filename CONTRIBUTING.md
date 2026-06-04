# Contributing

Thanks for your interest in contributing to Nelson.

## How to contribute

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Open a pull request

## What to contribute

Bug fixes, improvements to the skill instructions or templates, documentation fixes, and new ideas are all welcome. If you're thinking about a larger change, open an issue first so we can discuss it.

## Skill structure

The skill lives in `.claude/skills/nelson/`. The key files:

- `SKILL.md` — Main skill instructions (the entrypoint Claude reads)
- `references/` — Supporting docs loaded on demand (risk tiers, templates, team sizing)
- `agents/` — Agent interface definitions

## Local development

The repo ships AI-targeted sensors (linter, formatter, pre-commit hooks,
secret scanner) so the same checks run locally and in CI. Set them up
once after cloning:

```bash
# Install pre-commit hooks (runs on every `git commit`)
pre-commit install
```

Day-to-day commands:

```bash
ruff check                              # Lint with AI-targeted thresholds
ruff format                             # Apply formatting
pre-commit run --all-files              # Run every hook on every file
pytest skills/nelson/scripts/ -v        # Tests — one directory at a
pytest hooks/ -v                        #   time (each dir has its
pytest scripts/ -v                      #   own conftest.py)
```

See [CLAUDE.md](./CLAUDE.md) → *Maintainability sensors* for the
suppress-with-reason and bump-threshold conventions. If a sensor
disagrees with you, propose the threshold change rather than reaching
for `--no-verify`.

## Development tooling (optional)

Nelson's development uses [beads](https://github.com/gastownhall/beads) for dependency-aware task tracking across agent sessions. Beads is **not required** — you can contribute without it.

If you'd like to use it:

```bash
# Install beads CLI (global, one-time)
brew install beads

# Initialize in your local clone
bd init --stealth

# Set up Claude Code integration
bd setup claude
```

`--stealth` keeps beads local-only — no files are committed to the repo. The `.beads/` directory is gitignored.

Beads is a development aid for Nelson contributors. It is not a dependency of the Nelson skill and Nelson users are never exposed to it.

## Guidelines

- Keep things simple and clear
- Test your changes by installing the skill locally and running a mission
- Follow the existing style and tone
