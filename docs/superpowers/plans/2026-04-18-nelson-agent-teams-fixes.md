# Nelson Agent Teams Capability Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring Nelson's agent-orchestration guidance fully in line with Claude Code's experimental Agent Teams feature — fix two confirmed-broken combinations (issues #40270 and #37549), document the experimental env-var prerequisite, wire spawn-time hygiene (permission mode + model + spawn-authority) systematically into the formation flow, add background-agent and team-aware hook coverage, and resolve one open design question.

**Architecture:** Three implementation phases plus a closing analysis. Phase 1 ships safety fixes for currently-broken paths (new damage-control entries + warnings in mode-selection). Phase 2 wires existing-but-unused Claude Code parameters (`mode`, `model`) into the spawn template so they're set deliberately rather than by accident. Phase 3 adds a new background-agent reference and extends `nelson_hooks.py` to read team config for enrollment validation. Each task ends with a commit so PR history reads as discrete, reviewable fixes.

**Tech Stack:** Markdown (skill references), Python 3.12+ stdlib (hook code), pytest (hook tests), bash (verification commands).

**Beads issues closed by this plan:** `nelson-wgt`, `nelson-84f`, `nelson-la9`, `nelson-onj`, `nelson-n1p`, `nelson-x7c`, `nelson-74q`, `nelson-3nb`, `nelson-43e`

**Working directory:** `/Users/harry/Workspace/nelson/.claude/worktrees/affectionate-jones-01dcf7` (worktree on branch `claude/affectionate-jones-01dcf7`).

**Verification context:** Two GitHub bugs were confirmed open as of late March 2026 against `anthropics/claude-code`: [#40270](https://github.com/anthropics/claude-code/issues/40270) (`Agent` with `team_name` raises an internal error) and [#37549](https://github.com/anthropics/claude-code/issues/37549) (`team_name` + `isolation: "worktree"` silently lands in main repo). Plan steps assume those bugs remain open; if either has shipped a fix by execution time, adjust the wording in the new damage-control files accordingly but keep the entries — they are useful even as historical references.

---

## Pre-flight

### Task 0: Create feature branch and claim issues

**Files:**
- None (git operations only)

- [ ] **Step 1: Create the feature branch**

Run:
```bash
cd /Users/harry/Workspace/nelson/.claude/worktrees/affectionate-jones-01dcf7
git checkout -b feat/agent-teams-capability-fixes
```

Expected: `Switched to a new branch 'feat/agent-teams-capability-fixes'`

- [ ] **Step 2: Claim all nine bd issues**

Run:
```bash
bd update nelson-wgt --claim
bd update nelson-84f --claim
bd update nelson-la9 --claim
bd update nelson-onj --claim
bd update nelson-n1p --claim
bd update nelson-x7c --claim
bd update nelson-74q --claim
bd update nelson-3nb --claim
bd update nelson-43e --claim
```

Expected: each line prints `✓ Updated …`.

---

## Phase 1 — Safety fixes for broken Agent Teams paths

These tasks ship guidance and warnings for the two confirmed bugs and the undocumented env-var prerequisite. They do not change runtime behaviour but stop Nelson recommending broken patterns.

### Task 1: Add damage-control entry for the broken `Agent(team_name=...)` call (closes nelson-wgt)

**Files:**
- Create: `skills/nelson/references/damage-control/agent-team-spawn-broken.md`

- [ ] **Step 1: Create the new damage-control file**

Write the following content to `skills/nelson/references/damage-control/agent-team-spawn-broken.md`:

```markdown
# Agent Team Spawn Broken

Use when spawning a captain via `Agent(team_name=..., name=...)` returns
`[Tool result missing due to internal error]` or otherwise silently fails to
produce a teammate.

This is a known upstream regression — see
[claude-code#40270](https://github.com/anthropics/claude-code/issues/40270).
The `team_name` parameter on the `Agent` tool currently triggers an internal
error in the teammate spawn path even when `TeamCreate` and `TaskCreate`
succeed first. The issue is open as of April 2026.

## Symptoms

- `Agent(team_name="...", name="...")` returns `[Tool result missing due to
  internal error]` or empty content with no captain spawned.
- `TeamCreate` succeeded but the team has no enrolled members afterwards.
- The admiral cannot reach any captain via `SendMessage` because no captains
  exist.

## Procedure

1. Confirm the failure is the `#40270` regression by retrying once. If the
   second `Agent(team_name=...)` call returns the same error, treat the
   experimental Agent Teams spawn path as unavailable for this session.
2. Stand down the empty team if `TeamCreate` succeeded but no members
   enrolled:
   ```
   TeamDelete(team_name="<name>")
   ```
3. Fall back to `subagents` mode for the rest of the mission:
   - Update `battle-plan.json` `squadron.mode` to `subagents`.
   - Re-run the conflict scan: `python3 .claude/skills/nelson/scripts/nelson_conflict_scan.py --plan {mission-dir}/battle-plan.json`.
   - Re-spawn captains with `Agent(subagent_type="general-purpose", ...)`
     instead of `Agent(team_name=..., name=...)`.
   - Reassign captain visibility tracking via the admiral's
     `TaskCreate`/`TaskUpdate` calls (admiral exception, not captain
     coordination).
4. Log the regression and mode change in the captain's log so future
   missions know to check #40270 status before selecting `agent-team`.

## Prevention

- At the start of every `agent-team` mission, the admiral should make ONE
  test spawn before assigning the full squadron. If that spawn fails with
  the #40270 symptom, abort `agent-team` mode and select `subagents`
  instead before any tasks are committed.
- When upstream confirms a fix, remove this damage-control entry and the
  preflight check. Track the issue's status when planning new missions.

## Related

- `references/standing-orders/wrong-ensign.md` — mode/tool consistency.
- `references/damage-control/comms-failure.md` — broader infrastructure
  failure recovery.
- `references/squadron-composition.md` — mode selection (which now warns
  about #40270).
```

- [ ] **Step 2: Verify the file is well-formed and links resolve**

Run:
```bash
ls -la skills/nelson/references/damage-control/agent-team-spawn-broken.md
grep -c '^#' skills/nelson/references/damage-control/agent-team-spawn-broken.md
```

Expected:
```
-rw-r--r-- ... agent-team-spawn-broken.md
6
```
(File exists; 6 markdown headings.)

- [ ] **Step 3: Run the cross-reference checker**

Run:
```bash
bash scripts/check-references.sh
```

Expected: exit 0. If it warns about broken refs in the new file, fix the path before continuing.

- [ ] **Step 4: Commit**

```bash
git add skills/nelson/references/damage-control/agent-team-spawn-broken.md
git commit -m "docs(nelson): damage-control for broken Agent(team_name=...) #40270"
```

---

### Task 2: Add damage-control entry for `team_name` + worktree silent failure (closes nelson-84f)

**Files:**
- Create: `skills/nelson/references/damage-control/worktree-team-conflict.md`
- Modify: `skills/nelson/references/squadron-composition.md` (Worktree Isolation section, lines 51-62)

- [ ] **Step 1: Create the new damage-control file**

Write the following content to `skills/nelson/references/damage-control/worktree-team-conflict.md`:

```markdown
# Worktree + Team Name Conflict

Use when a captain spawned with both `team_name` and `isolation: "worktree"`
appears to be running in the main repository instead of an isolated worktree.

This is a known upstream bug — see
[claude-code#37549](https://github.com/anthropics/claude-code/issues/37549).
The combination silently lands the captain in the main repo with no error
raised, defeating the isolation guarantee. The bug is open as of April
2026.

## Symptoms

- Multiple captains spawned with `isolation: "worktree"` write to the same
  files and produce merge-style conflicts where none should be possible.
- `git worktree list` shows fewer worktrees than captains spawned.
- Captain logs reference paths in the main repo rather than under
  `.claude/worktrees/`.

## Procedure

1. Detect: after spawning the squadron, run
   `git worktree list` and compare the count to the number of captains
   intended to be isolated. Mismatch confirms the bug.
2. If captains have already started writing, pause them via
   `SendMessage(type="message")` instructing them to stop and report
   current state.
3. Choose one of two recovery paths:
   - **Path A (preferred): drop worktree isolation, enforce file ownership.**
     Update the battle plan so each captain owns disjoint files
     (`split-keel.md`). Re-run `nelson_conflict_scan.py` to confirm no
     overlap. Continue in `agent-team` mode without isolation.
   - **Path B: drop `agent-team` mode, keep worktrees.** Stand down the
     team via `TeamDelete`. Switch `squadron.mode` to `subagents` (which
     spawns via `subagent_type` and supports worktree isolation correctly).
     Re-spawn each captain with `isolation: "worktree"` only.
4. Log the bug and chosen recovery path in the captain's log.

## Prevention

- Until #37549 is fixed, do not combine `team_name` with `isolation:
  "worktree"` in the same `Agent` call. Choose one or the other:
  `agent-team` mode without worktrees, or `subagents` mode with worktrees.
- The squadron-composition reference now reflects this constraint.

## Related

- `references/squadron-composition.md` — Worktree Isolation guidance.
- `references/standing-orders/split-keel.md` — file ownership as the
  primary conflict-prevention mechanism.
- `references/damage-control/agent-team-spawn-broken.md` — companion bug
  in the same surface area (#40270).
```

- [ ] **Step 2: Update `squadron-composition.md` Worktree Isolation section**

In `skills/nelson/references/squadron-composition.md`, replace the entire `## Worktree Isolation` section (lines 51-62) with:

```markdown
## Worktree Isolation

When file ownership boundaries are hard to draw or multiple captains must modify overlapping files, use `isolation: "worktree"` on the `Agent` tool. This gives each captain an isolated copy of the repository via a git worktree.

Worktree isolation is a stronger alternative to the file-ownership approach in `standing-orders/split-keel.md`. Use it when:

- Multiple captains need to edit the same files.
- Merge conflict risk is high and the split-keel standing order cannot resolve it.
- Tasks are large enough that the merge cost is justified.

**Trade-off:** Worktree isolation prevents conflicts during execution but requires merging changes afterward. The admiral is responsible for coordinating the merge.

> **⚠ Known bug — do not combine `team_name` with `isolation: "worktree"`.** Per [claude-code#37549](https://github.com/anthropics/claude-code/issues/37549), the combination silently lands the captain in the main repo, defeating isolation. Choose one:
> - `agent-team` mode → enforce file ownership via `standing-orders/split-keel.md`, no worktrees.
> - `subagents` mode → use `isolation: "worktree"` freely (subagent spawning is unaffected).
>
> See `references/damage-control/worktree-team-conflict.md` for the recovery procedure.
```

- [ ] **Step 3: Verify the changes**

Run:
```bash
grep -n "37549" skills/nelson/references/squadron-composition.md skills/nelson/references/damage-control/worktree-team-conflict.md
```

Expected: at least 3 matches (1 in squadron-composition, 2 in damage-control).

- [ ] **Step 4: Run the cross-reference checker**

Run:
```bash
bash scripts/check-references.sh
```

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add skills/nelson/references/damage-control/worktree-team-conflict.md skills/nelson/references/squadron-composition.md
git commit -m "docs(nelson): warn about team_name + worktree silent failure #37549"
```

---

### Task 3: Document the `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` prerequisite (closes nelson-la9)

**Files:**
- Modify: `skills/nelson/references/squadron-composition.md` (Mode Selection section, after line 7)
- Modify: `skills/nelson/references/standing-orders/wrong-ensign.md` (add env-var symptom)
- Modify: `skills/nelson/SKILL.md` (Step 3, after line 90)

- [ ] **Step 1: Add prerequisite block to `squadron-composition.md`**

In `skills/nelson/references/squadron-composition.md`, immediately after line 7 (the User preference override paragraph), insert a new section:

```markdown
## Prerequisite for `agent-team` Mode

`agent-team` mode requires the `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` environment variable to be set when Claude Code launched. Without it, `TeamCreate`, `SendMessage` between captains, and the `team_name` parameter on `Agent` are unavailable or silently degrade.

**Quick check before selecting `agent-team`:**

1. Inspect the tool surface available in this session — if `TeamCreate` is not listed in the available tools, the env var is unset.
2. If unset, fall back to `subagents` mode, or ask the admiral to relaunch Claude Code with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 claude ...`.
3. Do not proceed past mode selection assuming agent-team capabilities will appear later — the env var is read at session start only.

> **Bug status:** Even when the env var is set, `Agent(team_name=...)` may fail with an internal error per [claude-code#40270](https://github.com/anthropics/claude-code/issues/40270). See `references/damage-control/agent-team-spawn-broken.md` for the workaround.
```

- [ ] **Step 2: Add the env-var symptom to `wrong-ensign.md`**

In `skills/nelson/references/standing-orders/wrong-ensign.md`, in the Symptoms list (lines 10-19), append a new bullet after the existing five:

```markdown
- `TeamCreate` not listed in the available tools, indicating
  `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` was not set at session launch
  (agent-team mode requires this prerequisite — see
  `references/squadron-composition.md`).
```

- [ ] **Step 3: Add prerequisite check to `SKILL.md` Step 3**

In `skills/nelson/SKILL.md`, immediately after line 90 (the closing `agent-team` description bullet) and before the **Mode-Tool Consistency Gate** header, insert:

```markdown

**Agent Teams Prerequisite:** Before committing to `agent-team` mode, confirm `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` was set at session launch — see `references/squadron-composition.md` for the quick check. If the env var is unset, `TeamCreate`/`SendMessage`/`team_name` are unavailable; fall back to `subagents` mode or have the admiral relaunch Claude Code with the env var set.
```

- [ ] **Step 4: Verify the changes**

Run:
```bash
grep -n "EXPERIMENTAL_AGENT_TEAMS" skills/nelson/SKILL.md skills/nelson/references/squadron-composition.md skills/nelson/references/standing-orders/wrong-ensign.md
```

Expected: at least 4 matches across 3 files.

- [ ] **Step 5: Cross-reference check**

Run:
```bash
bash scripts/check-references.sh
```

Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add skills/nelson/SKILL.md skills/nelson/references/squadron-composition.md skills/nelson/references/standing-orders/wrong-ensign.md
git commit -m "docs(nelson): require CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 for agent-team mode"
```

---

### Task 4: Wire new damage-control entries into `SKILL.md`'s Damage Control table

**Files:**
- Modify: `skills/nelson/SKILL.md` (Damage Control table, lines 308-321)

- [ ] **Step 1: Add two rows to the Damage Control table**

In `skills/nelson/SKILL.md`, locate the Damage Control table (around line 308). Append two rows directly before the closing of the table (after the existing `comms-failure.md` row):

```markdown
| Agent spawn returns "Tool result missing due to internal error" with `team_name` | `references/damage-control/agent-team-spawn-broken.md` |
| Captains share files despite `isolation: "worktree"` set | `references/damage-control/worktree-team-conflict.md` |
```

- [ ] **Step 2: Verify table integrity**

Run:
```bash
grep -A2 "agent-team-spawn-broken" skills/nelson/SKILL.md
grep -A2 "worktree-team-conflict" skills/nelson/SKILL.md
```

Expected: each finds the new row in the Damage Control table.

- [ ] **Step 3: Commit**

```bash
git add skills/nelson/SKILL.md
git commit -m "docs(nelson): index new agent-teams damage-control entries"
```

- [ ] **Step 4: Close Phase 1 issues**

```bash
bd close nelson-wgt nelson-84f nelson-la9
```

Expected: three `✓ Closed …` lines.

---

## Phase 2 — Spawn-time hygiene

These tasks make Nelson set the `mode` and `model` parameters deliberately at every captain spawn, and add a standing order clarifying that only the admiral can spawn agents.

### Task 5: Map Action Stations risk tiers to `Agent.mode` (closes nelson-onj)

**Files:**
- Modify: `skills/nelson/references/action-stations.md` (Plan Mode section, lines 116-122)
- Modify: `skills/nelson/SKILL.md` (Step 3 Edit permissions block, line 171)

- [ ] **Step 1: Replace the action-stations Plan Mode section with a full mapping**

In `skills/nelson/references/action-stations.md`, replace the entire `## Plan Mode for High-Risk Stations` section (lines 116-123) with:

```markdown
## Permission Mode by Station Tier

When spawning captains, set `mode` on the `Agent` tool deliberately. The mapping below applies the minimum constraint required for each station tier — overriding only when the task itself demands it.

| Station tier | Default `mode` | Rationale |
|---|---|---|
| Station 0 (Patrol) | `acceptEdits` | Low blast radius; let the captain proceed without per-edit prompts. |
| Station 1 (Caution) | `acceptEdits` | Moderate impact; rely on red-cell review and rollback notes for control. |
| Station 2 (Action) | `plan` | Captain explores in read-only plan mode; admiral approves the plan via `SendMessage(type="plan_approval_response")` before execution. |
| Station 3 (Trafalgar) | `plan` + human gate | Same as Station 2, plus the admiral must obtain explicit human confirmation before approving. |

### Plan Mode Flow (Station 2 / 3)

- The captain submits its plan via `ExitPlanMode`.
- The admiral reviews and either approves via `SendMessage(type="plan_approval_response")` (agent-team mode) or by re-spawning the captain with `mode: "acceptEdits"` once the plan is approved (subagents mode).
- Station 3 additionally requires explicit human confirmation before the admiral approves.

### When to override the default

- Use `mode: "plan"` for any captain whose task involves exploration before changes, regardless of tier.
- Use `mode: "default"` (the unset value) only when the captain is a pure-read operation (Explore subagents, Coxswain, Recce Marines).

See `references/tool-mapping.md` for the full set of coordination tools.
```

- [ ] **Step 2: Update `SKILL.md` Edit permissions block**

In `skills/nelson/SKILL.md`, replace the **Edit permissions** paragraph (line 171) with:

```markdown
**Permission mode at spawn:** Set the `mode` parameter on every `Agent` tool call per the tier mapping in `references/action-stations.md` (Permission Mode by Station Tier). At minimum, captains whose task involves editing files MUST receive `mode: "acceptEdits"` to avoid silent permission stalls; Station 2 and Station 3 captains MUST receive `mode: "plan"` for the read-only review gate. The mapping is also recorded in the formation summary (Step 3 template).
```

- [ ] **Step 3: Add `Mode` column to the formation summary template**

Still in `skills/nelson/SKILL.md`, replace the `Ships:` block inside the `SQUADRON FORMATION ORDERS` template (around lines 116-119) with:

```markdown
Ships:
  [Ship name] — [vessel type] — [station tier] — [mode] — [one-line task summary]
    Crew: [roles, or "Captain implements directly"]
  [repeat for each ship]
```

- [ ] **Step 4: Verify and check references**

Run:
```bash
grep -n "Permission Mode by Station Tier" skills/nelson/references/action-stations.md
grep -n "mode parameter on every" skills/nelson/SKILL.md
bash scripts/check-references.sh
```

Expected: each grep returns one match; check-references exits 0.

- [ ] **Step 5: Commit**

```bash
git add skills/nelson/references/action-stations.md skills/nelson/SKILL.md
git commit -m "feat(nelson): map Action Stations tiers to Agent.mode in spawn template"
```

---

### Task 6: Wire model selection into the spawn template (closes nelson-n1p)

**Files:**
- Modify: `skills/nelson/SKILL.md` (Step 3 model assignment paragraph, line 108; formation template, lines 110-122)
- Modify: `skills/nelson/references/model-selection.md` (top-of-file applicability note)

- [ ] **Step 1: Update the model-selection.md applicability note**

In `skills/nelson/references/model-selection.md`, replace lines 1-4 (the title and intro paragraph) with:

```markdown
# Model Selection

This reference governs `model` parameter assignment for all squadron agents. **All missions** must record an explicit model per ship in the formation summary (visibility); cost-savings missions additionally apply the weight-and-threshold rules below to override defaults toward `haiku`.

## Default behaviour (no cost-savings priority)

- The admiral records each ship's model in the formation summary as `inherit` (i.e. the admiral's model) unless a ship's role definition recommends otherwise.
- The `model` parameter is **omitted** from the `Agent` tool call when the ship inherits — explicit `"sonnet"` resolves to an older alias and does not match the admiral's model.
- This makes model assignment auditable in the squadron summary even when no parameter is passed at spawn.
```

(The existing Default Weight Table, Threshold Rule, and subsequent sections remain unchanged; just keep them after this new top block.)

- [ ] **Step 2: Update SKILL.md to require model assignment in all missions**

In `skills/nelson/SKILL.md`, replace line 108 (the cost-savings-only model bullet) with:

```markdown
- For each captain, record an explicit model in the formation summary using `references/model-selection.md`. In cost-savings missions, apply the weight-and-threshold rules to push appropriate roles to `haiku` and include haiku briefing enhancements. In standard missions, record `inherit` for ships that should use the admiral's model.
```

- [ ] **Step 3: Add `Model` column to the formation summary template**

Still in `skills/nelson/SKILL.md`, replace the `Ships:` block inside the `SQUADRON FORMATION ORDERS` template (which Task 5 Step 3 has already updated) with:

```markdown
Ships:
  [Ship name] — [vessel type] — [station tier] — [mode] — [model] — [one-line task summary]
    Crew: [roles, or "Captain implements directly"]
  [repeat for each ship]
```

- [ ] **Step 4: Verify**

Run:
```bash
grep -n "All missions" skills/nelson/references/model-selection.md
grep -n "record an explicit model" skills/nelson/SKILL.md
grep -c '\[model\]' skills/nelson/SKILL.md
```

Expected: each grep returns at least one match; the third returns ≥1.

- [ ] **Step 5: Commit**

```bash
git add skills/nelson/references/model-selection.md skills/nelson/SKILL.md
git commit -m "feat(nelson): record explicit model per captain in all missions"
```

---

### Task 7: Add a standing order making spawn authority explicit (closes nelson-x7c)

**Files:**
- Create: `skills/nelson/references/standing-orders/spawning-authority.md`
- Modify: `skills/nelson/SKILL.md` (Standing Orders table, lines 285-302)
- Modify: `skills/nelson/SKILL.md` (Battle Plan Gate Standing Order Check, lines 67-79)

- [ ] **Step 1: Create the new standing order**

Write the following content to `skills/nelson/references/standing-orders/spawning-authority.md`:

```markdown
# Standing Order: Spawning Authority

Only the admiral spawns agents and Royal Marines.

Captains and crew operate inside an isolated teammate context that does NOT include the `Agent` or `TeamCreate` tools. A captain that "deploys" a marine or "spawns" a sub-agent without admiral involvement cannot succeed — those tool calls are not present in the captain's tool surface.

This is not a stylistic rule; it is a structural constraint of Claude Code's teammate spawning model. The instruction set in `references/royal-marines.md` and `references/crew-roles.md` may read as if captains deploy crew or marines directly. They do not. The admiral spawns on a captain's behalf when the captain requests support.

## Symptoms

- A captain attempts an `Agent` call and receives "tool not available" or no result.
- A captain's brief instructs them to "spawn a marine" or "deploy a Recce" without specifying how to request the deployment.
- Marine deployments appear in the battle plan with a captain as the spawner rather than the admiral.

## Correct flow

1. Captain identifies need for marine support (per `references/royal-marines.md` deployment rules).
2. Captain sends `SendMessage(type="message")` to the admiral with a marine deployment brief (using `references/admiralty-templates/marine-deployment-brief.md`).
3. Admiral evaluates the request against station-tier rules (Station 2 requires admiral approval before deployment per `references/action-stations.md`).
4. Admiral spawns the marine via `Agent(subagent_type="general-purpose", ...)` (or other suitable subagent type), passing the captain's brief as the marine's prompt.
5. Marine reports back to the admiral. The admiral relays results to the captain via `SendMessage`.

## When the captain is in subagents mode

- There is no `SendMessage` channel back to the admiral. The captain instead returns control via the `Agent` return value with a "marine support requested" note. The admiral inspects the return value, decides, and spawns a follow-up subagent for the marine work.

## Remedy when violated

- If a captain's brief implies they will spawn a marine, rewrite the brief to instruct them to **request** the deployment via `SendMessage` (or via the Agent return value in subagents mode).
- If marine deployments appear in the battle plan with a captain as spawner, reassign the spawner to "Admiral" before formation closes.

## Related

- `references/royal-marines.md` — marine deployment rules.
- `references/admiralty-templates/marine-deployment-brief.md` — request format.
- `references/action-stations.md` — Marine Deployments section, station-tier gates.
- `references/crew-roles.md` — crew composition (also admiral-spawned).
```

- [ ] **Step 2: Add the new standing order to the `SKILL.md` Standing Orders table**

In `skills/nelson/SKILL.md`, locate the Standing Orders table (lines 285-302) and append a new row before the closing of the table (after the `wrong-ensign.md` row):

```markdown
| Captain or crew attempting to spawn agents or marines | `references/standing-orders/spawning-authority.md` |
```

- [ ] **Step 3: Add the new gate question to the Battle Plan Standing Order Check**

In `skills/nelson/SKILL.md`, in the **Battle Plan Gate — Standing Order Check** list (lines 68-79), append a new bullet at the end:

```markdown
- `spawning-authority.md`: Does any task assign agent or marine spawning to a captain? Reassign to the admiral.
```

- [ ] **Step 4: Verify**

Run:
```bash
ls -la skills/nelson/references/standing-orders/spawning-authority.md
grep -c "spawning-authority" skills/nelson/SKILL.md
bash scripts/check-references.sh
```

Expected: file exists; ≥2 matches in SKILL.md; check-references exits 0.

- [ ] **Step 5: Commit**

```bash
git add skills/nelson/references/standing-orders/spawning-authority.md skills/nelson/SKILL.md
git commit -m "feat(nelson): standing order — only the admiral spawns agents/marines"
```

- [ ] **Step 6: Close Phase 2 issues**

```bash
bd close nelson-onj nelson-n1p nelson-x7c
```

Expected: three `✓ Closed …` lines.

---

## Phase 3 — New capabilities

These tasks add background-agent guidance and team-aware hook validation. Phase 3 is implementable in parallel with Phase 2 if you dispatch via subagents — they touch disjoint files.

### Task 8: Add background-agent and Monitor coordination patterns (closes nelson-74q)

**Files:**
- Create: `skills/nelson/references/background-patterns.md`
- Modify: `skills/nelson/references/tool-mapping.md` (append Long-Running Tools section)
- Modify: `skills/nelson/SKILL.md` (Step 5 Quarterdeck rhythm, after line 199)

- [ ] **Step 1: Create the background-patterns reference**

Write the following content to `skills/nelson/references/background-patterns.md`:

```markdown
# Background Agent Patterns

Use this reference when a captain's task is long-running and would otherwise block the admiral's quarterdeck rhythm. Background agents free the admiral to process other captains' completions while a long-running task continues.

## When to background a captain

- The task duration exceeds two quarterdeck checkpoint intervals.
- The captain is producing intermediate output that the admiral does not need to review until completion (long builds, large refactors, exhaustive test runs).
- The captain has no upstream dependencies on other captains' output.

Do NOT background:
- Station 2 or Station 3 captains — admiral oversight is required.
- Captains whose output unblocks others (the admiral must be present to relay).
- Captains in `agent-team` mode where peer-messaging from other captains may require routing.

## Spawning a background captain

Use `run_in_background: true` on the `Agent` tool:

```
Agent(
  name="HMS Argyll",
  subagent_type="general-purpose",
  prompt="<captain brief>",
  mode="acceptEdits",
  model="sonnet",
  run_in_background=true,
)
```

The admiral receives a notification when the background agent completes; do not poll, do not insert sleep loops. Continue the quarterdeck rhythm with foreground captains while the background agent runs.

## Monitoring a background captain mid-task

Use the `Monitor` tool to stream events from a background agent's stdout. Each output line arrives as a notification:

```
Monitor(target="HMS Argyll")
```

Monitor is appropriate when:
- The captain's progress is visible in stdout and the admiral wants periodic visibility without spawning a quarterdeck checkpoint specifically for this ship.
- A circuit-breaker condition (token budget overrun, hull-integrity threshold) needs to be detected from output rather than a checkpoint.

If you only need to know when the background agent is done, do not start a Monitor — the completion notification is sufficient.

## Quarterdeck integration

When a background agent's completion notification arrives:
1. Treat it identically to a foreground idle notification — apply the three questions in `SKILL.md` Step 5.
2. Mark the captain's task `completed` in the shared task list (or session task list in `subagents` mode).
3. Continue the rhythm; do not write a checkpoint specifically for the background agent unless the cadence rule requires it.

If a background agent's circuit-breaker trips (hull integrity Red, idle timeout), invoke the corresponding damage-control procedure exactly as for a foreground captain.

## Related

- `references/damage-control/circuit-breakers.md` — automated breaker rules.
- `references/damage-control/hull-integrity.md` — threshold response.
- `references/tool-mapping.md` — Long-Running Tools section.
```

- [ ] **Step 2: Append a Long-Running Tools section to `tool-mapping.md`**

In `skills/nelson/references/tool-mapping.md`, after the Anti-Patterns table (after line 65), append:

```markdown

## Long-Running Tools

| Nelson Operation | Claude Code Tool | Mode |
|---|---|---|
| Spawn captain in background | `Agent` with `run_in_background: true` | subagents / agent-team (Station 0-1 only) |
| Stream a background captain's output | `Monitor` with target=ship name | all modes |
| Wait for any pending notification | (no explicit call) | all modes |

See `references/background-patterns.md` for when to background a captain and how to integrate completion notifications into the quarterdeck rhythm.
```

- [ ] **Step 3: Add a one-paragraph Quarterdeck integration note to SKILL.md Step 5**

In `skills/nelson/SKILL.md`, immediately after line 199 (the closing of the idle-notification rule paragraph) and before the **Shutdown attempt ceiling** header, insert:

```markdown

**Background-agent notifications:** Background captains (`Agent` with `run_in_background: true`) deliver completion notifications identical to foreground idle notifications — apply the same three questions above. Use `Monitor` to stream a background captain's output mid-task only when periodic visibility is needed; do not poll. See `references/background-patterns.md` for backgrounding criteria.
```

- [ ] **Step 4: Verify**

Run:
```bash
ls -la skills/nelson/references/background-patterns.md
grep -n "Long-Running Tools" skills/nelson/references/tool-mapping.md
grep -n "Background-agent notifications" skills/nelson/SKILL.md
bash scripts/check-references.sh
```

Expected: file exists; each grep returns one match; check-references exits 0.

- [ ] **Step 5: Commit**

```bash
git add skills/nelson/references/background-patterns.md skills/nelson/references/tool-mapping.md skills/nelson/SKILL.md
git commit -m "feat(nelson): document background-agent and Monitor patterns"
```

---

### Task 9: Add team-aware validation to `nelson_hooks.py` (closes nelson-3nb)

**Files:**
- Modify: `hooks/nelson_hooks.py` (extend `_check_mode_tool_consistency`, add helpers)
- Modify: `hooks/test_nelson_hooks.py` (new test class)

This task uses TDD — write the failing tests first, then the implementation.

- [ ] **Step 1: Write failing tests for the team-config reader**

In `hooks/test_nelson_hooks.py`, immediately before the closing test classes, add a new test class. First add the import at the top of the file with the existing `from nelson_hooks import (...)` block — append `_read_team_config` and `_check_team_enrollment` to the imported names.

Then append:

```python
class TestReadTeamConfig:
    def test_no_team_dir(self, tmp_path: Path) -> None:
        from nelson_hooks import _read_team_config
        assert _read_team_config(tmp_path / "missing", "acme") == {}

    def test_team_dir_present_no_config(self, tmp_path: Path) -> None:
        from nelson_hooks import _read_team_config
        teams_dir = tmp_path / "teams"
        (teams_dir / "acme").mkdir(parents=True)
        assert _read_team_config(teams_dir, "acme") == {}

    def test_team_config_loaded(self, tmp_path: Path) -> None:
        from nelson_hooks import _read_team_config
        teams_dir = tmp_path / "teams"
        team_dir = teams_dir / "acme"
        team_dir.mkdir(parents=True)
        cfg = {"members": [{"name": "HMS Argyll"}, {"name": "HMS Kent"}]}
        (team_dir / "config.json").write_text(json.dumps(cfg))
        assert _read_team_config(teams_dir, "acme") == cfg


class TestCheckTeamEnrollment:
    def test_no_team_name_skips_check(self) -> None:
        from nelson_hooks import _check_team_enrollment
        assert _check_team_enrollment({}, {"name": "HMS Argyll"}) is None

    def test_no_name_provided(self) -> None:
        from nelson_hooks import _check_team_enrollment
        cfg = {"members": [{"name": "HMS Argyll"}]}
        assert _check_team_enrollment(cfg, {"team_name": "acme"}) is None

    def test_duplicate_name_rejected(self) -> None:
        from nelson_hooks import _check_team_enrollment
        cfg = {"members": [{"name": "HMS Argyll"}]}
        msg = _check_team_enrollment(
            cfg, {"team_name": "acme", "name": "HMS Argyll"},
        )
        assert msg is not None
        assert "duplicate" in msg.lower()

    def test_unique_name_allowed(self) -> None:
        from nelson_hooks import _check_team_enrollment
        cfg = {"members": [{"name": "HMS Argyll"}]}
        assert _check_team_enrollment(
            cfg, {"team_name": "acme", "name": "HMS Kent"},
        ) is None
```

- [ ] **Step 2: Run the new tests — confirm they fail**

Run:
```bash
cd hooks && python3 -m pytest test_nelson_hooks.py::TestReadTeamConfig test_nelson_hooks.py::TestCheckTeamEnrollment -v
```

Expected: ImportError or AttributeError on `_read_team_config` and `_check_team_enrollment`. (Tests fail because the functions don't exist yet.)

- [ ] **Step 3: Implement `_read_team_config` and `_check_team_enrollment`**

In `hooks/nelson_hooks.py`, immediately before the `# Preflight helpers` section divider (around line 120), add:

```python
# ---------------------------------------------------------------------------
# Team config helpers
# ---------------------------------------------------------------------------


def _read_team_config(teams_dir: Path, team_name: str) -> dict[str, Any]:
    """Read a team's config.json. Returns empty dict on failure."""
    if not team_name:
        return {}
    return _read_json(teams_dir / team_name / "config.json")


def _check_team_enrollment(
    team_config: dict[str, Any], tool_input: dict[str, Any],
) -> str | None:
    """Return rejection message if the agent's name conflicts with an existing member."""
    team_name = tool_input.get("team_name")
    member_name = tool_input.get("name")
    if not team_name or not member_name:
        return None
    members = team_config.get("members", [])
    existing_names = {m.get("name") for m in members if isinstance(m, dict)}
    if member_name in existing_names:
        return (
            f"Team enrollment violation: agent name '{member_name}' is "
            f"already a member of team '{team_name}'. Spawning would "
            f"create a duplicate. Choose a different ship name from "
            f"references/crew-roles.md."
        )
    return None
```

- [ ] **Step 4: Run the tests — confirm they pass**

Run:
```bash
cd hooks && python3 -m pytest test_nelson_hooks.py::TestReadTeamConfig test_nelson_hooks.py::TestCheckTeamEnrollment -v
```

Expected: 7 passed.

- [ ] **Step 5: Wire team-enrollment check into `cmd_preflight`**

In `hooks/nelson_hooks.py`, in `cmd_preflight` (around lines 202-222), extend the check loop to include the new check. Replace the loop:

```python
    for check in (
        lambda: _check_station_tiers(tasks),
        lambda: _check_file_ownership(tasks),
        lambda: _check_mode_tool_consistency(_get_mode(battle_plan), tool_input),
    ):
```

with:

```python
    teams_dir = Path.home() / ".claude" / "teams"
    team_name = tool_input.get("team_name", "")
    team_config = _read_team_config(teams_dir, team_name) if team_name else {}

    for check in (
        lambda: _check_station_tiers(tasks),
        lambda: _check_file_ownership(tasks),
        lambda: _check_mode_tool_consistency(_get_mode(battle_plan), tool_input),
        lambda: _check_team_enrollment(team_config, tool_input),
    ):
```

- [ ] **Step 6: Add an integration test for the preflight wiring**

In `hooks/test_nelson_hooks.py`, in the existing `TestCmdPreflight` class (or equivalent — find the class that tests `cmd_preflight`), add a new test method:

```python
    def test_preflight_rejects_duplicate_team_member(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        mission_dir = _make_mission(
            tmp_path,
            mode="agent-team",
            tasks=[{
                "id": "task-1",
                "name": "Refactor auth",
                "owner": "HMS Argyll",
                "station_tier": 1,
                "file_ownership": ["src/auth.py"],
            }],
        )
        teams_dir = tmp_path / "teams"
        team_dir = teams_dir / "acme"
        team_dir.mkdir(parents=True)
        (team_dir / "config.json").write_text(
            json.dumps({"members": [{"name": "HMS Argyll"}]}),
        )
        monkeypatch.setattr(
            "pathlib.Path.home", lambda: tmp_path,
        )
        # The hook builds teams_dir as ~/.claude/teams/acme
        (tmp_path / ".claude").mkdir(exist_ok=True)
        (tmp_path / ".claude" / "teams").mkdir(exist_ok=True)
        (tmp_path / ".claude" / "teams" / "acme").mkdir(exist_ok=True)
        (tmp_path / ".claude" / "teams" / "acme" / "config.json").write_text(
            json.dumps({"members": [{"name": "HMS Argyll"}]}),
        )

        payload = {
            "tool_input": {
                "team_name": "acme",
                "name": "HMS Argyll",
                "prompt": "...",
            },
        }
        code = _run(cmd_preflight, payload, cwd=str(tmp_path))
        assert code == 2
```

- [ ] **Step 7: Run the full hook test suite**

Run:
```bash
cd hooks && python3 -m pytest test_nelson_hooks.py -v
```

Expected: all tests pass (existing + new).

- [ ] **Step 8: Commit**

```bash
git add hooks/nelson_hooks.py hooks/test_nelson_hooks.py
git commit -m "feat(nelson): team-aware enrollment validation in preflight hook"
```

- [ ] **Step 9: Close Phase 3 issues**

```bash
bd close nelson-74q nelson-3nb
```

Expected: two `✓ Closed …` lines.

---

## Phase 4 — Resolve open design question

### Task 10: Resolve nelson-43e (task list visibility in subagents mode)

This is an analysis task — there is no code change, only a closure rationale.

**Files:**
- None (bd close with reason)

- [ ] **Step 1: Confirm current behaviour**

Read `skills/nelson/references/tool-mapping.md` lines 26-52. The footnote `¹` confirms that the **admiral already uses** `TaskCreate`/`TaskUpdate`/`TaskList` for visibility tracking in subagents mode (and single-session mode). What is forbidden is **captain** use of the task list — and that's structurally impossible: captains in subagents mode are isolated subagents with no shared task surface.

- [ ] **Step 2: Verify by grepping the relevant doc**

Run:
```bash
grep -n "Admiral exception" skills/nelson/references/tool-mapping.md
```

Expected: returns the line that establishes the admiral exception is already documented.

- [ ] **Step 3: Close the bd issue with the rationale**

Run:
```bash
bd close nelson-43e --reason="Admiral already uses TaskCreate/TaskUpdate/TaskList for visibility tracking in subagents mode (tool-mapping.md footnote ¹). Captains physically cannot share a task list across subagent boundaries — there is no decoupling work to do. Issue resolved as already-implemented."
```

Expected: `✓ Closed nelson-43e (reason: …)`.

---

## Final wrap-up

### Task 11: Update CLAUDE.md project structure if needed

**Files:**
- Modify: `CLAUDE.md` (project structure tree)

- [ ] **Step 1: Check whether CLAUDE.md's tree should reflect the new files**

Run:
```bash
grep -n "damage-control" CLAUDE.md
grep -n "standing-orders" CLAUDE.md
```

Expected: the tree includes both directories.

- [ ] **Step 2: Add the four new file entries to the tree**

In `CLAUDE.md`, in the project structure block, locate the `damage-control/` subtree and append the new entries:

```
      agent-team-spawn-broken.md  — Recovery for #40270 broken Agent(team_name=...)
      worktree-team-conflict.md   — Recovery for #37549 worktree+team_name silent failure
```

Locate the `standing-orders/` subtree (if listed) and append:

```
      spawning-authority.md       — Only the admiral spawns agents and marines
```

Locate the `references/` subtree and append:

```
    background-patterns.md  — Background-agent and Monitor coordination patterns
```

If any subtree is not currently enumerated in CLAUDE.md (e.g., standing-orders is summarised rather than itemised), skip that bullet — match the existing granularity.

- [ ] **Step 3: Verify**

Run:
```bash
grep -n "agent-team-spawn-broken\|worktree-team-conflict\|spawning-authority\|background-patterns" CLAUDE.md
```

Expected: at least two matches (the always-listed damage-control entries; standing-orders/references depending on existing detail level).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(nelson): list new agent-teams files in project structure"
```

### Task 12: Pre-PR checks

- [ ] **Step 1: Run the full test suite**

Run:
```bash
cd hooks && python3 -m pytest test_nelson_hooks.py -v
cd ../scripts && python3 -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Run cross-reference checker**

Run:
```bash
bash scripts/check-references.sh
```

Expected: exit 0.

- [ ] **Step 3: Run bd preflight**

Run:
```bash
bd preflight
```

Expected: no warnings about stale issues, orphans, or lint failures introduced by this work.

- [ ] **Step 4: Verify all bd issues are closed**

Run:
```bash
bd list --status=open | grep -E "nelson-(wgt|84f|la9|onj|n1p|x7c|74q|3nb|43e)" || echo "all closed"
```

Expected: `all closed`.

- [ ] **Step 5: Open the PR**

Run:
```bash
git push -u origin feat/agent-teams-capability-fixes
gh pr create --title "Wire Nelson to fully exploit Claude Code Agent Teams" --body "$(cat <<'EOF'
## Summary

- Document and route around two confirmed-broken Agent Teams paths (Agent(team_name=...) per #40270; team_name + worktree per #37549) with new damage-control entries and an updated mode-selection warning.
- Document the `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` prerequisite for `agent-team` mode and add a quick check.
- Wire `mode` (Action Stations tier mapping) and `model` into the spawn template so every captain is launched with deliberate parameters.
- Add a standing order clarifying that only the admiral spawns agents and Royal Marines.
- Add a new background-agent + `Monitor` reference and integrate completion notifications into the quarterdeck rhythm.
- Extend `nelson_hooks.py` preflight with team-config-aware enrollment validation (rejects duplicate names within a team).

Closes nelson-wgt, nelson-84f, nelson-la9, nelson-onj, nelson-n1p, nelson-x7c, nelson-74q, nelson-3nb, nelson-43e.

## Test plan

- [ ] `pytest hooks/test_nelson_hooks.py -v` — all green (existing + new team-config tests).
- [ ] `pytest scripts/ -v` — all green.
- [ ] `bash scripts/check-references.sh` — no broken references.
- [ ] Manual smoke: run `nelson` with a small mission, verify SKILL.md Step 3 prompts for the env var prerequisite when `agent-team` is selected.
- [ ] Manual smoke: confirm formation summary now includes station tier, mode, and model columns per ship.
EOF
)"
```

Expected: PR URL printed.

---

## Self-review notes

**Spec coverage:**
- nelson-wgt → Task 1, 4 ✓
- nelson-84f → Task 2, 4 ✓
- nelson-la9 → Task 3 ✓
- nelson-onj → Task 5 ✓
- nelson-n1p → Task 6 ✓
- nelson-x7c → Task 7 ✓
- nelson-74q → Task 8 ✓
- nelson-3nb → Task 9 ✓
- nelson-43e → Task 10 ✓

**Type and identifier consistency:**
- The spawn template `[mode]` column added in Task 5 Step 3 is reused (extended with `[model]`) in Task 6 Step 3 — tasks must execute in order or the second edit will fail to find the line shape established by the first.
- `_read_team_config` and `_check_team_enrollment` function signatures are consistent between Task 9 Step 1 (test imports) and Step 3 (definitions).

**Open assumptions worth flagging at execution time:**
- The hook test in Task 9 Step 6 monkeypatches `Path.home`. If `nelson_hooks.py` ends up resolving the teams dir through a different mechanism (e.g., reading an env var like `CLAUDE_HOME`), adjust the monkeypatch to match.
- Task 11 (`CLAUDE.md` update) assumes the project structure tree itemises the damage-control directory at file granularity. If the tree summarises that directory at a higher level, fewer edits are needed — match the existing detail level rather than introducing inconsistency.
