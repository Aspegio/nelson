# Escalation: Chain of Command

Escalation flows upward: Crew to Captain to Admiral to Admiralty (human).

## Triggers

| Trigger | First Action |
| --- | --- |
| Ambiguous requirement or acceptance criteria | Captain pauses and requests clarification from admiral |
| Agent disagreement on approach | Admiral decides; if uncertain, escalates to Admiralty |
| Scope creep detected (task expanding beyond original definition) | Admiral re-scopes or escalates to Admiralty for approval |
| Unexpected dependency on out-of-scope system | Admiral pauses dependent work and escalates to Admiralty |
| Station 2+ risk discovered mid-task | Admiral elevates the action station and applies required controls |
| Budget approaching limit with critical work remaining | Admiral escalates to Admiralty with options: extend budget, descope, or abort |

## Procedure

1. The agent encountering the issue pauses work on the affected task.
2. Agent reports to admiral with: issue summary, options considered, and one recommendation.
3. Admiral evaluates whether the issue can be resolved within current authority:
   - If yes: admiral decides and documents the rationale.
   - If no: admiral escalates to Admiralty (human) with a summary and recommendation.
4. Admiralty provides direction.
5. Admiral communicates the decision to the affected agent and updates the battle plan.
6. Agent resumes work under the new direction.

## Authority Boundaries

- **Crew member**: Can resolve issues within their sub-task scope. Must escalate anything affecting other crew members or the ship's deliverable to captain.
- **Captain**: Can resolve issues within their own task scope. Must escalate anything affecting other tasks, shared resources, or mission scope.
- **Admiral**: Can re-assign tasks, replace agents, adjust timelines, elevate action stations, and descope within the original sailing orders. Must escalate scope changes, budget extensions, and abort decisions.
- **Admiralty (human)**: Final authority on scope, budget, and abort. All irreversible or high-blast-radius decisions require Admiralty confirmation.
