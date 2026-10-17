# Current implementation specification

## Application and interfaces

Iron Web stores text memories in two embedded databases. Qdrant stores vectors and record payloads. Kùzu stores entities, observations and relationships. No database server or Docker container is required by the application.

`MemoryEngine` is the main Python facade. Its operations are `add`, `add_batch`, `get`, `search`, `update`, `delete`, maintenance methods, `memory_ids`, `storage_status`, `get_device_status`, and `close`. `MemoryRecord` and `MemorySearchResult` carry contents, identifiers, metadata, validity bounds, timestamps and storage/retrieval information. `MemoryToolAdapter` dispatches in-process Python calls; it has no MCP transport or protocol session.

The dashboard runs on the standard-library HTTP server at `127.0.0.1:8080` by default. It provides live search, ingestion, observed device information and recorded local evaluations. `POST /api/add` accepts a memory record; `POST /api/search` accepts search controls. `GET /api/status` reports state. `GET /api/results` and `/api/ablations` return saved records with the current evaluation protocol. `/api/competitors` declares that there is no verified current comparison. Missing results are displayed as missing results.

POST requests require a JSON object, have a one MiB body limit, and receive validation errors for malformed or unsupported fields. Cross-origin writes are rejected. The dashboard inserts saved text through DOM text nodes. The server is a local application interface; it does not provide authentication, tenant isolation or a remote deployment configuration.

## Records and ingestion

A record contains a stable `memory_id`, text, entity identifiers, creation timestamp, validity start/end, importance, memory type, and additional JSON metadata. New generated identifiers use the full UUID value. Qdrant point identifiers are deterministic UUIDv5 values derived from memory identifiers. Metadata cannot replace record identity, text, entity associations, time bounds, importance or creation time. Importance is restricted to the range zero to one. Validity start cannot exceed expiration. New unbounded validity uses the maximum signed 64-bit value; existing finite expiration values retain their meaning.

The complete input batch is validated before its first write. Batch storage commits occur per record. A later storage failure does not make the whole batch a single transaction.

Entity extraction is explicit. The default `none` policy records text and an observation without inventing a named entity. Manual entity identifiers bypass extraction. The `nim` policy uses an OpenAI-compatible NVIDIA NIM client and a disk cache, and requires `NVIDIA_API_KEY`. Extraction failures propagate. Mock extraction is confined to test fixtures. Metadata records extraction status, whether it was a fixture, and the extractor name.

Automatic entity identities derive from normalized entity type/name hashes, rather than the model's per-document sequence numbers. Relationship endpoints are remapped to those identities. Complete JSON is required; truncated responses are rejected. The versioned cache validates responses, rejects mock delegates, and migrates valid legacy responses without deleting them or reissuing the request. A corrupt entry is reported instead of silently causing a hosted retry.

`IngestionPipeline` delegates writes to the engine and supports pre-extracted records, batches and UTF-8 files. File chunks use a positive size and an overlap smaller than that size. Optional contradiction enrichment participates in the coordinated write, so enrichment failures restore the original record.

## Storage consistency

Facade operations sharing a graph store use the same lock. A write opens a native graph transaction and snapshots the affected vector records. Graph failures roll back graph changes and restore exact vector payloads/vectors. Vector compensation is checked by retrieving the restored record. An incomplete rollback is reported as incomplete.

Memory deletion uses explicit ownership, with an exact legacy observation-name rule for older records. It removes owned observations and owned entity relationships. Shared entities remain unless orphan cleanup is explicitly selected. Relationship updates retain separate intervals and provenance. Creation, replacement, update and deletion use the same coordinator. Metadata returned by the vector wrapper is copied rather than exposed as a live mutable reference.

These guarantees cover caught failures in the running process. The two stores do not share a durable crash-atomic transaction. Unexpected process termination or machine failure can still require reconciliation. Existing user databases are preserved; historical incorrect extracted content is not automatically reconstructed.

`get` reports actual store presence. If only owned graph observations remain, it returns a marked graph-only recovery record. Conflicting observation contents are reported instead of selecting an arbitrary version. Engine-owned stores close with the facade; borrowed stores retain their caller's lifecycle.

## Retrieval

Supported modes are vector, graph, hybrid, hybrid without reranking, hybrid without graph, hybrid without time filtering, and no memory. Unknown modes and invalid result limits are rejected. Result limits are one to one hundred. Optional document-ID scope filters retrieval before candidate limits; benchmark questions use their own conversation histories.

Vector retrieval uses exact embedded Qdrant search. Server-only payload indexes, HNSW settings and quantization controls are not exposed as effective local options. Query embedding uses the configured FastEmbed model; the default remains `BAAI/bge-small-en-v1.5`. Embedding batch size is passed to the model.

Graph retrieval links query text to existing entity names/identifiers and performs bounded breadth-first traversal. Seeds, one-hop nodes and two-hop nodes are included within configured bounds. Queries use parameters, including identifiers containing quotes. Observations resolve to their original memory IDs. Metadata is preserved, and repeated observations do not become repeated result records.

Hybrid retrieval gathers vector and graph candidates, applies time/scope checks, resolves explicit graph conflicts, optionally reranks, and calculates the final weighted score. Graph candidates participate before final ranking. CPU and GPU reranking process the same bounded pool. Reranking is disabled by default and initialized only when selected. The model tokenizer controls its sequence limit.

The weighted signals are semantic or reranker score, graph participation, recency, importance, entity overlap, historical relevance and contradiction penalty. Recency uses a ninety-day half-life. The score is a weighted ranking value, not a confidence probability. Relationship-strength and contrastive terms that had no active source were removed. Reciprocal-rank fusion is used only by the explicit research fusion baseline.

`auto` searches all validity periods. `now` includes facts valid at the reference timestamp, with inclusive endpoints. `historical` includes facts whose expiration is earlier than the reference time. The mode is evaluated per request. Supersession edges are directed from the older observation to the newer observation and take effect at their recorded time. Incoming edges do not label the newer record as superseded. Distinct facts are retained when they share an entity.

Updates replace an existing record. Separate memory IDs and explicit supersession edges represent separate versions of a fact. Automatic entity links are recomputed when automatically extracted content changes; manual associations remain explicit.

## Maintenance

Decay computes importance from the initial value and creation time using an actual exponential half-life. Future ages are clamped to zero. Repeated runs at the same reference time do not compound decay. The graph and vector changes share rollback protection.

Deduplication applies to identical semantic text, validity and known context. It retains distinct similar statements, different users/conversations, and individual episodes. It checks explicit conflicts before deleting anything. Canonical observations include all retained entity associations, while provenance retains original record payloads and observations. Previews report proposed counts without committing changes.

Consolidation selects explicitly episodic records in a time window. It requires an extractor supporting skill extraction and validates the returned skill fields. It does not synthesize generic skills when extraction is unavailable or fails. Source IDs determine stable skill identity alongside its contents, and repeated unchanged runs do not add another copy. Stored skills have graph observations and provenance. Previews do not invoke hosted extraction or initialize models. An empty maintenance task list performs no work.

## Configuration and models

Configuration is validated against effective settings with unknown fields rejected. The default file is resolved from the project, and configured relative paths are anchored to the configuration location. Explicit constructor store paths are recorded as the paths actually used. GPU preference follows explicit argument, then `USE_GPU`, then configuration. The default application profile selects CPU execution.

Public package imports do not import the model or database clients. Models initialize when an operation requires them. CUDA DLL preparation is explicit to GPU initialization. Device reporting uses available and live providers and NVIDIA memory telemetry when available. Reported profile targets do not enforce a VRAM allocation ceiling. Uninitialized components are reported as uninitialized; SDK provider information that cannot be inspected is reported as unknown.

Dependency profiles separate storage, CPU models, GPU models, hosted extraction, development tools and optional SDK research. CPU and GPU ONNX distributions are intended for separate environments. The existing installed environment is preserved. Real model files, external services and hardware can introduce failures beyond the offline control-flow tests.

## Evaluation and research

The shared runner performs ingestion, scoped retrieval, first-context-line answer generation and scoring. Retrieval metrics use exact document IDs. Duplicate IDs consume positions and cannot earn repeated credit. Empty evidence is unscored in evaluation, and direct metric helpers return zero. Dates are parsed in UTC, including actual source release formats. LoCoMo category labels and evidence-session mapping follow the local upstream reference.

Non-smoke runs require complete selected context/evidence and an isolated corpus. Mock extraction is rejected outside labelled smoke tests. Results bind to source, input and configuration fingerprints. Resume checks compatibility, includes saved records in the summary, retries failed examples, and rejects malformed checkpoints. Failures, missing evidence, dates and scoring denominators remain visible.

Slices are versioned, hash-checked and cannot overwrite existing versions. Selecting a fraction of questions retains their complete conversation histories; unscoped derived data retains its corpus. Historical slices are preserved.

Project-owned research mechanisms are named `entity_neighborhood`, `dense_lexical_fusion` and `temporal_room`. They are not third-party SDK implementations. Optional genuine Mem0, Zep and MemPalace adapters are separate and use the shared local runner with complete-context cohorts. External SDK errors propagate, identifiers are mapped explicitly, and unknown scores/provider state are not invented. These local metrics do not constitute official benchmark scoring or a verified product comparison.

Original datasets, provenance, official evaluator references, research papers, credentials, active stores and genuine extraction caches are preserved. Historical output and unused checkouts are organized in recoverable archives with integrity records.
