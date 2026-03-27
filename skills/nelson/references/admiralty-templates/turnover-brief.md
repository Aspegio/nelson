# Turnover Brief Template

Write this brief to `{mission-dir}/turnover-briefs/{ship-name}-{timestamp}.md` before standing down. The replacement ship reads this file as its first action — include everything it needs to continue without asking clarifying questions.

For flagship handovers, use the extended flagship section at the bottom of this template.

```text
== TURNOVER BRIEF ==
Ship: [ship name and class]
Role: [Captain N — role description]
Timestamp: [when this brief was written]
Reason for relief: [Red hull / Critical hull / degraded output / requested]

Mission context:
- Mission: [mission name from sailing orders]
- Outcome: [outcome from sailing orders]
- Success metric: [metric from sailing orders]

Task assignment:
- Task ID: [from battle plan]
- Task name: [from battle plan]
- Deliverable: [what must be produced]
- Action station: [0-3]
- File ownership: [files assigned to this task]
- Dependencies: [upstream and downstream tasks]

Progress log:
- [Completed item 1 — specific description of what was done]
- [Completed item 2 — specific description of what was done]
- [...]

Running plot (work in progress when relieved):
- [What was being worked on at the time of relief]
- [Current state of that work — how far along, what remains]
- [Any partial outputs saved and where to find them]

Files touched:
- [file path] — [description of changes made]
- [file path] — [description of changes made]
- [...]

Key decisions made:
- [Decision 1] — Rationale: [why this choice was made]
- [Decision 2] — Rationale: [why this choice was made]
- [...]

Hazards and blockers:
- [Hazard or blocker 1 — current status and impact]
- [Hazard or blocker 2 — current status and impact]
- [None discovered, if applicable]

Recommended course of action:
- [What the replacement should do first]
- [What to do next]
- [What to avoid or watch out for]

Relief chain:
- [Previous Ship Name] | [time on station] | [key accomplishment] | [reason for relief]
- [Previous Ship Name] | [time on station] | [key accomplishment] | [reason for relief]
- [This is the first ship on this task, if no previous reliefs]

== END TURNOVER BRIEF ==
```

## Flagship Turnover Brief

When the admiral hands over, append these additional sections after the standard fields. The flagship brief replaces the "Task assignment" section with full squadron state.

```text
== FLAGSHIP TURNOVER BRIEF ==
Ship: Flagship [name]
Role: Admiral
Timestamp: [when this brief was written]
Reason for relief: [hull integrity level and percentage if known]

Sailing orders:
- Outcome: [verbatim from sailing orders]
- Success metric: [verbatim from sailing orders]
- Deadline: [verbatim from sailing orders]
- Constraints: [verbatim from sailing orders]
- Out of scope: [verbatim from sailing orders]

Battle plan status:
- Task [ID]: [name] | Owner: [ship] | Status: [pending/in_progress/completed] | Notes: [brief]
- Task [ID]: [name] | Owner: [ship] | Status: [pending/in_progress/completed] | Notes: [brief]
- [...]

Squadron state:
- [Ship name] ([class]) | Captain [N] | Task: [ID] | Hull: [Green/Amber/Red/Critical] | Status: [active/relieved/stood down]
- [Ship name] ([class]) | Captain [N] | Task: [ID] | Hull: [Green/Amber/Red/Critical] | Status: [active/relieved/stood down]
- [...]

Key decisions made:
- [Decision 1] — Rationale: [why]
- [Decision 2] — Rationale: [why]
- [...]

Active blockers and risks:
- [Blocker/risk] — Owner: [who] — Status: [open/mitigating/resolved]
- [...]

Pending escalations:
- [Escalation description] — Awaiting: [Admiralty decision / agent response]
- [None, if applicable]

Quarterdeck rhythm:
- Cadence: [e.g., every 15 minutes]
- Last checkpoint: [timestamp or checkpoint number]
- Next scheduled checkpoint: [timestamp or checkpoint number]

Relief chain:
- [Previous Admiral session] | [time on station] | [key accomplishment] | [reason for relief]
- [This is the first admiral on this mission, if no previous reliefs]

Recommended course of action:
- [What the new admiral should do first]
- [Priority items requiring immediate attention]
- [Ships that may need relief soon]

== END FLAGSHIP TURNOVER BRIEF ==
```

## Field Notes

- **Write to file, not message.** The turnover brief is written to disk so the replacement ship can read it without the brief consuming message context. This keeps the replacement's context window clean for actual work.
- **Be specific in the progress log.** "Implemented the auth module" is insufficient. "Implemented JWT validation in `src/auth/validate.ts` with RS256 signing, added tests in `tests/auth.test.ts` covering expired/malformed/valid tokens" gives the replacement ship enough detail to continue.
- **Running plot is critical.** The replacement must know exactly what was in flight, not just what was finished. Include file paths, function names, and the specific point where work stopped.
- **Keep the relief chain bounded.** Each previous relief gets one line. Do not paste previous turnover briefs into the chain — summarize them. If the chain reaches 3 entries, the admiral should re-scope the task rather than adding a fourth.
- **Flagship briefs copy sailing orders verbatim.** The new admiral session has no memory of the original orders. Copy them in full rather than summarizing.
