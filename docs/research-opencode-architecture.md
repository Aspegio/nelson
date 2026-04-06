# OpenCode Architecture Research — HMS Medway Report

**Date:** 2026-04-06
**Objective:** Map OpenCode's multi-agent architecture and extensibility model to Nelson concepts, identifying compatibility surfaces and gaps for making Nelson coding-agent agnostic.

---

## 1. Subagent Architecture

### Built-in Agents

OpenCode ships with two **primary agents** and two **subagents**:

| Agent | Type | Purpose | Tools |
|-------|------|---------|-------|
| **Build** | Primary | Default development agent | All tools enabled |
| **Plan** | Primary | Analysis and planning | Read-only; `edit` and `bash` set to `"ask"` |
| **General** | Subagent | Multi-step parallel tasks | Full tool access (except todo) |
| **Explore** | Subagent | Fast codebase exploration | Read-only |

Additionally, hidden system agents (Compaction, Title, Summary) run automatically for housekeeping.

### Spawning Mechanism

Subagents are invoked via the **Task tool** (`task.ts`). The Task tool:

1. Lists available agents dynamically (excluding primary agents).
2. Creates a new session for the selected subagent.
3. Applies agent-specific tools and system prompt.
4. Executes the task autonomously with its own context window.
5. Returns a single result message containing tool calls and text output.

Each invocation is **stateless** — no two-way communication after spawning. The parent agent pauses its LLM loop while the child runs to completion, then resumes with the child's output in context.

### Custom Agent Definition

Users define custom agents via:

- **Markdown files** in `.opencode/agents/` (project) or `~/.config/opencode/agents/` (global)
- **JSON** in `opencode.json`
- **CLI command** `opencode agent create`

Markdown agent format:

```yaml
---
description: Agent purpose description
mode: primary | subagent | all
model: provider/model-id
temperature: 0.0-1.0
permission:
  edit: ask | allow | deny
  bash:
    "git *": allow
    "rm *": deny
---

System prompt text goes here.
```

Configuration options include: `color`, `temperature`, `top_p`, `max_steps`, `hidden`, and provider-specific passthrough parameters.

### Nelson Mapping

| Nelson Concept | OpenCode Equivalent | Notes |
|---|---|---|
| Admiral | Primary agent (Build) | The orchestrating session |
| Captain (spawned) | Task tool → custom subagent | Each captain = one Task tool call |
| Crew (PWO, MEO, etc.) | Task tool from within subagent | Subagent spawns further subagents |
| Explore-type roles (NO, COX) | Explore subagent | Read-only, maps directly |
| General-purpose roles (PWO, XO) | General subagent | Full tool access, maps directly |

**Gap:** OpenCode's Task tool is sequential and stateless. A captain cannot maintain ongoing communication with the admiral after spawning. The subagent runs to completion and returns. This is fundamentally different from Claude Code's `Agent` tool which (in agent-team mode) keeps agents alive for messaging.

---

## 2. Task Coordination

### Built-in Task List

OpenCode has a `todowrite` tool that manages per-session task lists. However, these are **scoped to a single session** — there is no shared task list across subagents in the default Task tool mode.

### Agent Teams (Community Implementation)

Agent teams were implemented via PRs #12730–12732 on the `dev` branch. This adds:

- **Shared task lists** with atomic claiming and dependency support
- **Message passing** via per-agent JSONL inboxes at `team_inbox/<projectId>/<teamName>/<agentName>.jsonl`
- **Message broadcasting** — any teammate can broadcast to all members
- **Plan approval workflows** with tagged permission patterns
- **Delegate mode** — leads restricted to coordination-only tools

### Message Passing Architecture

Two-layer system:

1. **Inbox Layer (Persistent):** Append-only JSONL files. Each line: `{id, from, text, timestamp, read}`. O(1) write performance.
2. **Session Injection Layer (Delivery):** Messages injected as synthetic user messages into recipient's session. Auto-wake mechanism restarts idle recipients when new messages arrive.

### Nelson Mapping

| Nelson Concept | OpenCode Equivalent | Notes |
|---|---|---|
| Shared task list (`TaskCreate`/`TaskList`) | Agent teams task lists | Only available in agent-team mode |
| `SendMessage` (peer messaging) | JSONL inbox + session injection | Full peer-to-peer mesh (not leader-centric) |
| `SendMessage(type="broadcast")` | Broadcast to all team members | Supported natively |
| `SendMessage(type="shutdown_request")` | Member status state machine | Explicit shutdown_requested state |
| Quarterdeck checkpoint | No direct equivalent | Would need custom implementation |

**Gap:** The agent teams feature appears to be a community contribution on the `dev` branch. Its availability in stable releases is uncertain. The default Task tool has no coordination primitives.

---

## 3. Agent Teams — Parallel Orchestration

### Capabilities

- Lead AI spawns teammate agents, each with independent context windows.
- **Full mesh** peer-to-peer communication (any agent can message any other).
- **Fire-and-forget** spawning — lead returns immediately, no blocking.
- **Multi-provider mixing** — documented success with GPT-5.3 Codex, Gemini 2.5 Pro, and Claude Sonnet 4 coordinating through the same message bus.

### State Management

Two independent state machines per agent:

1. **Member Status** (coarse): ready -> busy -> shutdown_requested -> shutdown (+ error)
2. **Execution Status** (fine): idle, awaiting_input, processing, etc.

Transitions validate against allowed-transition maps with escape hatches (`guard: true` for race prevention, `force: true` for crash recovery).

### Comparison with Claude Code

| Feature | Claude Code | OpenCode Agent Teams |
|---------|-------------|----------------------|
| Storage | JSON array (O(N) rewrites) | JSONL append-only (O(1)) |
| Discovery | Polling on intervals | Event-driven auto-wake |
| Communication | Leader-centric routing | Full peer-to-peer mesh |
| State tracking | Implicit | Explicit two-level machines |
| Spawn backends | tmux, iTerm2, in-process | Single-process only |
| Provider mixing | Single provider | Multi-provider |

### Limitations

- **Single-process only** — cannot run multiple server instances against shared storage.
- **No automatic restart** — crashed teammates stay idle; human must re-engage.
- **No cross-team communication** — teams are isolated.
- **Best-effort delivery receipts** — crash between markRead and receipt injection loses notification.
- **No backpressure** — fast senders can flood slow receivers (10KB message limit).

### Nelson Mapping

| Nelson Concept | OpenCode Equivalent | Compatibility |
|---|---|---|
| `TeamCreate` | Agent teams creation | Direct mapping |
| `TeamDelete` | Team shutdown | Direct mapping |
| Squadron cap (10 agents) | No hard cap documented | Nelson would enforce this in skill logic |
| Worktree isolation | Not documented | Would need custom implementation |
| Red-cell navigator | Custom read-only agent | Definable via agent config |

---

## 4. Tool System

### Built-in Tools (14)

| Tool | Nelson Equivalent | Category |
|------|-------------------|----------|
| `bash` | Shell execution | Execution |
| `edit` | File modification (string replacement) | Code modification |
| `write` | File creation/overwrite | Code modification |
| `read` | File content retrieval | Codebase access |
| `grep` | Regex content search | Codebase access |
| `glob` | Pattern file discovery | Codebase access |
| `list` (ls) | Directory listing | Codebase access |
| `lsp` | Code intelligence (experimental) | Codebase access |
| `apply_patch` | Patch file application | Code modification |
| `skill` | Load SKILL.md documentation | Execution |
| `todowrite` | Task list management | Coordination |
| `webfetch` | Web content retrieval | External |
| `websearch` | Web search (Exa-powered) | External |
| `question` | User clarification | Interaction |

Additional tools discovered in source: `multiedit`, `codesearch`, `batch`, `plan`, `external-directory`, `truncate`.

### Tool-to-Tool Mapping (Nelson -> OpenCode)

| Nelson Tool Call | OpenCode Equivalent |
|---|---|
| `Read` | `read` |
| `Edit` | `edit` |
| `Write` | `write` |
| `Bash` | `bash` |
| `Grep` | `grep` |
| `Glob` | `glob` |
| `WebSearch` | `websearch` |
| `WebFetch` | `webfetch` |
| `Agent` (subagent) | `task` |
| `TaskCreate` / `TaskList` / `TaskGet` / `TaskUpdate` | `todowrite` (limited) or agent-team tasks |
| `SendMessage` | Agent-team messaging (if available) |
| `TeamCreate` / `TeamDelete` | Agent-team lifecycle (if available) |
| `Skill` | `skill` |

**Key observation:** The core file operation tools map almost 1:1. The divergence is entirely in the coordination layer (task management, messaging, team lifecycle).

---

## 5. Extensibility

### Skills

OpenCode has a **skill system nearly identical to Claude Code's**:

- Skills live in `skills/<name>/SKILL.md` directories.
- SKILL.md uses YAML frontmatter: `name`, `description`, `license`, `compatibility`, `metadata`.
- Skills can include `scripts/`, `references/`, and `assets/` subdirectories.
- Loaded via the `skill` tool by name.

**Discovery paths** (project-local, walking up to git root):
- `.opencode/skills/<name>/SKILL.md`
- `.claude/skills/<name>/SKILL.md` (backward compatible)
- `.agents/skills/<name>/SKILL.md`

**Global paths:**
- `~/.config/opencode/skills/<name>/SKILL.md`
- `~/.claude/skills/<name>/SKILL.md` (backward compatible)
- `~/.agents/skills/<name>/SKILL.md`

### Custom Tools

TypeScript/JavaScript files in `.opencode/tools/` (project) or `~/.config/opencode/tools/` (global):

```typescript
export default tool({
  description: "Tool description",
  args: {
    param: tool.schema.string().describe("Parameter description"),
  },
  async execute(args, context) {
    // context includes: agent, sessionID, messageID, directory, worktree
    return result;
  }
})
```

Filename becomes tool name. Multiple exports create `<filename>_<exportname>` tools. Custom tools can override built-in tools.

### Plugins

JavaScript/TypeScript modules that hook into OpenCode's event lifecycle:

- **Hook categories:** Commands, Files, LSP, Messages, Permissions, Sessions, Shell, Tools, TUI
- **Plugin context:** `project`, `client` (SDK), `$` (Bun shell), `directory`, `worktree`
- **Installation:** Local files in `.opencode/plugins/` or npm packages in `opencode.json`
- **Dependencies:** Managed via `.opencode/package.json`, auto-installed by Bun at startup

### Rules (Instructions)

- `AGENTS.md` in project root or `~/.config/opencode/AGENTS.md` globally.
- **Backward compatible with `CLAUDE.md`** — reads Claude Code's instruction files as fallback.
- Disable via `OPENCODE_DISABLE_CLAUDE_CODE` environment variable.
- Additional instructions via `opencode.json` `instructions` field (supports globs and remote URLs).

### Nelson Mapping

| Nelson Concept | OpenCode Equivalent | Compatibility |
|---|---|---|
| `SKILL.md` | `SKILL.md` (identical format) | **Direct — Nelson skills work as-is** |
| Skill `references/` directory | Supported in skill directory | Direct mapping |
| Skill `scripts/` directory | Supported in skill directory | Direct mapping |
| `CLAUDE.md` | `AGENTS.md` (with `CLAUDE.md` fallback) | **Works today without changes** |
| Plugin system (`.claude-plugin/`) | Plugin system (`.opencode/plugins/`) | Different format; needs adapter |

**Critical finding:** Nelson's SKILL.md would be discoverable by OpenCode from the `.claude/skills/nelson/` path without any changes, because OpenCode searches `.claude/skills/` as a fallback path. However, the tool-mapping references inside Nelson are Claude Code-specific and would need an abstraction layer.

---

## 6. Model Support

### Providers

OpenCode supports **75+ LLM providers** via the AI SDK and Models.dev:

- **Major:** Anthropic, OpenAI, Google Vertex AI, Amazon Bedrock, Azure OpenAI, Groq, DeepSeek, xAI
- **Routing:** OpenRouter, Together AI
- **Local:** Ollama, LM Studio, llama.cpp, vLLM
- **Specialized:** GitHub Copilot, GitLab Duo, Cerebras, Fireworks AI, Helicone

### Per-Agent Model Assignment

Each agent can specify its own `model: provider/model-id` in its YAML frontmatter. Confirmed: different subagents can use different models and different providers.

Agent teams support **multi-provider mixing** — agents from different providers coordinate through the same message bus.

### Authentication

- API keys via `/connect` command, stored in `~/.local/share/opencode/auth.json`
- OAuth (GitHub Copilot, GitLab)
- AWS credential chain (Bedrock)
- Environment variables via `{env:VARIABLE_NAME}` substitution
- Service account JSON (Google Vertex AI)

### Nelson Mapping

| Nelson Concept | OpenCode Equivalent | Notes |
|---|---|---|
| Admiral's model (never overridden) | Primary agent model | Configurable per-agent |
| Haiku for weight <= 4 | Any cheap model (Haiku, GPT-4o-mini, Gemini Flash) | More flexible — not Anthropic-locked |
| `model: "haiku"` in Task tool | `model: provider/model-id` in agent config | Must use full provider/model string |
| Cost-weight system | No built-in equivalent | Nelson's weight system is skill-level logic |

**Opportunity:** OpenCode's multi-provider model support is strictly superior to Claude Code's single-provider constraint. Nelson's model-selection reference could be generalized to support a provider-agnostic cost tier system (e.g., "cheap", "standard", "premium") rather than hardcoded model names.

---

## 7. Configuration

### Config Hierarchy (ascending precedence)

1. Remote config (`.well-known/opencode` endpoint)
2. Global config (`~/.config/opencode/opencode.json`)
3. Custom config (`OPENCODE_CONFIG` env var)
4. Project config (`opencode.json` in project root)
5. `.opencode/` directories (agents, commands, plugins)
6. Inline config (`OPENCODE_CONFIG_CONTENT` env var)
7. Managed config / MDM preferences (highest)

### Config Format

JSON/JSONC with schema validation at `opencode.ai/config.json`. Configs **merge additively** — later configs override only conflicting keys.

### Key Config Sections

```jsonc
{
  "model": "anthropic/claude-sonnet-4-5",
  "small_model": "anthropic/claude-haiku-3-5",
  "default_agent": "build",
  "provider": {
    "anthropic": {
      "options": { "timeout": 600000 }
    }
  },
  "permission": {
    "edit": "ask",
    "bash": { "git *": "allow", "rm *": "deny" }
  },
  "plugin": ["opencode-helicone-session"],
  "instructions": ["packages/*/AGENTS.md"]
}
```

### Nelson Mapping

| Nelson Config | OpenCode Equivalent |
|---|---|
| `.claude/settings.local.json` | `opencode.json` (project) |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` | Agent teams config (if merged to stable) |
| Nelson mission directory (`.nelson/missions/`) | No equivalent — Nelson creates this |

---

## 8. Permission Model

### Permission Levels

- `"allow"` — executes without approval (default for most tools)
- `"ask"` — prompts user for confirmation
- `"deny"` — blocks the action

### Granularity

- **Per-tool:** `edit`, `bash`, `read`, `webfetch`, etc.
- **Per-agent:** Agent-level permissions override global settings.
- **Bash patterns:** Glob matching with last-match-wins semantics (e.g., `"git *": "allow"`, `"git push *": "ask"`).
- **File patterns:** Edit permission can target specific paths.
- **MCP tools:** Wildcard patterns (e.g., `"mymcp_*": "ask"`).

### Defaults

Most permissions default to `"allow"`. Exceptions:
- `doom_loop`: defaults to `"ask"`
- `external_directory`: defaults to `"ask"`
- `read` on `.env` files: defaults to `"deny"`

### Nelson Mapping

| Nelson Concept | OpenCode Equivalent | Notes |
|---|---|---|
| Action Station tiers (0-3) | Permission config per agent | Nelson maps risk to permission levels |
| Read-only roles (NO, COX) | `permission: { edit: "deny", bash: "deny" }` | Agent-level config |
| Explore subagent type | Explore agent (read-only) | Direct mapping |
| Standing orders (anti-patterns) | No equivalent | Nelson's operational guardrails |

---

## Summary: Compatibility Matrix

### Features That Map Directly (low effort to abstract)

| Feature | Confidence |
|---------|------------|
| SKILL.md format and discovery | High — OpenCode reads `.claude/skills/` |
| CLAUDE.md / AGENTS.md project instructions | High — backward compatible |
| Core file tools (read, edit, write, grep, glob, bash) | High — 1:1 mapping |
| Custom agent definitions (YAML/markdown) | High — similar declarative format |
| Per-agent model assignment | High — more flexible than Claude Code |
| Permission model (allow/ask/deny) | High — similar granularity |
| Subagent spawning (basic task delegation) | High — Task tool maps to Agent tool |

### Features That Require Abstraction (medium effort)

| Feature | Challenge |
|---------|-----------|
| Agent teams (messaging, shared tasks) | Different implementation; community-contributed; may not be in stable release |
| Model selection (cost tiers) | Nelson hardcodes "haiku" — needs provider-agnostic tier system |
| Tool names in references | `tool-mapping.md` references Claude Code-specific tool names |
| Team lifecycle (TeamCreate/TeamDelete) | Different API surface |
| Message types (shutdown, broadcast, plan_approval) | Different message schema |

### Features With No OpenCode Equivalent (requires Nelson-side logic)

| Feature | Status |
|---------|--------|
| Mission directory structure (`.nelson/missions/`) | Nelson creates this via bash — portable as-is |
| Structured data capture (`nelson-data.py`) | Python script — portable as-is |
| Standing orders (anti-pattern library) | Pure prompt logic — portable as-is |
| Quarterdeck rhythm (checkpoints) | Prompt-driven — portable as-is |
| Damage control procedures | Prompt-driven — portable as-is |
| Commendations system | Prompt-driven — portable as-is |
| Hull integrity tracking | Script-based — portable as-is |
| Worktree isolation | OpenCode has no documented equivalent |

### Features Where OpenCode Is Superior

| Feature | Advantage |
|---------|-----------|
| Multi-provider model mixing | Agents can use different LLM providers in same team |
| Peer-to-peer messaging | Full mesh vs. Claude Code's leader-centric routing |
| Custom tools (TypeScript/Zod) | Richer programmatic extensibility |
| Plugin hooks (lifecycle events) | No Claude Code equivalent |
| 75+ provider support | Far broader than Claude Code's Anthropic-only |

---

## Sources

- [Agents | OpenCode](https://opencode.ai/docs/agents/)
- [Tools | OpenCode](https://opencode.ai/docs/tools/)
- [Config | OpenCode](https://opencode.ai/docs/config/)
- [Plugins | OpenCode](https://opencode.ai/docs/plugins/)
- [Custom Tools | OpenCode](https://opencode.ai/docs/custom-tools/)
- [Permissions | OpenCode](https://opencode.ai/docs/permissions/)
- [Providers | OpenCode](https://opencode.ai/docs/providers/)
- [Agent Skills | OpenCode](https://opencode.ai/docs/skills/)
- [Rules | OpenCode](https://opencode.ai/docs/rules/)
- [Ecosystem | OpenCode](https://opencode.ai/docs/ecosystem/)
- [Models | OpenCode](https://opencode.ai/docs/models/)
- [How Coding Agents Actually Work: Inside OpenCode](https://cefboud.com/posts/coding-agents-internals-opencode-deepdive/)
- [Building Agent Teams in OpenCode](https://dev.to/uenyioha/porting-claude-codes-agent-teams-to-opencode-4hol)
- [OpenCode vs Claude Code: Which AI CLI Coding Agent Wins in 2026?](https://dev.to/tech_croc_f32fbb6ea8ed4/opencode-vs-claude-code-which-ai-cli-coding-agent-wins-in-2026-45md)
- [GitHub: anomalyco/opencode](https://github.com/anomalyco/opencode)
- [Agent Teams Feature Request #12661](https://github.com/anomalyco/opencode/issues/12661)
- [Agent Teams Design #12711](https://github.com/anomalyco/opencode/issues/12711)
- [Task Tool Custom Subagent Support #20059](https://github.com/anomalyco/opencode/issues/20059)
