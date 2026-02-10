# Scuttle and Re-Form: Mission Abort

Use when the mission cannot succeed under current conditions and continuing wastes budget.

Triggers:
- Budget (token or time) is exhausted with critical tasks still pending.
- Mission outcome is no longer achievable due to discovered constraints.
- Admiral determines that remaining risk exceeds acceptable threshold.

Procedure:

1. Admiral halts all in-progress work immediately.
2. Each agent saves current partial outputs and documents their last known state.
3. Admiral produces an abort log using the Captain's Log Template with:
   - Reason for abort.
   - Tasks completed and their outputs.
   - Tasks abandoned and their partial state.
   - Conditions required before re-attempting the mission.
4. Admiral issues shutdown requests to all agents.
5. Admiral presents the abort log to the human (Admiralty) with a recommendation: retry with new constraints, descope, or abandon.
