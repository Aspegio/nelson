# Standing Order: Wrong Ensign

Do not use tools that belong to a different execution mode.

Each execution mode has a distinct coordination surface. Using tools from the
wrong mode produces silent failures — `TaskGet` returns "Task not found" in
subagents mode, `SendMessage` fails without a prior `TeamCreate`, and agents
spawned with mismatched parameters cannot communicate with the squadron.

**Symptoms:**

- `TaskGet` or `TaskList` returning empty results or "Task not found" errors
  when captains have reported work complete.
- `SendMessage` failing because no team exists (subagents mode has no team).
- Captains spawned with `team_name` in subagents mode, or with `subagent_type`
  in agent-team mode.
- Admiral attempting to retrieve results via `TaskGet` when captains were
  dispatched as teammates (agent-team mode).
- Captains unable to update shared task state because no task list exists.
- `TeamCreate` not listed in the available tools, indicating
  `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` was not set at session launch
  (agent-team mode requires this prerequisite — see
  `references/squadron-composition.md`).

**Remedy:** Before spawning any agents, review `references/tool-mapping.md` and
confirm every planned tool call is valid for the selected execution mode:

- **`subagents` mode — available:** `Agent` with `subagent_type` to spawn,
  `SendMessage(type="shutdown_request")` to shut down. **Not available
  (captains):** `TaskCreate`, `TaskList`, `TaskGet`, `TaskUpdate`,
  `SendMessage(type="message")`, `SendMessage(type="broadcast")`, `TeamCreate`,
  `TeamDelete`. **Exception:** The admiral uses `TaskCreate`/`TaskUpdate`/`TaskList`
  for session-level visibility tracking (the user's Ctrl+T task list). These
  tasks are not visible to captains — they are for the user's benefit only.
- **`agent-team` mode — available:** `TeamCreate` to form squadron, `Agent`
  with `team_name` + `name` to spawn, `TaskCreate`/`TaskList`/`TaskGet`/`TaskUpdate`
  for coordination, `SendMessage` for all message types, `TeamDelete` to
  stand down. **Not available:** `Agent` with `subagent_type` for captains
  (marines still use `subagent_type`).

- **`single-session` mode — available:** `TaskCreate`, `TaskUpdate`, `TaskList`,
  `TaskGet` (for visibility tracking). **Not available:** `Agent`, `TeamCreate`,
  `TeamDelete`, `SendMessage`.

If detected mid-mission, consult `references/damage-control/comms-failure.md`
for recovery procedures.
