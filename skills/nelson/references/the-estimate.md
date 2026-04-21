# The Estimate

The analytical phase between Sailing Orders and Battle Plan. Read this when conducting The Estimate.

The Royal Navy's 7 Question Maritime Tactical Estimate drives the thinking that turns a mission brief into a plan worth executing. Nelson the admiral used a version of it to produce his Trafalgar Memorandum — the document that gave every captain enough understanding of his intent to act independently when the signal flags were lost in the smoke.

## Contents

- [The seven questions](#the-seven-questions)
- [Interactive flow](#interactive-flow)
- [Checkpoint discipline](#checkpoint-discipline)
- [Effects, acceptance criteria, and commander's guidance](#effects-acceptance-criteria-and-commanders-guidance)
- [Adaptive planning — dated addenda](#adaptive-planning--dated-addenda)
- [Voice and register](#voice-and-register)
- [Output](#output)

## The seven questions

| # | Name | What it answers |
|---|------|-----------------|
| 1 | **Reconnaissance** | What is the terrain? What are we working with? |
| 2 | **Intent** | What are we really trying to achieve, and why? |
| 3 | **Effects** | What changes must occur to fulfil the intent? |
| 4 | **Terrain** | Where in the codebase does each effect land? |
| 5 | **Forces** | What agents, models, and context do we need? |
| 6 | **Coordination** | What depends on what? What runs in parallel? |
| 7 | **Control** | Where are the quality gates and intervention points? |

The numbering carries a thought-process, not a form. Short answers for simple missions; deeper analysis for complex ones. Always seven questions.

## Interactive flow

The Estimate is a conversation between admiral and user, not a monologue. Respect the user's time.

**Q1 — Reconnaissance.** The only question that dispatches sub-agents. Send one or more Explore agents into the codebase with a scouting brief derived from the Sailing Orders. For ambiguous or unfamiliar terrain, dispatch them in parallel with different search targets. Synthesise their reports into a terrain assessment in your own voice. Do not paste raw agent output into the estimate.

**Checkpoint 1 — after Q1.** Present findings to the user:

> *"Here is what I found. Is there anything I have missed? Are there additional constraints I should know?"*

This is also the natural point for **mission reframing**. If reconnaissance reveals the stated mission will not achieve the user's actual intent, say so plainly and propose a reframing. The user confirms, amends, or overrides. If the mission is reframed, amend `sailing-orders.json` and preserve the original as context.

**Q2 — Intent.** Reason from Q1 findings and the Sailing Orders. Derive the commander's intent — one paragraph that will travel with every captain's brief.

**Q3 — Effects.** Decompose the intent into the concrete changes required. For each effect, draft commander's guidance and acceptance criteria (see below).

**Checkpoint 2 — after Q3.** Present intent and effects to the user:

> *"Here is what I believe needs to happen and why. Does this match your understanding?"*

This is the substantive gate — the user is approving *what* will be done before you plan *how*.

**Q4-Q7 — Terrain, Forces, Coordination, Control.** These flow from the approved effects and are the admiral's professional judgement about execution. Work through them without interrupting the user.

**Final review.** Present the complete estimate. The user approves, requests amendments, or overrides specific questions. On approval, advance the phase from `ESTIMATE` to `BATTLE_PLAN`.

## Checkpoint discipline

Checkpoints are *available*, not *mandatory*. Collapse to a single end-of-estimate review when **all three** conditions hold:

1. The Sailing Orders specify outcome, metric, and deadline.
2. Reconnaissance (Q1) reveals no surprises requiring reframing.
3. The work lands in a single subsystem or file.

Outside that narrow case, the two-checkpoint flow is the default. If in doubt, checkpoint.

## Effects, acceptance criteria, and commander's guidance

Each effect in the Effects section (Q3) carries three elements:

```markdown
### Effect: Replace session auth with JWT signing

Lands on `src/auth/session.ts`. High complexity.

**Commander's guidance:** Use the `jose` library, ES256 algorithm,
15-minute expiry with refresh rotation.

**Acceptance criteria:**
- All 47 existing auth tests pass without modification
- New unit tests cover token signing, verification, and expiry
- No runtime dependency on Redis for authentication
- Token payload contains only `sub`, `iat`, `exp` claims
```

- **The effect** states what must change (outcome-focused).
- **Commander's guidance** states how it should be done — library choices, patterns, design decisions. Specific enough to prevent wrong turns, loose enough to allow professional judgement.
- **Acceptance criteria** state what must be true when the effect is complete. Each criterion must have an appropriate verification method: existing test suites, type-checkers, linters, review agents, and visual inspection are all valid. Not every criterion demands a new unit test.

Acceptance criteria flow through the pipeline:

1. **Battle Plan** — each task inherits the criteria of its parent effect.
2. **Captains** — know what "done" looks like before writing a line of code. They pick the appropriate verification method per criterion.
3. **Quarterdeck** — verifies every criterion and records both outcome (`pass` / `fail` / `not-verified`) and method used via `nelson-data.py estimate-outcome`.

## Adaptive planning — dated addenda

The Estimate is a living document, not a contract. When you or a captain encounter something that contradicts the estimate — a file more complex than expected, a dependency not apparent, an approach that proves unworkable — amend the relevant section with a dated addendum:

```markdown
## Addendum — 14:32

Reconnaissance assumed `src/auth/session.ts` was a single-concern module.
In practice it also owns refresh token rotation and rate-limit state.
Effects revised: the original signing effect now splits into two.
Coordination updated accordingly.
```

The original reasoning stays visible. The course correction is explicit. Downstream plans adjust.

## Voice and register

Write as a capable officer briefing peers. Concise but never terse. Clear but never flat. Confident but never glib. Cross-references between questions use natural prose, not IDs or schemas — the Battle Plan step reads the estimate in context, and it is the same admiral reading its own work.

## Output

A single markdown file, `{mission-dir}/estimate.md`, with one H2 section per question:

```
{mission-dir}/estimate.md
  ## 1. Reconnaissance
  ## 2. Intent
  ## 3. Effects
  ## 4. Terrain
  ## 5. Forces
  ## 6. Coordination
  ## 7. Control
```

If a section grows unwieldy during a complex mission, split it into its own file at `{mission-dir}/estimate/0N-name.md` and leave a prose pointer in the parent. The default is one file — splitting is the exception, not the rule.

See `admiralty-templates/estimate.md` for the skeleton to work from.
