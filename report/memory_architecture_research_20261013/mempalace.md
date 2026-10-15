# MemPalace: storage, graph connections, live ingestion and shared agents

Research checkpoint: 2026-10-13, Asia/Calcutta. Read-only inspection; no services, ingestion, model downloads, dependency installations or migration edits were performed. Caching research was excluded as requested.

## Identity and local compatibility

The exact requested project is **MemPalace/mempalace**, formerly linked under milla-jovovich/mempalace. The project's official sources are its GitHub repository, PyPI distribution and mempalaceofficial.com documentation. Its latest published release inspected is **v3.10.0**, released September 16, 2026. The development branch has commits after that release; this note uses tag-pinned source wherever behavior matters. [Official repository](https://github.com/MemPalace/mempalace), [v3.10.0 release](https://github.com/MemPalace/mempalace/releases/tag/v3.10.0)

Locally, [requirements/research.txt](/D:/Opencode_/reserchpaper/requirements/research.txt:4) pins `mempalace==3.10.0`, but **the active .venv does not currently have it installed**. Read-only `importlib.metadata.distribution('mempalace')` raised `PackageNotFoundError`; no matching package directory was present. [Earlier runtime verification](/D:/Opencode_/reserchpaper/report/runtime_verification.json:17) also reports it as absent. A dependency pin is not an installation or a successful benchmark run.

The [existing adapter](/D:/Opencode_/reserchpaper/research/upstream/packages.py:153) is a research wrapper, not the full product. It writes each supplied document to a text file, runs `mempalace.miner.mine()` when `palace/chroma.sqlite3` is absent, and retrieves through `search_memories()`. It maps filenames back to document IDs. Changed input fingerprints require a new namespace. It does not call knowledge-graph writes, temporal queries, the shared hub or coordination tools. Its Chroma-specific existence check would need revision before using another MemPalace backend. Imports remain present upstream, but runtime compatibility cannot be claimed without installing and testing the pinned package in an isolated environment.

## What is actually stored

There are three distinct structures—not one interchangeable graph:

| Structure | What it holds | Role |
|---|---|---|
| Searchable drawers | Original text chunks, vectors, source references and wing/room labels | Finds memories with related wording or meaning |
| Palace navigation | Rooms and links between organizational areas | Helps agents navigate related topics |
| Temporal knowledge graph | Entities and typed facts, with validity dates and evidence references | Answers relationship and history questions |

Wings are people/projects; rooms are topics. These labels also act as vector-search filters. A shared room can provide a cross-wing navigation connection. **That hierarchy alone is not a factual knowledge graph.** The official concept page itself describes this filtering as a standard storage feature. Drawers are its main retrieval layer. [Palace organization](https://mempalaceofficial.com/concepts/the-palace.html)

The pinned release defaults to **Chroma**. It also includes Qdrant, Milvus, PostgreSQL/pgvector and SQLite/Rust exact-vector backends. Choosing another vector backend does not automatically move the temporal KG into that backend. [Pinned default configuration](https://raw.githubusercontent.com/MemPalace/mempalace/v3.10.0/mempalace/config.py), [pinned backend implementations](https://raw.githubusercontent.com/MemPalace/mempalace/v3.10.0/mempalace/backends/__init__.py)

The actual KG is stored in SQLite `entities` and `triples` tables. A triple has a subject, relationship, object, valid-from/valid-to times, confidence and source references. `supersede()` closes the old fact and opens its successor in one transaction at the same precise boundary. Old facts remain available for historical inspection. Source references can include the original file and drawer ID. A stored confidence value is not evidence of an automatic fuzzy decay engine or calibrated truth probability. [Pinned temporal KG implementation](https://raw.githubusercontent.com/MemPalace/mempalace/v3.10.0/mempalace/knowledge_graph.py)

The official Python API distinguishes SQLite entity-fact queries from palace navigation built from vector metadata. The source/evidence references connect facts to original memories; the agent or integration must choose appropriate graph queries and writes. **The local adapter only tests drawer retrieval, so its results cannot demonstrate MemPalace's full KG behavior.** [Python API](https://mempalaceofficial.com/reference/python-api)

## Retrieval: what happens and what does not

The tag-pinned `search_memories()` path searches drawers directly with scope filters. It fetches a wider vector candidate pool; optional `union` mode adds lexical candidates. Closet matches can boost rankings, but are not allowed to hide direct drawer hits. Results retain original text/source identity. I found no temporal KG query in this function: entity/history search is a separate interface rather than automatic graph traversal inside every drawer search. [Pinned search flow](https://raw.githubusercontent.com/MemPalace/mempalace/v3.10.0/mempalace/searcher/query.py)

Its normal hybrid reranking mixes vector similarity and a word-matching score, with defaults 0.6 and 0.4. This is an inexpensive scoring calculation, **not an LLM judging each candidate**. The ranking source breaks score ties toward more recently authored records. [Pinned ranking implementation](https://raw.githubusercontent.com/MemPalace/mempalace/v3.10.0/mempalace/searcher/ranking.py)

The project's published benchmark page reports raw LongMemEval retrieval recall of 96.6% at five results and held-out hybrid recall of 98.4%. These are publisher-reported results, not rerun here, and retrieval recall is not answer accuracy. Its own page corrects earlier metric mixing and explains why an earlier LoCoMo 100% claim was uninformative when more results were returned than sessions existed. Do not rank MemPalace versus Mem0 or Zep by incompatible headline scores. [Official benchmark methodology summary](https://mempalaceofficial.com/reference/benchmarks.html)

## Ingestion and “real time”

Mining scans files or conversation exports, splits content and stores original text with classification metadata. That is suitable for history/backfill. Re-running a directory mine for every agent message is a poor live-ingestion design inference, because it repeats scanning and may introduce writer contention. [Mining guide](https://mempalaceofficial.com/guide/mining.html)

A live agent can instead call `mempalace_add_drawer` for each meaningful event or checkpoint several memories together. Identical-content IDs provide idempotency. The checkpoint tool can report partial errors; do not assume a whole-session save is one atomic success. MCP directory mining is synchronous and a competing mine is refused with an already-running error. These interfaces enable incremental ingestion, but do not establish any guaranteed millisecond write-to-search delay. [MCP write interfaces](https://mempalaceofficial.com/reference/mcp-tools)

The documented auto-save hooks trigger periodically and before compaction. They are not proof that every agent event is immediately saved and converted into facts. The AI performs the filing; the hooks trigger it. [Auto-save hooks](https://mempalaceofficial.com/guide/hooks.html)

Automatic contradiction checking is explicitly documented as planned/experimental rather than a shipped end-to-end MCP feature. Temporal supersession primitives are real; automatic reliable contradiction understanding must not be inferred from them. [Contradiction feature status](https://mempalaceofficial.com/concepts/contradiction-detection.html)

## Shared memory and concurrency

A shared hub lets local or remote agents access the same palace. One server process owns the writer lease and serializes writes; the guidance says not to point two server processes at the same palace. Agents can use stable host:harness:project identities. This is a useful operational model for a fleet, but not proof of unlimited parallel writes. [Shared-brain architecture](https://mempalaceofficial.com/guide/shared-brain.html)

The remote deployment documentation supports HTTP, bearer tokens, TLS and networked vector storage. These authenticate access to the shared service. **Wing labels and agent identities are organizational metadata, not independently verified tenant access controls.** I did not find a documented guarantee of per-user/per-company authorization enforcement within one shared palace. A company product therefore needs an explicit isolation design and adversarial cross-user tests. [Remote/team deployment](https://mempalaceofficial.com/guide/remote-server.html)

Coordination uses a separate durable `logstream.sqlite3`: append-only task messages, acknowledgements and exact artifacts. Agents can resume with event-ID cursors, wait for matching events or receive live notifications. Coordination continues independently of vector indexing. A concluded task produces both a coordination trail and an outcome filed for future recall. This separates “tell another agent now” from “remember this later.” [Agent logstream](https://mempalaceofficial.com/concepts/agent-logstream.html)

## Lessons for our system — recommendations, not measured conclusions

1. **Keep the original event.** Connect extracted facts to it so another agent can inspect what was actually said.
2. **Separate receiving from understanding.** Acknowledge a durable receipt promptly; show when indexing and fact interpretation have completed. Never advertise unmeasured latency.
3. **Use a shared service.** Agents should not independently open local files and hope their state agrees. The service owns updates, access checks and notifications.
4. **Keep coordination independent of expensive interpretation.** A handoff should be deliverable even while semantic processing is busy.
5. **Use narrow retrieval scope and bounded evidence expansion.** Search likely memories, then follow only the relationships required to explain the result. Do not scan the whole graph for each question.
6. **Retain accepted replacements and disputes separately.** MemPalace's temporal replacement is useful, but our proposed disputed/protected memories and decision invalidation require additional policy.
7. **Measure receipt delay, searchable delay, accepted-fact delay and handoff delay separately**, including concurrency and failure cases. None of the source reading substitutes for those measurements on our hardware.

Beginner takeaway: MemPalace supplies an organized searchable archive, a separate factual timeline, and a shared agent message channel. It offers useful patterns to borrow. Our current wrapper uses only the searchable archive; it does not already give us the complete graph-based shared memory system.

This note does not change or prescribe the in-progress Kuzu-to-FalkorDB migration. It distinguishes competitor evidence from our eventual architecture decisions.
