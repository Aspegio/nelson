# Squadron Composition Reference

Use this file to choose execution mode and team size.

## Mode Selection

**User preference override:** If the user explicitly requests a specific execution mode (e.g., "use agent teams"), that request MUST be honoured. User preference takes priority over the decision matrix below. Do not second-guess or override the user's choice.

Evaluate all three conditions and select the best fit. When two modes could apply, prefer the one that gives captains more autonomy.

- `single-session`: Work is sequential, tightly coupled, or mostly in the same files.
- `subagents`: Work is parallel and each captain's task is fully independent — no shared coordination surface needed.
- `agent-team`: Work is parallel and captains benefit from a shared task list, peer messaging, or coordinated deliverables. Also use when 4+ captains are needed, or when the user requests it.

## Decision Matrix

| Condition | Preferred Mode | Why |
| --- | --- | --- |
| Single critical path, low ambiguity | `single-session` | Lowest coordination overhead |
| Parallel, fully independent tasks | `subagents` | Independent tasks with no cross-captain dependencies |
| Parallel implementation with dependencies | `agent-team` | Supports teammate-to-teammate coordination |
| 4+ parallel captains | `agent-team` | Shared task list simplifies coordination at scale |
| High threat or high blast radius | `agent-team` + red-cell navigator | Adds explicit control points |
| User explicitly requests a mode | As requested | User preference overrides the matrix |

## Team Sizing

The right number of captains equals the number of independently executable work units — not a complexity tier. Before choosing a number, map the dependency graph and count how many tasks can run concurrently with zero shared state. That count is the target.

**Zero shared state** means: no file ownership overlap AND no sequencing dependency (task B does not require the output of task A). Peer coordination across module boundaries (e.g., agreeing on an API contract) is permitted and handled by the admiral.

- Assign one captain per independent work unit.
- Only merge tasks onto one captain when they share files, have a sequencing dependency, or are so small that agent setup cost clearly exceeds the work itself.
- Add `1 red-cell navigator` at medium/high threat.
- Keep one admiral only.
- Squadron cap: 10 squadron-level agents (admiral, captains, red-cell navigator). Crew are additional — up to 4 per captain, governed by `references/crew-roles.md`.

An analysis mission with 8 independent sections warrants 8 captains. An implementation mission with 3 independent modules warrants 3. When in doubt, add a captain — idle context is cheap; serialized work is slow. In cost-optimized missions (sailing orders with token-budget priority), consult `references/model-selection.md` before defaulting to maximum parallelism.

## Role Guide

- `admiral`: Defines sailing orders, delegates, tracks dependencies, resolves blockers. Coordinates final synthesis but MUST NOT perform it directly — assign a captain or dedicate a synthesis task.
- `captain`: Commands a ship. Breaks task into sub-tasks, coordinates crew, verifies outputs. Implements directly only when the task is atomic (0 crew). Initial crew composition is set by the admiral at formation; captains may request mid-task adjustments with admiral approval.
  - Crew roles: Executive Officer (XO), Principal Warfare Officer (PWO), Navigating Officer (NO), Marine Engineering Officer (MEO), Weapon Engineering Officer (WEO), Logistics Officer (LOGO), Coxswain (COX). See `references/crew-roles.md` for role definitions and crewing rules.
- `red-cell navigator`: Challenges assumptions, validates outputs, checks rollback readiness.

## Anti-Patterns

See the Standing Orders table in SKILL.md for the full list of standing orders and known anti-patterns.

## Worktree Isolation

When file ownership boundaries are hard to draw or multiple captains must modify overlapping files, use `isolation: "worktree"` on the `Agent` tool. This gives each captain an isolated copy of the repository via a git worktree.

Worktree isolation is a stronger alternative to the file-ownership approach in `standing-orders/split-keel.md`. Use it when:

- Multiple captains need to edit the same files.
- Merge conflict risk is high and the split-keel standing order cannot resolve it.
- Tasks are large enough that the merge cost is justified.

**Trade-off:** Worktree isolation prevents conflicts during execution but requires merging changes afterward. The admiral is responsible for coordinating the merge.
