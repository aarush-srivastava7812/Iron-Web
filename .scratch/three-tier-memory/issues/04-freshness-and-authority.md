# Prevent Stale Cards, Lost Changes and Cross-User Memory

Labels: wayfinder:task
Type: task
Mode: AFK
Status: resolved
Assignee: Codex
Parent: ../map.md
Blocked by: 03

## Question

How do cached profiles and cards preserve authenticated scope, current claims, pending/failed-event blocking, deletion and safe agent handoffs?

## Answer

FalkorDB remains the authority for eligible semantic claims and work dependencies. The receipt journal remains the authority for whether new input is pending, failed or unclear. Application configuration owns agent-profile/policy versions. Tiers 1/2 are disposable materialized views, not alternative authorities.

### Cache admission and freshness

1. Authenticate first. Use the credential-bound private space and actor, never a caller-supplied tenant name. Key entries by space, actor/profile version, explicit subject, canonical scope, task, temporal mode, query/known-at time where supplied, compiler/policy version and actual dependency IDs. GPU slot handles must carry owner and generation; never reuse a bare row number from a prior allocation.
2. Run the existing `_ready` gate before a cache lookup can return usable context. `queued`, `interpreting`, `failed` and `needs_review` continue to block current work. A graph revision alone cannot detect an unprocessed budget change.
3. Add a durable per-space journal state generation, incremented transactionally with receipt submission and every eligibility-relevant state transition, withdrawal and redaction. This is **new implementation work**; the current receipt sequence alone does not change on withdrawal/status updates.
4. Construct a snapshot stamp from graph revision, journal generation, agent-profile/policy versions and applicable time boundaries. Under the per-user request gate and graph operation lock, read readiness/revision and compile or validate current evidence consistently. Cache publication must not interleave with an unchecked graph change. Do not hold these locks during model inference.
5. First implementation uses **coarse invalidation**: any relevant space generation/revision change invalidates its private cache entries. Card dependency IDs preserve explanations and enable later measured selective invalidation; exact source-ID invalidation alone is insufficient because a new competing claim may also change eligibility.
6. Expiration/validity transitions must miss even when no database revision changes. Compute each view's earliest next validity transition plus explicit mood expiry; cap residence at **five minutes** as a secondary bound. Rebuild at expiration so fuzzy scores/state remain read-time calculations. TTL is not the correctness mechanism.

The snapshot/context API is proposed, not an existing `/v1` endpoint. Notifications can hasten eviction but are not the only freshness check; a missed notification must not permit a stale hit. Cold start discards all volatile entries and verifies any persisted derivative manifest against current source state.

### Inference and work

After generating a response, revalidate its snapshot/readiness before emission. If new input or evidence changed, discard/reassemble/retry; after at most **two rebuild attempts**, return a visible `context_changed` state so a busy stream cannot cause infinite retries. This assures the response is checked against state at final validation; it cannot prevent a later change arriving after the response.

Before registering/claiming/completing dependent work, retain the existing service checks and exact claim IDs. A cached brief cannot certify completion or ownership. Handoffs include used/current evidence and review reasons; credentials and active task lease tokens are never put in cards or shared profile text. Completed work is retained when evidence changes.

External provider actions still require their own conditional execution/idempotency/recovery contract. A fresh memory snapshot and task lease do not guarantee an external booking is performed exactly once.

### Deletion and partial failure

Receipt acceptance of deletion must block new contexts immediately through pending-state/generation checks. Committed deletion invalidates dependent card manifests, host text, embedding slots, token/prefix derivatives and in-flight contexts before eligibility resumes. Invalidate slot generations, clear owned device slices where supported, and prevent old handles from resolving after reallocation. Releasing a tensor is not a claim of forensic device erasure.

Persist no executable cache state that can replay deleted evidence. If compilation, device allocation or invalidation fails, serve an equivalent freshly verified CPU view or report an explicit error. Do not continue with the last good but now stale card. Source storage and card compilation are separate; this design does not invent a crash-atomic transaction across FalkorDB, Qdrant, SQLite and VRAM.
