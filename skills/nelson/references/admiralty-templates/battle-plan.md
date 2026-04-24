# Battle Plan Template

Every captain's brief opens with the commander's intent from the Estimate (§2) — one paragraph, verbatim. This is how each ship sails under a shared understanding of purpose.

```text
Commander's intent:
[One paragraph from the Estimate §2 — prepended to every captain's brief.]

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

JSON schema note: the battle-plan `task` object accepts an optional `acceptance_criteria: list[str]` field carrying the inherited criteria. This enables programmatic aggregation of verification outcomes.

**`admiralty-action-required`:** Mark `yes` for any task where a step cannot be completed by an agent — requires the human to interact with an external system, provide credentials or URLs, or take an action only the human can perform. Fill this field consciously for every task; leaving it blank is a claim that the task requires no human action. When marked `yes`, the admiral will surface this in the Admiralty Action List before agents launch, and the captain will invoke the `awaiting-admiralty` standing order when the step is reached.

**Note on `blocks:` field:** The `blocks:` value names the task that cannot proceed until the human acts. The Admiralty Action List displays this as `unblocks:` — same task name, inverted label.
