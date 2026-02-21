---
# nelson-3lax
title: Soundings — Proactive Budget Cliff Detection
status: completed
type: feature
priority: high
created_at: 2026-02-21T01:18:39Z
updated_at: 2026-02-21T01:42:08Z
parent: nelson-yfhj
---

Add proactive token budget monitoring every 5-10 turns. Check remaining context window percentage, calculate burn rate (tokens used in last N turns / N), estimate turns to Critical ((remaining context × 0.35) / burn rate), escalate to admiral if turns to Critical < 3. Prevents silent context exhaustion. Source: HMS Tirpitz (Resilience). Effort: Low. Impact: High.

## Summary of Changes\n\nDelivered as part of the full-fleet mission. All files created/modified and integrated into SKILL.md.
