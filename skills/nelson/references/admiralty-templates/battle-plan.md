# Battle Plan Template

```text
Task ID:
- Name:
- Owner: [assigned at Step 3 — Formation]
- Ship (if crewed): [assigned at Step 3 — Formation]
- Crew manifest (if crewed):
- Deliverable:
- Dependencies:
- Station tier (0-3):
- File ownership (if code):
- Validation required:
- Rollback note required: yes/no
- admiralty-action-required: yes/no
  - action: [one sentence — what the human must do]
  - timing: before this task starts | after this task completes
  - blocks: [task name or "stand-down"]
```

**`admiralty-action-required`:** Mark `yes` for any task where a step cannot be completed by an agent — requires the human to interact with an external system, provide credentials or URLs, or take an action only the human can perform. Fill this field consciously for every task; leaving it blank is a claim that the task requires no human action. When marked `yes`, the admiral will surface this in the Admiralty Action List before agents launch, and the captain will invoke the `awaiting-admiralty` standing order when the step is reached.

**Note on `blocks:` field:** The `blocks:` value names the task that cannot proceed until the human acts. The Admiralty Action List displays this as `unblocks:` — same task name, inverted label.
