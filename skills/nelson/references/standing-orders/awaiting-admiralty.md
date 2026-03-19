# Standing Order: Awaiting Admiralty

A captain that has reached a planned human-action step and completed all autonomous work must invoke this standing order.

**Status convention:** `TaskUpdate` accepts only `pending`, `in_progress`, and `completed` as status values. `awaiting-admiralty` is a naming convention, not a status enum. Prefix the task description with `[AWAITING-ADMIRALTY]:` and leave status as `in_progress`.

**Trigger:** Captain completes all autonomous work for a task and reaches a step marked `admiralty-action-required: yes`.

**Captain's procedure:**
1. Complete all work that does not require human input. Write all produced artifacts to disk.
2. Call `TaskUpdate` to prefix the task description with `[AWAITING-ADMIRALTY]:` and leave status as `in_progress` (do not set status to `completed`).
3. Report to admiral with three elements:
   - What was completed (artifact name and location).
   - Exact ask: what the human must do and what to return.
   - What is blocked until this resolves.
4. Do not attempt to continue, skip, or substitute. Wait for a `SendMessage` from the admiral relaying the admiralty's input. Take no further action until that message arrives. Do not poll. Normal hull-integrity procedures continue to apply while holding — if context pressure builds before the `SendMessage` arrives, signal the admiral so a turnover brief can be written before context exhaustion.

**Admiral's procedure on receiving this report:**
1. Surface to Admiralty immediately — do not defer to the next scheduled quarterdeck checkpoint.
2. Place any dependent tasks on hold.
3. When Admiralty provides the input, relay it to the captain via `SendMessage`, call `TaskUpdate` to remove the `[AWAITING-ADMIRALTY]:` prefix from the description, and confirm status remains `in_progress`.
4. Record the resolved value in the quarterdeck report.
