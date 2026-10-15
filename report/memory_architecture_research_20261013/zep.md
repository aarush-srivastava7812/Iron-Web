# Zep / Graphiti architecture research

Checked October 13, 2026. Primary-source desk research and read-only inspection of this repository. No provider calls, ingestion, database mutation, service startup, migration edits, or caching research were performed.

## Main finding

The name is **Zep**. Distinguish its hosted service from **Graphiti**, the open-source temporal graph framework. The current hosted documentation identifies **Konig** as Zep's graph database service. A Graphiti deployment can instead use FalkorDB. Installing Graphiti with FalkorDB does not recreate every hosted Zep feature. [Zep Context Lake](https://help.getzep.com/v3/context-lake), [Graphiti FalkorDB configuration](https://help.getzep.com/v3/graphiti/configuration/falkordb-configuration)

For this project, the most useful lessons are to preserve the original event, connect derived facts to it, distinguish receipt from completion, combine meaning search with exact-word search and graph connections, and authorize memory scope before any read or write. These are design conclusions from the sources below, not a claim that adopting Graphiti alone supplies the coordination system we need.

## What is stored, and how graph and vector search connect

The January 2025 Zep paper describes three linked layers: original episodes, semantic entities/facts extracted from those episodes, and summaries of strongly connected communities. Episodes can be messages, text or JSON. Facts are relationships between entities; their sources remain traceable. The paper's deployment used Neo4j search facilities. It is historical architecture evidence, not proof of today's hosted storage implementation. [Zep paper, sections 2–3](https://arxiv.org/html/2501.13956v1)

Current Zep ingestion documentation describes this path:

1. Keep the incoming material as a retrievable episode.
2. Extract entities and facts.
3. Derive dates where the source supports them.
4. Resolve entities against existing ones.
5. Resolve repeated or conflicting facts.
6. Update summaries, embed the objects and persist them.

Entity matching is best-effort; Zep says it prefers leaving ambiguous identities separate over merging the wrong people. Directly added nodes are not deduplicated merely by name. [How graph creation works](https://help.getzep.com/v3/how-graph-creation-works)

**For open-source Graphiti with FalkorDB, graph records and their embedding properties reside in FalkorDB; a separate Qdrant installation is not required by the inspected driver.** Its fact edges have `fact_embedding` and entity nodes have `name_embedding`; search obtains matching graph objects from those properties. Full-text search calls FalkorDB's full-text facilities. [Graphiti v0.30.2 FalkorDB search operations](https://raw.githubusercontent.com/getzep/graphiti/v0.30.2/graphiti_core/driver/falkordb/operations/search_ops.py)

There is an important performance distinction: the inspected v0.30.2 similarity methods start with a graph `MATCH`, calculate cosine similarity over matching records, sort, and limit. They do **not** call a native approximate-nearest-neighbor vector index. Filters can reduce the candidates, but a small final result limit does not eliminate the preceding scoring work. Thus **FalkorDB supporting vector indexes does not establish that this Graphiti path uses them**. The database capability and this adapter's actual query path must be checked separately. [Same pinned search source](https://raw.githubusercontent.com/getzep/graphiti/v0.30.2/graphiti_core/driver/falkordb/operations/search_ops.py), [cosine helper](https://raw.githubusercontent.com/getzep/graphiti/main/graphiti_core/graph_queries.py)

For hosted Zep, the docs expose graph objects and semantic/full-text retrieval, but they do not disclose enough implementation detail to confidently name every physical vector store, index implementation, replication mechanism or consistency boundary. Do not infer that hosted Zep uses FalkorDB or Qdrant from Graphiti's available adapters. [Hosted Context Lake](https://help.getzep.com/v3/context-lake)

## Retrieval behavior

Current hosted Zep graph search combines semantic similarity and BM25 keyword retrieval; optional breadth-first search follows specified starting nodes. Rank fusion combines candidates. Scopes choose facts/edges, entity nodes, original episodes, observations or thread summaries; auto search assembles context across scopes. **Episode search is currently documented as BM25-only, with no reranker.** Its scores are not comparable to node/edge scores. Cross-encoder reranking trades speed for closer query/result relevance assessment; its 0–1 result is not our protected-memory acceptance score. [Zep graph search](https://help.getzep.com/v3/searching-the-graph)

Graphiti's recipes explicitly configure BM25, cosine similarity and optionally graph traversal. A combined RRF recipe searches nodes, facts, communities and keyword episodes; a combined cross-encoder recipe adds richer reranking. This is controllable retrieval, not a need to send the entire graph to an agent. [Graphiti search recipes](https://raw.githubusercontent.com/getzep/graphiti/main/graphiti_core/search/search_config_recipes.py)

The paper distinguishes candidate search, reranking, and construction of a compact context block with facts and their dates. It reports benchmark results, but those comparisons do not guarantee our performance, current hosted latency, or FalkorDB driver latency. We need our own measurements of evidence completeness and outdated decisions, alongside response time. [Zep paper, sections 3–4](https://arxiv.org/html/2501.13956v1)

## Real-time ingestion: accepted does not mean ready

Zep recommends recording both human and assistant messages on each turn, preserving their creation order. `thread.add_messages` saves thread history and builds the user graph. The graph-add API returns HTTP 202 Accepted. Those are live event submissions, not a promise that interpreted facts are immediately searchable. [Adding messages](https://help.getzep.com/v3/adding-messages), [graph add API](https://help.getzep.com/sdk-reference/graph/add-data)

Hosted processing is asynchronous. The docs describe seconds-to-minutes variation, and support episode status, task status and batch status. `processed=true` on a final episode establishes extraction progress but does not prove every earlier episode succeeded. Search indexing can take additional time; an arbitrary nonempty search does not verify the newly submitted record. Ordered live submissions and batches have different ordering boundaries, so mixing them cannot be treated as one globally serialized stream. [Check ingestion status](https://help.getzep.com/v3/check-data-ingestion-status)

Zep recommends production completion notifications through `episode.processed` webhooks, available on certain plans. Signed notifications identify the episode and graph so an application can react after processing. Batch completion has documented failure/cancellation qualifications; notification handling should not replace failed-item inspection. [Webhooks](https://help.getzep.com/v3/webhooks)

The local open-source `await graphiti.add_episode(...)` method executes extraction, resolution, attribute updates and persistence before returning its result. It is an asynchronous Python function, not the hosted 202 acceptance contract. It does not, by itself, provide a durable background queue that survives process crashes. Community updates are optional and default to false in the inspected entry point. [Graphiti ingestion source](https://raw.githubusercontent.com/getzep/graphiti/main/graphiti_core/graphiti.py)

**Proposed lesson for our service:** give a saved event an immediate receipt ID, then track saved / interpreting / accepted / disputed / failed / searchable independently. Persist work before acknowledging it. Notify relevant agents when the accepted update has been committed. This is our architectural recommendation, not a verified Zep implementation detail. For an important correction, dependent actions must wait for a version/current-state check rather than assume a quick acknowledgement means the change has taken effect.

## Updating memory over time

Zep facts distinguish four dates: when the system learned a fact, when the fact became applicable, when it stopped being applicable, and when the system learned it had ended. Old facts can be invalidated while retaining history. A date range records a derived claim's temporal scope; it does not certify truth. [Temporal facts](https://help.getzep.com/v3/facts)

This supports our temporal-memory goals, but **automatic contradiction invalidation is not our proposed authority policy**. Our protected `1`, accepted correction, unaccepted dispute, different scope, and changed-world-state cases must remain explicit application rules. Keeping these distinctions is a possible extension and evaluation subject; a temporal graph alone is already established prior work.

## Sharing across sessions and agents

Zep users can have multiple threads; messages from all their threads contribute to the same user graph. An authorized new session can therefore retrieve previous knowledge without needing the old conversation kept in its prompt. [Threads](https://help.getzep.com/v3/threads)

Shared account/project/domain context is addressed by `graph_id`; private personal context uses `user_id`. The official recipe retrieves authorized personal and shared context separately for one task. Shared memory therefore means selecting allowed scopes, not merging all users into one pool. [Sharing personal and account context](https://help.getzep.com/v3/how-to-share-context-across-users-using-graphs)

Hosted Zep agent ABAC policies attach to API keys and can limit actions and data access. Source metadata is projected onto derived graph artifacts for source-based policies. This is relevant because a summary or derived fact can otherwise expose a restricted source even if its original episode is hidden. These controls have documented product/plan limitations and do not authorize an external action on behalf of the user. [Agent access](https://help.getzep.com/v3/attribute-based-access-control)

Zep UserGroups are access-control groupings, **not data containers**. Membership does not merge personal graphs. Current docs apply those grants to authenticated Context/Memory MCP shared-graph access; ordinary API-key traffic follows agent policies instead. The page states Enterprise-only availability. [UserGroup access](https://help.getzep.com/v3/usergroup-access)

Graphiti `group_id` provides namespace separation. Its docs explicitly require deriving and authorizing group IDs in the application, rather than trusting an ID from a caller. For FalkorDB the driver selects a named graph; this grouping is not a complete identity/access service. [Graphiti namespacing](https://help.getzep.com/v3/graphiti/core-concepts/graph-namespacing), [FalkorDB driver](https://raw.githubusercontent.com/getzep/graphiti/main/graphiti_core/driver/falkordb_driver.py)

**Proposed lesson:** authorized agents should use one memory service with stable user/workspace identifiers. Handoffs need their own task owner, work status, evidence used, applicable memory version, pending actions and completion acknowledgement. The inspected sources do not establish that Graphiti provides a complete task-claiming, exactly-once external action or dependent-plan invalidation protocol.

## FalkorDB compatibility and concurrency findings

The inspected Graphiti v0.30.2 release supports the FalkorDB extra. Its Python dependency is `falkordb>=1.1.2,<2.0.0`; **this is the Python client package range, not a demonstrated FalkorDB server minimum**. Do not pin a server image by interpreting that number as a database version. [Pinned project configuration](https://raw.githubusercontent.com/getzep/graphiti/v0.30.2/pyproject.toml)

The v0.30.2 release notes include request-scoped driver fixes for concurrent group isolation and a FalkorDB full-text search improvement. This is evidence that backend routing and query behavior are version-sensitive. A separate official issue reports multi-group read routing problems. Release fixes for one routing case do not prove every multi-tenant path is correct. Pin and test the exact installed combination with simultaneous reads/writes across two users before relying on it. [Release notes](https://github.com/getzep/graphiti/releases/tag/v0.30.2), [multi-group read issue](https://github.com/getzep/graphiti/issues/1842)

FalkorDB documents concurrent readers and serialized writes per graph. Atomicity of an individual query does not turn an entire extraction pipeline, with many queries and model calls, into one indivisible update. Multi-query operations need explicit coordination; broad transaction blocks can restrict concurrency across graphs. Batch related changes when possible and measure the queue for a busy shared graph. [FalkorDB concurrency](https://docs.falkordb.com/design/concurrency)

## What the repository's Zep comparison actually does

Read-only inspection found `zep-cloud==3.30.0` in `requirements/research.txt`. It is a recorded optional dependency pin; the expected SDK files were not present at the checked primary `.venv` location. No installed-version or service execution claim is made.

`research/upstream/packages.py` creates a Zep user, ingests each evaluation document as a text episode with a document ID, and searches `scope="episodes"`. It checks document visibility by repeating search up to three times with two-second waits. Consequently this adapter evaluates original-document episode retrieval, not full graph-fact retrieval, temporal answers, shared-agent handoffs or production ingestion readiness. Its limited search-based waiting is weaker than a tracked completion plus record-specific readiness check. Current hosted documentation says episode search is keyword-only; the fixed SDK pin does not freeze the hosted server behavior. [Local adapter](/D:/Opencode_/reserchpaper/research/upstream/packages.py), [local pin](/D:/Opencode_/reserchpaper/requirements/research.txt), [current episode-search contract](https://help.getzep.com/v3/searching-the-graph)

This work did not modify the adapter or the parallel Kuzu-to-FalkorDB migration.

## Recommended next measurements, without assuming speed

These are our proposed tests:

- Measure separately receipt time, interpreted-memory completion, searchable completion, retrieval time, and total answer time. Record the typical and slow cases under concurrent load.
- Test both paraphrases and exact identifiers; compare fused retrieval with keyword-only and meaning-only retrieval.
- Scope retrieval first, cap graph expansion, and reserve companion facts required to interpret a condition or change. Rerank a bounded candidate set only where the added accuracy warrants it.
- Inspect the actual FalkorDB similarity query plan. Test graph-native indexed vector candidates against the inspected cosine-scoring path before claiming scale.
- Re-deliver the same event, crash after receipt, deliver an older fact late, and submit competing changes. Verify no silent lost event, duplicate action, or unjustified replacement.
- Run cross-user simultaneous operations and intentionally attempt unauthorized reads. Verify original episodes, derived facts and summaries all respect the same permissions.
- Measure whether a accepted correction makes a dependent decision outdated and whether a handoff transfers that status. Retrieval quality alone cannot establish safe coordination.

Unverified areas remain: our actual deployment latency and load limits, selected server/client/library compatibility, all hosted physical indexing details, Graphiti concurrency behavior for the exact deployment, and completeness of application-level change authority/handoff rules. Vendor benchmarks and product positioning do not settle these questions.
