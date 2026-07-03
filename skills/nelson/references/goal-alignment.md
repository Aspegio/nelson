# Goal Alignment

Nelson treats a Claude Code `/goal` as the admiral's **standing goal**: a
harness-level completion barrier that keeps a session from standing down before
the mission is truly done. Where Nelson's Mission Complete Gate is a discipline
the admiral applies to itself, the standing goal is enforced by the harness — it
fires after every turn and blocks stopping until a condition is judged met.

## What a `/goal` is

`/goal <condition>` installs a **session-scoped Stop hook**. After each turn a
small, fast evaluator model judges whether the natural-language condition holds
and either lets the session stop or sends it back to keep working. The goal
**auto-clears** once the condition is judged met. There is **one goal per
session**; setting a new one replaces the old. Clear early with `/goal clear`
(aliases: `stop`, `off`, `reset`, `none`, `cancel`); check status with a bare
`/goal`. A condition may carry its own bound, e.g. `... or stop after 20 turns`.

Requires Claude Code v2.1.139+. Unavailable when `disableAllHooks` or
`allowManagedHooksOnly` is set — in that case rely on the Mission Complete Gate
alone.

## The transcript rule (read this first)

**The evaluator judges the condition against the conversation transcript only.
It does not read files or run commands.** Nelson's completion evidence —
`captains-log.md`, `stand-down.json` — lives on disk, which the evaluator cannot
see. So a well-formed Nelson goal must be phrased against facts the admiral
**surfaces into the conversation**, and Stand Down must actually state them.

If the goal is phrased against on-disk artifacts the admiral never mentions in
chat, the Stop hook will loop forever on a mission that is genuinely complete.
This is the single most common way to misuse `/goal` with Nelson.

## Composing the condition

Do not hand-write the condition. Compose it from the sailing orders so it stays
aligned with `outcome`, `success_metric`, and `stop_criteria`:

```bash
python3 .claude/skills/nelson/scripts/nelson-data.py goal-condition \
  --mission-dir {mission-dir} --record
```

This prints a ready-to-paste `/goal ...` line and (with `--record`) persists the
condition into `sailing-orders.json` and logs a `goal_set` event so a resumed
session can re-establish it. The composed condition requires, in the transcript:
the success metric confirmed met, every stop criterion satisfied, and the
captain's log written with its path stated — plus a legitimate stop path if the
mission is formally abandoned via `scuttle-and-reform`. Add `--max-turns N` for a
turn cap, `--json` for a machine-readable object. See `references/structured-data.md`.

## When to set a standing goal

Set one when the session must run to completion without a human watching every
turn:

- long autonomous missions where premature stand-down is the failure mode;
- headless / `-p` invocations and scheduled runs;
- ultracode or otherwise high-automation sessions;
- any mission where "don't stop until the log is written" is worth enforcing.

Prefer **not** to set one for short, interactive missions where the human is
steering turn by turn — the Stop hook mostly adds friction there, and the
Mission Complete Gate already covers you.

If the user set a `/goal` **before** invoking Nelson, do not silently replace it.
Read it back with a bare `/goal`, reconcile the sailing orders to it (the goal is
the outer contract; the sailing orders must serve it), and only re-issue a
composed goal if the user agrees.

## Relationship to the Mission Complete Gate

The two are complementary, not redundant:

- **Mission Complete Gate** (Step 8) is Nelson's internal rule: never declare
  complete until `captains-log.md` exists on disk. It is what the admiral
  checks.
- **Standing goal** is the harness backstop: the session physically cannot stop
  until the transcript shows the mission is done.

Keep them in agreement. The composed condition already mirrors the gate, so at
Stand Down, satisfying the gate (and *stating* it in chat) is what clears the
goal. If you ever tighten the gate, re-compose the goal so the two do not drift.

## Clearing at Stand Down

When Stand Down completes, state the completion evidence in the conversation so
the evaluator can clear the goal:

- the success metric result (matching `success_metric`);
- that `captains-log.md` was written, with its path;
- that stand-down was recorded.

The goal then auto-clears. Do **not** instruct the user to run `/goal clear` on a
successful mission — that is only for abandoning a goal early. If the mission is
abandoned, run `scuttle-and-reform`, state the blocking reason in chat (which the
condition accepts as a legitimate stop), and log a `goal_cleared` event.

## Session resumption

A goal active at session end is **restored on `--resume` / `--continue`** (the
condition carries over; the turn/time/token counters reset). It is **not**
restored in a fresh, non-resumed session, and never crosses into a brand-new
session. So on resumption of an underway mission, check whether a goal is active
(bare `/goal`); if none is and `sailing-orders.json` carries a recorded
`goal_condition`, re-issue it. This is part of the session-resumption procedure —
see `references/damage-control/session-resumption.md`.

## Subagents

Whether a parent goal governs spawned captains/marines is **undocumented**. Do
not depend on it. Nelson's model already fits the safe assumption: the standing
goal governs the **admiral's** session — the one that stands down — while
captains and marines are governed by Nelson's own gates (action stations,
task-completion quality, red-cell review). Never rely on a `/goal` to police
subagent completion; use the battle plan's verification contract for that.

## Interaction with workflows

A standing goal survives a resumed session, but a dynamic workflow run has **no
mid-run human gate** and the goal evaluator does not see inside it. Use the goal
as the mission-level completion barrier around workflow stages, not as a control
inside a run. For `hybrid-workflow`, the goal should require that every planned
stage's results have been reviewed and accepted in the transcript before the
session may stop. See `references/workflow-doctrine.md`.

## Anti-patterns

- **Unverifiable goal:** a condition phrased against on-disk state the admiral
  never states in chat. The Stop hook loops forever. Compose from sailing orders
  instead.
- **Goal that fights the permission gate:** a condition worded so the session
  cannot stop while it is legitimately waiting for user approval (Step 5) or an
  admiralty action. Word completion as the target; let the escape path cover
  blocked-on-human states, or set a turn bound.
- **Replacing a user's goal silently:** clobbering a `/goal` the user set before
  invoking Nelson. Reconcile, don't overwrite.
- **Goal instead of the gate:** treating `/goal` as a substitute for writing the
  captain's log. The goal enforces the gate; it does not replace the work the
  gate protects.
