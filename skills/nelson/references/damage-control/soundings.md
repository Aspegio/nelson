# Soundings: Proactive Budget Cliff Detection

Use to detect approaching context window exhaustion before a ship crosses into a critical material condition. Soundings are the navigational practice of measuring water depth to avoid running aground — applied here to token budgets to avoid running aground on a context cliff.

## Purpose

Quarterdeck checkpoints catch condition changes after they happen. Soundings detect them before they happen. A ship that knows it will reach Condition ZEBRA in two turns can prepare an orderly handoff. A ship that discovers it is already at ZEBRA (Critical) cannot.

## When to Take Soundings

Take soundings every 5 to 10 turns, independent of the quarterdeck rhythm. Soundings are lightweight and should not wait for a full checkpoint cycle.

- Every captain takes soundings of their own ship's budget.
- The admiral takes soundings of the flagship budget and reviews ship-level soundings at each quarterdeck checkpoint.
- Between checkpoints, captains report soundings to the admiral only when the forecast is alarming (see Escalation below).

## Sounding Procedure

1. **Read current hull integrity.** Determine the ship's remaining context window as a percentage.
2. **Calculate burn rate.** Divide the tokens consumed over the last N turns by N (where N is typically 5 turns, or fewer if the ship has completed fewer than 5 turns). Express as tokens per turn.
3. **Estimate turns to ZEBRA (Critical).** Calculate the number of turns until hull integrity falls below 40%:

   ```
   tokens_to_critical = remaining_tokens - (total_capacity * 0.40)
   turns_to_critical  = tokens_to_critical / burn_rate
   ```

4. **Estimate turns to Condition ZEBRA.** Calculate the number of turns until hull integrity falls below 60%:

   ```
   tokens_to_zebra = remaining_tokens - (total_capacity * 0.60)
   turns_to_zebra  = tokens_to_zebra / burn_rate
   ```

5. **Compare against thresholds.** If turns to ZEBRA (Critical) is less than 3, escalate immediately.

## Soundings Report

File a soundings report using the following format. This is a lightweight status — not a full damage report.

```
Ship: {ship-name}
Material Condition: {XRAY | YOKE | ZEBRA | ZEBRA (Critical)}
Hull Integrity: {percentage}%
Burn Rate: {tokens-per-turn} tokens/turn (measured over last {N} turns)
Turns to ZEBRA: {estimate}
Turns to ZEBRA (Critical): {estimate}
Forecast: {STEADY | CLOSING | SHOAL WATER}
```

### Forecast Definitions

- **STEADY**: Turns to ZEBRA (Critical) is 10 or more. No concern.
- **CLOSING**: Turns to ZEBRA (Critical) is between 3 and 9. Monitor closely; increase sounding frequency to every 3 turns.
- **SHOAL WATER**: Turns to ZEBRA (Critical) is fewer than 3. Immediate escalation required.

## Escalation

When a sounding returns SHOAL WATER:

1. Captain sends the soundings report to the admiral immediately. Do not wait for the next quarterdeck checkpoint.
2. Admiral assesses whether the ship can complete its current task within the remaining budget.
3. If the task cannot complete, admiral initiates relief on station per `hull-integrity.md` and `relief-on-station.md`.
4. If the task is close to completion, admiral may authorise the captain to push through — but only if the estimated remaining work is fewer turns than turns to ZEBRA (Critical).

When a sounding returns CLOSING:

1. Captain notes the forecast in their next damage report.
2. Captain increases sounding frequency to every 3 turns.
3. Admiral factors the ship's trajectory into readiness board decisions at the next quarterdeck checkpoint.

## Flagship Soundings

The admiral takes soundings of the flagship budget at the same cadence as ship captains. Flagship SHOAL WATER is the highest-priority escalation in the squadron because losing the admiral's coordination context is unrecoverable within the current session.

1. At CLOSING, admiral begins writing session state to disk incrementally.
2. At SHOAL WATER, admiral writes a full quarterdeck report and flagship turnover brief, then signals the Admiralty (human) that a session resumption will be needed.

## Relationship to Hull Integrity

Soundings do not replace hull integrity monitoring — they augment it. Hull integrity thresholds define the material conditions and the actions required at each condition. Soundings provide early warning so those actions can be planned rather than reactive.

See `hull-integrity.md` for material condition definitions and threshold percentages.
