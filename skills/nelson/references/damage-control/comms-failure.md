# Communications Failure: Agent Team Infrastructure

Use when agent team communication fails — agent IDs become unreachable, `SendMessage` returns errors, or the shared task list becomes inaccessible.

This procedure covers infrastructure-level failures where the communication channel itself is broken, not agent-level issues (for stuck or unresponsive agents that are still reachable, use `man-overboard.md`).

## Symptoms

- `SendMessage` fails with agent ID not found or similar errors.
- Multiple ships become unreachable simultaneously.
- `TaskList` or `TaskGet` returns errors or stale data.
- Ship results cannot be retrieved despite the agent having completed work.

## Procedure

1. Admiral records which ships are unreachable and which tasks they owned.
2. Admiral checks `TaskList` for any results that were written before the failure.
3. For each lost ship:
   a. Check if the ship wrote any output to disk (files, partial deliverables) that can be recovered.
   b. Record the ship's last known status and any recovered outputs in the quarterdeck report.
4. Admiral assesses mission viability:
   - If enough work is complete to finish the mission with remaining ships, redistribute lost tasks to reachable ships or spawn new sub-agents.
   - If the agent team infrastructure is fully down, fall back to `subagents` mode for remaining work. Spawn replacement captains as independent sub-agents and brief them with recovered context.
   - If the mission cannot continue, invoke `scuttle-and-reform.md`.
5. Admiral MUST NOT take over implementation work from lost ships. The `admiral-at-the-helm` standing order applies even during infrastructure failures. Spawn replacement agents instead.
6. Log the communications failure, affected ships, recovered outputs, and remedial action in the quarterdeck report.

## Prevention

- For missions with 4+ ships, prefer writing intermediate outputs to disk rather than relying solely on the message bus for result delivery.
- Include explicit "write checkpoint to disk" instructions in crew briefings for long-running tasks.
- At each quarterdeck checkpoint, verify all ships are still reachable before continuing.
