# ADR-001: Replace the embedded graph with FalkorDB

Status: Accepted. Date: 13 October 2026.

The requested backend change replaces Kùzu while retaining the current memory API, Qdrant vectors, temporal history, ownership rules and caught-failure recovery. It does not implement the separate proposed agent-coordination or fuzzy-acceptance designs.

Use the official FalkorDB Python client against a named graph, with a pinned local Compose service. Translate node-table schema and wildcard property projections into native indexes, unique/mandatory ID constraints and explicit Cypher projections. Replace local graph-file paths with service connection settings and graph names. Credentials remain environment-only.

Redis MULTI alone does not restore earlier graph writes when a later command fails. Instead, coordinated operations use a copied staging graph. A token-owned, renewed Redis lease serializes cooperating clients. Atomic key publication checks the lease/revision and retains the old graph as a recovery copy until the vector/graph operation finishes. This preserves the earlier compensation guarantee without pretending that FalkorDB implements Kùzu's BEGIN/ROLLBACK commands.

This choice adds a service dependency, network round trips and graph-copy overhead per coordinated write. Full graph copies prioritize correctness for the current workload; they are not a claim of improved bulk-write latency. Leases do not coordinate clients that bypass the store API. Both-store crash atomicity is still absent, and an interrupted process may leave staging/recovery copies for deliberate inspection. Automatic cleanup does not delete unfamiliar graphs.

An optional import utility preserves the old graph file and verifies all source properties and relationship direction/multiplicity before publishing. Existing targets with different populated content are rejected. Earlier benchmark outputs retain their original interpretation as Kùzu results.

Revisit this design if graph-copy cost becomes material, a shared remote vector service is introduced, or durable operation replay is required.

References: [FalkorDB graph copying](https://docs.falkordb.com/commands/graph.copy), [official Python client](https://github.com/FalkorDB/falkordb-py), [Redis key renaming](https://redis.io/docs/latest/commands/rename/).

Follow-up, 13 October 2026: graph expansion reads seed entities in bounded batches while preserving input order and traversal limits. Conflict ownership/direction/time is cached against the shared graph revision and staging graph identity, with mutation/rollback invalidation and copied caller results. Cache retention is capped at 50,000 observations and 100,000 conflict edges. The application graph lease still serializes cooperating readers and writers.

Bulk ingestion exposed a Redis background-fork collision during automatic AOF rewrite. Graph-copy startup retries only the explicit `GRAPH.COPY failed, could not fork` error, only while its destination is absent and the lease remains owned, and only until the configured socket-timeout deadline. Ambiguous transport failures are not retried. Graph-copy overhead and cross-store crash limits remain.
