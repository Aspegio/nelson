# Tool Mapping Reference

Maps Nelson operations to Claude Code tool calls by execution mode.

## Tool Reference

| Nelson Operation | Claude Code Tool | Mode |
|---|---|---|
| Form the squadron | `TeamCreate` | agent-team |
| Spawn captain | `Agent` with `team_name` + `name` | agent-team |
| Spawn captain | `Agent` with `subagent_type` | subagents |
| Create task (coordination) | `TaskCreate` | agent-team |
| Assign task to captain | `TaskUpdate` with `owner` | agent-team |
| Check task progress (coordination) | `TaskList` / `TaskGet` | agent-team |
| Track task visibility (admiral) | `TaskCreate` / `TaskUpdate` / `TaskList` | all modes ¹ |
| Message a captain | `SendMessage(type="message")` | agent-team |
| Broadcast to squadron | `SendMessage(type="broadcast")` | agent-team |
| Shut down a ship | `SendMessage(type="shutdown_request")` | agent-team / subagents |
| Respond to shutdown | `SendMessage(type="shutdown_response")` | agent-team |
| Deploy Royal Marine | `Agent` with `subagent_type` | all modes |
| Approve captain's plan | `SendMessage(type="plan_approval_response")` | agent-team |
| Stand down squadron | `TeamDelete` | agent-team |

## Mode Differences

- **`subagents` mode:** No shared task list. The admiral tracks state directly
  and captains report only to the admiral. Use the `Agent` tool to spawn
  captains.
    - **Available:** `Agent` with `subagent_type`, `SendMessage(type="shutdown_request")`
    - **Not available (captains):** `TaskCreate`, `TaskList`, `TaskGet`, `TaskUpdate`,
      `SendMessage(type="message")`, `SendMessage(type="broadcast")`, `TeamCreate`,
      `TeamDelete`
    - **Admiral exception:** The admiral uses `TaskCreate`/`TaskUpdate`/`TaskList`
      for session-level visibility tracking (the user's Ctrl+T task list). These
      tasks are not visible to captains — they are for the user's benefit only. ¹
- **`agent-team` mode:** The task list (`TaskCreate`, `TaskList`, `TaskGet`,
  `TaskUpdate`) is the shared coordination surface. Captains can message each
  other via `SendMessage`. Use `TeamCreate` first, then spawn captains with the
  `Agent` tool using `team_name` and `name` parameters.
    - **Available:** `TeamCreate`, `TeamDelete`, `Agent` with `team_name` + `name`,
      all `Task*` tools, all `SendMessage` types
    - **Not available:** `Agent` with `subagent_type` for captains (marines still
      use `subagent_type`)
- **`single-session` mode:** No spawning. The admiral executes all work directly.
    - **Available:** `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet` (for
      visibility tracking) ¹
    - **Not available:** `Agent`, `TeamCreate`, `TeamDelete`, `SendMessage`

¹ Visibility tracking uses the same task tools as agent-team coordination but
serves a different purpose: making mission progress visible in the user's
Ctrl+T task list. In `subagents` and `single-session` modes, only the admiral
calls these tools; captains never see or interact with these task entries.

## Anti-Patterns

Common mode-tool mismatches and their correct alternatives. See
`references/standing-orders/wrong-ensign.md` for the full standing order.

| Anti-Pattern | Why It Fails | Correct Alternative |
|---|---|---|
| `TaskGet` in subagents mode | No shared task list exists | Read the `Agent` tool return value directly |
| `SendMessage(type="message")` in subagents mode | No team exists to route messages | Include instructions in the `Agent` prompt instead |
| `Agent` with `subagent_type` to spawn a captain in agent-team mode | Agent is not registered as a teammate | Use `Agent` with `team_name` + `name` |
| `TeamCreate` in subagents mode | Creates an unnecessary team structure | Omit — spawn captains directly with `Agent` |
| `TaskCreate` by captains in subagents mode | No shared task list exists for captains | Admiral tracks visibility via `TaskCreate`/`TaskUpdate` in its own session; captains report via `Agent` return value |

## Long-Running Tools

| Nelson Operation | Claude Code Tool | Mode |
|---|---|---|
| Spawn captain in background | `Agent` with `run_in_background: true` | subagents / agent-team (Station 0-1 only) |
| Stream a background captain's output | `Monitor` with target=ship name | all modes |
| Wait for any pending notification | (no explicit call) | all modes |

See `references/background-patterns.md` for when to background a captain and how to integrate completion notifications into the quarterdeck rhythm.
