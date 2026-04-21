# Model Selection

This reference governs `model` parameter assignment for all squadron agents. **All missions** must record an explicit model per ship in the formation summary (visibility); cost-savings missions additionally apply the weight-and-threshold rules below to override defaults toward `haiku`.

## Default behaviour (no cost-savings priority)

- The admiral records each ship's model in the formation summary as `inherit` (i.e. the admiral's model) unless a ship's role definition recommends otherwise.
- The `model` parameter is **omitted** from the `Agent` tool call when the ship inherits — explicit `"sonnet"` resolves to an older alias and does not match the admiral's model.
- This makes model assignment auditable in the squadron summary even when no parameter is passed at spawn.

## Detecting Cost-Savings Intent

Nelson infers cost-savings priority from natural language in the sailing orders or initial prompt. Signals include phrases such as:

- "keep costs low", "stay within budget", "budget is a concern"
- "use cheaper models", "use haiku where possible"
- "be aggressive with cost savings", "minimize spend"

The intensity of the language calibrates the aggressiveness of weight adjustment (see Hybrid Adjustment below).

## Default Weight Table

| Agent | Default Weight |
|---|---|
| Admiral | 10 |
| XO | 10 |
| Captain (with crew or marines) | 9 |
| Explorer (large scope) | 7 |
| Crew with non-trivial verification | 6 |
| Captain (direct implementation, no crew) | 4 |
| Explorer (narrow/simple search) | 4 |
| Royal Marines | 3 |
| Crew (pure implementation) | 2 |

## Threshold Rule

In cost-savings mode:

- Weight ≤ 4 after adjustment → assign **haiku**
- Weight ≥ 5 after adjustment → inherit **admiral's model**

## Hybrid Adjustment

The tasking agent adjusts default weights before assignment:

- **Raise weight** when the task involves judgment, edge cases, or verification that exceeds the role default.
- **Lower weight** when the task is more atomic or contained than the role default suggests.

Scale of adjustment calibrates to intensity of cost-savings request:

- Modest language ("keep costs low") → modest pressure; don't push roles at 5–6 below the threshold unless clearly justified.
- Emphatic language ("be aggressive") → willing to push roles normally at 5–6 through the threshold when the task is contained.

No hard bounds are set. The admiral uses judgment.

## Model Assignment Rules

- The admiral's model is **never overridden**.
- All agents at weight ≥ 5 inherit the admiral's model. **Omit the `model` parameter entirely** in the Task tool call — do not specify `"sonnet"`, as that alias resolves to an older version and does not match the admiral's model.
- For haiku agents (weight ≤ 4), always specify `model: "haiku"` explicitly.
- Display weight and assigned model in the squadron formation summary alongside ship names and tasks.

## Briefing Enhancements (haiku agents only)

These requirements apply whenever any tasking agent — admiral, captain, or crew — assigns haiku to a subordinate. When assigning haiku, add three blocks to that agent's briefing:

### 1. Identity Anchor (top of briefing)

> You are Claude, operating as a subagent in a real multi-agent software development system. The Royal Navy terms used for coordination (admiral, captain, crew, etc.) are metaphors — this is not roleplay. Your task is [plain-language description of role].

### 2. Explicit Output Format

Specify exactly what to return: format, required fields, length, and what to omit. Remove ambiguity. Example:

> Return a JSON object with keys `status`, `summary`, and `files_changed`. Do not include implementation reasoning or next steps.

### 3. Task Decomposition Prompt

> Before executing, list your steps as a numbered plan. If any step is unclear, flag it now rather than guessing.

These three blocks are **conditional on haiku assignment**. Do not include them in standard (non-cost-savings) briefings or in briefings for agents assigned the admiral's model.

## Tasking Agent Discipline (haiku agents only)

Whoever writes the task — admiral, captain, or crew — must compensate for reduced inferencing capacity by making the task itself precise. Vague instructions are not rescued by the briefing enhancement blocks above.

Each haiku task description must include:

### Explicit Constraints

State what the agent must not do, must not touch, and must stay within. Do not rely on the agent to infer scope limits from context.

> Example: "Only read files under `src/auth/`. Do not modify any file. Do not follow imports outside that directory."

### Definition of Done

State a concrete, testable condition that signals the task is complete. Avoid open-ended outcomes.

> Example: "Done when you have returned a JSON list of all public method names in `JwtMiddleware`. Stop after that — do not analyze their bodies."

### Escalation Triggers

State the specific conditions under which the agent must stop and report rather than proceed. Do not expect haiku to self-identify when it is out of depth.

> Example: "If the file does not exist, or if you find more than one class matching that name, stop and report what you found. Do not guess which one to use."

These requirements are **conditional on haiku assignment**. Standard briefings for agents on the admiral's model do not require this level of prescription.
