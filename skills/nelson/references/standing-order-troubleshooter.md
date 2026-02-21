# Standing Order Troubleshooter

Use when you observe a problem during a mission but are not sure which standing order addresses it. Work through the symptom categories below to identify the correct standing order, then load and apply it.

## Work Distribution Problems

Problems with how work is spread across the squadron.

- **Most agents are idle while one or two are overloaded** -- The squadron may be too large for the mission scope. See `standing-orders/becalmed-fleet.md`.
- **An agent was added but has no meaningful work** -- A ship was launched without canvas to fill. See `standing-orders/crew-without-canvas.md`.
- **Every role is crewed regardless of whether the task warrants it** -- Over-crewing wastes budget and adds coordination overhead. See `standing-orders/all-hands-on-deck.md`.
- **A single crew member was spawned for an atomic task** -- One crew member adds overhead without parallelism. See `standing-orders/skeleton-crew.md`.

## Scope and Authority Problems

Problems with mission drift, unclear authority, or leaders doing the wrong work.

- **Task scope is drifting from the original sailing orders** -- The anchorage is dragging. See `standing-orders/drifting-anchorage.md`.
- **The admiral is writing code or editing files instead of coordinating** -- The admiral has left the quarterdeck. See `standing-orders/admiral-at-the-helm.md`.
- **Unclear who has decision authority for a contested area** -- The chain of command has a break. See `standing-orders/chain-break.md`.
- **A captain is implementing tasks directly when crew should be doing the work** -- The captain is at the capstan. See `standing-orders/captain-at-the-capstan.md`.

## Coordination Problems

Problems with how agents communicate and synchronise.

- **Multiple agents are unknowingly doing the same work** -- Ghost crews are duplicating effort. See `standing-orders/ghost-crews.md`.
- **Multiple agents are interpreting the same order differently** -- Signals are crossing. See `standing-orders/crossing-signals.md`.
- **Tasks are blocking each other in a circular dependency** -- The tides are running in circles. See `standing-orders/circular-tides.md`.

## Quality and Context Problems

Problems with output quality degrading or context going stale.

- **Output quality is degrading silently over time** -- The tether is fraying. See `standing-orders/fraying-tether.md`.
- **An agent is working with stale context from an earlier phase** -- The watch has gone silent. See `standing-orders/silent-watch.md`.
- **Critical context is lost during handoffs between agents or sessions** -- The tidal pull is carrying information away. See `standing-orders/tidal-pull.md`.

## Task and Dependency Problems

Problems with task sizing, structure, or blocking dependencies.

- **Tasks are too large, too vague, or too interdependent** -- A storm surge of poorly scoped work. See `standing-orders/storm-surge.md`.
- **A low-priority blocker is holding up high-value work** -- Time to cut the line. See `standing-orders/cutting-the-line.md`.

## Role Violations

Problems with agents or crew working outside their assigned roles.

- **Crew are assigned work outside their defined role** -- Pressed into the wrong service. See `standing-orders/pressed-crew.md`.
- **The red-cell navigator has been assigned implementation work** -- The navigator has been press-ganged. See `standing-orders/press-ganged-navigator.md`.
- **Marines are being used for sustained crew work instead of short sorties** -- A battalion has gone ashore. See `standing-orders/battalion-ashore.md`.

## Risk Classification

Problems with missing or incorrect action station tiers.

- **Tasks are proceeding without a risk tier classification** -- An unclassified engagement. See `standing-orders/unclassified-engagement.md`.

## File Conflicts

Problems with file ownership collisions.

- **The same file is assigned to multiple agents** -- The keel is split. See `standing-orders/split-keel.md`.
