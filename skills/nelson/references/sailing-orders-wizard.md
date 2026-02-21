# Sailing Orders Wizard

An interactive scaffold that guides users through creating complete sailing orders. Instead of presenting a blank template, the wizard asks structured questions and populates the template from the answers. This reduces the barrier to writing good sailing orders, especially for first-time users who face unfamiliar fields like "outcome," "success metric," and "stop criteria."

## Purpose

The sailing orders template at `admiralty-templates/sailing-orders.md` is comprehensive but can feel daunting when empty. The wizard walks the user through each field with a plain-language question, validates the answers, and assembles the completed template. The result is a fully populated set of sailing orders ready for the admiral to issue.

## Quick vs. Full Mode

| Mode | Questions | When to Use |
|---|---|---|
| Quick | 1-3 only | Small missions, familiar users, low ambiguity |
| Full  | 1-7 all  | Complex missions, first-time users, high stakes |

In quick mode, questions 4-7 receive sensible defaults (see Defaults and Validation below). The admiral may always override defaults before issuing orders.

## Wizard Questions

Ask these questions in order. Map each answer to the corresponding sailing orders field.

| Step | Question | Populates |
|---|---|---|
| 1 | "What should be different when this mission is done?" | Outcome |
| 2 | "How will we know it worked? What is the measurable result?" | Success Metric |
| 3 | "When does this need to be done?" | Deadline |
| 4 | "What must NOT happen? Any forbidden actions or safety constraints?" | Constraints |
| 5 | "What is explicitly out of scope?" | Out of Scope |
| 6 | "When should we stop, even if not everything is done?" | Stop Criteria |
| 7 | "What artifacts must exist at the end?" | Handoff Artifacts |

### Guidance for Each Question

**Step 1 — Outcome.** Push for a concrete end state, not an activity. "Refactor the auth module" is an activity. "Auth module uses token-based sessions with all existing tests passing" is an outcome.

**Step 2 — Success Metric.** The metric must be independently verifiable. Ask: "Could someone who was not involved confirm this was achieved?" If the answer is no, the metric needs sharpening.

**Step 3 — Deadline.** Accept a specific time, a session boundary, or a token budget. If the user is unsure, default to "End of session."

**Step 4 — Constraints.** Prompt for forbidden actions, safety rails, and budget limits. If the user has none, apply the default.

**Step 5 — Out of Scope.** The admiral should name at least one exclusion. An empty out-of-scope section is a leading indicator of scope drift. If the user offers nothing, suggest boundaries based on the stated outcome.

**Step 6 — Stop Criteria.** Must be concrete and testable. "When it feels done" is not a stop criterion. "When all 14 endpoints return 200 on the integration test suite" is.

**Step 7 — Handoff Artifacts.** Name the files, documents, or states that must exist when the mission is complete. This is what the admiral inspects at stand-down.

## Defaults and Validation

### Defaults

Apply these when a question is skipped or the user has no answer.

| Field | Default |
|---|---|
| Deadline | "End of session" |
| Constraints | "Standard Nelson standing orders apply" |
| Out of Scope | Admiral should suggest at least one exclusion based on the stated outcome |
| Stop Criteria | Derived from the success metric — "Stop when the success metric is met or the deadline is reached" |
| Handoff Artifacts | Derived from the outcome — the minimum artifacts that prove the outcome was achieved |

### Validation Rules

Run these checks before assembling the final sailing orders.

| Rule | Check | Remedy |
|---|---|---|
| Outcome and metric are distinct | Compare outcome (Step 1) and metric (Step 2) for duplication | If they are identical or near-identical, ask: "The outcome and metric look the same. Can you give a metric that someone else could independently verify?" |
| Stop criteria are testable | Confirm stop criteria contain a concrete condition | If vague, ask: "How would we know this condition has been met? Can you make it more specific?" |
| Out of scope is not empty | Confirm at least one exclusion exists | If empty, suggest: "Based on the outcome, consider excluding [related but tangential area]. Does that seem right?" |
| Metric is independently verifiable | Confirm the metric does not require subjective judgement | If subjective, ask: "Could someone uninvolved confirm this? What would they check?" |

## Assembled Output

After all questions are answered and validation passes, assemble the completed sailing orders using the template from `admiralty-templates/sailing-orders.md`.

```text
Sailing orders:
- Outcome: [Step 1 answer]
- Success metric: [Step 2 answer]
- Deadline: [Step 3 answer or default]

Constraints:
- Token/time budget: [from Step 3 or Step 4]
- Reliability floor: [from Step 4 if applicable]
- Compliance/safety constraints: [from Step 4 if applicable]
- Forbidden actions: [from Step 4 if applicable]

Scope:
- In scope: [derived from Step 1]
- Out of scope: [Step 5 answer or suggested exclusion]

Stop criteria:
- Stop when: [Step 6 answer or derived default]

Required handoff artifacts:
- Must produce: [Step 7 answer or derived default]
```

## Cross-Reference

- `admiralty-templates/sailing-orders.md` — the template this wizard populates.
