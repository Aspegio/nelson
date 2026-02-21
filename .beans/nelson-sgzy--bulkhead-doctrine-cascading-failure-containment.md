---
# nelson-sgzy
title: Bulkhead Doctrine — Cascading Failure Containment
status: completed
type: feature
priority: normal
created_at: 2026-02-21T01:19:30Z
updated_at: 2026-02-21T01:42:08Z
parent: nelson-4iqy
---

Allocate separate token budgets per ship in the battle plan. Each ship gets an explicit token allocation based on task complexity. Admiral holds a 15-20% reserve pool for relief operations and emergencies. If 3+ ships reach Red hull integrity simultaneously, pause all new work and escalate. Downstream tasks don't proceed if upstream dependency is in Red. Prevents cascading resource consumption. Source: HMS Tirpitz (Resilience). Effort: Medium-High. Impact: High.

## Summary of Changes\n\nDelivered as part of the full-fleet mission. All files created/modified and integrated into SKILL.md.
