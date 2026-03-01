# Tool Mapping Reference

Maps Nelson operations to Claude Code tool calls by execution mode.

## Tool Reference

| Nelson Operation | Claude Code Tool | Mode |
|---|---|---|
| Form the squadron | `TeamCreate` | agent-team |
| Spawn captain | `Agent` with `team_name` + `name` | agent-team |
| Spawn captain | `Agent` with `subagent_type` | subagents |
| Create task | `TaskCreate` | agent-team |
| Assign task to captain | `TaskUpdate` with `owner` | agent-team |
| Check task progress | `TaskList` / `TaskGet` | agent-team |
| Message a captain | `SendMessage(type="message")` | agent-team |
| Broadcast to squadron | `SendMessage(type="broadcast")` | agent-team |
| Shut down a ship | `SendMessage(type="shutdown_request")` | agent-team / subagents |
| Respond to shutdown | `SendMessage(type="shutdown_response")` | agent-team |
| Deploy Royal Marine | `Agent` with `subagent_type` | all modes |
| Approve captain's plan | `SendMessage(type="plan_approval_response")` | agent-team |
| Stand down squadron | `TeamDelete` | agent-team |

## Mode Differences

- **`subagents` mode:** No shared task list. The admiral tracks state directly and captains report only to the admiral. Use the `Agent` tool to spawn captains.
- **`agent-team` mode:** The task list (`TaskCreate`, `TaskList`, `TaskGet`, `TaskUpdate`) is the shared coordination surface. Captains can message each other via `SendMessage`. Use `TeamCreate` first, then spawn captains with the `Agent` tool using `team_name` and `name` parameters.
- **`single-session` mode:** No spawning. The admiral executes all work directly.
