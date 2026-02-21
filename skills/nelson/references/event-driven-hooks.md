# Event-Driven Hooks for Automated Damage Control

Claude Code supports hooks — shell commands triggered on specific events during a session. Nelson leverages these hooks to automate routine monitoring and damage control tasks that would otherwise require manual admiral attention, reducing cognitive load at the quarterdeck.

## Hook Types Available

Claude Code exposes three hook events that Nelson can act upon:

| Hook | Fires When | Nelson Use Case |
|---|---|---|
| **PreToolUse** | Before a tool runs | Gate dangerous operations, enforce standing orders |
| **PostToolUse** | After a tool completes | Monitor token burn, detect idle crew, inject checkpoint reminders |
| **Stop** | When an agent session ends | Persist session state, auto-save captain's log |

Hooks execute shell commands. They can read environment variables, write files, and trigger alerts, but they cannot issue Claude prompts or make coordination decisions. The admiral retains all decision-making authority.

## Recommended Hooks

### Token Burn Monitor

**Event:** PostToolUse

After each tool use, check cumulative token usage against hull integrity thresholds. When a ship crosses a material condition boundary (XRAY to YOKE, YOKE to ZEBRA, or into ZEBRA Critical), the hook auto-files a damage report to `.claude/nelson/damage-reports/`.

This removes the burden of manual hull integrity tracking from captains and ensures the admiral's readiness board stays current between quarterdeck checkpoints.

**Behaviour:**

1. Read current token usage from the session environment.
2. Calculate hull integrity percentage.
3. Compare against the last recorded material condition.
4. If a boundary has been crossed, write a damage report using the template from `admiralty-templates/damage-report.md`.
5. If the new condition is ZEBRA or ZEBRA (Critical), write an additional alert file that the admiral's next checkpoint will surface.

### Idle Crew Detection

**Event:** PostToolUse

Alert when a crew member has produced no file changes in a configurable number of turns (default: 5). Prolonged inactivity may indicate confusion, a blocked state, or unclear orders — all conditions that benefit from early intervention rather than discovery at the next quarterdeck checkpoint.

**Behaviour:**

1. After each tool use, record the agent identifier and whether any file modifications occurred.
2. Maintain a rolling count of consecutive turns with no file changes per agent.
3. When the threshold is exceeded, write an alert to `.claude/nelson/alerts/` naming the idle agent and the turn count.
4. The admiral reviews alerts at the next checkpoint and decides whether to signal, reassign, or unblock.

### Forced Checkpoint Prompt

**Event:** PostToolUse

After every N tool uses (recommended default: 20), inject a reminder to run a quarterdeck checkpoint. This acts as a dead-reckoning fix — preventing the admiral from becoming absorbed in implementation and drifting past scheduled coordination points.

**Behaviour:**

1. Increment a per-session tool use counter after each PostToolUse event.
2. When the counter reaches the configured interval, write a checkpoint reminder file to `.claude/nelson/alerts/`.
3. Reset the counter.
4. The reminder does not force a checkpoint. It surfaces the prompt; the admiral decides whether to act on it or defer.

### Auto-Save Captain's Log

**Event:** Stop

When a session ends — whether by completion, context exhaustion, or manual termination — automatically persist the current session state to disk. This ensures that even an unexpected session end produces a recoverable record.

**Behaviour:**

1. On the Stop event, gather available session state: battle plan status, filed damage reports, unresolved blockers, and the last quarterdeck report.
2. Write a structured log entry to `.claude/nelson/captains-log/` with a timestamp and session identifier.
3. If a turnover brief has already been written, note its location in the log entry. If not, write a minimal state snapshot sufficient for session resumption.

## Configuration

Hooks are configured in the Claude Code settings file (`.claude/settings.json` or `.claude/settings.local.json`) under the `hooks` key. Each hook specifies the event, an optional tool name matcher, and the shell command to execute.

Example configuration:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "command": "bash .claude/nelson/hooks/token-burn-monitor.sh",
        "description": "Auto-file damage report on hull integrity threshold crossing"
      },
      {
        "command": "bash .claude/nelson/hooks/idle-crew-detection.sh",
        "description": "Alert on crew inactivity exceeding threshold"
      },
      {
        "command": "bash .claude/nelson/hooks/checkpoint-prompt.sh",
        "description": "Inject quarterdeck checkpoint reminder every 20 tool uses"
      }
    ],
    "Stop": [
      {
        "command": "bash .claude/nelson/hooks/auto-save-log.sh",
        "description": "Persist captain's log and session state on session end"
      }
    ]
  }
}
```

Hook scripts live in `.claude/nelson/hooks/`. Each script is a standalone shell script with no runtime dependencies beyond standard Unix utilities.

## Limitations

Hooks are automation, not intelligence. They observe and record but do not coordinate.

- Hooks run shell commands, not Claude prompts. They cannot reason about context or make judgement calls.
- Hooks cannot send messages to other agents. They write files that agents read at their next opportunity.
- Hook failures are silent by default. A failing hook does not halt the session, but it may leave gaps in monitoring.
- The admiral still makes all coordination decisions: relief on station, task reassignment, descoping, and escalation are human-in-the-loop or admiral-in-the-loop actions.
- Hook configuration is per-installation. Each user must configure hooks in their own settings file.

## Cross-References

- `damage-control/hull-integrity.md` — Material condition thresholds and the squadron readiness board.
- `damage-control/soundings.md` — Proactive budget monitoring between quarterdeck checkpoints.
- `admiralty-templates/damage-report.md` — Template used by the token burn monitor hook.
