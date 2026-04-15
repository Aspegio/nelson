# Circuit Breakers: Automated Budget Alarms

Use to supplement the admiral's checkpoint rhythm with automatic, threshold-based alarms. Circuit breakers surface advisories when resource thresholds are crossed — they do not abort ships or auto-execute damage control. The admiral decides the remedy.

## What They Are

Circuit breakers are a set of named thresholds evaluated at two points:

1. **At each quarterdeck checkpoint**, by `nelson-data.py checkpoint`, against the freshly-written `fleet-status.json` and mission log.
2. **On `TeammateIdle` hook fires**, for per-ship idle timeouts, via the `idle-ship` hook handler.

When a threshold is crossed, a `circuit_breaker_tripped` event is appended to `mission-log.json` with the value, the threshold, and the recommended damage control procedure. The admiral sees a single advisory line per trip on stdout (or stderr for the idle-ship hook) and decides what to do.

Circuit breakers are advisory in the current release. A future `strict` mode may auto-trigger relief on station for hull breaches or auto-abort on catastrophic budget overrun.

## Thresholds and Defaults

| Threshold | Default | Evaluated at | Recommends |
|---|---|---|---|
| `hull_integrity_threshold` — any ship hull ≤ N% | 80 | checkpoint | `damage-control/hull-integrity.md` |
| `budget_alarm_ratio` / `budget_alarm_completion_ratio` — tokens spent ≥ R1 of limit AND tasks completed < R2 of total | 0.7 / 0.4 | checkpoint | admiral review, elevate to Station 2 |
| `cost_per_task_multiplier` — latest burn/task ≥ N × rolling median (needs `cost_per_task_min_history` checkpoints of history) | 3.0 / 3 | checkpoint | `damage-control/crew-overrun.md` |
| `consecutive_failures` — `blocker_raised` events without an intervening `blocker_resolved` ≥ N | 2 | checkpoint | `damage-control/scuttle-and-reform.md` |
| `idle_timeout_minutes` — a single ship idle for ≥ N minutes with incomplete task | 10 | TeammateIdle hook | `damage-control/man-overboard.md` |
| `time_limit_grace_minutes` — mission duration ≥ `sailing_orders.budget.time_limit_minutes` + grace | 0 | checkpoint | admiral review, consider stand-down |

The `enabled` key (default `true`) is a master switch.

## Configuration

Circuit breaker thresholds live under `sailing-orders.json > circuit_breakers`. The admiral can edit this file directly after `nelson-data init`:

```json
{
  "version": 1,
  "outcome": "...",
  "budget": {"token_limit": 100000, "time_limit_minutes": 120},
  "circuit_breakers": {
    "hull_integrity_threshold": 75,
    "budget_alarm_ratio": 0.75,
    "idle_timeout_minutes": 5,
    "enabled": true
  }
}
```

Unknown keys are silently ignored so typos cannot secretly override defaults. Missing keys fall back to the defaults in `nelson_circuit_breakers.py`.

To disable all circuit breakers for a mission (e.g. a smoke test mission), set `enabled: false`.

## Output Format

When a checkpoint trips a breaker, `nelson-data.py checkpoint` prints one line per trip to stdout after the checkpoint summary:

```
[nelson-data] Checkpoint 3 recorded
Fleet: 1/4 done | Budget: 80.0% | Hull: 4G 0A 0R 0C | Blockers: 0
[CIRCUIT BREAKER: budget_alarm] Budget alarm: 80% of tokens spent with only 25% of tasks complete. Elevate to Station 2 and review scope.
```

The same trip is appended to `mission-log.json` as:

```json
{
  "type": "circuit_breaker_tripped",
  "checkpoint": 3,
  "timestamp": "2026-04-11T12:34:56Z",
  "data": {
    "type": "budget_alarm",
    "value": {"spent_ratio": 0.8, "completion_ratio": 0.25},
    "threshold": {"spent_ratio": 0.7, "completion_ratio": 0.4},
    "action": "admiral-review",
    "message": "Budget alarm: 80% of tokens spent with only 25% of tasks complete. ..."
  }
}
```

This record is the authoritative trail for post-mission analysis — `nelson-data history` and the cross-mission memory store will see circuit breaker events and can correlate them with outcomes.

## Idle Timeout: How the Hook Tracks State

The `TeammateIdle` hook does not receive an idle duration in its payload. To compute elapsed idle time, the circuit breaker keeps a small state file at `<mission-dir>/idle-tracker.json`:

1. First time `TeammateIdle` fires for ship X → record `{X: "2026-04-11T12:00:00Z"}` and emit no advisory.
2. Subsequent fires → compute elapsed from the stored timestamp. If elapsed ≥ `idle_timeout_minutes`, emit the man-overboard advisory.
3. When a ship's task becomes `completed` (the paid-off standing order path), its tracker entry is cleared.

Tracker state is best-effort: if the file cannot be written, the breaker silently degrades.

## Fleet-Status Budget Extensions

Each checkpoint now writes two new fields under `fleet-status.json > budget`:

- `burn_rate_per_task` — `tokens_spent / completed`, rounded to integer. `None` when no tasks have completed.
- `projected_budget_at_completion` — `burn_rate_per_task × total`. `None` when `burn_rate_per_task` is `None` or `total == 0`.

These are advisory projections, not guarantees. They exist so the admiral (and any future planner) can read a single field and see where the mission is heading without re-computing from raw counters.

## When Circuit Breakers Are Not Enough

Circuit breakers are a backstop, not a substitute for:

- The quarterdeck checkpoint rhythm — breakers run at checkpoint time but the admiral still owns the decision.
- Hull integrity reports — breakers detect a breach only if the ship has filed a damage report or the squadron readiness board has been updated.
- Standing orders — breakers do not evaluate anti-patterns; that is the admiral's standing-order check at each decision point.

If a circuit breaker fires repeatedly for the same root cause, that is signal that a new standing order may be warranted. See `docs/` for how standing orders are added.

## Relationship to Other Procedures

- **Hull integrity** (`hull-integrity.md`): the hull-integrity circuit breaker is a secondary alarm on top of the damage-report-driven readiness board. It catches misses.
- **Crew overrun** (`crew-overrun.md`): the cost-per-task circuit breaker detects overruns by burn-rate spike rather than by captain self-report.
- **Man overboard** (`man-overboard.md`): the idle-timeout circuit breaker catches stuck ships the admiral has not yet noticed.
- **Scuttle and reform** (`scuttle-and-reform.md`): the consecutive-failures circuit breaker triggers this consideration without the admiral having to count blockers manually.
