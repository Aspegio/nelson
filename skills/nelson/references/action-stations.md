# Action Stations

Classify each task before execution. Apply the minimum required controls.

## Contents

- [Station 0: Patrol](#station-0-patrol)
- [Station 1: Caution](#station-1-caution)
- [Station 2: Action](#station-2-action)
- [Station 3: Trafalgar](#station-3-trafalgar)
- [Risk Classification Decision Tree](#risk-classification-decision-tree)
- [Failure-Mode Checklist](#failure-mode-checklist)
- [Marine Deployments](#marine-deployments)

## Station 0: Patrol

Criteria:
- Low blast radius.
- Easy rollback.
- No sensitive data, security, or compliance impact.

Required controls:
- Basic validation evidence.
- Record rollback step.

## Station 1: Caution

Criteria:
- User-visible behavior changes.
- Moderate reliability or cost impact.
- Partial coupling to other tasks.

Required controls:
- Independent review by non-author agent.
- Validation evidence plus negative test or failure case.
- Explicit rollback note in task output.

## Station 2: Action

Criteria:
- Security, privacy, compliance, or data integrity implications.
- High customer or financial blast radius.
- Difficult rollback or uncertain side effects.

Required controls:
- Dedicated red-cell navigator participation.
- Adversarial review with failure-mode checklist.
- Pre-merge or pre-release go/no-go checkpoint by admiral.
- Staged rollout or guarded launch when possible.

## Station 3: Trafalgar

Criteria:
- Irreversible actions.
- Regulated or safety-sensitive effects.
- Mission failure likely causes severe incident.

Required controls:
- Keep scope minimal and isolate risky changes.
- Require explicit human confirmation before irreversible action.
- Two-step verification and documented contingency plan.
- If controls are unavailable, do not execute.

## Risk Classification Decision Tree

Walk through these questions in order. Stop at the first "yes" — that determines the Station tier.

**1. Is the action irreversible or regulated?**
   - Could it destroy data with no backup? → **Station 3**
   - Does it touch regulated, safety-critical, or compliance-governed systems? → **Station 3**
   - Could failure cause a severe incident that cannot be undone? → **Station 3**
   - If none apply, proceed to question 2.

   _Examples: Dropping a production database table (Station 3), deleting a cloud storage bucket without snapshots (Station 3), modifying HIPAA-regulated data pipelines (Station 3)._

**2. Does it affect security, privacy, or data integrity?**
   - Does it modify authentication, authorization, or encryption? → **Station 2**
   - Could it expose user data or PII? → **Station 2**
   - Does it have high financial or customer blast radius? → **Station 2**
   - If none apply, proceed to question 3.

   _Examples: Changing auth middleware or token validation (Station 2), updating payment processing logic (Station 2), modifying API rate-limiting or access controls (Station 2)._

**3. Is the change visible to users or coupled to other work?**
   - Does it alter user-facing behavior, UI, or API responses? → **Station 1**
   - Could it affect reliability, performance, or cost in a noticeable way? → **Station 1**
   - Is it tightly coupled to other in-flight tasks? → **Station 1**
   - If none apply, proceed to question 4.

   _Examples: Changing an API response format (Station 1), updating a shared configuration file (Station 1), refactoring a function used by multiple modules (Station 1)._

**4. None of the above?** → **Station 0**
   - Low blast radius, easy rollback, no sensitive impact.

   _Examples: Renaming an internal variable (Station 0), fixing a typo in a code comment (Station 0), adding a unit test for existing logic (Station 0)._

## Failure-Mode Checklist

Run this checklist for Station 1+ tasks.

- What could fail in production?
- How would we detect it quickly?
- What is the fastest safe rollback?
- What dependency could invalidate this plan?
- What assumption is least certain?

## Marine Deployments

Marine deployments inherit the parent ship's station tier:

- **Station 0-1:** Captain deploys at discretion. No admiral approval required.
- **Station 2:** Captain must signal admiral and receive approval before deploying marines.
- **Station 3:** Marine deployment is not permitted. All Trafalgar-tier work requires explicit Admiralty (human) confirmation.

## Plan Mode for High-Risk Stations

When spawning captains for Station 2 or Station 3 tasks, use `mode: "plan"` on the `Agent` tool. This forces the captain into read-only plan mode — they can explore the codebase and design their approach, but cannot write files until the admiral approves their plan.

- **Station 2 (Action):** Captain submits a plan via `ExitPlanMode`. Admiral reviews and approves via `SendMessage(type="plan_approval_response")`. This maps to the existing "admiral go/no-go" requirement.
- **Station 3 (Trafalgar):** Same flow, but the admiral must also obtain explicit human confirmation before approving the plan. This maps to the existing "human confirmation required" requirement.
- **Station 0-1:** Plan mode is not required. Captains execute directly.

See `references/tool-mapping.md` for the full set of coordination tools.

## Advanced: TaskCompleted Hook

An optional `TaskCompleted` hook can enforce quality gate validation before allowing a task to be marked complete. A hook that exits with code 2 rejects the completion and feeds back the reason to the agent.

Example hook configuration in `.claude/settings.json`:

```json
{
  "hooks": {
    "TaskCompleted": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Verify: validation evidence present, rollback note included, station tier controls satisfied'"
          }
        ]
      }
    ]
  }
}
```

This is an opt-in enhancement. Quality gates work without hooks via the admiral's quarterdeck checkpoint and red-cell review process.
