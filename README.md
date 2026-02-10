# Nelson

<p align="center">
  <img src="1024px-Young_Nelson-min.jpg" alt="Captain Horatio Nelson" width="500">
  <br>
  <em>Captain Horatio Nelson — John Francis Rigaud, 1781. Image: Wikimedia Commons</em>
</p>

A Claude Code skill for coordinating agent work based on the Royal Navy. It provides structured sailing orders, battle plans, action stations, and a captain's log to manage complex tasks — from single-session work through to parallel subagent squadrons.

## What it does




https://github.com/user-attachments/assets/2468679d-39f5-4efb-9d93-43d43eee8907




Nelson gives Claude a six-step operational framework for tackling complex missions:

1. **Sailing Orders** — Define the outcome, success metric, constraints, and stop criteria
2. **Form the Squadron** — Choose an execution mode (single-session, subagents, or agent team) and size the team
3. **Battle Plan** — Split the mission into independent tasks with owners, dependencies, and file ownership
4. **Quarterdeck Rhythm** — Run checkpoints to track progress, identify blockers, and manage budget
5. **Action Stations** — Classify tasks by risk tier and enforce verification before marking complete
6. **Stand Down** — Produce a captain's log with decisions, artifacts, validation evidence, and follow-ups

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI installed and authenticated
- **Recommended:** Enable [agent teams](https://code.claude.com/docs/en/agent-teams) for the full squadron experience. Nelson works without it (using single-session or subagent modes), but agent teams unlock teammate-to-teammate coordination — the `agent-team` execution mode. Enable it in your [settings.json](https://code.claude.com/docs/en/settings):

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

- **For split-pane visibility:** To see each agent working in its own pane (as shown in the demo video), run Claude Code inside [tmux](https://github.com/tmux/tmux/wiki). Agent teams auto-detect tmux and give every teammate a dedicated split pane so you can watch the whole squadron in action.

## Installation

### Prompt-based (recommended)

Open Claude Code and say:

```
Install skills from https://github.com/harrymunro/nelson
```

Claude will clone the repo, copy the skill into your project's `.claude/skills/` directory, and clean up. To install it globally across all projects, ask Claude to install it to `~/.claude/skills/` instead.

### Manual

Clone the repo and copy the skill directory yourself:

```bash
# Project-level (recommended for teams)
git clone https://github.com/harrymunro/nelson.git /tmp/nelson
mkdir -p .claude/skills
cp -r /tmp/nelson/.claude/skills/nelson .claude/skills/nelson
rm -rf /tmp/nelson

# Or user-level (personal, all projects)
cp -r /tmp/nelson/.claude/skills/nelson ~/.claude/skills/nelson
```

Then commit `.claude/skills/nelson/` to version control so your team can use it.

### Codex (OpenAI)

This repo also includes a Codex-native skill at `.codex/skills/nelson/`, tuned for Codex's experimental subagent tools.

```bash
git clone https://github.com/harrymunro/nelson.git /tmp/nelson
mkdir -p ~/.codex/skills
cp -r /tmp/nelson/.codex/skills/nelson ~/.codex/skills/nelson
```

Restart Codex to pick up the new skill. Invoke it with:

```
$nelson
```

### Verify installation

Open Claude Code and ask:

```
What skills are available?
```

You should see `nelson` listed. You can also invoke it directly:

```
/nelson
```

## Usage

### Let Claude invoke it automatically

Claude reads the skill description and loads it when your request matches — for example, when you ask for coordinated parallel work or structured mission execution. Just describe your task:

```
I need to refactor the authentication system. The work spans the API layer,
the frontend, and the test suite. Use nelson to coordinate this.
```

### Invoke it directly

Use the slash command with your mission brief:

```
/nelson Migrate the payment processing module from Stripe v2 to v3
```

### Provide structured sailing orders

For maximum control, provide your own sailing orders:

```
/nelson

Sailing orders:
- Outcome: All API endpoints return consistent error responses
- Success metric: Zero test failures, all error responses match the schema
- Deadline: This session

Constraints:
- Token/time budget: Stay under 50k tokens
- Forbidden actions: Do not modify the database schema

Scope:
- In scope: src/api/ and tests/api/
- Out of scope: Frontend error handling
```

## How it works

<p align="center">
  <img src="HMP_RNM_1973_76-001.jpg" alt="HMS Victory anchored off the Isle of Wight" width="700">
  <br>
  <em>HMS Victory anchored off the Isle of Wight — John Wilson Carmichael (1799–1868), National Museum of the Royal Navy, Portsmouth</em>
</p>

### Execution modes

The skill selects one of three execution modes based on your mission:

| Mode | When to use | How it works |
|------|------------|--------------|
| `single-session` | Sequential tasks, low complexity, heavy same-file editing | Claude works through tasks in order within one session |
| `subagents` | Parallel tasks where workers only report back to the coordinator | Claude spawns [subagents](https://code.claude.com/docs/en/sub-agents) that work independently and return results |
| `agent-team` | Parallel tasks where workers need to coordinate with each other | Claude creates an [agent team](https://code.claude.com/docs/en/agent-teams) with direct teammate-to-teammate communication |

### Chain of command

Nelson uses a three-tier hierarchy. The admiral coordinates captains, each captain commands a named ship, and crew members aboard each ship do the specialist work.

```
                          ┌───────────┐
                          │  Admiral  │
                          └─────┬─────┘
                  ┌─────────────┼─────────────┐
                  ▼             ▼             ▼
           ┌───────────┐ ┌───────────┐ ┌───────────┐
           │  Captain   │ │  Captain   │ │ Red-Cell  │
           │ HMS Daring │ │ HMS Kent   │ │ Navigator │
           └─────┬─────┘ └─────┬─────┘ └───────────┘
            ┌────┼────┐   ┌────┼────┐
            ▼    ▼    ▼   ▼    ▼    ▼
           XO  PWO  MEO  PWO  NO  COX
```

**Squadron level:**

- **Admiral** — Coordinates the mission, delegates tasks, resolves blockers, produces the final synthesis. There is always exactly one.
- **Captains** — Each commands a named ship. Breaks their task into sub-tasks, crews specialist roles, coordinates crew, and verifies outputs. Implements directly only when the task is atomic. Typically 2-7 per mission.
- **Red-cell navigator** — Challenges assumptions, validates outputs, and checks rollback readiness. Added for medium/high risk work.

**Ship level (crew per captain, 0-4 members):**

| Role | Abbr | Function | When to crew |
|------|------|----------|-------------|
| Executive Officer | XO | Integration & orchestration | 3+ crew or interdependent sub-tasks |
| Principal Warfare Officer | PWO | Core implementation | Almost always (default doer) |
| Navigating Officer | NO | Codebase research & exploration | Unfamiliar code, large codebase |
| Marine Engineering Officer | MEO | Testing & validation | Station 1+ or non-trivial verification |
| Weapon Engineering Officer | WEO | Config, infrastructure & systems integration | Significant config/infra work |
| Logistics Officer | LOGO | Documentation & dependency management | Docs as deliverable, dep management |
| Coxswain | COX | Standards review & quality | Station 1+ with established conventions |

NO and COX are read-only — they report findings but never modify files.

Ships are named from real Royal Navy warships, matched roughly to task weight: frigates for general-purpose, destroyers for high-tempo, patrol vessels for small tasks, historic flagships for critical-path, and submarines for research.

Squadron size caps at 10 squadron-level agents (admiral, captains, red-cell navigator). Crew are additional — up to 4 per ship. If a task needs more crew, split it into two ships.

Here's an example of the crew in action: we create four captains. Two of the captains are single-crew (minimum, since captains don't do the work themselves) and two of them are two-crew. So we have 11 agents working together in total:


https://github.com/user-attachments/assets/f3bafd06-790e-44a0-9061-7d1fd666b445



### Action stations (risk tiers)

Every task is classified into a risk tier before execution. Higher tiers require more controls:

| Station | Name | When | Required controls |
|---------|------|------|-------------------|
| 0 | Patrol | Low blast radius, easy rollback | Basic validation, rollback step |
| 1 | Caution | User-visible changes, moderate impact | Independent review, negative test, rollback note |
| 2 | Action | Security/compliance/data integrity implications | Red-cell review, failure-mode checklist, go/no-go checkpoint |
| 3 | Trafalgar | Irreversible actions, regulated/safety-sensitive | Minimal scope, human confirmation, two-step verification, contingency plan |

Tasks at Station 1 and above also run a **failure-mode checklist**:

- What could fail in production?
- How would we detect it quickly?
- What is the fastest safe rollback?
- What dependency could invalidate this plan?
- What assumption is least certain?

### Templates

The skill includes structured templates for consistent output across missions:

- **Sailing Orders** — Mission definition with outcome, constraints, scope, and stop criteria
- **Battle Plan** — Task breakdown with owners, dependencies, threat tiers, and validation requirements
- **Ship Manifest** — Captain's crew plan with ship name, crew roles, sub-tasks, and budget
- **Quarterdeck Report** — Checkpoint status with progress, blockers, budget tracking, and risk updates
- **Red-Cell Review** — Adversarial review with challenge summary, checks, and recommendation
- **Captain's Log** — Final report with delivered artifacts, decisions, validation evidence, and follow-ups

## Skill file structure

Claude Code skill (original): `.claude/skills/nelson/`  
Codex skill: `.codex/skills/nelson/`

```
.claude/skills/nelson/
├── SKILL.md                                  # Main skill instructions (entrypoint)
├── agents/
│   └── openai.yaml                           # OpenAI agent interface definition
└── references/
    ├── action-stations.md                    # Risk tier definitions and controls
    ├── admiralty-templates.md                # Template routing index
    ├── admiralty-templates/                  # Individual template files
    │   ├── battle-plan.md
    │   ├── captains-log.md
    │   ├── quarterdeck-report.md
    │   ├── red-cell-review.md
    │   ├── sailing-orders.md
    │   └── ship-manifest.md
    ├── crew-roles.md                         # Crew role definitions, ship names, sizing
    ├── damage-control.md                     # Error recovery routing index
    ├── damage-control/                       # Individual procedure files
    │   ├── crew-overrun.md
    │   ├── escalation.md
    │   ├── man-overboard.md
    │   ├── partial-rollback.md
    │   ├── scuttle-and-reform.md
    │   └── session-resumption.md
    ├── squadron-composition.md              # Mode selection and team sizing rules
    ├── standing-orders.md                    # Anti-pattern routing index
    └── standing-orders/                      # Individual anti-pattern files
        ├── admiral-at-the-helm.md
        ├── all-hands-on-deck.md
        ├── becalmed-fleet.md
        ├── captain-at-the-capstan.md
        ├── crew-without-canvas.md
        ├── drifting-anchorage.md
        ├── press-ganged-navigator.md
        ├── pressed-crew.md
        ├── skeleton-crew.md
        ├── split-keel.md
        └── unclassified-engagement.md
```

- `SKILL.md` is the entrypoint that Claude reads when the skill is invoked. It defines the six-step workflow and references the supporting files.
- Files in `references/` contain detailed guidance that Claude loads on demand — they are not all loaded into context at once.

## Customisation

### Modify templates

Edit the individual template files in `references/admiralty-templates/` to match your team's reporting style. The templates use plain text format — adjust fields, add sections, or remove what you don't need.

### Adjust risk tiers

Edit `references/action-stations.md` to change what controls are required at each station level. For example, you might require red-cell review at Station 1 instead of Station 2 for a security-sensitive project.

### Change team sizing

Edit `references/squadron-composition.md` to adjust the decision matrix or default team sizes.

## Compatibility notes

- **Subagents** are a stable Claude Code feature and work out of the box.
- **Agent teams** are experimental and disabled by default. See [Prerequisites](#prerequisites) above for setup. Without agent teams enabled, Nelson falls back to `single-session` or `subagents` mode. Full details: [Agent teams documentation](https://code.claude.com/docs/en/agent-teams).
- **Codex** support is provided via `.codex/skills/nelson/`, which uses Codex's experimental subagent tools (`spawn_agent`, `send_input`, `wait`, `close_agent`).

## Disclaimer

This project is not associated with, endorsed by, or affiliated with the British Royal Navy or the UK Ministry of Defence. All Royal Navy terminology and references are used purely as a creative framework for organising software development tasks.

## License

MIT — see [LICENSE](LICENSE) for details.
