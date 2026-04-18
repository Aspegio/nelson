# Standing Order: Spawning Authority

Only the admiral spawns agents and Royal Marines.

Captains and crew operate inside an isolated teammate context that does NOT include the `Agent` or `TeamCreate` tools. A captain that "deploys" a marine or "spawns" a sub-agent without admiral involvement cannot succeed — those tool calls are not present in the captain's tool surface.

This is not a stylistic rule; it is a structural constraint of Claude Code's teammate spawning model. The instruction set in `references/royal-marines.md` and `references/crew-roles.md` may read as if captains deploy crew or marines directly. They do not. The admiral spawns on a captain's behalf when the captain requests support.

**Symptoms:**

- A captain attempts an `Agent` call and receives "tool not available" or no result.
- A captain's brief instructs them to "spawn a marine" or "deploy a Recce" without specifying how to request the deployment.
- Marine deployments appear in the battle plan with a captain as the spawner rather than the admiral.

**Correct flow:**

1. Captain identifies need for marine support (per `references/royal-marines.md` deployment rules).
2. Captain sends `SendMessage(type="message")` to the admiral with a marine deployment brief (using `references/admiralty-templates/marine-deployment-brief.md`).
3. Admiral evaluates the request against station-tier rules (Station 2 requires admiral approval before deployment per `references/action-stations.md`).
4. Admiral spawns the marine via `Agent(subagent_type="general-purpose", ...)` (or other suitable subagent type), passing the captain's brief as the marine's prompt.
5. Marine reports back to the admiral. The admiral relays results to the captain via `SendMessage`.

**When the captain is in subagents mode:**

- There is no `SendMessage` channel back to the admiral. The captain instead returns control via the `Agent` return value with a "marine support requested" note. The admiral inspects the return value, decides, and spawns a follow-up subagent for the marine work.

**Remedy when violated:**

- If a captain's brief implies they will spawn a marine, rewrite the brief to instruct them to **request** the deployment via `SendMessage` (or via the Agent return value in subagents mode).
- If marine deployments appear in the battle plan with a captain as spawner, reassign the spawner to "Admiral" before formation closes.

**Related:**

- `references/royal-marines.md` — marine deployment rules.
- `references/admiralty-templates/marine-deployment-brief.md` — request format.
- `references/action-stations.md` — Marine Deployments section, station-tier gates.
- `references/crew-roles.md` — crew composition (also admiral-spawned).
