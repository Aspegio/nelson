# Plan: Making Nelson Coding-Agent Agnostic

**Date:** 2026-04-06
**Status:** Draft -- reviewed, decisions recorded
**Author:** HMS Argyll (synthesis captain)
**Reviewed:** 2026-04-06 by Admiralty

---

## 1. Executive Summary

Nelson is a Claude Code skill that orchestrates multi-agent software development using a Royal Navy metaphor. Today, Nelson is tightly coupled to Claude Code's API surface: 280+ direct references across 45+ files targeting Claude Code-specific tools (`Agent`, `TaskCreate`, `SendMessage`, `TeamCreate`), Anthropic-specific model names (`haiku`, `sonnet`, `opus`), and Claude Code's plugin/settings infrastructure.

This coupling locks Nelson to a single platform at a time when the coding-agent landscape is diversifying rapidly. OpenCode, Gemini CLI, and Codex CLI all support subagent architectures, skill systems, and file operation tools that are functionally equivalent to Claude Code's -- but with different API surfaces, different coordination primitives, and different packaging formats.

### Admiralty Review Decisions (2026-04-06)

After reviewing the initial plan and research, the following decisions were taken:

1. **Nelson requires agent-team primitives.** Nelson's core value is the coordination layer: quarterdeck rhythm, peer messaging, shared task list, damage control, crew hierarchy. On platforms without agent-team support, Nelson degrades to "subagents with fancy naming" -- which defeats the purpose. **Nelson will NOT target platforms that lack agent-team coordination primitives.**

2. **Codex CLI is the first non-Claude-Code target** -- when ready. Codex has near-identical SKILL.md format and can act as an MCP server for external orchestration via OpenAI's Agents SDK, which may provide the coordination surface Nelson needs.

3. **Tier 2 (hub-and-spoke) is acceptable** for platforms that eventually gain partial agent-team support. Full Tier 1 parity is not required.

4. **Clean cut, no backward compatibility.** When Nelson abstracts its tool references, the old Claude Code-specific SKILL.md will not be maintained alongside.

5. **Operations vocabulary lives inline in SKILL.md**, not in a separate reference file.

6. **Phase 4 (native plugin packaging per platform) is dropped.** Manual skill installation is sufficient.

7. **This is a longer-term roadmap item**, not the next implementation priority. The plan serves as a reference for when the ecosystem matures.

### Revised Strategy

Given these decisions, the plan pivots from "make Nelson work everywhere now" to:

- **Short-term:** Introduce operations vocabulary and model-tier abstraction as documentation hygiene (makes Nelson's docs cleaner regardless of multi-platform ambitions).
- **Medium-term:** Write a Codex CLI adapter specification when Codex adds agent-team primitives or when Agents SDK orchestration proves viable.
- **Watch list:** Monitor OpenCode (agent-teams on dev branch) and Gemini CLI (no multi-agent roadmap yet).
- **Dropped:** Graceful degradation to single-session/subagents-only mode. If a platform can't run a squadron, Nelson doesn't sail there.

**What this plan does NOT propose:** Nelson will not become a runtime library or code artifact. It remains a documentation-driven skill. The "abstraction layer" is a set of conventions, reference documents, and naming patterns -- not compiled code. Nelson will not target platforms that lack the coordination primitives that make it valuable.

---

## 2. Current State: Nelson's Claude Code Coupling

### Coupling Inventory

| Category | Coupling Type | Count | Examples |
|---|---|---|---|
| **Agent spawning** | CRITICAL | ~40 refs | `Agent` tool with `team_name`, `name`, `subagent_type`, `mode`, `isolation` |
| **Task management** | CRITICAL | ~30 refs | `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet` |
| **Team lifecycle** | CRITICAL | ~15 refs | `TeamCreate`, `TeamDelete` |
| **Messaging** | CRITICAL | ~25 refs | `SendMessage` with types: message, broadcast, shutdown_request, shutdown_response, plan_approval_response |
| **Plan mode** | HARD | ~10 refs | `ExitPlanMode` for Station 2/3 workflows |
| **Subagent types** | HARD | ~20 refs | `"general-purpose"`, `"Explore"` |
| **Permission modes** | HARD | ~15 refs | `mode: "acceptEdits"`, `mode: "plan"` |
| **Model names** | HARD | ~20 refs | `"haiku"`, `"sonnet"`, `"opus"` |
| **Plugin system** | HARD | ~10 refs | `.claude-plugin/`, `plugin.json`, `marketplace.json` |
| **Settings files** | HARD | ~15 refs | `.claude/settings.json`, `.claude/settings.local.json` |
| **Worktree isolation** | HARD | ~5 refs | `isolation: "worktree"` on Agent tool |
| **Environment vars** | HARD | ~5 refs | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` |
| **File tools** | SOFT | ~60 refs | `Read`, `Edit`, `Write`, `Bash`, `Grep`, `Glob` (portable names) |
| **Nelson-layer concepts** | SOFT | ~100+ refs | Standing orders, damage control, quarterdeck rhythm, hull integrity, commendations |

### Key Observation

Nelson's value is overwhelmingly in its prompt-driven operational logic -- the standing orders, damage control procedures, crew roles, quarterdeck rhythm, and action stations system. These are pure markdown instructions that work identically on any LLM platform. The platform-specific coupling is concentrated in two areas:

1. **Tool names and parameters** in `tool-mapping.md`, `SKILL.md`, `squadron-composition.md`, and `crew-roles.md`.
2. **Infrastructure assumptions** about plugin format, settings files, environment variables, and model names.

---

## 3. Target Platforms

### Capability Comparison

| Capability | Claude Code | OpenCode | Gemini CLI | Codex CLI |
|---|---|---|---|---|
| **Subagent spawning** | `Agent` tool | `task` tool | Auto-delegation / `@agent` | Built-in spawn |
| **Subagent recursion** | Unlimited | Unlimited | None (single-level) | `max_depth=1` default |
| **Agent teams (shared coordination)** | Native (`TeamCreate`, `TaskCreate`, `SendMessage`) | Community branch (JSONL inboxes, peer mesh) | None | None |
| **Shared task list** | `TaskCreate`/`TaskList`/`TaskGet`/`TaskUpdate` | Agent-team tasks (dev branch) | `write_todos` (single-agent) | `update_plan`/`todo_write` (single-agent) |
| **Peer messaging** | `SendMessage` (leader-centric) | JSONL inboxes (full mesh, dev branch) | None | None |
| **File tools** | Read, Edit, Write, Bash, Grep, Glob | read, edit, write, bash, grep, glob | read_file, replace, write_file, run_shell_command, grep_search, glob | read_file, apply_patch, shell, rg, glob_file_search |
| **Custom agents** | YAML in agents/ | Markdown+YAML in .opencode/agents/ | Markdown+YAML in .gemini/agents/ | TOML in .codex/agents/ |
| **Skill system** | SKILL.md + references/ | SKILL.md + references/ (reads .claude/ fallback) | GEMINI.md context files | SKILL.md + references/ |
| **Instructions file** | CLAUDE.md | AGENTS.md (reads CLAUDE.md fallback) | GEMINI.md | AGENTS.md |
| **Model providers** | Anthropic only | 75+ providers | Google only (Gemini family) | OpenAI + Ollama/custom |
| **Per-agent model** | Via Agent tool params | Via agent frontmatter | Via agent frontmatter | Via TOML config |
| **Sandbox** | OS-level (permission modes) | Per-tool allow/ask/deny | Seatbelt/Docker/gVisor profiles | Seatbelt/Bubblewrap modes |
| **Plugin/Extension** | .claude-plugin/ (JSON) | .opencode/plugins/ (JS/TS) | gemini-extension.json | Plugin system (TOML) |
| **Hooks** | 3 types (Pre/Post ToolUse, Stop) | Plugin lifecycle hooks | 12 event types | hooks.json (experimental) |
| **Worktree isolation** | `isolation: "worktree"` | Not documented | Not supported | Not supported |
| **MCP support** | Client | Client | Client + Server | Client + Server |

### Platform Maturity for Nelson

| Platform | Single-Session | Subagents Mode | Agent-Team Mode |
|---|---|---|---|
| Claude Code | Full | Full | Full |
| OpenCode | Full | Full | Partial (dev branch, uncertain release timeline) |
| Gemini CLI | Full | Partial (no recursion, no structured reporting) | None |
| Codex CLI | Full | Full (hub-and-spoke) | None (MCP server mode enables external orchestration) |

---

## 4. Abstraction Architecture

### Design Principles

1. **Convention over code.** Nelson is a documentation-driven skill. The abstraction layer is a set of naming conventions and reference documents, not compiled adapters.
2. **Platform detection at mission start.** Nelson detects which platform it is running on and loads the appropriate adapter reference.
3. **Graceful degradation.** Nelson operates at the highest capability tier the platform supports. Missing primitives trigger fallback strategies, not errors.
4. **One SKILL.md, multiple adapters.** The core SKILL.md uses platform-neutral operation names. Each platform has a `platform-adapters/<platform>.md` reference that maps those names to concrete tool calls.

### Architecture Diagram

```
SKILL.md (platform-neutral operations)
    │
    ├── references/                     (unchanged -- standing orders, damage control, etc.)
    │
    ├── references/platform-adapters/   (NEW -- one per platform)
    │   ├── claude-code.md
    │   ├── opencode.md
    │   ├── gemini-cli.md
    │   └── codex-cli.md
    │
    ├── references/operations.md        (NEW -- canonical Nelson operation vocabulary)
    │
    └── references/tool-mapping.md      (REPLACED by operations.md + adapters)
```

### How It Works

1. **Mission start:** Nelson detects the platform (see Section 7, Phase 3).
2. **Adapter load:** Nelson reads the appropriate `platform-adapters/<platform>.md` file.
3. **Capability tier:** The adapter declares which Nelson capability tier the platform supports (Full, Subagents, Single-Session).
4. **Operation execution:** When SKILL.md says "Spawn Captain," the agent looks up the concrete tool call in the loaded adapter.

---

## 5. Nelson Capability Tiers

### Tier 1: Full Orchestration (agent-team mode)

**Available on:** Claude Code. Partially on OpenCode (if agent-team feature reaches stable release).

All Nelson features operational:
- Shared task list with dependency tracking
- Peer-to-peer messaging between captains
- Coordinated shutdown (shutdown_request/response)
- Team lifecycle (form squadron / stand down)
- Plan approval workflows
- Quarterdeck rhythm with full checkpoint cadence
- Worktree isolation (Claude Code only)

### Tier 2: Hub-and-Spoke Orchestration (subagents mode)

**Available on:** All four platforms.

Nelson features with adaptations:
- Admiral spawns captains as independent subagents
- Each captain runs to completion and returns results (no live messaging)
- Admiral tracks state directly (no shared task list -- admiral maintains a local task tracker in the quarterdeck report)
- No peer communication between captains -- all coordination flows through the admiral
- Shutdown is implicit (subagent completes and returns)
- Quarterdeck checkpoints occur between captain returns, not on a timer
- Standing orders, damage control, action stations, crew roles all operate normally
- Crew recursion: available on Claude Code and OpenCode; unavailable on Gemini CLI; limited (`max_depth=1`) on Codex CLI

**Degradation strategy for missing primitives:**

| Tier 1 Primitive | Tier 2 Fallback |
|---|---|
| `TeamCreate` / `TeamDelete` | No-op; squadron is a logical concept tracked in quarterdeck report |
| `TaskCreate` / `TaskUpdate` / `TaskList` / `TaskGet` | Admiral maintains task state in `{mission-dir}/quarterdeck-report.md` and in-context notes |
| `SendMessage(type="message")` | Not available; admiral includes all necessary context in captain's initial briefing |
| `SendMessage(type="broadcast")` | Not available; admiral communicates with captains individually at spawn time |
| `SendMessage(type="shutdown_request")` | Not needed; subagent returns naturally on completion |
| `SendMessage(type="plan_approval_response")` | Not available; captain plans must be self-contained or use file-based handoff |
| Worktree isolation | Not available; strict file ownership enforcement via standing orders |

### Tier 3: Sequential Execution (single-session mode)

**Available on:** All four platforms.

Nelson operates with a single agent executing all work:
- No spawning, no coordination overhead
- All standing orders, damage control, and action stations still apply
- Quarterdeck checkpoints become self-checkpoints at task boundaries
- Hull integrity monitoring applies to the single session
- All prompt-driven Nelson logic is fully functional

### Tier Selection Logic

```
IF platform supports agent-team primitives (shared task list + messaging):
    → Tier 1 (Full Orchestration)
ELSE IF platform supports subagent spawning:
    → Tier 2 (Hub-and-Spoke)
ELSE:
    → Tier 3 (Sequential)

User override: User can explicitly request any tier at or below the platform maximum.
```

---

## 6. Abstraction Layer Design

### 6.1 Operations Vocabulary (`references/operations.md`)

This new reference defines Nelson's canonical operation names -- platform-neutral verbs that SKILL.md and all references use instead of Claude Code tool names.

| Nelson Operation | Category | Description |
|---|---|---|
| `spawn-captain` | Agent | Create a new captain agent with briefing, model, and permissions |
| `spawn-crew` | Agent | Captain creates a crew member with role, briefing, and tool restrictions |
| `spawn-marine` | Agent | Deploy a short-lived specialist subagent |
| `form-squadron` | Team | Establish the team coordination infrastructure (Tier 1 only) |
| `disband-squadron` | Team | Tear down team infrastructure and archive (Tier 1 only) |
| `create-task` | Task | Register a task with owner, dependencies, deliverables |
| `update-task` | Task | Change task status, reassign owner, add notes |
| `list-tasks` | Task | Retrieve current task states |
| `get-task` | Task | Retrieve a single task's full details |
| `send-message` | Comms | Send a directed message to a specific captain |
| `broadcast` | Comms | Send a message to all captains |
| `request-shutdown` | Comms | Ask a captain to shut down cleanly |
| `respond-shutdown` | Comms | Captain acknowledges shutdown |
| `approve-plan` | Comms | Admiral approves a captain's proposed plan |
| `read-file` | File | Read file contents |
| `edit-file` | File | Replace text in a file |
| `write-file` | File | Create or overwrite a file |
| `run-command` | File | Execute a shell command |
| `search-content` | File | Search file contents with regex |
| `find-files` | File | Find files by glob pattern |
| `enter-worktree` | Isolation | Give an agent an isolated repository copy |
| `exit-worktree` | Isolation | Merge worktree changes back |

### 6.2 Agent Factory

The Agent Factory abstraction governs how Nelson spawns agents across platforms.

**Interface:**

```yaml
spawn-captain:
  inputs:
    name: string           # Ship name (e.g., "HMS Kent")
    briefing: string       # Full crew briefing from template
    model-tier: string     # "flagship" | "standard" | "economy"
    permissions: string    # "full" | "read-only" | "plan-only"
    file-ownership: list   # Files this captain may modify
    team: string?          # Team identifier (Tier 1 only)
    isolation: string?     # "worktree" | "shared" (default: shared)
  outputs:
    agent-id: string       # Platform-specific agent reference
```

**Platform Mapping:**

| Parameter | Claude Code | OpenCode | Gemini CLI | Codex CLI |
|---|---|---|---|---|
| `name` | `Agent(name=...)` | Agent filename | Agent filename | Agent TOML name |
| `briefing` | Prompt content in `Agent` call | Markdown body of agent file | Markdown body of agent file | `developer_instructions` in TOML |
| `model-tier: flagship` | Omit model param (inherits admiral) | `model: <configured flagship>` | `model: gemini-3-pro` | `model: gpt-5.4` |
| `model-tier: standard` | Omit model param | `model: <configured standard>` | `model: gemini-2.5-pro` | `model: gpt-5.4` |
| `model-tier: economy` | `model: "haiku"` | `model: <configured economy>` | `model: gemini-3-flash` | `model: gpt-5.4-mini` |
| `permissions: full` | `mode: "acceptEdits"` | `permission: { edit: "allow" }` | `tools: ["*"]` | `sandbox_mode: "workspace-write"` |
| `permissions: read-only` | `subagent_type: "Explore"` | `permission: { edit: "deny" }` | `tools: ["read_file","glob","grep_search"]` | `sandbox_mode: "read-only"` |
| `team` | `Agent(team_name=...)` | Agent teams API | N/A | N/A |
| `isolation: worktree` | `Agent(isolation="worktree")` | N/A | N/A | N/A |

### 6.3 Task Store

The Task Store abstraction governs how Nelson tracks task state.

**Interface:**

```yaml
create-task:
  inputs:
    id: number
    name: string
    owner: string          # Captain ship name
    dependencies: list     # Task IDs this depends on
    deliverables: list     # Expected output files/artifacts
    station: number        # Action station tier (0-3)
  outputs:
    task-ref: string       # Platform-specific task reference

update-task:
  inputs:
    task-ref: string
    status: string         # "pending" | "in_progress" | "completed" | "blocked"
    notes: string?

list-tasks:
  outputs:
    tasks: list            # All tasks with current status

get-task:
  inputs:
    task-ref: string
  outputs:
    task: object           # Full task details
```

**Platform Mapping:**

| Operation | Claude Code (Tier 1) | All Platforms (Tier 2 Fallback) |
|---|---|---|
| `create-task` | `TaskCreate` | Admiral records task in `{mission-dir}/quarterdeck-report.md` and in-context state |
| `update-task` | `TaskUpdate` | Admiral updates quarterdeck report on captain return |
| `list-tasks` | `TaskList` | Admiral reads quarterdeck report |
| `get-task` | `TaskGet` | Admiral reads quarterdeck report |

**Tier 2 implementation detail:** The quarterdeck report already contains a task status table. In Tier 2, this becomes the authoritative task store rather than a reflection of an external tool. The structured data capture script (`nelson-data.py`) records task state transitions regardless of tier.

### 6.4 Message Bus

The Message Bus abstraction governs inter-agent communication.

**Interface:**

```yaml
send-message:
  inputs:
    to: string             # Target agent name
    content: string
    type: string           # "message" | "broadcast" | "shutdown_request" | "shutdown_response" | "plan_approval"

broadcast:
  inputs:
    content: string
```

**Platform Mapping:**

| Operation | Claude Code (Tier 1) | OpenCode Agent Teams | Tier 2 Fallback |
|---|---|---|---|
| `send-message` | `SendMessage(type="message")` | JSONL inbox write | Not available -- include all context in initial briefing |
| `broadcast` | `SendMessage(type="broadcast")` | Broadcast to all members | Not available |
| `request-shutdown` | `SendMessage(type="shutdown_request")` | Member status transition | Not needed -- subagent returns naturally |
| `respond-shutdown` | `SendMessage(type="shutdown_response")` | Status acknowledgement | Not needed |
| `approve-plan` | `SendMessage(type="plan_approval_response")` | Custom message type | Not available -- captain's plan must be self-contained |

### 6.5 Permission Model

**Interface:**

```yaml
agent-permissions:
  levels:
    full:        "Agent can read, write, and execute"
    edit-only:   "Agent can read and write but not execute shell"
    read-only:   "Agent can only read files and search"
    plan-only:   "Agent can only produce plans, not execute"
```

**Platform Mapping:**

| Level | Claude Code | OpenCode | Gemini CLI | Codex CLI |
|---|---|---|---|---|
| `full` | `mode: "acceptEdits"` + `subagent_type: "general-purpose"` | `permission: { edit: "allow", bash: "allow" }` | `tools: ["*"]` | `sandbox_mode: "workspace-write"` |
| `read-only` | `subagent_type: "Explore"` | `permission: { edit: "deny", bash: "deny" }` | `tools: ["read_file","glob","grep_search"]` | `sandbox_mode: "read-only"` |
| `plan-only` | `mode: "plan"` | N/A (use read-only + instructions) | Approval mode: `plan` | N/A (use read-only + instructions) |

### 6.6 Model Selection

The current model-selection reference uses Anthropic-specific names (`haiku`, `sonnet`, `opus`). The abstraction replaces these with provider-agnostic cost tiers.

**Interface:**

```yaml
model-tiers:
  flagship:    "Most capable model available -- used for admiral and high-weight agents"
  standard:    "Strong general-purpose model -- used for captains and complex crew"
  economy:     "Fast, cheap model -- used for low-weight crew and marines"
```

**Platform Mapping:**

| Tier | Claude Code | OpenCode | Gemini CLI | Codex CLI |
|---|---|---|---|---|
| `flagship` | Admiral's model (Opus/Sonnet) | Configured primary model | Gemini 3 Pro / 2.5 Pro | gpt-5.4 |
| `standard` | Admiral's model (inherited) | Configured primary model | Gemini 2.5 Pro | gpt-5.4 |
| `economy` | `model: "haiku"` | Configured small model | Gemini 3 Flash / 2.5 Flash | gpt-5.4-mini |

**Weight mapping preserved:** The existing weight table (admiral=10, crew=2, etc.) and threshold rule (weight <= 4 gets economy, weight >= 5 gets standard/flagship) remain unchanged. Only the model name resolution changes.

### 6.7 Isolation

| Strategy | Claude Code | OpenCode | Gemini CLI | Codex CLI |
|---|---|---|---|---|
| Worktree | `isolation: "worktree"` | Not available | Not available | Not available |
| File ownership | Standing order `split-keel.md` | Same | Same | Same |
| Sandbox | Permission modes | allow/ask/deny per tool | Seatbelt profiles | Sandbox modes |

**Degradation:** On platforms without worktree support, Nelson falls back to strict file ownership enforcement via the `split-keel.md` standing order. This is already the default approach -- worktree isolation is an optional enhancement.

---

## 7. Migration Strategy

### Phase 1: Introduce Nelson Operations Vocabulary

**Goal:** Decouple SKILL.md and references from Claude Code tool names.

**Scope:**
- Create `references/operations.md` defining the canonical operation vocabulary.
- Update `SKILL.md` to use operation names (e.g., "Use `spawn-captain`" instead of "Use the `Agent` tool with `team_name` and `name`").
- Update `references/tool-mapping.md` to become the Claude Code adapter (or replace it with `references/platform-adapters/claude-code.md`).
- Update `references/squadron-composition.md` to reference operation names.
- Update `references/crew-roles.md` to use `permissions: read-only` instead of `subagent_type: "Explore"`.
- Update `references/model-selection.md` to use tier names instead of `"haiku"`.
- Add a "Platform Detection" section to SKILL.md Step 1 (Sailing Orders).

**Key constraint:** After Phase 1, Nelson MUST still work identically on Claude Code. The Claude Code adapter maps every operation back to the exact same tool calls used today.

**Estimated file changes:** 8-12 files modified, 2-3 new files created.

### Phase 2: Create Adapter Specifications

**Goal:** Define how Nelson operations map to each target platform.

**Scope:**
- Create `references/platform-adapters/claude-code.md` -- the reference adapter.
- Create `references/platform-adapters/opencode.md`.
- Create `references/platform-adapters/gemini-cli.md`.
- Create `references/platform-adapters/codex-cli.md`.
- Each adapter declares: supported capability tier, operation-to-tool mappings, platform-specific setup instructions, known limitations.

**Key constraint:** Adapters are reference documents, not code. They instruct the LLM on how to translate Nelson operations into platform-specific tool calls.

**Estimated file changes:** 4 new files created, 0 existing files modified.

### Phase 3: Platform Detection and Graceful Degradation

**Goal:** Nelson auto-detects the platform and adjusts its behavior.

**Scope:**
- Add platform detection logic to SKILL.md Step 1 (before Sailing Orders). Detection heuristics:

| Signal | Platform |
|---|---|
| `TeamCreate` tool available in tool list | Claude Code (agent-team mode) |
| `Agent` tool available | Claude Code |
| `task` tool available + `todowrite` tool | OpenCode |
| `run_shell_command` tool + `replace` tool | Gemini CLI |
| `apply_patch` tool + `shell` tool | Codex CLI |
| Env var `OPENCODE_CONFIG` set | OpenCode |
| Env var `GEMINI_API_KEY` set | Gemini CLI |
| Env var `CODEX_HOME` set | Codex CLI |
| Config file `.opencode/` exists | OpenCode |
| Config file `.gemini/` exists | Gemini CLI |
| Config file `.codex/` exists | Codex CLI |

- Add Tier 2 fallback instructions for every coordination primitive in SKILL.md Steps 3-5.
- Update damage control procedures to include Tier 2 recovery paths.
- Update session-hygiene to detect platform and record it in mission metadata.

**Key constraint:** Detection must be robust but not fragile. If detection fails, default to Tier 2 (subagents mode) with generic file operation tool names.

**Estimated file changes:** 3-5 files modified, 0 new files created.

### Phase 4: Plugin/Extension Packaging (Future)

**Goal:** Distribute Nelson natively on each platform.

**Scope:**
- Create `gemini-extension.json` manifest for Gemini CLI.
- Create OpenCode plugin packaging.
- Create Codex CLI plugin packaging.
- Maintain `.claude-plugin/` for Claude Code.

**Key constraint:** This phase is lower priority -- Nelson can work on other platforms via manual skill installation (copying files) before native packaging exists.

**Estimated file changes:** 3-4 new packaging files per platform.

### Phase Summary

| Phase | Effort | Risk | Dependency |
|---|---|---|---|
| Phase 1: Operations Vocabulary | Medium (2-3 sessions) | Low -- purely additive, Claude Code keeps working | None |
| Phase 2: Adapter Specifications | Medium (1-2 sessions) | Low -- new files only, no existing changes | Phase 1 |
| Phase 3: Platform Detection | High (2-3 sessions) | Medium -- modifies SKILL.md control flow | Phase 1 + 2 |
| Phase 4: Plugin Packaging | Low per platform (1 session each) | Low -- parallel with other work | Phase 3 |

---

## 8. File-by-File Impact Assessment

### Files That Change

| File | Phase | Change Type | Description |
|---|---|---|---|
| `skills/nelson/SKILL.md` | 1, 3 | **Major rewrite** | Replace all Claude Code tool names with Nelson operations. Add platform detection in Step 1. Add Tier 2 fallback paths in Steps 3-5. |
| `skills/nelson/references/tool-mapping.md` | 1 | **Replace** | Becomes `platform-adapters/claude-code.md` or is rewritten to reference the operations vocabulary. |
| `skills/nelson/references/squadron-composition.md` | 1 | **Moderate edit** | Replace `Agent` tool references, `isolation: "worktree"`, and `subagent_type` with operation names. Replace mode-specific tool references with tier references. |
| `skills/nelson/references/crew-roles.md` | 1 | **Moderate edit** | Replace `subagent_type: "general-purpose"` and `subagent_type: "Explore"` with `permissions: full` and `permissions: read-only`. Replace `cost-weight` model name references. |
| `skills/nelson/references/model-selection.md` | 1 | **Moderate edit** | Replace `"haiku"`, `model: "haiku"`, and admiral's model references with tier names (`economy`, `flagship`). Keep weight table and threshold rule unchanged. |
| `skills/nelson/references/action-stations.md` | 1 | **Minor edit** | Replace any Claude Code tool name references with operation names. |
| `skills/nelson/references/damage-control/relief-on-station.md` | 1, 3 | **Moderate edit** | Replace Agent tool references. Add Tier 2 fallback (file-based turnover instead of messaging). |
| `skills/nelson/references/damage-control/comms-failure.md` | 3 | **Moderate edit** | Add Tier 2 section (comms failure is moot in hub-and-spoke mode). |
| `skills/nelson/references/damage-control/man-overboard.md` | 1 | **Minor edit** | Replace tool names. |
| `skills/nelson/references/damage-control/hull-integrity.md` | 1 | **Minor edit** | Replace tool names if any. |
| `skills/nelson/references/damage-control/session-hygiene.md` | 3 | **Moderate edit** | Add platform detection recording step. |
| `skills/nelson/references/damage-control/session-resumption.md` | 1 | **Minor edit** | Replace tool names. |
| `skills/nelson/references/admiralty-templates/crew-briefing.md` | 1 | **Minor edit** | Replace Claude Code-specific instructions in briefing template. |
| `skills/nelson/references/admiralty-templates/damage-report.md` | 1 | **No change** | JSON schema is platform-neutral. |
| `skills/nelson/references/admiralty-templates/turnover-brief.md` | 1 | **No change** | Markdown template is platform-neutral. |
| `skills/nelson/references/admiralty-templates/quarterdeck-report.md` | 1 | **No change** | Markdown template is platform-neutral. |
| `skills/nelson/references/admiralty-templates/captains-log.md` | 1 | **No change** | Markdown template is platform-neutral. |
| `skills/nelson/references/standing-orders/*.md` | 1 | **Minor edits** | Replace tool names where referenced. Most standing orders are pure operational logic -- no tool names. |
| `skills/nelson/references/structured-data.md` | 1 | **No change** | Python script calls are platform-neutral. |
| `skills/nelson/references/royal-marines.md` | 1 | **Minor edit** | Replace spawning instructions with operation names. |
| `CLAUDE.md` | 3 | **Minor edit** | Add note about multi-platform support. |
| `.claude-plugin/plugin.json` | - | **No change** | Claude Code packaging unchanged. |
| `.claude-plugin/marketplace.json` | - | **No change** | Claude Code packaging unchanged. |

### New Files

| File | Phase | Description |
|---|---|---|
| `skills/nelson/references/operations.md` | 1 | Canonical Nelson operations vocabulary |
| `skills/nelson/references/platform-adapters/claude-code.md` | 2 | Claude Code adapter specification |
| `skills/nelson/references/platform-adapters/opencode.md` | 2 | OpenCode adapter specification |
| `skills/nelson/references/platform-adapters/gemini-cli.md` | 2 | Gemini CLI adapter specification |
| `skills/nelson/references/platform-adapters/codex-cli.md` | 2 | Codex CLI adapter specification |

### Files That Do NOT Change

The following files are platform-neutral and require no modifications:

- All standing orders (pure operational logic, no tool names in most files)
- `references/commendations.md`
- `references/structured-data.md`
- All admiralty templates (JSON/markdown schemas)
- `scripts/nelson-data.py` and `scripts/test_nelson_data.py`
- `scripts/check-references.sh`
- `scripts/count-tokens.py`
- `agents/*.yaml` (these define Nelson's agent interfaces, not platform tool calls)
- `demos/` (entirely independent)

---

## 9. Risks and Trade-offs

### Risk 1: Increased Cognitive Load for the LLM

**Risk:** Adding an indirection layer (operations vocabulary -> adapter -> tool call) increases the number of reference documents the LLM must hold in context. This could degrade performance, especially on smaller models.

**Mitigation:** The adapter is loaded once at mission start and contains a simple lookup table. The operations vocabulary is a short reference. The total additional context is ~500-800 tokens per adapter -- well within budget.

**Trade-off accepted:** Minor context overhead in exchange for platform portability.

### Risk 2: Tier 2 Loses Coordination Fidelity

**Risk:** Hub-and-spoke (Tier 2) fundamentally changes Nelson's coordination model. Captains cannot message each other, cannot observe shared task state, and cannot be redirected mid-task. This reduces the admiral's ability to respond to emergent blockers.

**Mitigation:**
- Captain briefings must be more comprehensive in Tier 2 (all context up-front, no mid-task corrections).
- The admiral processes captain results sequentially and can adapt the next captain's briefing based on previous results.
- File-based coordination (writing status to `{mission-dir}/`) provides a partial shared state surface.
- The quarterdeck report becomes the authoritative coordination artifact.

**Trade-off accepted:** Reduced coordination fidelity on platforms without agent-team support, in exchange for broad platform availability.

### Risk 3: Platform Detection May Be Fragile

**Risk:** Heuristic-based detection (checking for tool availability, environment variables, config directories) could misidentify the platform or fail on unusual setups.

**Mitigation:**
- Detection uses multiple signals with a confidence scoring approach.
- If detection is ambiguous, Nelson asks the user to confirm.
- Users can explicitly specify the platform in sailing orders.
- Default fallback (Tier 2 with generic tool names) is safe.

### Risk 4: Adapter Drift

**Risk:** Platform APIs evolve. Claude Code may change tool names. OpenCode's agent-team feature may ship with a different API than the dev branch. Gemini CLI may add agent-team support. Codex CLI may change tool signatures.

**Mitigation:**
- Each adapter has a `last-verified` date.
- Adapters are documentation files that are quick to update.
- Platform release notes should be monitored quarterly.

**Trade-off accepted:** Ongoing maintenance burden in exchange for multi-platform support.

### Risk 5: Subagent Recursion Gaps

**Risk:** Gemini CLI does not support subagent recursion (captains cannot spawn crew). Codex CLI limits depth to 1 by default. This means Nelson's captain-crew hierarchy is unavailable on these platforms.

**Mitigation:**
- On platforms without recursion, the captain implements directly (0 crew). The crew-or-direct decision tree in `crew-roles.md` already has a "captain implements directly" path.
- On Codex CLI, the default `max_depth=1` can be increased via configuration if the user opts in.
- The battle plan step explicitly checks platform capability before assigning crew.

**Trade-off accepted:** Reduced crew depth on some platforms. Nelson's crew system is an optimization, not a requirement -- captains can always implement directly.

### Risk 6: Loss of Claude Code-Specific Optimizations

**Risk:** Nelson currently uses Claude Code-specific features (worktree isolation, Explore subagent type, acceptEdits mode) that have no equivalent on other platforms. Abstracting these away may reduce effectiveness on Claude Code.

**Mitigation:** The Claude Code adapter maps operations back to the exact same tool calls and parameters used today. No Claude Code functionality is lost. The abstraction is purely in naming -- the underlying behavior is identical.

---

## 10. Open Questions

### Q1: Should Nelson maintain backward compatibility with pre-abstraction SKILL.md?

The current SKILL.md is Claude Code-specific. After Phase 1, it will use platform-neutral operations. Should the old Claude Code-specific SKILL.md be preserved as an alternative entry point, or is a clean cut acceptable?

**Recommendation:** Clean cut. The Claude Code adapter ensures identical behavior. Maintaining two SKILL.md versions doubles maintenance for zero functional benefit.

### Q2: When should OpenCode's agent-team feature be considered stable enough for Tier 1 support?

The feature is currently on OpenCode's `dev` branch as a community contribution. Its availability in stable releases is uncertain.

**Recommendation:** Write the OpenCode adapter for Tier 2 (subagents mode) now. Add Tier 1 support to the adapter when/if the feature reaches a stable release. The adapter format supports declaring capability tiers.

### Q3: Should Nelson support mixed-platform squadrons?

OpenCode's agent-team feature supports multi-provider model mixing. Could a Nelson squadron have captains running on different LLM providers?

**Recommendation:** Out of scope for the initial abstraction. This is an OpenCode-specific feature that would require a fundamentally different coordination model. Revisit after the basic abstraction is proven.

### Q4: How should Nelson's plugin packaging work for platforms with different manifest formats?

Nelson currently uses `.claude-plugin/plugin.json` for distribution. Gemini CLI uses `gemini-extension.json`. Codex and OpenCode have their own formats.

**Recommendation:** Defer to Phase 4. Nelson can work on other platforms via manual skill installation (copying the `skills/nelson/` directory). Native packaging for each platform is a nice-to-have that does not block the core abstraction work.

### Q5: Should the operations vocabulary use verbs or nouns?

Current proposal uses imperative verbs (`spawn-captain`, `create-task`). An alternative is noun-based (`captain-spawn`, `task-create`).

**Recommendation:** Imperative verbs. They match the Royal Navy command tone ("Spawn captain," "Form the squadron") and read naturally in SKILL.md instructions.

### Q6: How should damage control procedures handle platform-specific failure modes?

Each platform has unique failure modes (e.g., Claude Code agent-team communication failure, Gemini CLI sandbox expansion failures, Codex CLI thread crashes). Should damage control be extended with platform-specific sections?

**Recommendation:** Add a "Platform-Specific Considerations" subsection to each adapter specification. Keep the core damage control procedures platform-neutral. Platform-specific recovery steps go in the adapter, not in the shared damage control references.

### Q7: What is the minimum viable abstraction?

If resources are constrained, what is the smallest change that delivers meaningful value?

**Recommendation:** Phase 1 alone (operations vocabulary) is the minimum viable abstraction. It decouples Nelson's core logic from Claude Code tool names and makes the skill readable by any platform's LLM, even without a formal adapter. An LLM reading "spawn-captain" can infer the correct tool call on its platform better than one reading `Agent(team_name=..., name=..., subagent_type="general-purpose", mode="acceptEdits")`.

---

## Appendix A: Nelson Operations to Platform Tool Calls (Quick Reference)

| Nelson Operation | Claude Code | OpenCode | Gemini CLI | Codex CLI |
|---|---|---|---|---|
| `spawn-captain` | `Agent(team_name, name, ...)` | `task(agent, prompt)` | Delegation / `@agent` | Spawn subagent |
| `spawn-crew` | `Agent(subagent_type, ...)` | `task(agent, prompt)` | Not supported | Spawn with `max_depth` |
| `form-squadron` | `TeamCreate(name)` | Agent teams create | N/A | N/A |
| `disband-squadron` | `TeamDelete(name)` | Agent teams shutdown | N/A | N/A |
| `create-task` | `TaskCreate(...)` | Agent teams task list | Admiral tracks locally | Admiral tracks locally |
| `update-task` | `TaskUpdate(...)` | Agent teams task update | Admiral tracks locally | Admiral tracks locally |
| `list-tasks` | `TaskList` | Agent teams task list | Admiral tracks locally | Admiral tracks locally |
| `send-message` | `SendMessage(type="message")` | JSONL inbox write | N/A | N/A |
| `broadcast` | `SendMessage(type="broadcast")` | Broadcast all members | N/A | N/A |
| `request-shutdown` | `SendMessage(type="shutdown_request")` | Member status change | N/A (implicit) | N/A (implicit) |
| `read-file` | `Read` | `read` | `read_file` | `read_file` |
| `edit-file` | `Edit` | `edit` | `replace` | `apply_patch` |
| `write-file` | `Write` | `write` | `write_file` | N/A (use `apply_patch`) |
| `run-command` | `Bash` | `bash` | `run_shell_command` | `shell` |
| `search-content` | `Grep` | `grep` | `grep_search` | `rg` |
| `find-files` | `Glob` | `glob` | `glob` | `glob_file_search` |

---

## Appendix B: Recommended Reading Order for Implementation

1. This plan (you are here)
2. `docs/research-opencode-architecture.md` -- for OpenCode adapter details
3. `docs/research-gemini-cli-multi-agent.md` -- for Gemini CLI adapter details
4. `docs/research-codex-cli-agent-architecture.md` -- for Codex CLI adapter details
5. `skills/nelson/SKILL.md` -- the primary file to refactor
6. `skills/nelson/references/tool-mapping.md` -- the file being replaced
7. `skills/nelson/references/crew-roles.md` -- for subagent type abstraction
8. `skills/nelson/references/model-selection.md` -- for model tier abstraction
