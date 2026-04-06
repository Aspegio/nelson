# OpenAI Codex CLI: Agent Architecture Research

> HMS Tamar patrol report -- researched 2026-04-06
> Focus: Codex CLI multi-agent capabilities, extensibility, and mapping to Nelson concepts

---

## 1. Subagent Architecture

### How subagents are spawned

Codex CLI supports spawning subagents as a stable feature (`features.multi_agent` defaults to `on`). Subagents are spawned only when the user explicitly requests parallel work -- Codex does not autonomously decide to spawn them.

The system handles full orchestration: spawning new subagents, routing follow-up instructions, waiting for results, and closing agent threads. When multiple agents run simultaneously, Codex waits until all requested results are available, then returns a consolidated response.

### Built-in agent types

Three default agent types ship out of the box:

| Agent Type | Purpose |
|---|---|
| `default` | General-purpose fallback |
| `worker` | Execution-focused implementation |
| `explorer` | Read-heavy codebase analysis |

### Spawning mechanisms

Two distinct spawning tools exist:

1. **Direct subagent spawning** -- The model calls an internal spawn tool, providing agent type, prompt, and optional model override. Each subagent gets its own thread.

2. **`spawn_agents_on_csv`** (batch/experimental) -- Reads CSV input, spawns one worker per row, each worker must call `report_agent_job_result` exactly once, and combined results are exported. This enables batch processing patterns.

### Agent addressing

As of CLI 0.117.0 (March 2026), subagents use readable path-based addresses like `/root/agent_a` with structured inter-agent messaging, replacing the earlier UUID-based system.

### Nelson mapping

| Nelson Concept | Codex Equivalent | Gap? |
|---|---|---|
| Admiral spawns captains | Parent agent spawns subagents | Close match |
| Captain spawns crew | Subagent nesting (max_depth) | Codex limits depth to 1 by default |
| Ship types (frigate/corvette) | Agent types (default/worker/explorer) | Different taxonomy but same idea |
| Royal Marines (ad-hoc specialists) | No direct equivalent | Gap -- Codex has no ephemeral specialist concept |

---

## 2. Task Coordination

### Coordination primitives

Codex CLI provides minimal built-in coordination compared to Claude Code's agent-team mode:

- **No shared task list** -- There is no equivalent of `TaskCreate`/`TaskList`/`TaskGet`/`TaskUpdate`. The parent agent tracks state directly.
- **No message passing between peers** -- Subagents report results back to their parent only. There is no equivalent of `SendMessage` between sibling agents.
- **Thread switching** -- The `/agent` slash command lets users switch between active agent threads, inspect ongoing work, and steer running subagents.
- **Consolidated results** -- The parent waits for all subagents to complete and receives a merged response.

### CSV jobs as coordination

The `spawn_agents_on_csv` tool provides a rudimentary coordination pattern: define tasks as CSV rows, spawn workers, collect structured results. This is closer to a map-reduce pattern than a coordination protocol.

### Nelson mapping

| Nelson Concept | Codex Equivalent | Gap? |
|---|---|---|
| Quarterdeck rhythm (checkpoints) | No equivalent | Significant gap -- no structured checkpoint mechanism |
| Task list as coordination surface | No shared task list | Significant gap |
| SendMessage (directed/broadcast) | No inter-agent messaging | Significant gap |
| Damage reports (structured status) | `report_agent_job_result` (CSV jobs only) | Partial -- only works in batch mode |
| Turnover briefs (handover docs) | No equivalent | Gap |

---

## 3. Agent Teams

### Parallel execution

Multiple agents can work in parallel. Key controls:

- `agents.max_threads`: Concurrent agent cap (default: **6**)
- `agents.max_depth`: Nesting depth limit (default: **1**, preventing deep recursion)
- `agents.job_max_runtime_seconds`: Per-worker timeout (default: **1800s**)

### Orchestration model

Codex uses a **hub-and-spoke** model: one parent agent orchestrates multiple child agents. Children cannot communicate with each other -- they only report back to the parent. This is simpler than Claude Code's agent-team mode where agents can message peers and share a task list.

### External orchestration via Agents SDK

For more sophisticated multi-agent workflows, Codex can run as an MCP server (`codex mcp-server`) and be orchestrated by OpenAI's Agents SDK. This enables:

- Tiered agent structures (Project Manager -> Specialists)
- Gated handoffs (verify deliverables before progressing)
- Parallel execution of independent agents
- Full trace auditability via OpenAI Traces dashboard

The MCP server exposes two tools:
- `codex` -- Initiates a session with prompt, model, approval-policy, sandbox config
- `codex-reply` -- Continues an existing conversation by thread ID

### Nelson mapping

| Nelson Concept | Codex Equivalent | Gap? |
|---|---|---|
| Form the Squadron (`TeamCreate`) | No team abstraction | Gap -- agents are individual threads, not a named group |
| Stand Down (`TeamDelete`) | Close agent threads individually | No atomic group shutdown |
| Squadron composition rules | `agents.max_threads` + `agents.max_depth` | Simpler -- no mode selection or sizing rules |
| Admiral as orchestrator | Parent agent | Close match |

---

## 4. Tool System

### Built-in tools available to agents

| Tool | Purpose | Claude Code Equivalent |
|---|---|---|
| `apply_patch` | Structured diff-based file editing (model is specifically trained on this format) | `Edit` tool |
| `shell` / `shell_exec` | Terminal command execution with working directory, timeout, escalation | `Bash` tool |
| `read_file` | Read file contents | `Read` tool |
| `list_dir` | List directory contents | `Bash` (ls) |
| `glob_file_search` | Find files by pattern | `Glob` tool |
| `rg` (ripgrep) | Content search | `Grep` tool |
| `update_plan` / `todo_write` | Task tracking with status indicators | `TaskCreate`/`TaskUpdate` |
| `view_image` | Attach local images for visual analysis | `Read` (image files) |
| `web_search` | Web search (cached by default, live optional) | `WebSearch` tool |
| `git` | All git operations | `Bash` (git) |

### Tool parallelisation

Codex supports `multi_tool_use.parallel` for simultaneous file reads, searches, and other operations -- similar to Claude Code's ability to batch tool calls.

### MCP extensibility

Codex supports Model Context Protocol (MCP) servers for adding third-party tools:

- **STDIO transport**: Local process servers
- **Streamable HTTP transport**: Remote servers with bearer token/OAuth auth
- Tool allowlists (`enabled_tools`) and denylists (`disabled_tools`)
- Per-tool approval modes
- Configurable timeouts and startup requirements

### Nelson mapping

The tool systems are broadly equivalent. Nelson's `tool-mapping.md` reference maps Nelson operations to Claude Code tools. A Codex equivalent would need to map to `apply_patch`, `shell`, `read_file`, etc. instead of `Edit`, `Bash`, `Read`.

---

## 5. Extensibility

### AGENTS.md (equivalent of CLAUDE.md)

Codex uses `AGENTS.md` files for custom instructions, following a hierarchical discovery chain:

1. **Global scope** (`~/.codex/AGENTS.md` and `~/.codex/AGENTS.override.md`)
2. **Project scope** (Git root downward to current working directory)
3. **Merge order**: Files concatenate, later files override earlier guidance
4. Max combined size: 32 KiB (`project_doc_max_bytes`)
5. Fallback filenames configurable via `project_doc_fallback_filenames`

Override mechanism: `AGENTS.override.md` takes precedence without replacing base files.

### Skills (equivalent of Claude Code skills)

Codex Skills are reusable capability packages with a defined structure:

```
my-skill/
  SKILL.md          (required -- name, description, instructions)
  scripts/          (optional)
  references/       (optional)
  assets/           (optional)
  agents/openai.yaml  (optional -- agent interface definitions)
```

Skills are discovered at repository level (`.agents/skills`), user home, and system locations. They can be invoked explicitly (`/skills`, `$` mention) or implicitly (Codex matches task to skill purpose).

### Plugins (distribution mechanism)

Plugins bundle skills + apps + MCP servers into installable packages:

- Install via `/plugins` command in CLI
- Bundle skills, app connectors (GitHub, Slack, etc.), and MCP servers
- Self-serve publishing not yet available (as of March 2026)
- Existing approval settings apply to plugin actions

### Custom agents (TOML format)

Custom agents are defined as TOML files:

- **Personal**: `~/.codex/agents/<name>.toml`
- **Project-scoped**: `.codex/agents/<name>.toml`

Required fields: `name`, `description`, `developer_instructions`

Optional fields (inherit from parent if omitted): `model`, `model_reasoning_effort`, `sandbox_mode`, `mcp_servers`, `skills.config`

`nickname_candidates` can provide readable display names when many instances of the same agent spawn.

### Nelson mapping

| Nelson Concept | Codex Equivalent | Gap? |
|---|---|---|
| SKILL.md | SKILL.md (same concept!) | Very close -- Codex adopted the same standard |
| CLAUDE.md | AGENTS.md | Same purpose, different name |
| `.claude/settings.json` | `config.toml` (TOML not JSON) | Different format, similar role |
| Agent YAML definitions | Agent TOML definitions | Different format, similar structure |
| Plugin system | Plugin system | Both have install/distribution mechanisms |
| Skills + references directory | Skills + references directory | Nearly identical structure |

---

## 6. Model Support

### Available models

| Model | Role | Characteristics |
|---|---|---|
| `gpt-5.4` | Flagship | Best reasoning + coding + agentic workflows |
| `gpt-5.4-mini` | Subagent workhorse | Fast, efficient, recommended for subagents |
| `gpt-5.3-codex` | Legacy flagship | Strong coding, capabilities folded into 5.4 |
| `gpt-5.3-codex-spark` | Real-time preview | Near-instant iteration (Pro users only) |

### Model assignment for subagents

- Subagents can use different models from the parent via `model` field in custom agent TOML
- OpenAI explicitly recommends `gpt-5.4-mini` for parallel subagents (cheaper, faster)
- `gpt-5.4` for planning and final judgment
- Reasoning effort adjustable per agent: `minimal | low | medium | high | xhigh`

### Open-source model support

The `--oss` flag enables local models via Ollama or LM Studio. Custom model providers can be configured with `base_url`, `env_key` for API credentials, and optional HTTP headers.

### Nelson mapping

| Nelson Concept | Codex Equivalent | Notes |
|---|---|---|
| Model weight table (admiral=10, crew=2) | Per-agent model assignment in TOML | Nelson is more systematic about cost-weighted selection |
| Haiku for low-weight tasks | `gpt-5.4-mini` for subagents | Same pattern -- cheap model for simple work |
| Admiral's model for high-weight tasks | `gpt-5.4` for planning | Same pattern |
| Cost-savings mode (weight threshold) | Manual model choice per agent | Nelson automates this; Codex requires explicit config |

---

## 7. Configuration

### Configuration hierarchy (highest precedence first)

1. CLI flags (`--model`, `--sandbox`, `-c key=value`)
2. Project config (`.codex/config.toml`, closest to cwd wins)
3. User config (`~/.codex/config.toml`)
4. Defaults

### Key configuration files

| File | Location | Purpose |
|---|---|---|
| `config.toml` | `~/.codex/` or `.codex/` | Main configuration |
| `AGENTS.md` | `~/.codex/` or project root | Custom instructions |
| `AGENTS.override.md` | Same locations | Temporary overrides |
| `agents/<name>.toml` | `~/.codex/agents/` or `.codex/agents/` | Custom agent definitions |
| `hooks.json` | `.codex/` | Lifecycle event hooks (experimental) |

### Key environment variables

| Variable | Purpose |
|---|---|
| `CODEX_HOME` | Custom profile directory (default: `~/.codex`) |
| `CODEX_CA_CERTIFICATE` | Custom CA bundle |
| `CODEX_SQLITE_HOME` | State database location |

### Profiles

Named configuration sets allow switching between saved configurations: `codex --profile <name>`. Profiles can override personality, reasoning effort, model, and any other config key.

### Nelson mapping

| Nelson Concept | Codex Equivalent | Notes |
|---|---|---|
| `.claude/settings.json` | `config.toml` | Different format (JSON vs TOML) |
| Skill references/ directory | Skill references/ directory | Same |
| Plugin manifest (JSON) | Plugin manifest | Similar concept |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` | `features.multi_agent = true` (on by default) | Codex has multi-agent enabled by default |

---

## 8. Permission Model

### Approval policies

Three core levels:

| Policy | Behaviour |
|---|---|
| `untrusted` | Approval required before executing non-whitelisted commands |
| `on-request` | Autonomous within sandbox; prompts when exceeding boundaries |
| `never` | No approval prompts (for automation/CI) |

### Granular approval controls

Fine-grained categories can be individually toggled:

- `sandbox_approval` -- Sandbox escalation prompts
- `rules` -- Execution policy prompts
- `mcp_elicitations` -- MCP tool side-effect prompts
- `request_permissions` -- Permission tool prompts
- `skill_approval` -- Skill script execution prompts

### Subagent permission inheritance

Subagents inherit sandbox policies and approval requirements from their parent session. There is no mechanism for per-subagent permission escalation or de-escalation beyond what the custom agent TOML specifies for `sandbox_mode`.

### Nelson mapping

| Nelson Concept | Codex Equivalent | Notes |
|---|---|---|
| Action stations (risk tiers 0-3) | Sandbox modes (read-only, workspace-write, danger-full-access) | Different granularity -- Nelson has 4 tiers, Codex has 3 |
| Admiral approval gates | Approval policies | Similar -- both require human sign-off for risky actions |
| Standing orders (anti-patterns) | No equivalent | Gap -- Codex has no anti-pattern prevention system |

---

## 9. Sandbox/Execution

### OS-level sandboxing

| Platform | Technology | Notes |
|---|---|---|
| macOS | Seatbelt (`sandbox-exec`) | Native, no additional setup |
| Linux | Bubblewrap (`bwrap`) + Seccomp | Requires `bwrap` install; fallback to unprivileged user namespaces |
| Windows | Native Windows Sandbox or WSL2 | WSL2 uses Linux sandbox path |
| Docker | Host-provided isolation | Run with `--sandbox danger-full-access` inside containers |

### Sandbox modes

| Mode | Filesystem | Network | Use Case |
|---|---|---|---|
| `read-only` | Read only | Blocked | Consultative/review |
| `workspace-write` | Read + write in workspace + `/tmp` | Configurable | Default for local work |
| `danger-full-access` | Unrestricted | Unrestricted | CI/CD or hardened VMs |

### Multi-agent sandbox behaviour

The sandbox applies to spawned commands, not just built-in file operations. Subagents inherit the parent's sandbox policy. Each subagent's commands execute within the same sandbox constraints as the parent.

### Configurable isolation

- `sandbox_workspace_write.writable_roots` -- Additional writable directories
- `sandbox_workspace_write.network_access` -- Enable outbound network
- `sandbox_workspace_write.exclude_slash_tmp` -- Exclude `/tmp` from writable roots
- `--add-dir` flag -- Grant write access to additional paths

### Nelson mapping

| Nelson Concept | Codex Equivalent | Notes |
|---|---|---|
| Hull integrity monitoring | No equivalent | Gap -- Codex has no context window health tracking |
| Damage control procedures | No equivalent | Gap -- no structured recovery protocols |
| Scuttle and reform | Close agent threads | Informal -- no structured abort-and-reform |
| Relief on station | `/fork` command (fork conversation) | Partial -- forks conversation but no structured handover |

---

## Summary: Feature Parity Matrix

| Capability | Claude Code | Codex CLI | Nelson Portability |
|---|---|---|---|
| **Subagent spawning** | `Agent` tool | Built-in spawn + custom TOML agents | High -- both support spawning |
| **Team abstraction** | `TeamCreate`/`TeamDelete` | No team concept | Low -- Nelson needs team concept or workaround |
| **Shared task list** | `TaskCreate`/`TaskList`/`TaskGet`/`TaskUpdate` | No shared task list | Low -- major coordination gap |
| **Inter-agent messaging** | `SendMessage` (directed, broadcast, shutdown) | No peer messaging | Low -- hub-and-spoke only |
| **Custom instructions** | CLAUDE.md | AGENTS.md | High -- direct equivalent |
| **Skills** | SKILL.md + references/ | SKILL.md + references/ | Very high -- nearly identical format |
| **Plugins** | Plugin system (JSON manifest) | Plugin system (TOML) | High -- both have install mechanisms |
| **Custom agents** | Agent YAML | Agent TOML | High -- different format, same concept |
| **Model selection** | Per-agent model via YAML | Per-agent model via TOML | High -- same pattern |
| **Sandbox** | OS-level (permission-based) | OS-level (Seatbelt/Bubblewrap) | High -- both use OS enforcement |
| **Approval flow** | Allowed tools config | Granular approval policies | High -- similar concepts |
| **File editing** | `Edit` tool (string replacement) | `apply_patch` (structured diffs) | Medium -- different edit paradigms |
| **MCP support** | Client | Client + Server | Higher in Codex -- can also act as MCP server |
| **Batch processing** | No built-in | `spawn_agents_on_csv` | Codex-only feature |
| **Plan mode** | No built-in | `/plan` slash command | Codex-only feature |
| **Checkpoint rhythm** | No built-in (Nelson adds this) | No built-in | Nelson-only -- needs implementation on both |
| **Structured status reporting** | No built-in (Nelson adds this) | No built-in | Nelson-only -- needs implementation on both |
| **Context health monitoring** | No built-in (Nelson adds this) | No built-in | Nelson-only -- needs implementation on both |

---

## Key Findings for Nelson Portability

### What ports easily

1. **SKILL.md format** -- Codex adopted the same skill directory structure. Nelson's `SKILL.md` and `references/` directory would work with minimal changes.
2. **Custom agent definitions** -- Nelson's agent YAML files map to Codex's TOML agent files. Format conversion needed but concepts are 1:1.
3. **Model selection strategy** -- Both systems support per-agent model assignment. Nelson's weight table could drive Codex TOML generation.
4. **Sandbox/approval mapping** -- Action station tiers map to sandbox modes with minor granularity differences.
5. **Instructions file** -- CLAUDE.md content ports to AGENTS.md with minimal structural changes.

### What requires abstraction

1. **Team lifecycle** -- Nelson's `TeamCreate`/`TeamDelete` has no Codex equivalent. Nelson would need to manage agent threads individually or build a team abstraction layer.
2. **Task coordination** -- Nelson's shared task list (`TaskCreate`/`TaskList`/`TaskUpdate`) is absent in Codex. Nelson would need to use the parent agent as a coordination hub or leverage external state (files, MCP server).
3. **Inter-agent messaging** -- `SendMessage` (directed, broadcast, shutdown) has no Codex equivalent. All communication flows through the parent agent.
4. **Checkpoint rhythm** -- Nelson's quarterdeck checkpoint model is a Nelson-layer concept, not a platform feature on either side. It would need to be re-implemented as instructions rather than tool calls.

### What does not exist in Codex

1. **Standing orders** (anti-pattern prevention) -- No equivalent; would need to be encoded in `AGENTS.md` or `developer_instructions`.
2. **Damage control procedures** -- No structured recovery protocols; would be instruction-level only.
3. **Hull integrity tracking** -- No context window health monitoring; would need custom implementation.
4. **Structured handover** (turnover briefs) -- No equivalent; could be implemented via file-based conventions.
5. **Commendation system** -- No equivalent; Nelson-only concept.

### Codex advantages Nelson could leverage

1. **MCP server mode** -- Codex can run as an MCP server, enabling external orchestration by the Agents SDK. Nelson could potentially use this for richer multi-agent patterns.
2. **Batch processing** (`spawn_agents_on_csv`) -- Useful for parallel task execution with structured result collection.
3. **Built-in plan mode** -- `/plan` provides structured planning before execution.
4. **Profile system** -- Named configuration sets could map to Nelson mission profiles.

---

## Sources

- [Codex CLI Overview](https://developers.openai.com/codex/cli)
- [Codex CLI Features](https://developers.openai.com/codex/cli/features)
- [Codex Subagents](https://developers.openai.com/codex/subagents)
- [AGENTS.md Guide](https://developers.openai.com/codex/guides/agents-md)
- [Codex with Agents SDK](https://developers.openai.com/codex/guides/agents-sdk)
- [Configuration Reference](https://developers.openai.com/codex/config-reference)
- [Sample Configuration](https://developers.openai.com/codex/config-sample)
- [Advanced Configuration](https://developers.openai.com/codex/config-advanced)
- [Codex Models](https://developers.openai.com/codex/models)
- [Agent Skills](https://developers.openai.com/codex/skills)
- [Codex Plugins](https://developers.openai.com/codex/plugins)
- [Sandboxing](https://developers.openai.com/codex/concepts/sandboxing)
- [Agent Approvals & Security](https://developers.openai.com/codex/agent-approvals-security)
- [CLI Command Reference](https://developers.openai.com/codex/cli/reference)
- [Slash Commands](https://developers.openai.com/codex/cli/slash-commands)
- [Changelog](https://developers.openai.com/codex/changelog)
- [GitHub Repository](https://github.com/openai/codex) (73,000+ stars, Rust)
- [Codex Prompting Guide](https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide)
- [Multi-Agent Orchestration Discussion](https://github.com/openai/codex/discussions/3898)
- [Building Workflows with Codex CLI & Agents SDK](https://developers.openai.com/cookbook/examples/codex/codex_mcp_agents_sdk/building_consistent_workflows_codex_cli_agents_sdk)
