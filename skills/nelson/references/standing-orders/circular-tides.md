# Standing Order: Circular Tides

Do not allow circular dependencies or deadlocks to form between tasks.

**Symptoms:**
- Tasks remain in pending or blocked state indefinitely with no resolution path.
- Agents report waiting on each other, forming a cycle no one can break.
- No forward progress is made despite available budget and willing crews.

**Remedy:** When a dependency cycle is detected, the admiral must intervene to break it. One task in the cycle should be re-scoped to remove or stub its dependency, allowing the chain to advance. If no task can be cleanly unblocked, escalate to the admiral to re-sequence the battle plan and assign a captain to resolve the bottleneck directly.
