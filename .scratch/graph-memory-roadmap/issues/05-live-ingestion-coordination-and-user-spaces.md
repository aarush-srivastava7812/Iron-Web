# Live Ingestion, Shared Tasks and Private User Spaces

Labels: wayfinder:grilling
Type: grilling
Status: resolved
Assignee: Codex
Parent: [Shared Agent Memory: Hackathon, Research and Reuse](../map.md)
Blocked by: 01, 04

## Question

What receipt-to-ready behavior, task-ownership rules, handoff contents, isolation boundary and recovery guarantees will the first shared-memory service promise?

Separate an event saved from an interpreted memory ready to use. Address duplicate delivery, pending changes, two agents claiming the same task, stale decisions, interrupted external work, restart recovery and actual separation between users. Set small measurable demonstration targets once capacity and the memory contract are known. Do not equate database write serialization with safe multi-agent decisions.

Extend the existing architecture after the vector-placement decision; do not introduce a competing memory core. Connect the first pause's accepted changes to affected tasks, and carry the second pause's evidence/source paths into handoffs. Neither fuzzy scores nor vector-backend choice decides task ownership or access.


## Answer

The authenticated receipt-first service is implemented with private graph/vector spaces, a durable SQLite receipt/notification queue, ordered per-user workers, persistent history, pending/failed/unclear safeguards, fenced task ownership, completed prerequisites and dependency-aware handoffs. Real two-agent/two-user HTTP/browser proofs, bounded mixed submission, killed-process boundaries and cold JSON-record snapshot/fresh-target restore pass. Guarantees are local and bounded; public deployment, external booking effects and customer-scale throughput are not claimed.

[Implementation/evaluation contract](../../../docs/shared_memory_service.md). [Actual shared-service evidence](../../../report/shared_memory_20261014_final/results.json).

### Decision source

The user's 2026-10-14 instruction, “all the steps in the wayfinder plan complete, if remaining then complete it”, delegates completion of remaining engineering work under the existing destination and accepted architecture/protection boundary. The documented first-contract defaults implement that authorization; they are engineering choices, not fabricated answers about customer identity, teammate commitments, scientific findings or production readiness.
