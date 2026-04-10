# Task List Visibility for All Nelson Modes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Nelson mission progress visible in Claude Code's task list (Ctrl+T) in all execution modes, not just agent-team.

**Architecture:** The admiral creates `TaskCreate` entries for each battle plan task at the end of Step 2 (before owners are known), updates them with owners/status in Step 3, tracks completion during Step 5, and ensures cleanup at Step 7. The Mode-Tool Consistency Gate is refined to distinguish between "TaskCreate for coordination" (agent-team only) and "TaskCreate for visibility" (all modes). The tool-mapping reference is updated to reflect this dual-purpose distinction.

**Tech Stack:** Claude Code TaskCreate/TaskUpdate tools, Nelson SKILL.md, tool-mapping.md

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `skills/nelson/SKILL.md` | Modify | Add task visibility instructions at Steps 2, 3, 5, 7; refine Mode-Tool Consistency Gate |
| `skills/nelson/references/tool-mapping.md` | Modify | Add visibility tracking operation; update anti-pattern table |

---

### Task 1: Add task visibility instructions to Step 2 of SKILL.md

**Files:**
- Modify: `skills/nelson/SKILL.md:71` (after "Structured Data Capture" note in Step 2)

- [ ] **Step 1: Read the current Step 2 ending**

Confirm the current text at line 71:
```
**Structured Data Capture:** Task registration requires owners, which are assigned in Step 3. No script calls at this step.
```

- [ ] **Step 2: Add Task List Visibility block after the existing Structured Data Capture note**

Insert the following new block immediately after the existing "Structured Data Capture" note at line 71:

```markdown
**Task List Visibility:** After finalizing the battle plan, create a `TaskCreate` entry for each task to make mission progress visible in the Claude Code task list (Ctrl+T). This applies in **all execution modes** — it is admiral-level visibility tracking, not inter-agent coordination.

For each task:
- `subject`: Task name from the battle plan (imperative form, e.g., "Refactor auth module")
- `description`: One-line deliverable
- `activeForm`: Present-continuous form shown in the UI spinner (e.g., "Refactoring auth module")

All tasks start as `pending`. They will be updated with owners and status as the mission progresses.
```

- [ ] **Step 3: Verify the insertion reads correctly in context**

Read lines 68–80 of SKILL.md to confirm the new block sits between the existing Structured Data Capture note and the Step 3 heading.

---

### Task 2: Refine the Mode-Tool Consistency Gate in Step 3

**Files:**
- Modify: `skills/nelson/SKILL.md:80-82` (Mode-Tool Consistency Gate)

- [ ] **Step 1: Read the current gate text**

Confirm the current text at lines 80-82:
```markdown
**Mode-Tool Consistency Gate:** Before assigning ships, confirm your tool usage matches the selected mode by reviewing `references/tool-mapping.md`:
- **`subagents` mode:** Do NOT use `TaskCreate`, `TaskList`, `TaskGet`, `TaskUpdate`, or `SendMessage(type="message")`. Captains report via the `Agent` tool return value only.
- **`agent-team` mode:** Do NOT use `Agent` with `subagent_type` to spawn captains (marines still use `subagent_type`). Use `TeamCreate` first, then `Agent` with `team_name` + `name`. Coordinate via `TaskList` and `SendMessage`.
```

- [ ] **Step 2: Replace the gate text with a refined version**

Replace lines 80-82 with:

```markdown
**Mode-Tool Consistency Gate:** Before assigning ships, confirm your tool usage matches the selected mode by reviewing `references/tool-mapping.md`:
- **`subagents` mode:** Captains do NOT use `TaskCreate`, `TaskList`, `TaskGet`, `TaskUpdate`, or `SendMessage(type="message")`. Captains report via the `Agent` tool return value only. The admiral uses `TaskUpdate` to track progress in the session task list (visibility only — captains cannot see these tasks).
- **`agent-team` mode:** Do NOT use `Agent` with `subagent_type` to spawn captains (marines still use `subagent_type`). Use `TeamCreate` first, then `Agent` with `team_name` + `name`. Coordinate via `TaskList` and `SendMessage`.
- **`single-session` mode:** The admiral uses `TaskUpdate` to track progress as it completes each task sequentially.
```

- [ ] **Step 3: Verify the gate reads correctly**

Read lines 78-86 of SKILL.md to confirm the refined gate is well-formed and the surrounding context is intact.

---

### Task 3: Add task status updates to Step 3 (Form the Squadron)

**Files:**
- Modify: `skills/nelson/SKILL.md:128` (after Crew Briefing paragraph)

- [ ] **Step 1: Read the current Crew Briefing text**

Confirm the text at line 128:
```markdown
**Crew Briefing:** Spawning and task assignment are two steps. First, spawn each captain with the `Agent` tool, including a crew briefing from `references/admiralty-templates/crew-briefing.md` in their prompt. Then create and assign work with `TaskCreate` + `TaskUpdate`. Teammates do NOT inherit the lead's conversation context — they start with a clean slate and need explicit mission context. See `references/tool-mapping.md` for full parameter details by mode.
```

- [ ] **Step 2: Add task update instructions after Crew Briefing**

Insert a new block immediately after the Crew Briefing paragraph (after line 128):

```markdown
**Task Status Updates:** After formation, update the task list entries created in Step 2:
- **`agent-team` mode:** Tasks were already created for visibility. Use `TaskUpdate` to set `owner` to each captain's name and `status` to `in_progress` as captains are spawned. The team's shared task list now serves both visibility and coordination.
- **`subagents` / `single-session` mode:** Use `TaskUpdate` to set `status` to `in_progress` as each task begins. The admiral tracks these directly.
```

- [ ] **Step 3: Verify the insertion reads correctly**

Read lines 126-135 of SKILL.md to confirm the new block sits between Crew Briefing and Edit Permissions.

---

### Task 4: Add task completion tracking to Step 5 (Quarterdeck Rhythm)

**Files:**
- Modify: `skills/nelson/SKILL.md:156` (within checkpoint cadence list)

- [ ] **Step 1: Read the current checkpoint cadence block**

Read lines 154-177 to understand the checkpoint structure.

- [ ] **Step 2: Add task completion update instruction**

Insert after the "Update progress by checking `TaskList`" bullet (line 156), a new sub-bullet:

```markdown
    - Mark completed tasks with `TaskUpdate` setting `status` to `completed`. In `subagents` and `single-session` modes, the admiral updates the session task list directly; in `agent-team` mode, captains or the admiral update the shared task list.
```

- [ ] **Step 3: Verify the insertion**

Read lines 154-180 to confirm the new bullet integrates cleanly into the checkpoint cadence list.

---

### Task 5: Add task cleanup to Step 7 (Stand Down)

**Files:**
- Modify: `skills/nelson/SKILL.md:221` (after Structured Data Capture in Step 7)

- [ ] **Step 1: Read the current Stand Down ending**

Read lines 219-226 to understand the current structure.

- [ ] **Step 2: Add task list cleanup instruction**

Insert after the "Structured Data Capture" paragraph and before "Session State Cleanup":

```markdown
**Task List Cleanup:** Verify all task list entries reflect final state. Mark any remaining `in_progress` tasks as `completed` if their work is done, or note incomplete tasks in the captain's log. This ensures the Ctrl+T display shows an accurate final summary.
```

- [ ] **Step 3: Verify the insertion**

Read lines 219-228 to confirm the block sits between Structured Data Capture and Session State Cleanup.

---

### Task 6: Update tool-mapping.md with visibility tracking

**Files:**
- Modify: `skills/nelson/references/tool-mapping.md:7-21` (Tool Reference table)
- Modify: `skills/nelson/references/tool-mapping.md:43-54` (Anti-Patterns table)

- [ ] **Step 1: Read the current Tool Reference table**

Confirm the table at lines 7-21.

- [ ] **Step 2: Add visibility tracking row to the Tool Reference table**

Insert after the "Check task progress" row (line 14):

```markdown
| Track task visibility (admiral) | `TaskCreate` / `TaskUpdate` | all modes |
```

- [ ] **Step 3: Update the Anti-Patterns table**

Replace the `TaskCreate` anti-pattern row (line 53):

Current:
```markdown
| `TaskCreate` in subagents mode | Tasks are created but no agent can see them | Track work in the admiral's conversation context |
```

Replace with:
```markdown
| `TaskCreate` by captains in subagents mode | No shared task list exists for captains | Admiral tracks visibility via `TaskCreate`/`TaskUpdate` in its own session; captains report via `Agent` return value |
```

- [ ] **Step 4: Add a clarifying note to Mode Differences**

After line 31 (end of subagents "Not available" list), insert:

```markdown
    - **Exception:** The admiral uses `TaskCreate`/`TaskUpdate` for session-level
      visibility tracking (the user's Ctrl+T task list). These tasks are not visible
      to captains — they are for the user's benefit only.
```

- [ ] **Step 5: Verify both tables**

Read lines 7-22 and lines 43-56 to confirm both tables are well-formed.

---

## Spec Coverage Check

| Requirement | Task |
|-------------|------|
| Tasks visible in all modes via Ctrl+T | Task 1 (create at Step 2) |
| Mode-Tool Consistency Gate updated | Task 2 |
| Tasks updated with owners after formation | Task 3 |
| Tasks marked complete during execution | Task 4 |
| Tasks cleaned up at stand-down | Task 5 |
| Tool-mapping reference updated | Task 6 |

## Notes

- **No code changes required** — this is entirely SKILL.md and reference doc changes.
- **Backwards compatible** — agent-team mode behaviour is unchanged; TaskCreate was already used there. The change adds visibility in modes that previously had none.
- **The distinction is**: "TaskCreate for coordination" (shared team task list, agent-team only) vs "TaskCreate for visibility" (admiral's session task list, all modes). Both use the same tool but serve different purposes.
- **TaskCreate replaced TodoWrite** in Claude Code v2.1.16+. Superpowers still uses TodoWrite, but Nelson should use the current standard.
