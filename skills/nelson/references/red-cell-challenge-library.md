# Red-Cell Challenge Library

Seed red-cell reviews with domain-specific failure patterns instead of requiring the red-cell navigator to invent challenges from scratch. Loaded on demand.

## Purpose

The red-cell navigator currently generates challenges ad hoc. A library of known failure patterns by domain accelerates reviews and ensures coverage of common risks. Select the categories relevant to the task under review and use the patterns as a checklist.

## Auth and Security

| Pattern | What to look for |
|---|---|
| Token expiry edge cases | Refresh token behaviour during long-running operations; silent failures when tokens expire mid-request. |
| Privilege escalation | Role manipulation that grants unintended access; parameter tampering on role or permission fields. |
| Injection vectors | SQL, command, and template injection in user-supplied inputs; inadequate parameterisation or escaping. |
| Session fixation and replay | Session tokens that survive authentication state changes; replay of captured tokens after logout. |
| CORS misconfiguration | Overly permissive origins; credentials flag combined with wildcard origins; missing preflight validation. |

## Data Integrity

| Pattern | What to look for |
|---|---|
| Race conditions in concurrent writes | Two writers modifying the same record without locking or optimistic concurrency control. |
| Partial writes leaving inconsistent state | Operations that update multiple records without transactional guarantees; incomplete rollback on failure. |
| Schema drift between services | Producer and consumer disagreeing on field types, required fields, or enum values after independent deployments. |
| Orphaned records from failed cascading deletes | Parent record removed but child records persist because the cascade failed or was never configured. |
| Timezone and encoding edge cases | Implicit timezone conversions; mixed UTC and local time comparisons; non-UTF-8 input causing silent corruption. |

## API Design

| Pattern | What to look for |
|---|---|
| Breaking changes to public contracts | Renamed or removed fields, changed response shapes, or altered status codes without versioning. |
| Pagination edge cases | Empty pages, last-page boundary, concurrent modification between page fetches, off-by-one on page indices. |
| Rate limit behaviour under burst traffic | Missing or misconfigured rate limits; unclear client feedback when limits are hit; retry storms. |
| Error response format inconsistencies | Mixed error shapes across endpoints; missing error codes or messages; stack traces leaking in production. |
| Versioning strategy gaps | No deprecation path for old versions; multiple active versions with divergent behaviour; header vs. path confusion. |

## Infrastructure

| Pattern | What to look for |
|---|---|
| DNS propagation delays | Deployments that assume instant DNS updates; TTL misconfiguration causing stale resolution. |
| Certificate expiry and rotation | Missing automated renewal; hard-coded certificate paths; services that fail silently on expired certificates. |
| Connection pool exhaustion | Pool limits too low for peak load; connections leaked by error paths; no monitoring on pool utilisation. |
| Cold start latency in serverless | User-facing latency spikes after idle periods; timeout configurations that do not account for cold starts. |
| Disk space exhaustion from logging | Unbounded log growth; missing log rotation; verbose debug logging left enabled in production. |

## Usage

The red-cell navigator selects relevant categories for the task under review and uses the patterns as a checklist. Not all patterns apply to every review — select based on the task domain. When reviewing a task that spans multiple categories, combine the relevant tables into a single pass.

## Growth

This library grows with mission lessons learned. When a mission discovers a new failure pattern not already covered, add it to the relevant category table. If the pattern does not fit an existing category, create a new H2 section following the same table format.

## Cross-References

- `admiralty-templates/red-cell-review.md` — Review template used alongside this library.
- `action-stations.md` — Station tier definitions that determine when red-cell participation is required.
