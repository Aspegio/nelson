# Man Overboard: Stuck Agent Replacement

Use when an agent is unresponsive, looping, or producing no useful output. For infrastructure-wide communication failures (multiple agents unreachable, message bus down), see `comms-failure.md` instead.

1. Admiral identifies the stuck agent and its assigned task.
2. Admiral records the agent's last known progress and any partial outputs.
3. Admiral issues a shutdown request to the stuck agent.
4. Admiral spawns a replacement agent with the same role.
5. Admiral briefs the replacement with: task definition, dependencies, partial outputs, and known blockers.
6. Replacement agent resumes from the last verified checkpoint, not from scratch.
7. Admiral updates the battle plan to reflect the new assignment.

## Crew Variant

Use when a crew member aboard a ship is stuck, looping, or unresponsive. The captain handles recovery at ship level.

1. Captain identifies the stuck crew member and their assigned sub-task.
2. Captain records the crew member's last known progress and any partial outputs.
3. Captain issues a shutdown request to the stuck crew member.
4. Captain spawns a replacement crew member with the same role.
5. Captain briefs the replacement with: sub-task definition, dependencies, partial outputs, and known blockers.
6. Replacement crew member resumes from the last verified checkpoint, not from scratch.
7. Captain updates the ship manifest to reflect the new assignment.
8. If the same role fails twice, captain escalates to admiral with a summary and recommendation.

## Manual Cleanup Fallback

Use when the shutdown attempt ceiling is exhausted (3 failed attempts) and `TeamDelete` is blocked by stuck agents that will not respond to shutdown requests. This is a last resort — always attempt graceful shutdown first.

1. Admiral confirms that 3 shutdown attempts have failed and `TeamDelete` is blocked.
2. Admiral runs the following commands to remove the stuck team manually:
   - `rm -rf ~/.claude/teams/{team-name}` — removes the team registration
   - `rm -rf ~/.claude/tasks/{team-name}` — removes associated task data
3. Admiral verifies the team no longer appears in active team listings.
4. Admiral records the affected agents and the manual cleanup action in the captain's log.
5. Admiral spawns a fresh replacement team and re-issues the affected tasks from the last verified checkpoint.
