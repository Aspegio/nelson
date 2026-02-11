# Fleet Comms (Codex Subagents)

Codex subagents cannot message each other directly. Only the admiral can `send_input` to agents. Use this "Fleet Comms" protocol to emulate Claude-style agent-team chatter with low token overhead and minimal file conflicts.

## Policy

- If you are running `subagents` mode with 2+ agents, Fleet Comms is mandatory.
- If you cannot create `.nelson/comms/` in the target repo, fall back to `single-session` or reduce to 1 agent.
- Treat `.nelson/comms/interfaces.md` as the fleet's single source of truth for cross-ship contracts/decisions.

## Setup (mailboxes + broadcast)

Create a comms blackboard in the target repo:

```
.nelson/
  comms/
    fleet.md                # Broadcast log (admiral writes)
    interfaces.md           # Shared contracts/decisions (admiral writes)
    inbox/                  # Per-ship inbound orders (admiral writes)
      hms-kent.md
      hms-daring.md
    outbox/                 # Per-ship outbound status/signals (ship writes)
      hms-kent.md
      hms-daring.md
```

If the target repo uses git and these artifacts should not be committed, add `.nelson/` to `.gitignore`.

## Write Rules (avoid conflicts)

- Admiral writes:
  - `.nelson/comms/fleet.md`
  - `.nelson/comms/interfaces.md`
  - `.nelson/comms/inbox/*.md`
- Each ship writes only its own outbox file: `.nelson/comms/outbox/<ship>.md`
- Everyone may read everything.

## Signal Format

Use the template in `references/admiralty-templates/signal.md`.

Signal types:
- `request`: asks another ship for info/decision/work product
- `reply`: answers a prior signal
- `broadcast`: fleet-wide update (admiral -> fleet)

## Routing Procedure (admiral as signal officer)

1. Each checkpoint, the admiral reads all `.nelson/comms/outbox/*.md`.
2. For each `request` signal addressed to another ship:
  - Copy the signal into the destination ship's inbox: `.nelson/comms/inbox/<dest>.md`.
  - Notify the destination agent with a short message: "New signal in `.nelson/comms/inbox/<dest>.md`; please read and respond in your outbox."
3. For each `reply` signal:
  - Copy into the requesting ship's inbox and notify them similarly.
4. Publish fleet-wide decisions/changes to `.nelson/comms/fleet.md` and update `.nelson/comms/interfaces.md` when the change creates a new contract others depend on.

## Agent Instructions (standard)

When an agent is spawned, include these comms orders:
- "Write all status updates and outbound signals to `.nelson/comms/outbox/<ship>.md`."
- "Before starting new work and after any dependency changes, read `.nelson/comms/inbox/<ship>.md` and `.nelson/comms/interfaces.md`."
- "Acknowledge receipt of new inbox items by writing `ACK` in your outbox."

## Fallback (no file-based comms)

If agents cannot reliably read/write the comms files, fall back to routing signals inline:
- Agents include "Signals Out" blocks in their responses to the admiral.
- The admiral forwards the full signal content via `functions.send_input` to the target agent.