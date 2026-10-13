# Event rules and FalkorDB boundaries

Research checkpoint: 13 October 2026, Asia/Calcutta. Research only: no database was installed, migrated, or tested. Official documentation was checked against the organizer page, Redis transaction semantics, current release notes, and the existing local implementation. Documentation describes expected behavior; the proposed tests below must verify the chosen build.

## Everyday-language summary

Make a new event entry whose graph actually controls memory changes and agent handoffs. Keep earlier research and working data as reference material. FalkorDB can save connected memories, support meaning search, and serve several agents, but changing databases does not automatically provide safe handoffs, private users, or recovery from a crash. Those need explicit rules and demonstrations.

A single graph update can be treated as one change according to current documentation. A sequence of separate commands is a different promise. In particular, grouping commands with `MULTI/EXEC` does **not** mean every earlier command is undone if a later command fails while running. A booking, payment, email, or other external action is outside the graph update entirely.

## Verified event requirements

- The event runs **15 October, 12:01 AM IST through 18 October, 11:59 PM IST**, with submissions closing at the latter time; teams may have up to four members.
- Track 02 covers persistent episodic, semantic and procedural memory, conversation history, shared state and handoffs, concurrent access, and separate user/tenant memory.
- FalkorDB must be the primary graph database and support a central product function. The graph must affect what the agent does; a decorative graph viewer is insufficient.
- General libraries, templates and infrastructure may be reused. The submission and its main FalkorDB implementation must be new work completed during the event.
- Coding assistants are permitted; the team remains responsible and must explain its work. Live deployment is preferred, rather than mandatory; otherwise complete local instructions and a working demo video are required.

Source: [organizer requirements and FAQ](https://www.wemakedevs.org/hackathons/falkordb).

**Planning inference:** before the event, research, agreements, interfaces and test scenarios can reduce risk. Keep dated evidence of reused material versus event-built work. The precise treatment of a pre-event application-specific memory implementation is not clarified beyond the reuse rule; ask the organizer if the team wants to build that implementation early. No judging weights or promise of winning were verified.

## Database promises and their limits

### One change versus several changes

Current FalkorDB documentation states that an individual modifying query is atomic, including compound clauses: it succeeds fully or rolls back its changes. It documents parallel read queries, consistent read views, and serialized writes per graph. Several clients may submit writes together, but one graph processes those writes one at a time. These are not throughput measurements. [Atomicity and concurrency](https://docs.falkordb.com/design/concurrency).

That page's recommendation of `MULTI/EXEC` for multiple queries must **not** be read as runtime-error rollback across the commands. Redis documents that commands execute sequentially without interleaving, but a command failing after execution starts does not prevent other queued commands from executing; transaction rollback is unsupported. A queue-time error and a runtime error have different outcomes. [Redis transaction semantics](https://redis.io/docs/latest/develop/using-commands/transactions/).

**Design consequence:** put one accepted correction, its old/new state, and its dependency markers in one tested graph query where possible. A task claim must check availability and claim it in the same update; checking and later writing in separate calls still allows stale decisions. Larger workflows need recorded progress, retries that recognize repeated requests, and recovery. Graph atomicity cannot undo an external reservation or guarantee that a notification was delivered.

### Private graphs and permissions

ACL documentation permits graph-name patterns and read/write permissions, plus restrictions on commands. Naming one graph per tenant does not itself authenticate a caller. Permissions are graph scoped, rather than a documented universal per-node privacy mechanism. Read permission excludes some metadata, and mutation side channels are explicitly not covered. Do not give an untrusted tenant broad administrative or graph-list/copy access merely because normal queries are scoped. [ACL command reference](https://docs.falkordb.com/commands/acl).

Users created with `ACL SETUSER` live in memory until saved. A configured ACL file and `ACL SAVE` are needed to preserve them across restarts; graph persistence alone does not preserve these settings. The guide also recommends disabling the unrestricted default user after setting up administrators. [ACL persistence](https://docs.falkordb.com/operations/durability/acl-persistence).

**Design consequence:** resolve tenant identity from authenticated access, not a graph name supplied by the caller. Test denial and metadata leakage as well as allowed reads. A service using one privileged database account must enforce tenant access itself; that account does not make each application caller private automatically.

### Persistence and crash recovery

A mounted persistent volume preserves database files when a container is recreated. The documented normal-restart demonstration is useful but is not a crash test. [Docker persistence](https://docs.falkordb.com/operations/durability/persistence).

RDB snapshots can lose changes since the snapshot. AOF logs changes, with different disk-flush choices; the guide describes roughly one second of potential loss with `everysec`. Faster acknowledgement and stronger persistence are different requirements. Do not promise zero loss from the volume alone. Backups also need a restoration test. [Durability options](https://docs.falkordb.com/operations/durability).

**Design consequence:** decide what “received” means: accepted by the service, saved in the graph, or durably persisted under the chosen configuration. Store original events and processing status so interrupted interpretation can resume. If a client loses its connection after sending an update, the result may be unknown; retry using an event identity instead of assuming nothing happened.

### Meaning search can coexist with graph memory

FalkorDB documents vector indexes over graph properties, using HNSW and cosine/Euclidean similarity with configured dimensions. This permits one database to hold relationships and searchable embeddings. It does not supply an embedding model, contradiction judgement, useful graph structure, or a complete answer by itself. [Vector indexing](https://docs.falkordb.com/cypher/indexing/vector-index).

## Version-sensitive findings

Current release notes describe 6.0 as a new Rust engine replacing the 4.x C engine. They document differences in replication, package availability and search components; 4.x and 6.x cannot be mixed in one replication group. Floating tags can therefore select materially different implementations. [6.0 release notes](https://github.com/FalkorDB/FalkorDB/releases/tag/v6.0.0).

Pin the server image/version and Python client used during the event. Record them with test results. Confirm single-query rollback, ACL rules, vector operations, persistence and all required commands on that exact version. Do not infer feature availability from the latest docs or from a similarly named client method. This research did not verify a deployed build, a capacity limit, or read/write throughput.

## Comparison with the existing system

The [current specification](../../docs/specification.md) describes embedded Kuzu plus embedded Qdrant; text ingestion and retrieval already exist. [The write coordinator](../../memory/storage.py) confirms graph transactions plus compensating restoration of vector records after caught errors. Its own documentation explicitly excludes crash atomicity. [Qdrant setup](../../memory/vector_store/qdrant_store.py) uses local storage; [the API server](../../server.py) binds locally and the specification explicitly provides no authentication or tenant isolation.

Moving to a server database can allow authorized agents to share access, but does not reproduce the current Kuzu transaction API automatically. Keeping a separate vector store retains a two-store recovery problem. Putting graph and vectors together reduces that particular boundary; hosted extraction, notifications and external actions still remain outside the database change. Preserve existing stores and evaluation records, and create a separate event implementation and corpus.

## Human decisions still needed

| Decision | Feasible choices and tradeoff |
|---|---|
| Storage boundary | FalkorDB with graph/vector properties simplifies the initial deployment; FalkorDB plus Qdrant retains existing retrieval work but requires recovery between stores; a separate durable event log plus FalkorDB offers clearer replay but adds operational work. These are candidates, not a selected architecture. |
| Tenant boundary | One graph per user/tenant is easy to explain and test; organization-owned graphs with individual access require a clearer sharing policy. Decide who is allowed to share memories. |
| Durability | Choose an acceptable loss window and acknowledgement meaning, then configure and demonstrate it. A normal restart test alone is insufficient for commercial claims. |
| Event scope | Choose a narrow handoff/update scenario and divide the two-person work after agreeing the service contract. Keep research evaluation and later product hardening outside the event's critical path. |

## Suggested small tests for the roadmap

1. **Atomic correction:** deliberately fail a multi-clause graph change after an earlier modification; verify old/new memory and dependency state remain unchanged.
2. **Multi-command negative control:** deliberately fail one runtime command inside a `MULTI/EXEC` block and inspect every result and surviving change. Document the difference from test 1.
3. **One task, two agents:** issue competing claims at once; require exactly one owner. Repeat with stale task versions and a client disconnect.
4. **Repeated event:** submit the same event concurrently and after an unknown-result disconnect; retain one event and one accepted transition.
5. **Access boundary:** authenticate two tenants, test cross-tenant reads/writes and permitted commands, then restart and repeat. Include graph metadata and copy/delete operations.
6. **Recovery boundary:** compare clean restart, abrupt server termination, and interruption between event receipt and interpretation. Report any loss window and uncertain external action; restore a backup separately.
7. **Meaning plus relationships:** compare graph-only, vector-only and combined evidence on paraphrases, accepted corrections, disputed claims and absent facts. Prove dependencies change agent behavior when graph relationships are used.
8. **Concurrency measurement:** report completed reads/writes, waiting time and errors under the chosen workload, separately for one graph and multiple graphs. Many concurrent clients is not itself evidence of high write throughput.

## Publication

Findings are committed only on the local research branch `codex/research/memory-event-boundaries`. The repository has no configured remote, so a push or pull request cannot be published. Parent planning tickets should link this local evidence and retain that limitation.
