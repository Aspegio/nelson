# Crew Roles Reference

Use this file to decide whether a captain should crew a ship or implement directly, and which roles to muster.

## Crew-or-Direct Decision

Choose the first condition that matches.

1. If the task is atomic and can be completed in a single pass, captain implements directly (0 crew).
2. If the task has one clear deliverable with no research or testing needs, crew 1 PWO.
3. If the task needs exploration, testing, or a second specialism, crew PWO + 1 specialist.
4. If the task has multiple interdependent sub-tasks, crew XO + PWO + up to 2 specialists.

Never exceed 4 crew per ship. If the task demands more, split it into two ships.

## Crew Sizing

| Crew Size | When | Typical Manifest |
|---|---|---|
| 0 | Atomic task, single-pass fix | Captain implements directly |
| 1-2 | Typical task | PWO, optionally + 1 specialist |
| 3 | Complex task with research or testing needs | PWO + 2 specialists |
| 4 | Multi-part task requiring internal orchestration | XO + PWO + 2 specialists |

## Role Definitions

| Role | Abbr | Function | subagent_type | cost-weight | When to Crew |
|---|---|---|---|---|---|
| Executive Officer | XO | Integration & orchestration across sub-tasks | general-purpose | 10 | 3+ crew or interdependent sub-tasks |
| Principal Warfare Officer | PWO | Core implementation work | general-purpose | 2 | Almost always (default doer) |
| Navigating Officer | NO | Codebase research & exploration | Explore | 7 | Unfamiliar code, large codebase |
| Marine Engineering Officer | MEO | Testing & validation | general-purpose | 6 | Station 1+ or non-trivial verification |
| Weapon Engineering Officer | WEO | Config, infrastructure, systems integration | general-purpose | 6 | Significant config or infrastructure work |
| Logistics Officer | LOGO | Documentation & dependency management | general-purpose | 2 | Docs as deliverable, dependency management |
| Coxswain | COX | Standards review & quality enforcement | Explore | 4 | Station 1+ with established conventions |

### Read-Only Roles

NO and COX use the `Explore` subagent type. They cannot modify files. They report findings to the captain or XO, who decides how to act on them.

### Role Boundaries

Each crew member works strictly within their role definition. A PWO does not run tests (that is the MEO). A NO does not write code (they report findings). See standing order `standing-orders/pressed-crew.md` for the anti-pattern.

## Ship Name Registry

Admiral assigns a ship name to each captain during squadron formation. Choose names that roughly match task weight.

### Frigates (general-purpose tasks)

Argyll, Kent, Lancaster, Richmond, Somerset, Portland, Iron Duke, St Albans

### Destroyers (high-tempo or high-risk tasks)

Daring, Dauntless, Diamond, Dragon, Defender, Duncan

### Patrol Vessels (small tasks)

Forth, Medway, Trent, Tamar, Spey

### Historic Flagships (critical-path tasks)

Victory, Warspite, Vanguard, Ark Royal

### Submarines (stealth or research tasks)

Astute, Ambush, Artful, Audacious

## Crew Standing Orders

The following standing orders apply specifically to crew operations:

- `standing-orders/captain-at-the-capstan.md` — Captain must not implement when crew are mustered.
- `standing-orders/all-hands-on-deck.md` — Do not crew roles the task does not need (too many crew).
- `standing-orders/skeleton-crew.md` — Do not spawn a single crew member for an atomic task (too few crew).
- `standing-orders/pressed-crew.md` — Do not assign crew work outside their designated role (wrong crew).

## Royal Marines

Marines are NOT crew. They are short-lived sub-agents a captain deploys for discrete objectives outside the crew's task scope. See `references/royal-marines.md` for deployment rules and specialisations.

Key distinction: Crew subdivide the ship's deliverable. Marines execute independent sorties in support of the ship's task.
