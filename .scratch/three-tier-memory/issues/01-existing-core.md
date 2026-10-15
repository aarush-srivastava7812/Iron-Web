# Existing Memory Core and the Missing Tiers

Labels: wayfinder:task
Type: task
Mode: AFK
Status: resolved
Assignee: Codex
Parent: ../map.md
Blocked by: none

## Question

Which parts of the requested architecture already exist, and which parts must be added before site integration?

## Answer

Resolved by repository inspection on 2026-10-14. Preserve the existing core as tier 3 and add tiers 1/2 around its authenticated service. The tiers are a logical memory hierarchy, not three replacements for current persistence.

| Existing component | Evidence | Role in the new design |
| --- | --- | --- |
| Embedded vector discovery | [configuration](../../../config.yaml), [Qdrant adapter](../../../memory/vector_store/qdrant_store.py) | Tier 3 discovery; retain the measured placement decision |
| Versioned claims, scopes, retained changes, field recall, dependencies | [lifecycle service](../../../memory/lifecycle/service.py), [claim contract](../../../memory/lifecycle/models.py) | Authority and provenance for all derived user memory |
| Authenticated private user spaces and ordered receipts | [shared service](../../../memory/shared/service.py), [journal](../../../memory/shared/journal.py) | Cache scope and readiness boundary |
| Pending/failed/unclear-change blocking | `SharedMemoryService._ready`, `EventJournal.pending` | Must execute even on a cache hit |
| Shared graph revision | [graph store](../../../memory/graph/falkordb_store.py), `revision_key` and publication | Coarse safe invalidation signal; it is internal, not an existing public cache endpoint |
| Durable handoffs, notifications and execution ownership | `record_work`, `claim_work`, `complete_work`, `handoff` in shared service | Keep work decisions out of cached persona summaries |
| Optional GPU embeddings/reranking | [configuration](../../../config.yaml), [device code](../../../memory/device.py) | Model computation support; this is not a task-card or generative prefix-cache implementation |

Missing: versioned agent-profile registry, the equal-partition hot cache, evidence-backed persona/task card compiler, card routing, cache coherence/generation checks, residency accounting, model context assembly and acceptance measurements.

The default travel interpreter recognizes a limited grammar for budgets, seats and destinations. It does not already understand arbitrary moods, multi-currency budgets or general personas. New meanings must come from validated structured claims or a separately evaluated interpreter; a card summary cannot silently invent them.

Tier 3 includes the SQLite receipt/history/notification journal as well as FalkorDB and Qdrant. The journal retains processing state; it is not a competing semantic authority.

Prior reports establish the baseline only. This session runs no new application benchmark and changes no runtime settings.
