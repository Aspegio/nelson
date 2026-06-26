# Battle Plan Template

The rendered plan lives at `{mission-dir}/battle-plan.md` and is the prose authority for the mission — commander's intent and per-task briefs. The structured form at `{mission-dir}/battle-plan.json` is the execution-data authority (owners, dependencies, station tiers, file ownership). Keep them aligned: edit one, mirror the change in the other.

Every captain's brief opens with the commander's intent from the Estimate (§2) — one paragraph, verbatim. This is how each ship sails under a shared understanding of purpose.

```text
Commander's intent:
[One paragraph from the Estimate §2 — prepended to every captain's brief.]

Workflow suitability:
[For non-workflow modes: one line explaining why workflow was not selected.]

Workflow Charter: [include only when mode is workflow or hybrid-workflow]
- Execution primitive: [workflow | hybrid-workflow]
- Suitability: [why scripted orchestration is appropriate]
- Phases: [probe/full run/stage names and purposes]
- Human gates: [approval required before/after stages]
- Verification contract: [how findings or edits become accepted]
- Cost guardrail: [probe, scope cap, token/time limit, stop trigger]
- Fallback mode: [agent-team | single-session]

Task ID:
- Name:
- Owner: [assigned at Step 4 — Form the Squadron]
- Ship (if crewed): [assigned at Step 4 — Form the Squadron]
- Crew manifest (if crewed):
- Deliverable:
- Dependencies:
- Station tier (0-3):
- File ownership (if code):
- Modification targets (if extending): [specific functions, env vars, config to modify — not replace. Omit for greenfield tasks.]
- Acceptance criteria (inherited from effect):
  - [Criterion 1 — captain chooses verification method: test | type-check | lint | review | visual]
  - [Criterion 2 — ...]
- Validation required:
- Rollback note required: yes/no
- admiralty-action-required: yes/no
  - action: [one sentence — what the human must do]
  - timing: before this task starts | after this task completes
  - blocks: [task name or "stand-down"]
```

**Modification targets.** When a task extends existing code, the `Modification targets` field anchors the captain to specific functions, variables, and configuration that must be modified in place. This field flows from the Estimate's Reconnaissance (Q1) and Terrain (Q4) — if those questions identified the existing code, the Battle Plan must preserve that specificity. Omit the field for greenfield tasks where no existing code is being extended.

**Acceptance criteria inheritance.** Each task inherits the acceptance criteria of its parent effect from the Estimate (§3). Captains own the choice of verification method per criterion (test, type-check, lint, review, or visual). The quarterdeck records each outcome (`pass` / `fail` / `not-verified`) via `nelson-data.py estimate-outcome`.

JSON schema note: the battle-plan `task` object accepts an optional `acceptance_criteria: list[str]` field carrying the inherited criteria. This enables programmatic aggregation of verification outcomes. The `task` object also accepts an optional `modification_targets: list[str]` field for tracking the functions, environment variables, or configuration that must be modified in place.

**Workflow advisory fields.** The top-level battle-plan object may include optional planning fields: `execution_primitive`, `workflow_suitability`, `workflow_phases`, `human_gates`, `verification_contract`, `cost_guardrail`, `fallback_mode`, and `workflow`. These are advisory in v1. They document the workflow charter and gates; they do not generate runnable `.claude/workflows/*.js` files.

**`admiralty-action-required`:** Mark `yes` for any task where a step cannot be completed by an agent — requires the human to interact with an external system, provide credentials or URLs, or take an action only the human can perform. Fill this field consciously for every task; leaving it blank is a claim that the task requires no human action. When marked `yes`, the admiral will surface this in the Admiralty Action List before agents launch, and the captain will invoke the `awaiting-admiralty` standing order when the step is reached.

**Note on `blocks:` field:** The `blocks:` value names the task that cannot proceed until the human acts. The Admiralty Action List displays this as `unblocks:` — same task name, inverted label.
