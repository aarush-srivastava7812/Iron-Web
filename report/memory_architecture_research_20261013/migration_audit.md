# In-progress FalkorDB migration: architecture and latency audit

Observation date: October 13, 2026, Asia/Calcutta. This is a read-only source review, not a latency benchmark or a declaration that migration is complete. The source is being edited in parallel in the task named “Create a full codebase specs report”. Its latest user request is to replace Kuzu with FalkorDB and push that work. This research did not message, interrupt, modify, test, deploy or publish that task.

The accompanying migration_snapshot.json and migration_snapshot/ files preserve the exact source inspected for this audit. Later changes may supersede these observations. Source locations below refer to the live paths at inspection; the snapshots are the reproducible evidence.

## What has actually changed in the observed code

The selected migration is **local Qdrant vectors plus a service-backed FalkorDB graph**. It is not a selected move of vector search into FalkorDB. config.yaml now contains a falkordb connection and graph name. compose.yaml pins falkordb/falkordb:v4.20.7, mounts a named volume and enables append-only logging with one-second disk flushing. requirements/storage.txt pins the Python client to 1.7.1. These are separate server/client versions.

The engine imports FalkorDBGraphStore and selects the named graph. Entity/Observation records and ABOUT/RELATES/change relationships continue the earlier model. The graph still stores embeddings on observations, but ordinary meaning search still calls Qdrant; duplicated numeric data does not mean a FalkorDB vector index is being used. I found only ID/name/ownership range indexes in the observed graph setup, not an active native vector-search path.

Sources: [settings](/D:/Opencode_/reserchpaper/config.yaml), [service definition](/D:/Opencode_/reserchpaper/compose.yaml), [engine](/D:/Opencode_/reserchpaper/memory/engine.py), [graph store](/D:/Opencode_/reserchpaper/memory/graph/falkordb_store.py), [storage pins](/D:/Opencode_/reserchpaper/requirements/storage.txt).

The older docs/architecture.md and docs/specification.md inspected still describe embedded Kuzu and its transaction interface. They are not current evidence of a decided graph-native vector architecture. The prior hackathon direction document recommends investigating graph-contained vectors, but explicitly calls that a proposal. Do not confuse that proposal with the current migration choice.

## How graph and vectors connect today

1. An incoming memory receives a stable memory ID.
2. Qdrant stores its text, embedding, entity IDs, time bounds and other metadata under that memory ID.
3. FalkorDB stores entities and one or more observations; source_memory_id links observations back to the owning memory.
4. A meaning-search hit supplies entity IDs that become graph starting points.
5. The graph gathers related entities/observations; their owner IDs retrieve the original text/payload from Qdrant.
6. Results are deduplicated, checked against validity/change links and ranked.

This is a two-store join carried out by the application, not a physical cross-database edge. The source text can be repeated in observations attached to several entities, so deduplication and ownership identity matter.

Sources: [memory ingestion](/D:/Opencode_/reserchpaper/memory/engine.py:404), [hybrid retrieval](/D:/Opencode_/reserchpaper/memory/retrieval/hybrid.py:133), [observation ownership](/D:/Opencode_/reserchpaper/memory/graph/falkordb_store.py:843).

## Why the migration uses a graph copy

The new write coordinator preserves the previous application's caught-failure recovery behavior. It obtains a shared lease, takes exact vector snapshots, copies the live graph into a private staging graph, writes there, then publishes the completed graph by renaming it over the live graph after checking lease ownership. A caught pre-publication failure can delete the staged graph and restore the affected vectors. An uncertain publication outcome is reported rather than silently described as successful rollback.

This is a compatibility/recovery strategy, not a native multi-query FalkorDB transaction or crash-atomic change spanning Qdrant and FalkorDB. All cooperating readers and writers use the same lease to avoid seeing the two stores at different stages. Direct clients bypassing this discipline are not protected by it.

Sources: [write coordinator](/D:/Opencode_/reserchpaper/memory/storage.py), [graph begin/commit/rollback](/D:/Opencode_/reserchpaper/memory/graph/falkordb_store.py:1080), [lease](/D:/Opencode_/reserchpaper/memory/graph/connection.py:80). Official GRAPH.COPY duplicates the graph and its indexes/constraints; its docs permit source access during copy, but this application chooses stricter coordination. [GRAPH.COPY reference](https://docs.falkordb.com/commands/graph.copy).

Graph copy latency, memory usage and disk/commit cost must be measured as graph size grows. I did not measure those quantities. Do not claim an exact complexity or speedup from this code reading alone.

## Verified structural bottlenecks to measure

| Observation in source | Why it matters | Recommended investigation |
| --- | --- | --- |
| The engine's serialized decorator wraps whole save/search calls with the shared graph lease; save computes embeddings and optional extraction inside it. | Model/network work can make other cooperating readers and writers wait. Even a vector-only engine search enters this wrapper. | Separate expensive interpretation from the short state commit; introduce a consistent read/version contract before relaxing locks. |
| Graph execute and synchronized methods also acquire the shared lease; reads use the same query path. | Database support for parallel reads does not establish parallel application reads here. | Test concurrent reads, then implement a read-only snapshot path with accepted-version checks. |
| Each coordinated write makes a staging graph copy. | Ordinary small updates perform graph-wide publication work; the cost may grow or become a throughput limit. | Compare the compatibility strategy with small atomic graph transitions on the pinned server. Keep equivalent failure handling. |
| delete_memory scans all RELATES metadata; add invokes deletion even for a newly supplied memory ID. | Write work can depend on unrelated relationships. | Represent/index direct ownership and restrict cleanup to that memory; preserve compatibility with legacy ownership explicitly. |
| Conflict resolution first reads every Observation to map candidate ownership. | A bounded final candidate count does not prevent a whole-observation scan. | Resolve candidate owners by indexed IDs/source ownership, then fetch their change links only. |
| Hybrid expansion gets observations per entity and vector payloads per observation before final deduplication. | Repeated documents can incur repeated reads and graph/vector round trips. | Deduplicate owner IDs early, batch observation and vector payload retrieval, and keep a relevance/evidence budget. |
| Qdrant remains embedded/local. | Local storage is intended for smaller deployments and has an exclusive storage-directory lock across client instances. | Let one memory service own the current instance, or evaluate server Qdrant if independent workers/processes require direct vector access. |

Sources: [engine lock](/D:/Opencode_/reserchpaper/memory/engine.py:53), [save processing](/D:/Opencode_/reserchpaper/memory/engine.py:340), [graph execution](/D:/Opencode_/reserchpaper/memory/graph/falkordb_store.py:1061), [cleanup scan](/D:/Opencode_/reserchpaper/memory/graph/falkordb_store.py:702), [conflict scan](/D:/Opencode_/reserchpaper/memory/graph/falkordb_store.py:860), [hybrid per-observation reads](/D:/Opencode_/reserchpaper/memory/retrieval/hybrid.py:158), [Qdrant wrapper](/D:/Opencode_/reserchpaper/memory/vector_store/qdrant_store.py), [official Qdrant local implementation](https://github.com/qdrant/qdrant-client/blob/master/qdrant_client/local/qdrant_local.py).

The ordinary graph expansion already batches frontier traversal per hop. Do not misdescribe all of that traversal as one query per neighbor. The remaining per-seed/per-entity/payload reads are the targeted issue. The final ceiling also does not bound all intermediate observation reads.

FalkorDB documents parallel readers and serialized writers per graph. Those are database capabilities; this source snapshot uses a broader application lease. Verify the exact v4.20.7 behavior because current official docs can describe newer engines. [Concurrency reference](https://docs.falkordb.com/design/concurrency).

## What has not become implemented shared agent memory

The observed migration still has default extraction disabled, one configured graph name, a local API/tool adapter, and the old entity/observation model. It does not itself introduce authenticated tenant routing, a durable event-processing queue, interpreted-ready notifications, accepted-versus-proposed field revisions, protected-memory score semantics, dependent-task invalidation, a task-claim protocol or evidence/version-checked handoffs.

The application’s document-ID filter is useful retrieval scope; it is not authentication. A graph name is a storage selection; it is not verified per-user access. A PostgreSQL-style or Kuzu transaction interface cannot be inferred from the begin/commit method names. Vector/graph compensation still covers caught process failures, not all crash or disconnected-client outcomes.

This is not a finding that the migration is wrong. Its current purpose is to preserve working local behavior while changing the graph backend. The proposed low-latency shared-memory service is the next architecture layer and must be agreed, implemented and tested separately.

## Suggested decision boundary

Preserve this migration as a baseline. Choose between (a) FalkorDB graph plus a rebuildable Qdrant discovery service, and (b) graph plus native indexed vector/keyword search in FalkorDB, after equivalent tests. Neither choice automatically supplies correctness or access control.

For either route, prioritize: fast durable event receipt; background interpretation; short accepted-state commits; explicit memory/task versions; directly owned/indexed evidence; bounded batch reads; authenticated user/agent scopes; and action checks against current state. Relaxing the current lease without this replacement contract risks inconsistent reads or lost updates.

The user excluded caching research. This audit deliberately contains no cache design, measurements or recommended cache layer.

## Parallel-change review after the snapshot

The subsequent review found changes to the graph store, tool adapter and schema file hashes. A text comparison showed native UNIQUE/MANDATORY identifier constraints and readiness checks added to the graph schema setup; the other two files had no text-level difference after newline normalization. This is an integrity improvement. The reviewed delta does not change Qdrant/FalkorDB roles, whole-call locking, graph-copy publication, candidate-owner scanning or per-observation payload reads described above.

The original snapshot is intentionally preserved. review_checks.json records changed paths; reviewed_deltas.diff records the source comparison. This qualification avoids presenting a frozen source review as a finished migration result.
