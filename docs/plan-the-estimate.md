# Plan: The Estimate

**Date:** 2026-04-16
**Status:** Draft
**Author:** Admiralty design session

---

## 1. Executive Summary

Nelson currently moves from Sailing Orders directly to Battle Plan. The admiral receives a mission brief, then immediately decomposes it into parallel tasks and agent assignments. This works, but it skips a deliberate analytical phase — the kind of structured thinking that separates a considered plan from a reactive one.

The Royal Navy's **7 Question Maritime Tactical Estimate (7QMTE)** is the British military's core planning framework. Used at every scale from eight-person sections to twenty-thousand-strong divisions, it drives analytical rigour through seven sequential questions that build on each other. Nelson the admiral used a version of this process to produce his Trafalgar Memorandum — the document that gave every captain enough understanding of his intent to act independently when communications broke down.

This plan introduces **The Estimate** as a new phase between Sailing Orders and Battle Plan.

### The revised operational flow

```
Sailing Orders → The Estimate → Battle Plan → Form Squadron → Quarterdeck → Stand Down
```

### Why this matters

- The Battle Plan currently does both analysis and task decomposition in one step. The Estimate separates *thinking* from *organising*, making both sharper.
- Acceptance criteria defined during The Estimate flow through the entire pipeline — captains know what "done" looks like, the quarterdeck can verify objectively, and review passes have concrete criteria rather than vibes.
- Intent propagation becomes explicit. Each agent receives the commander's intent, enabling independent judgement when plans meet reality.
- The Estimate is the first mechanism by which Nelson can *measure* whether its output meets its spec — the beginning of evidence-based confidence in the framework.

---

## 2. Research Basis

### Royal Navy doctrine

The 7 Question Maritime Tactical Estimate is taught on the Royal Navy's Integrated Maritime Mission Planning (IMMP) course. The questions are numbered, not named; they drive a thought process rather than demand slavish adherence. The framework scales naturally — shorter answers for simpler missions, deeper analysis for complex ones.

Nelson's Trafalgar Memorandum (9-10 October 1805) is the historical exemplar of this thinking in action. Its distinctive qualities: simple enough that every captain understood the intent, explicitly anticipated chaos ("nothing is sure in a sea fight"), and delegated autonomy to column commanders who could improvise within a shared understanding of purpose.

### State of the art in AI agent quality

Research conducted on 16 April 2026 across four parallel investigations (TDD for AI agents, BDD for AI workflows, evaluation frameworks, and plan-then-verify patterns) revealed convergence on three principles:

1. **Spec-first development.** The dominant emerging pattern. Write a specification, derive acceptance criteria, then build against them. Agents that work from specs outperform those that generate code from bare instructions.

2. **Write-run-verify loops.** SWE-bench data is unambiguous: agents that run tests and iterate dramatically outperform one-shot generation. Trajectory quality — the full sequence of decisions, not just the final output — is the differentiator.

3. **Layered verification.** No single check is sufficient. The industry is converging on defence-in-depth: spec first, appropriate verification method per criterion, review agent second pass, automated pre-commit gates.

A notable gap identified in the BDD research: Gherkin-style specifications are being used as *input* to AI agents (structured prompts that reduce ambiguity), but no framework has yet bridged the gap to using them as **formal acceptance gates in agent pipelines**. The Estimate's acceptance criteria on effects are designed to close this loop.

---

## 3. Design

### 3.1 The seven questions

The Royal Navy uses bare numbers. We name them for clarity.

| # | Name | What it answers |
|---|------|-----------------|
| 1 | **Reconnaissance** | What is the terrain? What are we working with? |
| 2 | **Intent** | What are we really trying to achieve, and why? |
| 3 | **Effects** | What changes must occur to fulfil the intent? |
| 4 | **Terrain** | Where in the codebase does each effect land? |
| 5 | **Forces** | What agents, models, and context do we need? |
| 6 | **Coordination** | What depends on what? What runs in parallel? |
| 7 | **Control** | Where are the quality gates and intervention points? |

### 3.2 The interactive flow

The Estimate is a conversation between the admiral and the user, not a monologue. But it respects the user's time.

**Q1 (Reconnaissance)** is the only question that dispatches sub-agents. The admiral sends one or more Explore agents into the codebase with a scouting brief derived from the Sailing Orders. For complex or ambiguous terrain, multiple Explore agents may be dispatched in parallel with different search targets. The admiral synthesises their reports into a terrain assessment.

**Checkpoint 1 — after Q1.** The admiral presents findings to the user: *"Here is what I found. Is there anything I have missed? Are there additional constraints I should know?"* This is also the natural point for **mission reframing** — if reconnaissance reveals the stated mission will not achieve the user's actual intent, the admiral says so plainly and proposes a reframing. The user confirms, amends, or overrides. If the mission is reframed, the Sailing Orders are amended with the original preserved as context.

**Q2-Q3 (Intent, Effects)** are analytical. The admiral reasons from Q1 findings combined with the Sailing Orders, deriving the commander's intent and the effects needed to fulfil it.

**Checkpoint 2 — after Q3.** The admiral presents intent and effects (with acceptance criteria and commander's guidance): *"Here is what I believe needs to happen and why. Does this match your understanding?"* This is the substantive gate — the user is approving *what* will be done before the admiral plans *how*.

**Q4-Q7 (Terrain, Forces, Coordination, Control)** flow from the approved effects. These are the admiral's professional judgement about execution. The admiral works through them without interrupting the user.

**Final review.** The admiral presents the complete estimate. The user approves, requests amendments, or overrides specific questions. Upon approval, the phase advances from `ESTIMATE` to `BATTLE_PLAN`.

**Checkpoint discipline.** Checkpoints are *available*, not *mandatory*. The admiral should read the room. If the Sailing Orders are precise and the terrain is familiar, the admiral may present the complete estimate in one pass rather than stopping twice. The two-checkpoint flow is the default for complex or ambiguous missions.

### 3.3 Output format

Seven markdown files in `{mission-dir}/estimate/`:

```
{mission-dir}/estimate/
  01-reconnaissance.md
  02-intent.md
  03-effects.md
  04-terrain.md
  05-forces.md
  06-coordination.md
  07-control.md
```

The admiral writes these as a confident, thoughtful briefing — not as auto-generated documentation. Concise but never terse. Clear but never flat. The kind of prose a capable officer would want to read before going into action.

Cross-references between questions use natural prose, not IDs or schemas. The Battle Plan step reads the estimate in context; it is the same admiral reading its own work.

### 3.4 Effects, acceptance criteria, and commander's guidance

Each effect in `03-effects.md` carries three elements:

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
- **Commander's guidance** states how it should be done (design decisions, library choices, patterns). This is where implementation direction lives — specific enough to prevent wrong turns, loose enough to allow professional judgement.
- **Acceptance criteria** state what must be true when the effect is complete. Each criterion must have an appropriate verification method. Not every criterion demands a unit test — existing test suites, type-checkers, linters, review agents, and visual inspection are all valid verification methods depending on the nature of the work.

Acceptance criteria flow through the pipeline:

1. **Battle Plan** — each task inherits criteria from its parent effect.
2. **Captains** — know what "done" looks like before writing a line of code. Choose the appropriate verification method for each criterion.
3. **Quarterdeck** — verifies that every criterion has been addressed and reports the verification method used.

### 3.5 Intent propagation

The admiral writes a short **commander's intent** paragraph during Q2. This paragraph is carried into every agent's task brief — prepended to their assignment so they understand *why* they are doing the work, not just *what*.

This mirrors Nelson's practice before Trafalgar: one memorandum, shared with every captain, so that when signals could not be read through the smoke, each officer could improvise within a shared understanding of purpose.

### 3.6 Adaptive planning

The Estimate is a living document, not a contract. When the admiral or a captain encounters something that contradicts the estimate — a file more complex than expected, a dependency not apparent, an approach that proves unworkable — the admiral amends the relevant estimate file with a dated addendum:

```markdown
## Addendum — 14:32

Reconnaissance assumed `src/auth/session.ts` was a single-concern module.
In practice it also owns refresh token rotation and rate-limit state.
Effects revised: the original signing effect now splits into two.
Coordination updated accordingly.
```

The original reasoning stays visible. The course correction is explicit. Downstream plans adjust.

### 3.7 Opt-in and scaling

The admiral asks after capturing the Sailing Orders:

> *"Shall I carry out The Estimate before drafting the Battle Plan? I would recommend it for this mission — [brief reason]."*

The recommendation should be honest. For straightforward missions with clear scope, the admiral recommends proceeding. For complex, ambiguous, or multi-system missions, the admiral recommends The Estimate. The skill frontmatter should frame Nelson as a tool for work that warrants this level of coordination — if the task is trivial enough that The Estimate is overkill, Nelson itself is likely overkill.

When The Estimate is conducted for simpler missions, the admiral writes shorter answers. The seven questions are always followed; the depth scales with the mission.

### 3.8 How the Battle Plan simplifies

With The Estimate in place, the Battle Plan no longer performs analytical work. It inherits:

- **Terrain mapping** from Q4 (file ownership is already identified)
- **Dependency graph** from Q6 (coordination is already sequenced)
- **Risk assessment** from Q7 (control measures are already defined)
- **Resource planning** from Q5 (agent models and counts are already proposed)

The Battle Plan step reduces to: translate effects into task assignments, assign captains, apply standing order checks. The standing order gate remains — it catches structural problems in the *assignment*, not in the *analysis*.

---

## 4. Implementation

### 4.1 Phase engine

Add `ESTIMATE` to the phase sequence in `nelson-phase.py`, between `SAILING_ORDERS` and `BATTLE_PLAN`. The phase advances on user approval of the complete estimate.

### 4.2 Reference document

Create `skills/nelson/references/the-estimate.md` containing the seven questions, the interactive flow, checkpoint guidance, the acceptance criteria format, the style direction, and the adaptive planning protocol. This is what the admiral reads when conducting The Estimate.

### 4.3 SKILL.md changes

Insert The Estimate as a new step between the current steps 1 (Sailing Orders) and 2 (Battle Plan). Update the Sailing Orders step to include the opt-in prompt. Update the Battle Plan step to reference the estimate and remove analytical work that moves into The Estimate.

### 4.4 Estimate template

Create `skills/nelson/references/admiralty-templates/estimate.md` with the directory structure and per-question templates. Light scaffolding, not fill-in-the-blanks — the admiral writes prose, not forms.

### 4.5 Battle Plan template updates

Update `skills/nelson/references/admiralty-templates/battle-plan.md` to include commander's intent propagation and acceptance criteria inheritance from effects.

### 4.6 Voice and style

Encode in the reference document, not buried in templates. A short section setting the standard: *write like a commander who respects the reader's time and intelligence.* Nelson's prose should be a distinguishing quality of the tool, not an afterthought.

---

## 5. Honest Caveats

- **The Estimate adds time.** For missions where the admiral already knows the answers, it risks being bureaucracy in a tricorn hat. The opt-in mechanism and scaling by depth are the mitigations, but we should watch for this in practice.
- **Interactive checkpoints tax the user.** The admiral must read the room and collapse checkpoints when the user's brief is precise.
- **Nelson's core value proposition is unproven.** The Estimate's acceptance criteria are the first mechanism by which we can measure whether output meets spec. This data matters more than the feature itself.
- **The real problems will surface in use.** This design is considered but theoretical. Ship a clean minimal version, run it on live missions, and iterate.

---

## 6. Acceptance Criteria for This Feature

- [ ] The phase engine accepts `ESTIMATE` as a valid phase between `SAILING_ORDERS` and `BATTLE_PLAN`, and transitions correctly in both directions
- [ ] The admiral offers The Estimate after Sailing Orders with an honest recommendation
- [ ] Q1 dispatches at least one Explore agent and synthesises findings into `01-reconnaissance.md`
- [ ] The admiral presents findings after Q1 and pauses for user input (checkpoint 1)
- [ ] Mission reframing is possible at checkpoint 1 — Sailing Orders can be amended with original preserved
- [ ] Q3 produces effects with commander's guidance and verifiable acceptance criteria
- [ ] The admiral presents intent and effects after Q3 and pauses for user input (checkpoint 2)
- [ ] Commander's intent paragraph propagates into every agent's task brief during Battle Plan
- [ ] Acceptance criteria from effects carry into Battle Plan task assignments
- [ ] The quarterdeck verifies completion against acceptance criteria, not subjective assessment
- [ ] Estimate files are amendable with dated addenda when new information surfaces
- [ ] The Battle Plan step no longer duplicates analytical work covered by The Estimate
- [ ] All seven markdown files are written in the estimate directory within the mission directory
- [ ] Existing Nelson missions without The Estimate continue to function (backwards compatible)
- [ ] Tests cover the phase engine changes
