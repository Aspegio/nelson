# Broadside — Synchronised Quality Gates

A coordinated checkpoint where all ships submit validation evidence simultaneously, enabling cross-ship consistency checks. Loaded on demand.

## Concept

Named after a warship firing all guns on one side simultaneously. A Broadside is a coordinated quality gate where ALL ships pause and submit their outputs at the same time. Where individual ship reviews catch single-ship defects, a Broadside catches integration failures — the gaps between ships that no single captain can see.

## When to Call Broadside

The admiral signals Broadside in any of the following circumstances:

- At pre-defined milestones in the battle plan.
- Before final synthesis when multiple ships' outputs must integrate.
- When the admiral suspects cross-ship inconsistencies.
- Recommended for Station 2+ work where integration failures are the primary risk.

## Broadside Procedure

1. **Admiral signals "Broadside"** — all ships pause current work immediately.
2. **Each ship submits** three items to the admiral:
   - Current deliverable in its present state.
   - Validation evidence (tests, checks, or review notes).
   - A list of assumptions about other ships' outputs.
3. **Red-cell navigator reviews ALL submissions at once**, specifically checking:
   - Cross-ship consistency — do outputs align on shared interfaces, naming, and data formats?
   - Integration points — will these pieces fit together without modification?
   - Assumption validation — do ships' assumptions about each other hold true?
4. **Red-cell reports findings to the admiral.**
5. **Admiral makes a single go/no-go decision for the entire set.**
6. **Outcome:**
   - If go: all ships proceed to the next phase.
   - If no-go: admiral identifies which ships need rework and in what order.

## Broadside Report Format

```
Broadside checkpoint: [milestone name]
Ships reporting: [list]
Cross-ship consistency: pass/fail
Integration check: pass/fail
Assumption conflicts: [list or "none"]
Decision: go / rework [ships]
```

The red-cell navigator completes this report and delivers it to the admiral. The admiral records the decision in the Captain's Log.

## Anti-Patterns

| Anti-pattern | Why it matters |
|---|---|
| Calling Broadside too frequently | Overhead exceeds benefit. Ships lose momentum to repeated pauses. Reserve Broadside for genuine integration milestones. |
| Skipping Broadside for Station 2+ integration work | Integration failures at Station 2+ carry high blast radius. Skipping the checkpoint trades short-term speed for late-stage rework. |
| Individual ships proceeding past the Broadside point | One ship advancing while others wait defeats the purpose. The value is in simultaneous review — partial submissions produce incomplete consistency checks. |

## Cross-References

- `action-stations.md` — Station tier definitions that determine when Broadside is recommended.
- `admiralty-templates/red-cell-review.md` — Review template used by the red-cell navigator during Broadside.
