# Proposed direction: FalkorDB shared agent memory

Discussion checkpoint, updated 2026-10-13, Asia/Calcutta. This is a planning document, not evidence of completed implementation or hackathon compliance. The user has confirmed the existing architecture as the baseline. The next core work is a vector-placement comparison, followed by both paused KG additions; the current plan is indexed in [Shared Agent Memory: Hackathon, Research and Reuse](../.scratch/graph-memory-roadmap/map.md).

## The new objective

Design a reusable, real-time memory and coordination service using FalkorDB as the primary graph database. Travel planning is a later demonstration application, not the initial system boundary. The system must preserve conversations, distinguish episodes/facts/procedures, update knowledge without silently destroying history, share authorized state between agents, and keep users isolated.

Organizer source: https://www.wemakedevs.org/hackathons/falkordb . The page specifies October 15–18, 2026; FalkorDB must support a central product function. General libraries/templates/infrastructure may be reused, while the submission and main FalkorDB implementation must be new work completed during the event. Current research artifacts are planning/evaluation groundwork, not evidence that the event implementation already exists.

## Two paused discussions, preserved

1. **Evolving memory acceptance:** fuzzy degrees, time decay, accepted contradictions/supersessions, protected score one, and preservation of both claims. This becomes the proposed memory-lifecycle layer. A numeric score alone cannot resolve identity, context, authority, or time overlap.
2. **Retrieval evaluation and improvement:** KG-only question checks, field-aware retrieval, relevant companion records, varied wording, and missing-answer detection. This becomes the proposed discovery-and-evidence layer. The recent demo compared evidence retrieval on hand-prepared notes, not generated answers, automatic extraction, concurrency, or production scale.

Both discussions are now explicitly included as additions in the planned build, after testing and deciding vector placement. Their existing prototypes remain evidence and examples; this planning update does not merge them or run implementation work.

## What the graph owns

- Original conversation messages and tool-result episodes, with source, speaker/agent, user, session and receipt order.
- Interpreted claim records and independently changeable fields, scopes, evidence, source authority and known/unknown effective dates.
- Conditional procedures and policies, retaining their triggers and limits.
- Accepted identity aliases and explicitly unresolved candidates.
- Confirmation, contradiction and accepted supersession links, separate from current eligibility and prior acceptance history.
- Shared tasks, task versions, assigned agents, prerequisites, progress, handoff evidence and recorded decisions.
- Dependencies linking decisions/tasks to the exact memory versions used, so later changes can invalidate dependent work.

These may be linked views of the same evidence; episodic, semantic and procedural memory need not be three disconnected stores. Task coordination is a separate state category, not a fuzzy fact-confidence score. In particular, task ownership, allowed access and accepted replacements must not be decided by highest fuzzy score.

## Why the graph is essential

The graph is the authoritative record for current accepted memories and coordinated work. Search candidates must be reconciled with that graph before being used. Agents resolve prerequisites and record task claims/handoffs against the same authoritative state. Changed facts make dependent work stale until checked again.

An illustrative example: a user changes an approved limit from 1,000 to 600. Preserve the earlier preference and the new instruction; record the accepted change. Find plans that used the old limit and mark them for review. A second agent receives the current limit plus completed/pending/invalidated work and evidence for the handoff. A question about an earlier decision can trace the earlier source, while a current action uses the new accepted limit.

The honest claim is that graph relations are central to this implementation, not that no other database could ever represent equivalent state. Removing graph checks should measurably break supported memory-change and coordination behaviors, rather than merely suppress a visualization. Graph-only natural-language retrieval is not required for graph centrality.

## Proposed real-time flow

1. Agents and user sessions send message/tool/action events to one authorized memory service, at meaningful event boundaries rather than every generated token.
2. Durably record the original event first and issue a receipt. Interpretation may still be pending; receipt is not confirmation that semantic memory is ready.
3. A worker interprets the event into candidate fields, procedures, task updates and identity/change candidates. Agent guesses remain attributed assertions, not user instructions or verified observations.
4. Compare only relevant prior fields using subject/property/scope/cardinality/time and accepted identities. Validate changes and authority before promoting them.
5. Commit each accepted state change, its evidence/version and dependency invalidation consistently. Reject stale task claims or conflicting updates and retry against the latest state; do not assume database write serialization prevents an agent acting on an earlier read.
6. Notify affected agents after the committed change. Persist pending notifications so a crash or repeat delivery does not silently lose a handoff. Repeated event receipts should not duplicate memories or completed work.
7. Reading agents use the required state version, notice pending interpretation and stale dependencies, and either continue with suitable evidence or wait/ask for resolution.

Near-real-time is a measured service goal, not an instantaneous-processing claim. Record event-receipt and semantic-ready delays separately. New authoritative instructions that may affect an action should prevent acting on unchecked old state while interpretation is pending.

## FalkorDB-specific direction

Keep the existing architecture: FalkorDB graph memory with Qdrant vectors is the baseline. First compare it with the same graph behavior using FalkorDB's native indexed vector search. Use matching memories, embeddings, questions and evidence budgets, and measure both vector-query and full-retrieval latency and output evidence quality. The user requested a 5% condition; a relative tolerance is proposed pending clarification. See [Vector Comparison Plan](../.scratch/graph-memory-roadmap/vector-comparison-plan.md).

Select placement from the results rather than assuming a combined database is better. Keep Qdrant for a failing or inconclusive candidate result. Preserve the rest of the architecture, and use Mem0, MemPalace and Zep as references. Cache research remains deferred. The architecture/order decision lives in [Existing Architecture, Reference Use and Work Order](../.scratch/graph-memory-roadmap/issues/12-existing-architecture-and-work-order.md).

Official vector-index reference: https://docs.falkordb.com/cypher/indexing/vector-index . Native vector lookup can supply candidates on graph nodes; graph traversal and accepted-state checks must still follow. Test this combined path on the selected release before making quality or performance claims.

FalkorDB documents concurrent reads and one executing write at a time per graph: https://docs.falkordb.com/design/concurrency . Multiple clients may submit work simultaneously, but this does not promise unlimited simultaneous modifications of the same graph. Measure concurrent retrieval and updates on the actual migrated implementation. The earlier Kuzu-to-FalkorDB research established that atomicity and recovery assumptions need verification; it is not a new instruction to replace the user's accepted architecture. No assumption is made that grouping multiple commands supplies rollback on every runtime failure.

Separate graph spaces per user or tenant, with authenticated service-side graph selection and appropriate database permissions. Authorized agents working for one user share that user's space. A name prefix is not access control. Within a multi-user tenant, finer access rules are also required; the smallest hackathon proof can use one private graph per user. Explicit cross-user sharing is a later feature, not implicit graph traversal.

Permission reference: https://docs.falkordb.com/commands/acl . Persistence reference: https://docs.falkordb.com/operations/durability/persistence . Configure durable storage and the needed logging/backup policy, persist permissions as well as data, and test restart/crash recovery. A normal restart test alone does not prove every acknowledged write survives a sudden crash.

Migration reference: https://docs.falkordb.com/operations/migration/kuzu-to-falkordb . Preserve stable logical identities and source evidence, translate graph operations to the new store, rebuild discovery indexes, and compare memory semantics. Replacing the database does not create automatic extraction, typed memories, tenant safety, coordination or conflict-resolution logic.

## Relationship to the current implementation

Current implementation facts are documented in [specification](specification.md), [architecture](architecture.md), configuration and memory source. At this revision the baseline uses a FalkorDB named graph service and embedded Qdrant. Earlier Kuzu question-demo measurements are retained evidence for their original configuration, not latency measurements of the migrated backend. The vector comparison must capture the actual current code/settings and preserve that baseline.

Preserve the current architecture, stable IDs, evidence ownership, change handling, scopes and evaluation fixtures. Add the fuzzy/history and explainable-retrieval capabilities to its graph model, followed by the required sharing/handoff proofs. Check existing behavior before implementing each addition, and distinguish the database migration from newly demonstrated memory behavior.

## Where the two paused topics fit

The first planned addition uses fuzzy rules for suitable revisable beliefs and evidence freshness, while separating relevance, current eligibility, authority and protection. Ordinary values are capped at 0.99; explicit protection at 1 resists automatic decay. An accepted direct correction/replacement can end the old version's current acceptance and transfer protection. Preserve both nodes, evidence, prior values and explicit `CONTRADICTS`/`SUPERSEDES` links with reasons; an unresolved contradiction remains a visible dispute. Context-specific preferences do not silently replace general preferences. Exact authority, weights and decay periods still need decisions and tests.

The second planned addition makes claim/field, scope/condition, evidence, change and dependency relationships explainable. Retrieval combines question wording/meaning lookup with bounded graph expansion, gathers needed companion evidence, and checks current versions, disputes, task prerequisites and handoff state. It verifies that the requested field is available before answering or acting and shows the supporting source path. Compare KG-only, vector-only and combined retrieval on varied and held-out questions, then evaluate automatic ingestion and final answers separately. Good memory retention alone does not prove either retrieval quality or answer correctness.

## Smallest convincing proof, before the travel application

Demonstrate two agents and two isolated users. Show a conversation remembered after restart; an accepted field-level change with both versions retained; a handoff that includes evidence and unfinished work; a dependency invalidated by the change; a disputed claim that stops a confident action; a question whose answer is missing; concurrent task claims where only one agent becomes owner; and retries/recovery without duplicated completed work. Removing semantic relation checks should lose specific demonstrated behaviors.

Measure concurrent read/write submission separately from completed throughput and queue delay. Check lost updates, stale actions, duplicate event effects, tenant access, durability, complete retrieval evidence, explanation paths and final answer correctness. The previous small retrieval scores establish none of these shared-service guarantees.

## Proposed build order

First run the isolated FalkorDB-versus-Qdrant vector comparison and decide placement. Then add both paused ideas to the existing KG: the smallest complete fuzzy/protected memory lifecycle with retained change history, and explainable relation-aware retrieval with question checks. Connect accepted changes and evidence paths to shared tasks/handoffs, and repeat latency/output checks after these additions. The teammate can build the focused application in parallel. Detailed event-day timing and minimal scope remain decisions in the [updated route](../.scratch/graph-memory-roadmap/route-outline.md). This planning update performs no benchmark, installation, deployment or migration.

## Implementation checkpoint — 2026-10-14

The paragraphs above retain the original proposal. Subsequent execution authorization has now produced the [vector comparison](../report/vector_placement_20261013_p5_paired/REPORT.md) and a first implementation of both paused additions, retaining FalkorDB plus embedded Qdrant. The [implementation guide](memory_evolution.md) states the actual interfaces, defaults and boundaries. The [final graph demo](../report/lifecycle_implementation_20261014_final/README.md) retains real stored evidence for protection, accepted changes, disputes, missing fields, identity paths and dependency-aware handoffs.

This checkpoint does not complete the proposed asynchronous ingestion/notification service, authenticated tenant isolation, distributed ownership, larger concurrency/load proof, raw-message interpretation or the travel application. Those remain work in the route. The existing source and extraction paths remain available; typed semantic memory requires an application or agent to supply interpreted claims with attributable source events.
