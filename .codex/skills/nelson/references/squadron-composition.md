# Squadron Composition Reference

Use this file to choose execution mode and team size.

## Mode Selection

Choose the first condition that matches.

1. If work is sequential, tightly coupled, or mostly in the same files, use `single-session`.
2. If work is parallel but each worker only needs to report to admiral, use `subagents`.

## Decision Matrix

| Condition | Preferred Mode | Why |
| --- | --- | --- |
| Single critical path, low ambiguity | `single-session` | Lowest coordination overhead |
| Parallel discovery, synthesis by admiral | `subagents` | Fast throughput without peer chatter |
| Parallel implementation with dependencies | `subagents` + integration checkpoints | Keep ownership clear and coordinate merges explicitly |
| High threat or high blast radius | `subagents` + red-cell navigator | Adds explicit control points |

## Team Sizing

- Small mission: `1 admiral + 2-3 captains`.
- Medium mission: `1 admiral + 4-5 captains`.
- Large mission: `1 admiral + 6-7 captains`.
- Add `1 red-cell navigator` at medium/high threat.
- Keep one admiral only.
- Squadron cap: 10 squadron-level agents (admiral, captains, red-cell navigator). Crew are additional — up to 4 per captain, governed by `references/crew-roles.md`.

## Role Guide

- `admiral`: Defines sailing orders, delegates, tracks dependencies, resolves blockers, final synthesis.
- `captain`: Commands a ship. Breaks task into sub-tasks, crews roles, coordinates crew, verifies outputs. Implements directly only when the task is atomic (0 crew).
  - Crew roles: Executive Officer (XO), Principal Warfare Officer (PWO), Navigating Officer (NO), Marine Engineering Officer (MEO), Weapon Engineering Officer (WEO), Logistics Officer (LOGO), Coxswain (COX). See `references/crew-roles.md` for role definitions and crewing rules.
- `red-cell navigator`: Challenges assumptions, validates outputs, checks rollback readiness.

## Anti-Patterns

See `references/standing-orders.md` for the full list of standing orders and known anti-patterns.
