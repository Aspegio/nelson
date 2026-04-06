# Research: Gemini CLI Multi-Agent Architecture

**Date:** 2026-04-06
**Author:** HMS Trent (patrol vessel)
**Mission:** Produce a comprehensive plan for making Nelson coding-agent agnostic

---

## Executive Summary

Gemini CLI is Google's open-source terminal-based AI coding agent, written in TypeScript and hosted at [google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli). As of April 2026 (v0.36.0), it has a subagent system, an extensions framework, a hooks system, and plan mode with todos -- all of which have conceptual parallels to Nelson's orchestration model. However, its multi-agent coordination is significantly less mature than Claude Code's agent-team primitives. The subagent feature remains experimental (since March 2026), with no shared task list between subagents, no peer messaging, and no dependency tracking.

Nelson's three execution modes (single-session, subagents, agent-team) map cleanly to Gemini CLI's capabilities at different levels of fidelity. The biggest gap is the absence of agent-team equivalents -- Gemini CLI has no `TeamCreate`, `TaskCreate`, `SendMessage`, or shared coordination surface between agents.

---

## 1. Subagent Architecture

### How Subagents Are Defined

Subagents are Markdown files with YAML frontmatter, placed at:
- **Project level:** `.gemini/agents/*.md`
- **User level:** `~/.gemini/agents/*.md`

The YAML frontmatter contains configuration; the Markdown body becomes the agent's system prompt.

### Configuration Schema

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Unique slug (lowercase, hyphens, underscores) |
| `description` | Yes | Purpose description; helps main agent decide when to delegate |
| `kind` | No | `local` (default) or `remote` |
| `tools` | No | Allowlist of tool names; supports wildcards (`*`, `mcp_*`) |
| `mcpServers` | No | Inline MCP server config, isolated to this agent |
| `model` | No | Model override for this specific agent |
| `temperature` | No | 0.0-2.0 (default: 1) |
| `max_turns` | No | Max conversation turns (default: 30) |
| `timeout_mins` | No | Execution time limit in minutes (default: 10) |

### Invocation

Two mechanisms:
1. **Automatic delegation:** The main agent routes tasks based on subagent descriptions.
2. **Forced invocation:** Users prefix prompts with `@agent-name`.

From the main agent's perspective, a subagent looks like a tool call: invoke it, it does work, it returns a summary. The subagent's entire multi-turn conversation is compressed into a single entry in the main agent's history.

### Isolation Model

- Each subagent gets an independent conversation history (prevents main agent context bloat).
- Tool access is restricted to the explicit `tools` list -- no inheritance from the main agent.
- **Subagents cannot call other subagents** (recursion prevention).
- Per-agent policies can be enforced via `policy.toml` with a `subagent` property.

### Nelson Mapping

| Nelson Concept | Gemini CLI Equivalent | Fidelity |
|---|---|---|
| Spawn captain (subagents mode) | Automatic delegation or `@agent-name` | High |
| Captain briefing | Markdown body of agent file | High |
| Tool restriction per agent | `tools` array with wildcards | High |
| Model override per agent | `model` field in frontmatter | High |
| Subagent recursion (crew) | Not supported (single-level only) | None |

---

## 2. Task Coordination

### What Exists

Gemini CLI has a **todo system** (`write_todos` tool) that displays a task list above the input box. Tasks can be marked `IN_PROGRESS`, completed, or cancelled. Users can toggle the full view with `Ctrl+T`.

However, this is a **single-agent feature** -- it tracks one agent's work items within a single session. There is no shared task list across subagents, no cross-agent dependency tracking, and no peer messaging.

### What Does Not Exist

| Nelson Concept | Gemini CLI Status |
|---|---|
| `TaskCreate` / `TaskList` / `TaskGet` / `TaskUpdate` (shared) | Does not exist |
| `SendMessage` (peer-to-peer) | Does not exist |
| `SendMessage(type="broadcast")` | Does not exist |
| Dependency tracking between agents | Does not exist |
| Shared coordination surface | Does not exist |
| Admiral-mediated plan approval | Does not exist as a primitive |

### Orchestration Pattern

The current pattern is basic hub-and-spoke:
1. Main agent calls a subagent as a tool.
2. Subagent does work in isolation.
3. Subagent returns a compressed summary.
4. Main agent incorporates summary and decides next steps.

There is no way for Agent A to message Agent B, or for agents to observe each other's task progress.

---

## 3. Agent Teams / Parallel Execution

### Current State

Gemini CLI supports **limited parallel execution**: "Multiple subagents can run in the same turn if their tasks are independent and read-only." However:

- **No mutation in parallel:** "Never run parallel subagents that mutate the same files" -- race conditions are a known risk.
- **No team abstraction:** There is no `TeamCreate` / `TeamDelete` equivalent.
- **Experimental status:** Parallel execution has "known implementation issues" as of March 2026.
- **YOLO mode by default in subagents:** Subagents execute tools without confirmation, risking silent file modifications.

Third-party projects like [Maestro-Gemini](https://github.com/josstei/maestro-gemini) work around limitations by spawning separate CLI processes, but this is not a native capability.

### Community Interest

A [Multi-Agent Architecture Proposal](https://github.com/google-gemini/gemini-cli/discussions/7637) exists as a community discussion, and [post-v1.0 agent work](https://github.com/google-gemini/gemini-cli/issues/3132) is tracked, but formal multi-agent coordination is not yet on the released roadmap.

### Nelson Mapping

| Nelson Mode | Gemini CLI Support | Notes |
|---|---|---|
| `single-session` | Full | Main agent does all work sequentially |
| `subagents` | Partial | Subagents exist but no structured reporting, no recursion |
| `agent-team` | None | No shared task list, no messaging, no team lifecycle |

---

## 4. Tool System

### Built-in Tools

| Gemini CLI Tool | Internal Name | Description |
|---|---|---|
| `list_directory` | ReadFolder | List files/subdirs in a path |
| `read_file` | ReadFile | Read file contents (text, images, audio, PDF) |
| `write_file` | WriteFile | Write/overwrite a file (requires approval) |
| `glob` | FindFiles | Find files by glob pattern |
| `grep_search` | SearchText | Regex search in file contents (uses `git grep` if available) |
| `replace` | Edit | Replace text in files with precision control (requires approval) |
| `run_shell_command` | Shell | Execute arbitrary shell commands |
| `google_web_search` | WebSearch | Search the web |
| `web_fetch` | WebFetch | Fetch and process URL content |
| `write_todos` | Todos | Create/update task lists |
| `ask_user` | AskUser | Request input from user during execution |

### Mapping to Nelson's Tool Expectations

| Nelson/Claude Code Tool | Gemini CLI Equivalent | Match |
|---|---|---|
| `Read` | `read_file` | Direct |
| `Write` | `write_file` | Direct |
| `Edit` | `replace` | Direct (both use old/new string matching) |
| `Glob` | `glob` | Direct |
| `Grep` | `grep_search` | Direct |
| `Bash` | `run_shell_command` | Direct |
| `WebSearch` | `google_web_search` | Direct |
| `WebFetch` | `web_fetch` | Direct |
| `Agent` (spawn subagent) | `@agent-name` / automatic | Different mechanism (not a tool call) |
| `TaskCreate` / `TaskUpdate` | `write_todos` (single-agent only) | Partial -- not shared |
| `SendMessage` | None | No equivalent |
| `TeamCreate` / `TeamDelete` | None | No equivalent |
| `EnterWorktree` / `ExitWorktree` | None (Docker sandbox partially overlaps) | No equivalent |

### MCP Support

Gemini CLI is both an MCP client and server. MCP servers can be configured in `settings.json` or bundled in extensions. This is the primary extensibility mechanism for adding custom tools.

---

## 5. Extensibility

### Extensions Framework

Extensions are the primary packaging mechanism. An extension bundles:

| Component | Format | Description |
|---|---|---|
| MCP Servers | JSON config in manifest | Connect to external tools/APIs |
| Custom Commands | TOML files in `commands/` | Slash commands with prompt templates |
| Subagents | Markdown files in `agents/` | Agent definitions with YAML frontmatter |
| Hooks | JSON in `hooks/hooks.json` | Lifecycle interceptors |
| Policies | TOML files in `policies/` | Safety/permission rules |
| Context Files | `GEMINI.md` | Playbook instructions for the model |
| Themes | JSON in manifest | UI color customization |
| Settings | JSON in manifest | User-configurable values with env var binding |

### Extension Structure

```
.gemini/extensions/<name>/
  gemini-extension.json     -- Manifest (name, version, mcpServers, excludeTools)
  commands/                 -- Custom slash commands (TOML)
  agents/                   -- Subagent definitions (Markdown + YAML)
  hooks/hooks.json          -- Hook definitions
  policies/                 -- Policy rules (TOML)
  GEMINI.md                 -- Context/instructions
```

### Installation

```
gemini extensions install https://github.com/<owner>/<repo>
```

An [Extensions Gallery](https://geminicli.com/extensions/) serves as the central marketplace. Partners include Dynatrace, Elastic, Figma, Harness, Postman, Shopify, Snyk, and Stripe.

### Custom Commands (TOML)

```toml
prompt = "Analyze the codebase for security vulnerabilities"
description = "Run security audit"
```

Commands support argument injection (`{{args}}`), shell execution (`!{...}`), and file content injection (`@{...}`).

### Nelson Mapping

| Nelson Concept | Gemini CLI Equivalent | Fidelity |
|---|---|---|
| Plugin manifest (`.claude-plugin/plugin.json`) | `gemini-extension.json` | Analogous |
| SKILL.md entrypoint | `GEMINI.md` context file | Analogous |
| Skill references (loaded on demand) | Context files + subagent definitions | Partial |
| Agent YAML interfaces | Agent Markdown + YAML frontmatter | Analogous |
| Standing orders | Policies (TOML) | Partial -- Gemini policies are permission-focused, not anti-pattern-focused |

---

## 6. Model Support

### Available Models

| Model | Use Case |
|---|---|
| Gemini 3 Pro (preview) | Complex reasoning, latest generation |
| Gemini 3 Flash (preview) | Fast results, latest generation |
| Gemini 2.5 Pro | Deep reasoning, coding (1M+ token context) |
| Gemini 2.5 Flash | Fast, budget-friendly multimodal |
| Auto (Gemini 3) | System chooses Pro or Flash per task |
| Auto (Gemini 2.5) | System chooses Pro or Flash per task |

### Per-Agent Model Override

Subagents can specify a `model` field in their YAML frontmatter to use a different model than the main agent. This enables cost optimization: cheap Flash models for scanning/analysis, expensive Pro models for complex reasoning.

**Key limitation:** The `/model` command and `--model` flag do **not** override subagent models. Subagent model selection is controlled per-agent in the agent definition file.

### Nelson Mapping

Nelson's `model-selection.md` weight-based system (weight <= 4 gets haiku, weight >= 5 gets admiral's model) maps to Gemini CLI's per-agent model override, but the implementation mechanism differs:

| Nelson | Gemini CLI |
|---|---|
| Admiral decides model per agent at runtime | Model set statically in agent YAML frontmatter |
| Weight-based threshold rule | No weight system; manual per-agent configuration |
| Dynamic adjustment based on task complexity | Auto mode chooses Pro/Flash per task, but not per-subagent dynamically |

---

## 7. Configuration

### Hierarchy (lowest to highest precedence)

1. System defaults (`/etc/gemini-cli/system-defaults.json` or platform equivalent)
2. User settings (`~/.gemini/settings.json`)
3. Project settings (`.gemini/settings.json`)
4. System overrides (`/etc/gemini-cli/settings.json`)
5. Environment variables
6. Command-line arguments

### Key Environment Variables

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Authentication |
| `GEMINI_MODEL` | Override default model |
| `GEMINI_CLI_HOME` | Root config directory |
| `GOOGLE_CLOUD_PROJECT` | Vertex AI project |
| `GOOGLE_APPLICATION_CREDENTIALS` | Credentials JSON path |
| `SEATBELT_PROFILE` | macOS sandbox profile |
| `GEMINI_SANDBOX` | Sandbox method |
| `SANDBOX_FLAGS` | Custom Docker/Podman flags |

### Context Files (GEMINI.md)

Equivalent to Claude Code's `CLAUDE.md`:
- `~/.gemini/GEMINI.md` -- Global context
- Project root `GEMINI.md` -- Project context
- Subdirectory `GEMINI.md` -- Component-specific context
- Hierarchical loading with upward traversal (stops at `.git` or configured boundary markers)

### Approval Modes

| Mode | Equivalent |
|---|---|
| `default` | Standard confirmation prompts |
| `auto_edit` | Auto-approve file edits |
| `plan` | Read-only mode |
| `yolo` | No confirmation for any tool |

### Nelson Mapping

| Nelson / Claude Code | Gemini CLI |
|---|---|
| `CLAUDE.md` | `GEMINI.md` |
| `.claude/settings.json` | `.gemini/settings.json` |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` | No equivalent (no agent-team feature) |
| Plugin install | `gemini extensions install` |

---

## 8. Permission Model

### Sandbox Methods

| Method | Platform | Description |
|---|---|---|
| macOS Seatbelt | macOS | Built-in `sandbox-exec` with configurable profiles |
| Docker/Podman | Cross-platform | Container-based isolation |
| gVisor (runsc) | Linux | User-space kernel isolation |
| LXC/LXD | Linux (experimental) | Full-system containers |
| Windows Native | Windows | `icacls` integrity levels |

### Seatbelt Profiles (macOS)

| Profile | Writes | Network |
|---|---|---|
| `permissive-open` (default) | Restricted to project dir | Allowed |
| `permissive-proxied` | Restricted to project dir | Via proxy |
| `restrictive-open` | Strict (decline by default) | Allowed |
| `restrictive-proxied` | Strict | Via proxy |
| `strict-open` | Read+write restricted to working dir | Allowed |
| `strict-proxied` | Read+write restricted | Via proxy |

### Sandbox Expansion

When a sandboxed command fails due to permissions, Gemini CLI presents a "Sandbox Expansion Request" dialog. Users can approve additional permissions for that specific execution without reconfiguring the sandbox.

### Subagent Permissions

Subagent tool access is controlled by the `tools` array in the agent definition. Permissions do **not** inherit from the main agent. However, sandbox expansion for subagents is noted as "incomplete" in the current experimental release.

### Custom Sandbox

Projects can provide `.gemini/sandbox.Dockerfile` for project-specific sandbox configuration, or custom `.sb` Seatbelt profiles at `.gemini/sandbox-macos-custom.sb`.

---

## 9. Hooks System

Gemini CLI has a comprehensive hooks system with 12 event types across four categories. This is significantly more granular than Claude Code's PreToolUse/PostToolUse model.

### Hook Events

| Category | Events |
|---|---|
| **Tool** | `BeforeTool`, `AfterTool` |
| **Agent** | `BeforeAgent`, `AfterAgent` |
| **Model** | `BeforeModel`, `BeforeToolSelection`, `AfterModel` |
| **Lifecycle** | `SessionStart`, `SessionEnd`, `Notification`, `PreCompress` |

### Hook Actions

Hooks communicate via stdin/stdout JSON. Available actions per hook type include:
- **Block execution:** `decision: "deny"` or exit code 2
- **Modify arguments:** `hookSpecificOutput.tool_input`
- **Inject context:** `hookSpecificOutput.additionalContext`
- **Synthetic responses:** `hookSpecificOutput.llm_response` (skip LLM entirely)
- **Tail calls:** `hookSpecificOutput.tailToolCallRequest` (chain tool executions)
- **Kill loop:** `continue: false`

### Configuration

Hooks are configured in `settings.json` (project or user level) or bundled in extensions via `hooks/hooks.json`.

### Nelson Mapping

Nelson does not currently use Claude Code's hook system directly, but Gemini CLI's hooks could serve as enforcement points for Nelson's standing orders, damage control procedures, and action station tiers.

---

## 10. Remote Agents (A2A Protocol)

Gemini CLI supports the Agent-to-Agent (A2A) protocol for connecting to remote agents hosted as HTTP services.

### Configuration

```yaml
---
kind: remote
name: my-remote-agent
agent_card_url: https://example.com/agent-card
---
```

### Authentication

Four methods: API Key, HTTP (Bearer/Basic), Google Credentials (ADC), OAuth 2.0 (PKCE).

### Nelson Relevance

This is a forward-looking capability with no direct Claude Code equivalent. Nelson could theoretically delegate to remote specialist agents, but this would require the A2A protocol and is beyond the current scope.

---

## 11. Gap Analysis for Nelson Portability

### Features That Map Well (high portability confidence)

| Feature | Notes |
|---|---|
| Subagent spawning | Agent Markdown files with YAML frontmatter |
| Per-agent tool restriction | `tools` array with wildcards |
| Per-agent model override | `model` field in frontmatter |
| Context files | `GEMINI.md` hierarchy mirrors `CLAUDE.md` |
| Extension packaging | `gemini-extension.json` bundles agents, commands, hooks, MCP |
| Custom commands | TOML-based slash commands |
| File operations | All core tools have direct equivalents |
| Hooks/lifecycle | More granular than Claude Code |
| Sandbox/permissions | More granular than Claude Code |

### Features That Do Not Map (blockers for full portability)

| Nelson Feature | Gap | Impact |
|---|---|---|
| `agent-team` mode | No team abstraction exists | Cannot use shared task list, peer messaging, or coordinated deliverables |
| `TaskCreate`/`TaskUpdate` (shared) | `write_todos` is single-agent only | No shared coordination surface |
| `SendMessage` | No inter-agent messaging | Captains cannot communicate with each other or the admiral |
| `TeamCreate`/`TeamDelete` | No team lifecycle | No way to form or disband a squadron |
| Subagent recursion (crew) | Subagents cannot spawn subagents | Nelson's captain-crew hierarchy cannot be replicated |
| `EnterWorktree`/`ExitWorktree` | No git worktree support | Worktree isolation mode unavailable |
| Dynamic model assignment | Model is static per agent definition | Admiral cannot dynamically assign models based on task weight |
| Structured damage reports | No equivalent to JSON artifact exchange | Would need custom MCP server or file-based workaround |

### Features Where Gemini CLI Exceeds Claude Code

| Feature | Advantage |
|---|---|
| Context window per agent | 1M+ tokens (Gemini 2.5 Pro) vs ~200K (Claude) |
| Hooks granularity | 12 event types vs 3 (PreToolUse, PostToolUse, Stop) |
| Sandbox flexibility | 6+ profiles, Docker, gVisor, LXC, custom Seatbelt |
| Extension ecosystem | Marketplace with gallery, partner integrations |
| Remote agents (A2A) | No Claude Code equivalent for connecting to external agent services |
| Plan mode | Dedicated read-only planning mode with research subagents |
| Auto model routing | System can choose Pro/Flash automatically per task |

---

## 12. Recommendations for Nelson Portability

### Tier 1: Direct Translation (no architectural changes)

- `single-session` mode works as-is.
- `subagents` mode works with reduced capability (no structured reporting, but summary return is analogous).
- Agent definitions can be translated from Nelson's YAML agent interfaces to Gemini's Markdown+YAML frontmatter format.
- `GEMINI.md` replaces `CLAUDE.md` for context.
- Tool mapping is nearly 1:1 for file operations.

### Tier 2: Adaptation Required (workarounds needed)

- **Task tracking:** Use file-based coordination (write JSON to a shared directory) instead of `TaskCreate`/`TaskUpdate`.
- **Inter-agent communication:** Route all communication through the main agent (hub-and-spoke), since peer messaging does not exist.
- **Crew (subagent recursion):** Flatten the hierarchy. Captains cannot have crew; all agents report directly to the admiral. This means Nelson's crew sizing and role definitions need restructuring for Gemini CLI.
- **Model selection:** Pre-define agent files with appropriate model overrides rather than dynamic assignment.

### Tier 3: Not Feasible Without Gemini CLI Changes

- `agent-team` mode with full coordination (shared task list, peer messaging, plan approval).
- Deep hierarchical agent structures (admiral > captain > crew).
- Worktree isolation for parallel file mutation.
- Dynamic squadron reformation mid-mission.

---

## Sources

- [Gemini CLI Subagents Documentation](https://geminicli.com/docs/core/subagents/)
- [Remote Subagents (A2A)](https://geminicli.com/docs/core/remote-agents/)
- [Gemini CLI Extensions](https://geminicli.com/docs/extensions/)
- [Extension Reference](https://geminicli.com/docs/extensions/reference/)
- [Configuration Reference](https://geminicli.com/docs/reference/configuration/)
- [Sandbox Documentation](https://geminicli.com/docs/cli/sandbox/)
- [Hooks Reference](https://geminicli.com/docs/hooks/reference/)
- [Hooks Overview](https://geminicli.com/docs/hooks/)
- [Model Selection](https://geminicli.com/docs/cli/model/)
- [Plan Mode](https://geminicli.com/docs/cli/plan-mode/)
- [Task Planning with Todos](https://geminicli.com/docs/cli/tutorials/task-planning/)
- [Custom Commands](https://geminicli.com/docs/cli/custom-commands/)
- [File System Tools](https://geminicli.com/docs/tools/file-system/)
- [Release Notes](https://geminicli.com/docs/changelogs/)
- [GitHub Repository](https://github.com/google-gemini/gemini-cli)
- [Gemini CLI Subagents Comparison (morphllm.com)](https://www.morphllm.com/gemini-cli-subagents)
- [Multi-Agent Architecture Proposal (Discussion #7637)](https://github.com/google-gemini/gemini-cli/discussions/7637)
- [Post V1.0 Agent Work (Issue #3132)](https://github.com/google-gemini/gemini-cli/issues/3132)
- [Google Developers Blog: Hooks](https://developers.googleblog.com/tailor-gemini-cli-to-your-workflow-with-hooks/)
- [Google Developers Blog: Plan Mode](https://developers.googleblog.com/plan-mode-now-available-in-gemini-cli/)
- [Google Blog: Extensions](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-cli-extensions/)
