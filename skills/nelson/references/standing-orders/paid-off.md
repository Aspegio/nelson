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
in the sailing orders names a specific trigger that would re-task it — send a
`shutdown_request` immediately.

Only hold an agent when a concrete re-task condition is written into the sailing
orders (e.g., "if milestone < 90%, re-task WP1 captain for rework"). Once that
trigger is evaluated and not fired, stand down without hesitation.

"We might need them later" is not a trigger. It is noise.

**Exception:** A captain whose task description is prefixed `[AWAITING-ADMIRALTY]:` must not stand down. The admiral holds them at `in_progress` until Admiralty provides the required input. Only after the admiral relays the input, clears the prefix, and the captain completes the remaining work may the captain stand down normally.
