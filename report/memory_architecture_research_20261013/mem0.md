# Mem0 architecture research

Checked 13 October 2026. Research only: no paid API calls, package installation, benchmarks, migration edits or live memory changes. The requested excluded topic was not researched.

## Accessible conclusion

Mem0 is useful for finding compact remembered facts, but “Mem0 has a graph” now means different things depending on the product and version. The latest self-hosted Python release has **no external knowledge-graph backend**. Its entity index improves search through linked memory identifiers. The hosted product has a built-in connection graph. Older releases supported separately configured graph databases. Neither current option supplies our proposed typed change, evidence, decision-dependency and handoff model automatically. [Official migration guide](https://docs.mem0.ai/migration/oss-v2-to-v3), [Platform graph explanation](https://docs.mem0.ai/platform/features/graph-memory)

## Version and local evidence

- PyPI lists `mem0ai 2.2.1`, released 25 September 2026, as the current release. Its published provenance identifies commit `94c3fe9f238f3dbf29c9ce98643bd71eb13077cd`. Research checked the matching `v2.2.1` source tag, current documentation, and legacy `v1.0.7` source separately. [PyPI release/provenance](https://pypi.org/project/mem0ai/), [2.2.1 release](https://github.com/mem0ai/mem0/releases/tag/v2.2.1)
- Local `requirements/research.txt` pins `mem0ai==2.2.1`. This is an optional research profile, not the ordinary application. `research/upstream/packages.py` configures Qdrant, FastEmbed and `infer=False`, with no graph configuration. It preserves the original document identifier in metadata. [Local pins](/D:/Opencode_/reserchpaper/requirements/research.txt), [local adapter](/D:/Opencode_/reserchpaper/research/upstream/packages.py), [research boundaries](/D:/Opencode_/reserchpaper/research/README.md)
- The ordinary `.venv` inspected here has no Mem0 installation. No separate installed research environment was verified. The adapter also passes Python search `limit=k`; the current signature uses `top_k`, and unrecognized keyword arguments are not used to set the count in the inspected implementation. Therefore an unvalidated run could return its default count. This is a source-review finding, not a executed failure. [Pinned Python implementation](https://github.com/mem0ai/mem0/blob/v2.2.1/mem0/memory/main.py)

## How vectors and graph information connect

| Variant | Connection between stores and results |
|---|---|
| Legacy OSS, checked at 1.0.7 | The same incoming messages feed vector and optional graph branches. Both branches run concurrently, but return separate `results` and `relations`; vector reranking does not fuse graph relationships into its result list. Common scope identifiers join their *usage*, rather than proving a single transactional store or evidence linkage. [Legacy code](https://github.com/mem0ai/mem0/blob/v1.0.7/mem0/memory/main.py) |
| Current OSS, checked at 2.2.1 | Memory text and embeddings occupy the main vector collection. A second entity collection holds embedded entity names and `linked_memory_ids`. The history path is configured separately; there is no `graph_store` configuration field. [Pinned configuration](https://github.com/mem0ai/mem0/blob/v2.2.1/mem0/configs/base.py), [entity-store code](https://github.com/mem0ai/mem0/blob/v2.2.1/mem0/memory/main.py) |
| Current hosted Platform | Entity nodes connect memories mentioning the same entity. Retrieval boosts those memories alongside meaning similarity and keyword matching. It explicitly does not create typed entity-to-entity relationships such as `manages`; its old standalone `relations` field is empty. The private database engine/topology is not identified by these public docs. [Platform graph docs](https://docs.mem0.ai/platform/features/graph-memory) |

In words: **legacy** is message → two separate branches → text matches plus relation triples. **current OSS** is message → remembered facts in a vector collection → entity records linking to fact IDs → ranking boosts. **Platform** is remembered facts ↔ shared entity nodes → one ranked search response. The latter is a useful lookup web; it does not by itself represent accepted supersession or work dependencies.

Current OSS uses local spaCy-based entity extraction, including names and specific topic phrases; without that dependency it returns no extracted entities. Thus it need not make a query-time LLM call for this stage. [Entity extraction source](https://github.com/mem0ai/mem0/blob/v2.2.1/mem0/utils/entity_extraction.py)

## Change semantics and the FalkorDB compatibility trap

Current ingestion is ADD-only: the extraction model no longer decides automatic UPDATE/DELETE operations. New and old statements accumulate; explicit editing remains a separate operation. This is not our proposed graph of `CONTRADICTS`, accepted `SUPERSEDES`, sources and consequences. [Current ingestion contract](https://docs.mem0.ai/api-reference/memory/add-memories), [explicit update](https://docs.mem0.ai/core-concepts/memory-operations/update)

The 2025 Mem0 paper describes a different graph design: typed triples, entity embeddings, LLM conflict resolution and invalidating obsolete relations while retaining them. It used Neo4j and GPT-4o-mini. That historical description must not be substituted for current shipping behavior. The paper reports an approximately two-point graph improvement and 91% lower p95 latency for base Mem0 versus full context under its experiment; these are author-reported benchmark results, not our latency measurement or a real-time guarantee. [Mem0 paper, sections 2.2 and evaluation](https://arxiv.org/html/2504.19413v1)

FalkorDB publishes `mem0-falkordb`, checked at source version 0.4.1. Its registration imports `GraphStoreFactory` and `mem0.graphs.configs.GraphStoreConfig`. Those hooks were removed from current OSS; the 2.2.1 factory has no `GraphStoreFactory`. Consequently this inspected plugin cannot register against that pinned release as written. This is a direct source compatibility conclusion, not an installation test. The plugin does not pin Mem0 in its runtime dependencies. [Plugin registration](https://github.com/FalkorDB/mem0-falkordb/blob/main/src/mem0_falkordb/patch.py), [pinned factory](https://github.com/mem0ai/mem0/blob/v2.2.1/mem0/utils/factory.py), [plugin package](https://github.com/FalkorDB/mem0-falkordb/blob/main/pyproject.toml)

Its graph code has a separate graph per `user_id`, optional agent/run properties, vector matching of graph nodes and incoming/outgoing relationship retrieval. The inspected deletion path physically executes `DELETE r`; graph search invokes an LLM for query entity extraction. Thus it should not be assumed to provide either preserved contradiction history or an LLM-free fast read. Older third-party integration announcements are insufficient compatibility evidence. [Plugin graph implementation](https://github.com/FalkorDB/mem0-falkordb/blob/main/src/mem0_falkordb/graph_memory.py)

## Real-time ingestion: received is different from ready

The Platform's inferred add operation returns a pending event and completes in the background; callers poll for success/failure. Its documented `infer=False` path instead stores verbatim memories synchronously. A quick pending response does not mean interpreted memory is already searchable. [Add API, request/response contract](https://docs.mem0.ai/api-reference/memory/add-memories)

OSS `Memory.add` waits through the processing pipeline. `AsyncMemory.add` makes that operation awaitable and moves blocking work into threads; it is not a durable queue acknowledgement. Applications can schedule multiple operations, but still await completion, handle failure and cap concurrency. [AsyncMemory docs](https://docs.mem0.ai/open-source/features/async-memory)

Inference from source review: likely write-delay sources include input embedding, prior-fact lookup, fact-extraction LLM time, extracted-fact embeddings, insertion and entity linking. Current batching reduces some per-fact work but does not eliminate model/network time. Direct structured agent events could avoid interpretation on the immediate path in **our design**, while free-form conversation takes a background interpretation path. Keep a receipt record, unique event ID, visible processing state and a completion signal. Never advertise a queued correction as committed or let an affected agent continue silently against old accepted state.

## Sharing and permissions

Platform scopes include user, agent, application and run. Searching only a user can include that user's records with additional scopes; requiring an agent too can exclude user-level memories. Platform extraction also attributes a default extracted fact to either user or agent, rather than blindly setting both. Agent sharing therefore requires an intentional scope policy, not automatically adding every available identifier. [Entity-scoped memory](https://docs.mem0.ai/platform/features/entity-scoped-memory)

The OSS library constructs storage/filter scopes from supplied identifiers. These are selection fields, not proof of who may access them. Current bundled REST source authenticates requests, but inspected search/get/update routes do not bind requested memory scope to the authenticated person's identity. A deployment must separately enforce tenant and agent permissions; authentication alone is not demonstrated per-memory authorization. [REST routes](https://github.com/mem0ai/mem0/blob/v2.2.1/server/main.py), [authentication implementation](https://github.com/mem0ai/mem0/blob/v2.2.1/server/auth.py)

Proposed lesson: our agents should share one controlled memory service. Give shared facts a user/tenant scope; give private reasoning a narrower scope; record producing agent as provenance. Handoffs need task state and accepted evidence versions in addition to searchable notes. This is our recommendation, not an established Mem0 feature.

## Retrieval speed lessons

OSS combines semantic, normalized keyword and entity signals; its scoring source applies the relevance threshold to semantic similarity before fusion. A returned `score` is a relevance score, not confidence that a claim is true. [Scoring source](https://github.com/mem0ai/mem0/blob/v2.2.1/mem0/utils/scoring.py)

The migration docs explicitly say keyword/entity boosts do not add candidates outside the semantic shortlist. That can miss an exact fact never recalled by meaning search. [Migration retrieval description](https://docs.mem0.ai/migration/oss-v2-to-v3)

Recommendations for our system, not upstream promises:

1. Keep ordinary read paths free of LLM interpretation when possible; let writes establish normalized names, evidence and scopes.
2. Run independent meaning, exact-term and graph-anchor lookups together, allowing each to nominate candidates. Then follow only relevant evidence/change/dependency links under a bounded expansion budget.
3. Use indexes and reusable connections; optionally rerank a small shortlist when extra quality justifies extra time. Do not assume more candidates always help.
4. Measure receipt latency, interpreted-memory visibility, retrieval latency and handoff readiness separately, including p95 under simultaneous reads/writes. No numerical target is established by this research.
5. Preserve accepted state, conflicting history and decision dependencies in FalkorDB. Do not replace these with co-occurrence links or relevance boosts merely because those are easier to search.

## Remaining unknowns

No inspected public source establishes hosted database internals, atomicity across Mem0 stores, our model/provider latency, concurrency under our workload, or an interoperable FalkorDB plugin for current OSS. No automatic handoff correctness, stale-decision prevention or task-ownership protocol was verified here. The local SDK adapter's `infer=False` configuration also cannot substantiate quality of upstream fact extraction or graph memory. These require explicit contracts and separate tests after architecture agreement.
