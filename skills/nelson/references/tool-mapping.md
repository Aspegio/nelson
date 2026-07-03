# Tool Mapping Reference

Maps Nelson operations to Claude Code tool calls by execution mode.

## Tool Reference

| Nelson Operation | Claude Code Tool | Mode |
|---|---|---|
| Form the squadron | `TeamCreate` | agent-team |
| Spawn captain | `Agent` with `team_name` + `name` | agent-team |
| Spawn captain | `Agent` with `subagent_type` | subagents |
| Charter dynamic workflow | Battle-plan Workflow Charter prompt | workflow / hybrid-workflow |
| Launch workflow stage | Claude Code workflow run from approved charter | workflow / hybrid-workflow |
| Record workflow telemetry | `nelson-data.py event --type workflow_* ...` | workflow / hybrid-workflow |
| Compose a standing-goal condition | `nelson-data.py goal-condition --mission-dir ...` | all modes |
| Set the standing goal | `/goal <condition>` (Stop hook) | all modes |
| Check / clear the standing goal | `/goal` / `/goal clear` | all modes |
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
- **`workflow` mode:** One approved autonomous dynamic workflow run. Nelson v1
  does not directly call a workflow API or write runnable workflow scripts; it
  produces the Workflow Charter and verification contract that Claude Code can
  use to create or run the workflow. Track the workflow as a fleet asset and log
  `workflow_charter_created`, `workflow_run_started`, and
  `workflow_run_completed` / `workflow_run_stopped` events as appropriate.
    - **Available:** Workflow Charter, Claude Code workflow run, loose telemetry
      via `nelson-data.py event`
    - **Not available:** Mid-run Nelson approval gates. Stop the run and use
      `hybrid-workflow` when approval is needed before continuing.
- **`hybrid-workflow` mode:** A sequence of separately approved workflow stages.
  Use for Station 2/3 work, Sounding-the-Channel probes, or any mission that
  needs human sign-off between stages. Each stage is its own workflow run with
  Nelson review before the next stage launches.
    - **Available:** Same workflow primitives as `workflow`, plus Nelson
      permission gates between stages
    - **Not available:** Arbitrary mid-run human input inside a workflow stage

¹ Visibility tracking uses the same task tools as agent-team coordination but
serves a different purpose: making mission progress visible in the user's
Ctrl+T task list. In `subagents` and `single-session` modes, only the admiral
calls these tools; captains never see or interact with these task entries.

## Dynamic Workflow Notes

Agents spawned by Claude Code workflows run in `acceptEdits` mode and inherit
the session tool allowlist. Shell, web, or MCP calls outside that
allowlist may still prompt. Therefore, the workflow charter must state any
expected tool needs up front and the admiral must not assume a workflow can
bypass permission gates.

A reusable workflow can be saved as `.claude/workflows/<name>.js` (project) or
`~/.claude/workflows/<name>.js` (personal) and re-run as the `/<name>` command;
watch and pause/resume runs from the `/workflows` view. Nelson's charter is what
you hand to that mechanism. See `workflow-doctrine.md` for the charter-to-script
bridge, Sounding-the-Channel probes, verification contracts, cost guardrails,
telemetry, and damage-control mapping.

## Standing Goal Notes

`/goal <condition>` is an admiral-level Stop hook, not a per-agent tool — set it
once for the session, never inside a captain or workflow run. Its evaluator
judges the condition against the **conversation transcript only**; it does not
read files or run commands. Because Nelson's completion evidence lives on disk,
compose the condition with `nelson-data.py goal-condition` (which words it
against transcript-visible facts) rather than by hand, and surface that evidence
into chat at Stand Down. Full doctrine — availability, resumption, subagent
scope, anti-patterns — is in `references/goal-alignment.md`.

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
| Treating a workflow stage as an agent-team squadron | Workflows are scripted runs, not peer-messaging teams | Track it as a fleet asset with a Workflow Charter and telemetry |
| Expecting human input inside a workflow run | Dynamic workflows do not provide arbitrary mid-run Nelson gates | Use `hybrid-workflow` and require approval between separate workflow runs |
| Assuming Nelson v1 invokes workflow APIs directly | v1 ships doctrine and charters, not a workflow compiler | Give Claude Code the approved charter/prompt to create or run the workflow |
| Hand-writing a `/goal` against on-disk artifacts | The evaluator sees only the transcript, so it never observes them and the Stop hook loops forever | Compose with `nelson-data.py goal-condition` and state completion evidence in chat |
| Setting a `/goal` inside a captain or workflow run | The goal is a session-scoped admiral backstop, not a per-agent control | Set it once at Step 1; govern subagents with the verification contract |
