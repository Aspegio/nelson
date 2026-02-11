# Standing Order: Crew Without Canvas

Do not add agents without reducing the critical path length of the mission.

**Symptoms:**
- More captains are active but the mission does not finish sooner.
- Coordination messages increase while throughput stays flat.
- Token budget inflates with no improvement in mission metric.

**Remedy:** Before adding an agent, identify the specific critical-path task it will parallelize. If no such task exists, do not add the agent.
