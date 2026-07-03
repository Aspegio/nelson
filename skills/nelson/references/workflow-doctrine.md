# Workflow Doctrine

Nelson treats Claude Code dynamic workflows as a fleet asset: powerful for broad, repeatable orchestration, but still governed by sailing orders, action-station risk controls, cost discipline, and explicit verification.

## What a workflow is

A dynamic workflow moves orchestration into a JavaScript workflow script. The script can fan work out to many agents, keep intermediate results in script variables, aggregate outputs, and repeat a review or migration pattern across a large scope. The script begins with `export const meta = {...}` and a body using `agent()`, `parallel()`, `pipeline()`, and `phase()` under top-level `await`. A workflow may be one-shot (Claude writes and runs it inline) or saved as `.claude/workflows/<name>.js` (project) or `~/.claude/workflows/<name>.js` (personal) and re-run as the `/<name>` command; runs are watched, paused, and resumed from the `/workflows` view.

Nelson v1 does **not** compile or invoke workflow scripts directly; it produces the doctrine, battle-plan charter, gates, and verification contract that Claude Code can use to create or run the workflow. The charter-to-script bridge below turns that charter into a script skeleton a power user can run without re-deriving the structure.

`ultracode` is not a Nelson execution mode. It is a Claude Code `xhigh` effort/automation setting that can let Claude decide when dynamic workflows are appropriate. Nelson still owns the charter, approval gate, risk tiering, and acceptance criteria.

## Ultracode readiness

Before using ultracode on a Nelson mission, make sure the mission is safe for autonomous workflow selection:

- sailing orders state outcome, metric, deadline, forbidden actions, and budget;
- file ownership or target scope is bounded enough for broad fan-out;
- Station 2/3 gates are written as stage boundaries, not hoped-for mid-run prompts;
- verification contract says how accepted, rejected, and uncertain outputs are handled;
- fallback mode is named before launch.

If any of these are missing, do the planning work first and use `hybrid-workflow` or a conventional `agent-team` instead of letting ultracode choose blindly.

## Execution modes

- `workflow`: one approved autonomous workflow run for large fan-out, repeatable review, broad migration, audit, or cross-checked research.
- `hybrid-workflow`: a Nelson-gated sequence of separate workflow stages. Use this when the mission needs human review between stages, staged risk controls, or Station 2/3 approvals.

Station 2/3 work should prefer `hybrid-workflow`. Workflows do not support arbitrary mid-run human input; handle sign-off between stages by ending one workflow run, presenting results, and launching the next run only after approval.

## Suitability checks

Choose a workflow only when the work benefits from scripted orchestration. Good fits:

- codebase-wide audits across many files, packages, or services;
- large migrations with the same transformation repeated across independent targets;
- cross-checked research or review where multiple agents independently inspect the same question;
- repeatable verification sweeps with clear acceptance criteria;
- broad issue triage where findings can be collected, ranked, and de-duplicated.

Prefer `agent-team`, `subagents`, or `single-session` instead when:

- the work is tightly coupled in the same files;
- the path depends on frequent human steering;
- the mission needs rich peer-to-peer negotiation among a small number of captains;
- expected cost exceeds value or the scope cannot be bounded;
- acceptance criteria are vague enough that a workflow would amplify ambiguity.

## Sounding the Channel

Before full scope, run a small representative probe: one package, a handful of files, one migration pattern, or one research slice. The probe must report:

- target slice and why it represents the wider channel;
- agents completed versus total;
- elapsed time and approximate token burn;
- accepted findings, rejected findings, and uncertain findings;
- verification evidence for any accepted output;
- changes needed to the charter before broad execution.

Do not proceed from probe to full run until the admiral has reviewed the probe and, for `hybrid-workflow`, the user has explicitly approved the next stage.

## Workflow charter fields

When selecting `workflow` or `hybrid-workflow`, include a compact Workflow Charter in `battle-plan.md` and preserve the same data in `battle-plan.json` where useful:

- `execution_primitive`: `workflow` or `hybrid-workflow`;
- `workflow_suitability`: why a workflow is appropriate;
- `workflow_phases`: planned stages, including probes and full runs;
- `human_gates`: approvals required before or after stages;
- `verification_contract`: how findings or edits become accepted;
- `cost_guardrail`: budget limits, scope limits, and stop triggers;
- `fallback_mode`: usually `agent-team`, or `single-session` for tightly coupled recovery.

## From charter to a runnable script

The charter is not just documentation — its fields map one-to-one onto a Workflow
script, so a power user can run the approved plan instead of re-deriving it. This
is a **starting skeleton** the admiral hands over after approval, not something
Nelson executes itself. Each charter field becomes a script element:

- `workflow_phases` → a `phase('...')` group, or a `pipeline`/`parallel` stage per phase;
- `verification_contract` → a verify stage that adversarially re-checks each finding and drops those that fail the contract;
- `cost_guardrail` → a Sounding-the-Channel probe first, plus a budget/agent-count guard before the full run;
- `human_gates` → for `hybrid-workflow`, a script boundary where the run ends and the next stage is a separate approved run (workflows have no mid-run gate);
- `fallback_mode` → the mode to drop to if the probe shows low signal.

A review-shaped charter maps to the canonical find-then-verify pipeline:

```javascript
export const meta = {
  name: 'audit-<scope>',            // from the charter's workflow name
  description: '<workflow_suitability>',
  phases: [{ title: 'Probe' }, { title: 'Review' }, { title: 'Verify' }],
}
// Sounding the Channel — cost_guardrail: prove signal on one slice first.
const probe = await agent(`Review ${args.slice} for <finding type>.`, { phase: 'Probe', schema: FINDINGS })
if (!probe.findings.length) return { stopped: 'probe found no signal; fall back to <fallback_mode>' }

// Full run — one reviewer per target, each finding verified as its review lands.
const results = await pipeline(
  args.targets,                                    // bounded per cost_guardrail
  t => agent(`Review ${t} for <finding type>.`, { phase: 'Review', schema: FINDINGS }),
  review => parallel(review.findings.map(f => () =>  // verification_contract
    agent(`Adversarially verify: ${f.summary}. Default to rejected if uncertain.`, { phase: 'Verify', schema: VERDICT })
      .then(v => ({ ...f, verdict: v })))),
)
return { confirmed: results.flat().filter(Boolean).filter(f => f.verdict?.real) }
```

Keep the charter's Station tier in view: Station 2 outputs still need red-cell
review and Station 3 outputs still need explicit human confirmation, so a
Station 2/3 audit runs as `hybrid-workflow` — end the run at each `human_gate`
and resume only after approval.

## Verification contract

Workflow output is not accepted merely because the workflow completed. The battle plan must say what counts as verified. Common contracts:

- independent reviewer confirmation for findings above a risk threshold;
- tests, lint, type checks, or targeted manual review for generated edits;
- red-cell review for Station 2+ outputs;
- rejected and uncertain findings surfaced separately, not hidden in the summary;
- sample-based audit of accepted findings before final synthesis;
- rollback notes for any edit-bearing result.

Action Stations still apply. Station 2 requires adversarial review; Station 3 requires explicit human confirmation and contingency planning.

## Cost controls

Workflows can spend substantially more tokens than ordinary delegation because they may create many agents and hold intermediate results in script state. Apply these controls:

- run Sounding the Channel before broad execution;
- cap target scope per phase;
- cap agent count per wave where possible;
- stop after repeated agent failures rather than retrying blindly;
- require approximate token burn in telemetry;
- narrow or fall back if the probe shows low signal, high duplicate findings, or excessive cost.

## Telemetry

At each checkpoint or workflow stage boundary, capture what Claude Code exposes and allow manual entry from the `/workflows` view. Useful fields:

- workflow name and phase;
- agents completed / total;
- failed agents;
- elapsed time;
- token burn or best available estimate;
- accepted, rejected, and uncertain findings;
- current status;
- next gate.

Nelson v1 mission-log events are deliberately loose: `workflow_name`, `phase`, `status`, `agents_total`, `agents_completed`, `tokens_used`, `elapsed_minutes`, `summary`, and `next_gate` are all acceptable event data fields.

## Standing goal and workflows

A Claude Code `/goal` and a workflow operate at different levels and do not
interfere, but they must be coordinated:

- The goal is the **mission-level** completion barrier; the workflow is an
  orchestration primitive inside the mission. Never set a `/goal` inside a
  workflow run — set it once at Step 1 (see `references/goal-alignment.md`).
- The goal evaluator does not see inside a run, and a run has no mid-run human
  gate. So the goal cannot police workflow internals — it enforces that the
  mission's results are reviewed and accepted in the transcript before the
  session may stop.
- For `hybrid-workflow`, word the goal so it is met only once every planned stage
  has completed and its results have been accepted in the conversation. That
  keeps the session from standing down between stages while the human gate is
  still pending.

## Damage-control mapping

- **Low signal after probe:** stop, narrow the charter, or fall back to `agent-team`.
- **Budget burn too high:** halt at the next stage boundary, reduce scope, and record the cost finding.
- **Agent failures cluster around one target:** isolate that target for a human-reviewed or `single-session` task.
- **Contradictory findings:** require independent reviewer confirmation before acceptance.
- **Station 2/3 gate needed:** stop the current run and resume only as a separate approved `hybrid-workflow` stage.
- **Workflow runner or tool allowlist problem:** do not improvise around prompts; surface the blocked call and revise the charter or allowlist.
