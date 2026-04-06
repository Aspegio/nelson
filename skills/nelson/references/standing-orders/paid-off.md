# Standing Order: Paid Off

Stand down agents the moment they have no remaining work in the task graph.

**Symptoms:**
- An agent completed its task but remains idle while other tasks continue.
- Admiral is holding agents "just in case" without a concrete rework trigger
  defined in the sailing orders.
- Idle agents occupy panel slots and coordination attention without contributing
  to mission throughput.

**Remedy:** After confirming a task complete, check whether the completing agent
is a prerequisite for any remaining pending task. If not — and if no rework loop
in the sailing orders names a specific trigger that would re-task it — proceed
to shutdown. The shutdown gate depends on execution mode:

- **`agent-team` mode:** Before sending `shutdown_request`, confirm the admiral
  has received and processed the captain's results. "Processed" means the
  admiral has read the captain's deliverables — whether delivered via
  `SendMessage`, written to disk, or recorded in the `TaskList` description.
  If the results have not been received, retrieve them first (via `SendMessage`
  or by reading the output files), then send `shutdown_request`.
- **`subagents` mode:** The `Agent` tool returns results synchronously when the
  sub-agent completes. No additional confirmation step is needed. Send
  `shutdown_request` immediately.

Only hold an agent when a concrete re-task condition is written into the sailing
orders (e.g., "if milestone < 90%, re-task WP1 captain for rework"). Once that
trigger is evaluated and not fired, stand down without hesitation.

"We might need them later" is not a trigger. It is noise.

**Exception:** A captain whose task description is prefixed `[AWAITING-ADMIRALTY]:` must not stand down. The admiral holds them at `in_progress` until Admiralty provides the required input. Only after the admiral relays the input, clears the prefix, and the captain completes the remaining work may the captain stand down normally.
