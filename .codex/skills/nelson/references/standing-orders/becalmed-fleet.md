# Standing Order: Becalmed Fleet

Do not create an agent team for work that is mostly linear and sequential.

**Symptoms:**
- Captains idle waiting on a single predecessor task.
- Token budget burns on coordination overhead with no parallel throughput gain.
- Tasks form a long chain with no independent branches.

**Remedy:** Use `single-session` mode. Only form a squadron when at least two tasks can run concurrently.
