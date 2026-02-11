# Action Stations

Classify each task before execution. Apply the minimum required controls.

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
