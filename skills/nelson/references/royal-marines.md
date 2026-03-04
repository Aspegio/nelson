# Royal Marines

Royal Marines are short-lived sub-agents a captain deploys for focused, independent objectives in service of the ship's task. They are doctrinally distinct from crew: crew subdivide the ship's deliverable, marines execute discrete sorties and return.

## Deploy-or-Escalate Decision

Choose the first condition that matches.

1. Quick recon of unfamiliar area → **Recce Marine**
2. Targeted fix or small implementation to unblock ship → **Assault Marine**
3. Quick config/build/infra task → **Sapper**
4. Sustained work, own deliverable, needs file ownership → **NOT a marine.** Request a new ship from the admiral.
5. Work that subdivides the ship's main deliverable → **NOT a marine.** Crew the role instead.

## Marine Specialisations

| Type | Function | subagent_type | cost-weight | Use case |
|---|---|---|---|---|
| Recce Marine | Reconnaissance & intel gathering | Explore (read-only) | 4 | Scout unfamiliar code, gather findings |
| Assault Marine | Direct action, targeted changes | general-purpose | 3 | Small fix, unblock a dependency |
| Sapper | Engineering support | general-purpose | 3 | Quick config, build, infra task |

### Read-Only Specialisation

Recce Marines use the `Explore` subagent type. They cannot modify files. They report findings to the captain, who decides how to act on them.

## Deployment Rules

- **Max 2 marines per ship at any time.** If the task needs more, it is crew work or a new ship.
- **Marines cannot deploy marines.** No recursion permitted.
- **Marines report only to their deploying captain.** They do not communicate with crew or other ships.
- **Captain must verify marine output** before incorporating it into the ship's deliverable.
- **Marines do not get ship names.** Identify them as: `RM Detachment, HMS [Ship] — [objective]`.

## Action Station Interaction

Marine deployments inherit the parent ship's station tier:

- **Station 0-1:** Captain deploys at discretion. No admiral approval required.
- **Station 2:** Captain must signal admiral and receive approval before deploying marines.
- **Station 3:** Marine deployment is not permitted. All Trafalgar-tier work requires explicit Admiralty (human) confirmation.

## Recovery

Marine recovery is simple. No separate damage-control procedure is needed.

- If a marine is stuck or unresponsive, captain **abandons the deployment**.
- Captain either redeploys a fresh marine or handles the objective directly.
- If the same marine objective fails twice, captain **escalates to admiral**.

## Deployment Template

When deploying a marine, use the briefing template at `admiralty-templates/marine-deployment-brief.md`.
