# Iron Web — Prioritized Cleanup Plan

**Historical review:** This document describes the pre-cleanup baseline, Git commit `724c551`. See [current implementation](../docs/specification.md) and [applied cleanup report](cleanup_implementation_report.md) for the updated behavior.

**Date:** 12 October 2026  
**Status:** Proposed plan; application code and existing research records have not been changed.

## What this plan aims to achieve

Keep the memory application understandable and dependable: it should save information safely, find the right information, show its actual capabilities, and produce results that can be checked. The proposed cleanup removes broken behavior and duplicate work while retaining useful memory search, graph relationships, time filtering, optional acceleration, and research evidence.

Some entries mean deleting unused code. Others mean replacing incorrect behavior before removing the old implementation. Experimental features and historical research files should be moved out of the everyday application rather than discarded merely because they are not currently connected.

## Review basis

The review reassessed all 69 project source files, comprising 15,752 physical lines and 497 Python declarations. A fresh structural scan read and parsed the Python sources, checked imports and references, compared duplicate implementations, and inventoried the workspace. All original application source hashes matched the preceding specification review. That earlier full source review remains applicable; this pass concentrated on removal decisions, callers, architectural boundaries, and additional failure checks.

The review also assessed the current settings, requirements, project plans, documentation, saved evaluation reports, and directory contents. The 13 documentation files contain 7,471 lines, including many example implementations. Third-party checkouts and installed packages were inventoried and checked for their relationship to the application. Their independent implementations were not individually audited line by line, and they are not treated as Iron Web code.

Additional checks used deterministic sample embeddings and temporary databases. They exercised actual storage and application control flow without invoking a hosted model or modifying existing databases. These checks establish specific correctness issues, not model quality or performance results.

Evidence:

- [Fresh structural and storage audit](D:/Opencode_/reserchpaper/report/cleanup_audit_evidence.json).
- [New isolated check results](D:/Opencode_/reserchpaper/report/cleanup_probe_results.json).
- [Earlier implementation specification](D:/Opencode_/reserchpaper/report/full_specification_report.md).
- [Complete source and interface reference](D:/Opencode_/reserchpaper/report/source_reference.md).
- [File-by-file cleanup decisions](D:/Opencode_/reserchpaper/report/cleanup_file_review.md).

Priority is based on the effect on saved information and trustworthy results, followed by maintainability and storage tidiness. It is not ordered by the size of the files. Implementation dependencies are addressed separately below.

## Plain-language synopsis, highest priority first

| Order | Proposed removal | Short explanation |
|---:|---|---|
| 1 | Unsafe edits and deletions | Remove the behavior that can erase the wrong memory or leave different versions of the same memory in different places. |
| 2 | Risky merging and made-up summaries | Remove cleanup steps that throw away information before its replacement is complete, and generic summaries that are presented as learned knowledge. |
| 3 | Silent use of sample information | Remove the automatic switch to sample extraction when real extraction is unavailable. The application should say what it actually used. |
| 4 | Input handling that skips or gets stuck | Remove the paths that silently ignore part of a batch or repeatedly process the end of a file. |
| 5 | Inconsistent treatment of old information | Remove rules that confuse current and past facts, or treat both sides of a change as outdated. |
| 6 | Unreliable scoring and restart behavior | Remove scoring that rewards repeated information or missing evidence, and restarts that lose already completed results. |
| 7 | Unsupported performance and feature claims | Remove fixed scores and claims of capabilities that the running application has not established. |
| 8 | Checks that cannot prove their promises | Replace tests that rely on unavailable models or merely confirm that something was returned. They should check the behavior users depend on. |
| 9 | Hidden failures and unchecked input | Remove the handling that makes a broken operation look like an empty result or a success, and the routes that accept invalid information without a clear response. |
| 10 | Duplicate ways to save memories | Keep one dependable saving process and remove the competing copies after their useful functions have been transferred. |
| 11 | Duplicate experiment and scoring systems | Keep one shared way to run and score experiments, so the same question does not receive different treatment in different scripts. |
| 12 | Settings that have no effect | Remove switches that appear to control the system but are ignored. Connect the settings that users actually need. |
| 13 | Ranking extras that do no useful work | Remove calculations and score ingredients that do not influence the normal search result. Keep experimental alternatives separate. |
| 14 | Search shortcuts that discard evidence | Replace the steps that discard useful matches before all relevant information has been considered. |
| 15 | Unnecessary model loading | Remove the need to load a large model for an operation that will not use it. |
| 16 | Misleading unfinished agent integration | Remove the claim that the current helper is a complete agent connection, and replace its broken maintenance command. |
| 17 | Imitation products in the normal application | Move the project’s simplified comparison models into the research area and label them clearly. |
| 18 | Unfinished experiments in the everyday code | Move tuning and experimental search branches out of the main application, preserving them as research work. |
| 19 | Redundant one-off helper scripts | Combine repeated setup and checking scripts, while preserving useful diagnostics. |
| 20 | Obsolete instructions presented as current | Archive old plans and example implementations, and keep one set of instructions matching the application. |
| 21 | Unrelated or compulsory optional packages | Remove packages the application does not use and make specialist hardware and research packages optional. |
| 22 | Unused internal plumbing | Remove unused imports, duplicate names, unused fields, and outdated fallback paths after checking their callers. |
| 23 | Unrelated third-party code in the working project | Retain the benchmark inputs and their origin records; archive external application code that Iron Web does not run. |
| 24 | Disposable files and scattered outputs | Remove recreatable scratch files and caches, and organize old results so they cannot be mistaken for current evidence. |

## Detailed removal decisions

### 1. Unsafe edits and deletions — replace before removal

**Why it is first:** This affects stored user information.

Fresh checks confirmed that deleting memory `a` also deleted the graph observation belonging to `a_b`, while `a_b` remained in vector storage. A replacement write that failed during its graph step removed the previous vector and graph records. An update that failed on its second graph observation reported that it had rolled back, although one graph observation still contained the new text and the vector metadata still contained the new note. Metadata could also override the stored text and memory identifier while the graph retained the original text.

**Remove:** Prefix-based ownership guesses, unrestricted merging of metadata into reserved fields, unconditional deletion as a replacement-write rollback, automatic true storage flags, and reporting completed rollback without checking what was restored.

**Keep / replace with:** Explicit memory ownership on observations, protected record fields, snapshots of the prior state, exact deletion, and a result that distinguishes complete success, restored failure, and incomplete recovery. Preserve source/provenance fields during updates. Existing data needs a migration or reconciliation process before relying on the new ownership field.

**Affected files:** `memory/engine.py`, `memory/vector_store/qdrant_store.py`, `memory/graph/kuzu_store.py`, `memory/models.py`.

**Completion check:** A neighboring ID survives deletion; failed create/replace/update leaves previous content, metadata, graph links, and source fields intact or explicitly reports incomplete recovery. Graph-derived results can be read and changed using the same user-facing memory ID.

### 2. Risky merging and made-up summaries — replace and restrict

The current duplicate merge combines entity names in the vector record, deletes the duplicate, and does not create all the replacement graph associations. This was reproduced. Consolidation can manufacture a generic workflow statement when real skill extraction yields nothing, and repeatedly generates new skill IDs. It selects records by date without ensuring they are the intended source type.

**Remove:** Delete-before-complete merge behavior, empty task-list behavior that unexpectedly runs every task, generic fallback skills stored as learned facts, repeat synthesis without a stable identity, and source-field resets in maintenance writes.

**Keep / replace with:** Previewable, explicit maintenance tasks; complete canonical records and graph links before duplicate removal; source-linked consolidation that can report no pattern found; stable synthesis identity; rollback/recovery behavior. Dry run should clearly distinguish local preview from an optional remote extraction request.

**Affected files:** `memory/maintenance/maintenance.py`, engine maintenance methods, associated tests.

**Completion check:** Merged records remain findable through every preserved entity; contradictory and disjoint facts survive; repeated consolidation does not accumulate the same result; an empty task list performs no task.

### 3. Silent use of sample information — remove from ordinary and research operation

The engine automatically selects the mock extractor when a credential is missing or initialization fails. Its numbered entity IDs are reused between documents. A fresh check showed the graph entity initially called Python being renamed React after a second document. The real-model prompt also uses numbered example IDs without a global identity policy.

**Remove:** Automatic mock selection in normal/research modes, shared placeholder entities treated as extracted knowledge, and extraction failure converted into an apparently ordinary completed graph ingestion. Remove fixed mock judge scores from real evaluation paths.

**Keep / replace with:** Explicit test/demo fixtures; explicit extraction status; either a declared vector-only ingestion or a clear failure when graph extraction is required. Resolve entity identities using a defined policy rather than treating each document’s temporary labels as global names. Store extraction provenance.

**Affected files:** `memory/engine.py`, extractor validation, mock/NIM/cache modules, benchmark entry points.

**Completion check:** A real-extraction experiment cannot silently use a fixture; two unrelated entities cannot overwrite each other through reused temporary IDs; missing extraction is visible in the record and run summary.

### 4. Input handling that skips or gets stuck — replace

The engine and separate ingestion pipeline use zip over batch arguments, truncating work when companion lists have different lengths. A fresh check submitted two memories with one metadata entry and stored only one. The earlier bounded file-chunk check demonstrated repetition at the end of a short file with the default overlap.

**Remove:** Silent truncation, the nonterminating chunk progression, and any function that accepts contradictory chunk/overlap values without validation. Replace permissive truncated-JSON salvage that can collect objects beyond the intended array with bounded parsing or a declared extraction failure.

**Keep / replace with:** Explicit length validation or documented per-item defaults, a terminating file splitter, and per-input success/failure records. Preserve file ingestion and supplied-extraction capability when migrating to one saving path.

**Affected files:** `memory/engine.py`, `memory/ingestion/pipeline.py`, `memory/ingestion/nim_extractor.py`.

**Completion check:** Every submitted input has an outcome; empty, short, overlapping, and malformed inputs terminate or return a clear validation error.

### 5. Inconsistent treatment of old information — replace

A fresh check showed an expired fact returned by a current-time vector query when an earlier query used automatic mode. This happens because the cached vector retriever keeps a time-filter setting from its first query. Graph expansion applies different time rules; a later-added graph record can bypass the earlier explicit filter. Supersession lookup reads changes without direction, and the separate current-version resolver expects fields the store does not return.

**Remove:** First-query settings retained for later requests, duplicated conflicting time rules, directionless old/new treatment, and the current incompatible resolver. Remove the finite 2038 timestamp’s description as forever. Remove assertions of complete transaction-time history when updates overwrite records.

**Keep / replace with:** One documented current/past/at-time rule applied to every final candidate, explicit old-to-new transitions and change times, and a supported unbounded validity representation. Keep timestamp and validity as distinct concepts. True assertion-time version history should be a separate feature decision rather than added merely to justify an old label.

**Affected files:** Vector/hybrid/temporal retrieval, graph conflict methods, detector/resolver, public/extraction models.

**Completion check:** Search history does not affect a later query; both vector and graph results satisfy its requested time; only the old endpoint is marked outdated at the appropriate time.

### 6. Unreliable scoring and restart behavior — replace; withdraw affected claims

Fresh checks showed a fully resumed experiment producing an empty evaluation summary and duplicate retrieval of one document producing NDCG above one. Empty evidence gives recall one. Earlier slice checks found questions with evidence outside the corpus and zero/missing timestamps in every exported document.

**Remove:** Aggregate-only-new-results logic, successful-result treatment of missing evidence, repeated-document credit at document-level scoring, question-independent corpus slicing without coverage checks, silent failed queries scored as normal misses, and unqualified official/full-hybrid labels on incompatible experiment paths.

**Keep / replace with:** Immutable per-example records aggregated as a whole; explicit failures and missing-evidence categories; document/session/observation granularity chosen before scoring; evidence-complete manifests or clearly declared incomplete-corpus tests; parsed timestamps with defined timezone handling. Do not infer timestamps from zero by substituting the run time.

The upstream project adapter initially writes only vectors and requires a separate graph-population script. Retire that two-step arrangement for runs labeled hybrid. Retain an explicitly named vector-plus-reranker experiment if useful. Upstream product adapters must retain their actual configured protocol in the result, including Mem0 infer=False and Zep episode search.

**Affected files:** Harness runner/base/evaluator/adapters, official corpora loaders, slice exporter/freezer, upstream runner/populator.

**Completion check:** Resume retains the same totals; document-level metrics stay within their defined bounds; corpus/evidence/provider/extractor status is visible; configuration changes cannot append silently to an old run.

### 7. Unsupported performance and feature claims — delete from current presentation

Benchmark tables are typed into the dashboard; the JavaScript does not update them from saved reports. The comparison module returns fixed product descriptions/scores. The HTTP ablation fallback creates results that were not read from an actual ablation run. Standard report templates include predetermined gains and architecture claims.

**Remove:** Hardcoded benchmark numbers, default numbers substituted for absent results, predetermined winning-method highlighting, unsupported third-party capability assertions, unconditional GPU-active/100%-local/complete-MCP labels, and claims that a displayed memory buffer is reserved by the application.

**Keep / replace with:** Traceable values loaded from identified runs; absent results displayed as unavailable; model/provider/extraction status from actual execution; clearly marked historical reports. Keep real latency traces and result records.

**Affected files:** `web/index.html`, `web/app.js`, `server.py`, `memory/evaluation/baselines_comparison.py`, `memory/evaluation/report_generator.py`, current docs.

**Completion check:** Every displayed research number points to a run and protocol; empty report directories produce no invented values; GPU and local/cloud labels reflect the selected operation.

### 8. Checks that cannot prove their promises — replace, preserving useful coverage

The prior full offline attempt had 10 passes and 31 failures before most relevant application assertions: model files were unavailable, and the alternate interpreter initially lacked the Windows package search path. The supplied environment launcher references a previous user’s missing Python installation.

Several tests only check a nonempty result. The graph-only test has no constructed relation path. The supersession test expires the old record and never checks its supersession flag, so a working interval filter could satisfy it even with broken conflict handling. Resume testing checks JSONL length but not summary preservation.

**Remove:** Mandatory downloads/GPU/cloud credentials from ordinary correctness tests, checks that can pass without exercising the named mechanism, hardcoded provider expectations, and diagnostic scripts that catch all errors but appear to succeed.

**Keep / replace with:** Small explicit embedding/extraction/reranking fixtures for control-flow tests; real embedded database tests; separate optional neural/GPU/cloud integration tests; assertions proving graph participation, conflict direction, whole-state recovery, valid score ranges, and resume totals. Keep the directed-edge count regression tests.

**Completion check:** The essential suite runs offline in a recreated environment and exposes the newly demonstrated failures before they are repaired. Neural quality tests retain real inference and their explicit prerequisites.

### 9. Hidden failures and unchecked input — replace

The scan found 28 empty exception handlers across the reviewed sources. Some handle optional features or an absent hardware utility; others hide configuration, graph, or recovery failure. Ordinary metadata and request values are inconsistently validated. The frontend escapes content but inserts identifiers, entity strings, and error strings into HTML without equivalent handling.

**Remove:** Unknown retrieval modes silently becoming hybrid, malformed configuration silently becoming defaults, invalid JSON silently becoming an empty request, unchecked top-k/types/time bounds, swallowed consistency failures, and unsafe HTML interpolation. Remove mixed-identity traversal string construction after parameterized queries exist.

**Keep / replace with:** Shared validated input contracts, explicit error categories, text-safe UI rendering, and bounded request handling. Keep narrowly defined fallbacks for unavailable optional hardware and already-existing schema objects, while making their actual state observable. Do not remove every exception handler indiscriminately.

**Affected files:** Engine/configuration/storage/extraction, HTTP server, tool adapter, browser script.

**Completion check:** Invalid input is rejected clearly; a broken graph is distinguishable from no graph matches; normal text containing punctuation is stored and displayed safely; rollback failure is observable.

### 10. Duplicate ways to save memories — consolidate, then delete the older path

`IngestionPipeline.ingest_text()` and `ingest_text_with_extraction()` have 99.36% similarity in their normalized executable bodies. They also duplicate most of the engine's save process while applying different error handling and provenance.

**Remove:** Independent vector/graph write orchestration in the separate pipeline, after transferring file loading, chunking, supplied extraction, and optional conflict detection into the canonical saving service. Remove duplicated method bodies and inconsistent exports.

**Keep / replace with:** One ingestion implementation called by the engine, dashboard, benchmarks, and file loader. The public facade can remain small and stable; file reading does not need to become another full storage implementation.

**Affected files:** `memory/engine.py`, `memory/ingestion/pipeline.py`, ingestion/package exports, upstream direct-write path.

**Completion check:** All ingestion entry points create equivalent record identities, fields, graph associations, and failure outcomes. Migrate known callers before deleting the public pipeline class; unknown external consumers require a documented compatibility transition.

### 11. Duplicate experiment and scoring systems — consolidate

The repository contains older scenario/baseline/metric runners, the newer harness, multiple phase-script wrappers, and a standalone upstream loop. Four scoring function bodies are exact AST duplicates between the harness and upstream script; other rules are similar but differ. Baseline letters have different meanings across files.

**Remove:** Independent metric copies, older baseline factories and dataset loaders after callers migrate, phase-specific copies of orchestration, and contradictory baseline letter names. Replace duplicated upstream metric functions with the same versioned scoring implementation used by the harness.

**Keep / replace with:** One dataset contract, one scoring package, one run-record format, and one experiment registry. Local engine and upstream products should remain separate adapters because their operations differ. Lightweight CLI profiles can replace repeated full runner implementations.

**Affected files:** `memory/evaluation/baselines.py`, `metrics.py`, `official_corpora.py`, `scenarios.py`, `harness/`, phase/comparison/upstream scripts.

**Completion check:** Recomputing a result through any retained entry point gives the same metric definitions and run provenance. Historical metric versions remain identifiable rather than silently rewritten.

### 12. Settings that have no effect — connect useful settings and delete the rest

The YAML declares many features the engine never reads: maintenance intervals, tracing, logging rotation, some model/provider settings, ranking weights, and contrastive enablement. Its credential name differs from the code's name. Connecting its negative contradiction weight without changing sign conventions would reward contradictions rather than penalize them.

**Remove:** Unconnected options and duplicate defaults. Remove declared automatic schedules and tracing until implemented. Remove incompatible prompt shapes and unused answerer/judge settings from the ordinary memory-engine configuration.

**Keep / replace with:** One validated settings object for paths, model/device choice, retrieval limits/weights, extraction/cache policy, and manual maintenance parameters. Define positive penalty magnitude and consistent subtraction. Let experiment profiles carry their own answer-generation/judging settings.

**Affected files:** `config.yaml`, constructors, retrieval configuration/scoring, maintenance helpers, entry points.

**Completion check:** Each supported setting has an observable effect; unsupported settings are rejected rather than accepted silently; command-line, environment, and file precedence is documented once.

### 13. Ranking extras that do no useful work — remove from the normal path

Hybrid calculates RRF after ranking but does not use it to select the final results. Relationship-strength and contrastive-margin score terms have no normal-path producer. Several method parameters carry context that is not consumed. The main engine always disables contrastive candidates despite enabled settings.

**Remove:** Trace-only RRF work from ordinary search, unpopulated score terms, unused context parameters, and contradictory normal-mode contrastive switches. Retain a separate, explicitly configured RRF/contrastive experiment if the research question requires it.

**Keep / replace with:** One documented scoring rule built from signals actually supplied, with correctly named recency time constant and consistent missing-time treatment. Existing evidence does not justify deleting neural reranking or graph search entirely.

**Affected files:** `memory/retrieval/hybrid.py`, `memory/ranking/scorer.py`, contrastive module and experiment profiles.

**Completion check:** Every score term is exercised; disabling one term affects only that term; traces explain the selection rule; required legacy research records keep their previous metric/scoring version.

### 14. Search shortcuts that discard evidence — simplify and replace

Graph results are appended after reranking. On temporal/conflict routes, the combined list is sliced to 15 before final scoring, so newly added graph evidence can be discarded. Explicit temporal filtering runs before those additions. Graph-only search is gated by the same router as hybrid and can return nothing for a simple query. A two-hop expansion retrieves exact two-hop endpoints rather than the complete one-and-two-hop neighborhood.

**Remove:** Graph-only dependence on a hybrid-stage shortcut, post-filter additions without final validity checking, accidental pre-scoring discards, and unordered seed truncation. Remove the broken two-hop relation-filter alias.

**Keep / replace with:** A clear candidate lifecycle: collect permitted evidence, map it to canonical records, apply validity, score, optionally rerank a declared budget, and return results. Keep bounded traversal and adaptive routing where they preserve the requested mode's behavior. Candidate count and final top-k are separate limits; disabled graph experiments should not secretly rely on graph-derived signals.

**Completion check:** A relevant graph match can reach the final set; explicit mode/time rules are honored; results and traces remain deterministic with fixed data; speed/quality tradeoffs are measured after correctness is restored.

### 15. Unnecessary model loading — remove unused initialization

Creating ordinary stores can load the embedder. Engine hybrid-related branches access the reranker even when their mode disables it. Package exports eagerly import most of the implementation. Device DLL registration is repeated during import. The status endpoint also queries memory telemetry twice.

**Remove:** Model loads for get/delete/no-rerank/graph-only operations that do not require inference, repeated setup work, duplicate telemetry calls, and import-time requirements unrelated to the selected operation.

**Keep / replace with:** Lazy model initialization at the first operation that needs it, one process-level device setup, and one telemetry sample per response. Reuse initialized components with explicit ownership. Preserve supported GPU acceleration and warm-process performance.

**Affected files:** Engine, package exports, vector store, embedding/reranking/device wrappers, HTTP status.

**Completion check:** Disabled components are not instantiated; basic storage checks run without model files; selected acceleration is reported from the live session rather than assumed.

### 16. Misleading unfinished agent integration — correct the boundary

The module named MCP server is a Python tool catalog/dispatcher. It has no MCP transport or protocol initialization. Its maintenance tool passes arguments the engine does not accept.

**Remove:** Complete-MCP/JSON-RPC server assertions from the current helper, its incompatible maintenance call, and duplicate unvalidated tool declarations. Do not build another integration framework merely to retain a label.

**Keep / replace with:** A tested Python tool adapter with the correct inputs and engine calls. If a real MCP connection is part of the intended product, add it as a separate optional adapter around that dispatcher using a documented supported transport.

**Affected files:** `memory/mcp_server.py`, tool documentation and dashboard tab.

**Completion check:** All advertised tool calls work through the existing adapter; documentation distinguishes in-process use from an actual protocol endpoint; external MCP integration is claimed only after an interoperability test.

### 17. Imitation products in the normal application — relocate and rename

The internal Mem0/Zep/MemPalace classes are simplified project comparison mechanisms. They share the application's stores. They are different from the real upstream SDK adapters and some are described as doing more than their implementation does.

**Remove:** Product-branded comparison modes from the everyday engine search interface and competitor capability claims from its display. Migrate these modes to named research adapters such as dense-plus-keyword and time-bucket retrieval.

**Keep / replace with:** The underlying mechanisms when they remain useful experiments, their previous results clearly labeled as project baselines, and separate upstream product runs with exact configurations. Retain RRF for the dense-plus-keyword experiment if used there.

**Affected files:** `memory/retrieval/competitors.py`, engine dispatch, comparator scripts/tests, hardcoded comparison module.

**Completion check:** A user cannot mistake a local imitation mode for an installed product. Old experiment labels are preserved as historical metadata, not rewritten into upstream results.

### 18. Unfinished experiments in everyday code — separate, then prune

The older ablation/sweep CLIs parse arguments and print setup instructions without executing them. Config serialization uses a placeholder object. Some variants cannot disable the named behavior fully. Tuning evaluates and selects weights on the same scenarios and does not install them into the engine.

**Remove:** No-op CLI entry points, placeholder configuration recording, duplicate baseline subclasses, and claims that these branches are completed everyday features. Move Optuna, sweeps, bootstrapping, contrastive sampling, and scan-all conflict experiments under the research boundary.

**Keep / replace with:** Explicit experiment definitions using the shared runner, serialized actual settings, declared datasets/seeds, and a separation between tuning and evaluation. Retain the research hypothesis and negative results; do not delete an experiment simply because it is currently unconnected.

**Affected files:** Ablation/sweep/scenario modules, baseline subclasses, contrastive code, broad extractor/judge contracts.

**Completion check:** Every advertised experiment entry point either runs the selected experiment or is labeled a library helper; configurations describe actual executed stages; research packages are optional for ordinary use.

### 19. Redundant one-off helper scripts — combine

The project has separate import, GPU-path, latency, mode-audit, credential-probe, graph-population, and screenshot scripts. Some repeatedly perform the same environment preparation; some use fixed paths. Screenshot capture saves a new memory as part of its checks.

**Remove:** `test_imports.py` and `test_gpu_paths.py` as standalone proof-of-success scripts once their useful checks are in the test/diagnostic entry point. Fold mode-audit/latency/path-selection into shared diagnostics. Retire the separate graph populator once hybrid ingestion is coherent. Remove the optional Excel generation hook referencing a nonexistent script.

**Keep / replace with:** Useful diagnostics and explicit opt-in hosted/GPU/browser checks. Keep a thin upstream MemPalace launcher if required for the installed Windows package. A screenshot tool should use a disposable demonstration store or declare its mutation explicitly.

**Completion check:** A failing check returns a failing exit status, paths can be selected, and routine verification does not silently alter user memories or require cloud access.

### 20. Obsolete instructions presented as current — archive and replace

The phase documents contain long example implementations, expected gains, missing-file commands, and old architecture descriptions. Root plans disagree with current GPU defaults and maintenance behavior. Earlier generated reports include fixed research conclusions.

**Remove:** Superseded planning content from current onboarding; completion labels without supporting checks; claims of implemented LangGraph checkpoints/LangSmith tracing; missing commands; sample research results presented as findings.

**Keep / replace with:** One current overview, one factual architecture/specification, one operating guide, and one reproducibility guide. Archive phase 1–11 documents, old plans, `UPDATES_REQUIRED.md`, and generated research templates as historical material. Retain source papers, real results, and the new review reports.

**Completion check:** Following current instructions uses existing entry points; each capability description matches the code; historical material is unmistakably historical and has intact provenance.

### 21. Unrelated or compulsory optional packages — remove and separate

Neo4j is declared but only Kuzu is supported. The root environment requires GPU/TensorRT packages for ordinary use, while optional experiment packages are absent from that list. Transitive library pins and environment packages need reconciliation with the supported installation profile.

**Remove:** Neo4j from the application's active dependencies, mandatory specialist hardware packages from the ordinary profile, stale package comments, and unmaintained hand-pins that duplicate a resolved lock without a reason. Audit development-only test plugins before retaining them.

**Keep / replace with:** Minimal core, optional GPU/TensorRT, development, and research/upstream profiles, each with a reproducible resolution. Retain packages needed transitively even if the application does not import them. Recreate the environment using a valid interpreter and verify it before retiring the existing `.venv`.

No broad version upgrades, database replacements, or removal of the Windows DLL loader are justified solely by cleanup.

**Completion check:** Core storage/tests run without GPU packages; the selected acceleration and experiment profiles work independently; a clean installation produces the declared environment.

### 22. Unused internal plumbing — delete after caller migration

Static references identify unused import candidates and state such as `_hybrid_retriever`, an unused HybridRetriever sub-retriever, loader imports with no calls, scorer context arguments, and the unused factory embedding batch argument. `SearchFilter` and `MemoryMetadata` are exported but not connected to engine inputs. Legacy names and fallback conflict implementations duplicate behavior and differ in ID handling.

**Remove:** Confirmed unused imports and private fields; duplicated result serializers; unused model/query fields after API migration; redundant baseline aliases; legacy conflict fallbacks after one correct path has coverage. Remove local-Qdrant payload-index calls that have no effect in this fixed local backend and graph index calls that are unsupported or target nonexistent fields, after backend behavior is explicitly checked.

**Keep / replace with:** Public data contracts that are actually used, one result converter, and one correct conflict lookup. Treat exported names as potential external interfaces, even when local callers are absent. Rename misleading duration/half-life/device fields instead of removing useful measured data.

**Completion check:** Imports and tests pass; retained callers use a single interface; no external compatibility assumption is presented as proven; actual backend query behavior remains equivalent or intentionally corrected.

### 23. Unrelated third-party code in the working project — archive selectively

The checked-out Letta application alone contains 878 Python files. Root application imports do not use that server code; the DMR conversion reads the separately downloaded MSC data. LoCoMo and LongMemEval checkouts provide required data, provenance, and possibly useful official evaluation reference material.

**Remove from the active working tree:** The unused Letta application checkout after preserving required origin/version/license records. For LoCoMo/LongMemEval, keep a reproducible dataset acquisition route and required input files; move unrelated model-training/generation/demo code into an external reference archive.

**Keep / replace with:** Exact datasets, hashes, citations, licenses, upstream revision records, and any official evaluator selected for validation. Do not treat third-party code as defective because it is outside the application's purpose. Preserve recoverable copies before removal and check whether any external user workflow relies on them.

**Completion check:** All selected adapters and input verification work from the retained data; official reference code can be recovered; no unique dataset/provenance is lost.

### 24. Disposable files and scattered outputs — inventory, archive, then remove

Measured apparent file sizes, excluding Git internals: data about 5.00 GB, `.venv` about 3.00 GB, datasets about 325 MB. This is not a promised deletion saving; much of it is useful state. The TensorRT cache is about 1.12 GB, internal competitor experiment stores about 2.53 GB, and upstream data about 1.15 GB. Non-environment bytecode caches contain 76 files totaling about 0.92 MB.

**Remove when their disposability is established:** Bytecode and pytest caches; named probe stores and scratch logs with no unique results; duplicate generated tables whose original records and generator are retained; obsolete model engines after a compatible replacement exists. The apparent scratch files include `batch_conflict_probe*.db`, `gpu_probe_*`, `qdrant_gate4_probe`, and Kuzu `test_fresh*.db`.

**Archive and organize:** Phase/older experiment stores and historical outputs spread across `results/`, `metrics/`, and `data/results/`. Tie retained run records to manifests rather than selecting current evidence by modification time. Remove redundant stores only after verifying that inputs, extraction state, settings, and reconstruction steps exist.

**Preserve:** Active user Qdrant/Kuzu databases, `.env`, original datasets, freeze/provenance manifests, real NIM extraction caches, unique raw evaluation records, research papers, and needed model cache files. A real extraction cache avoids repeating remote calls and is not ordinary disposable clutter.

**Completion check:** Every removed item has a proven recovery/recreation route or contains no unique information; ordinary operation and selected result reproduction still work; current and historical outputs cannot be confused.

## Architecture decisions after cleanup

| Existing decision | Proposed decision | User-facing reason |
|---|---|---|
| Embedded vector and graph stores | Keep, with exact shared record ownership | Both serve useful purposes; replacing databases would add work without resolving the demonstrated bugs. |
| Unified engine facade | Keep; make one ingestion path its underlying implementation | Users should get the same saving behavior through every entry point. |
| Per-entity observations duplicating full text | Retain compatibility during migration; make memory identity explicit and evaluate a single-record representation separately | Multiple views of one memory should not become multiple unrelated memories. |
| Hosted structured extraction | Keep as an explicit choice; preserve cached real output and extraction status | Users need to know when information is interpreted remotely or stored without interpretation. |
| Automatic mock extraction | Restrict to explicit tests/demos | Sample interpretation should not become ordinary user memory or benchmark evidence. |
| Adaptive graph search | Keep when mode/time rules are respected | Extra relationship work can be useful, but must not silently change a requested search mode. |
| Weighted ranking plus optional neural reranking | Keep one measured, documented selection path | Search decisions should be understandable and adjustable. |
| RRF and contrastive alternatives | Research-only until explicitly connected and measured | Preserve the experiment without presenting it as the normal behavior. |
| GPU/TensorRT acceleration | Optional profiles, lazy initialization, live provider reporting | Acceleration remains available without being a prerequisite for every operation. |
| Manual maintenance | Keep manual; make tasks explicit and recoverable | The application should only reorganize information when requested and should retain the evidence behind it. |
| Python tool catalog named complete MCP server | Treat as a tool adapter; optional real MCP transport only if required | Agent connection claims should match a working connection. |
| Product-inspired baselines in engine dispatch | Research adapters with accurate mechanism names | A simplified local comparison should not look like a real third-party product. |
| Multiple phase-based evaluation frameworks | One runner/schema/metric contract with separate experiment profiles | Results should be comparable and reproducible. |
| Static research dashboard claims | Identified saved runs, live telemetry, explicit unavailable states | The screen should show evidence actually present. |
| Shared unsynchronized HTTP engine | One controlled owner of mutation and initialized resources; retain loopback scope | Concurrent requests should not race to change the same records. |
| Many competing settings and project plans | One current configuration and operating specification; archived history | There should be one answer to how the application is configured and used. |

No new orchestration framework, distributed service, agent swarm, cloud deployment, replacement database, or frontend framework is proposed by this cleanup.

## Implementation sequence and stopping conditions

### Stage A — Establish a recoverable baseline

Preserve code/configuration and identify active databases and unique research records. The root workspace currently has no Git repository, so a recoverable snapshot must not assume one exists. Record source hashes and artifact manifests; create version control or a recoverable backup before implementation. Build the offline test fixtures from item 8 and reproduce the correctness cases from items 1–6.

**Stop condition:** Baseline tests expose the demonstrated failures; records can be restored; current model-dependent failures are distinguished from application defects.

### Stage B — Correct stored-information behavior

Implement items 1–5 and the relevant validation/recovery work from item 9. Disable unsafe mutation paths while their replacements are being completed. Establish canonical IDs, complete save/update/delete behavior, explicit extraction status, safe file/batch handling, and time/conflict rules.

**Stop condition:** Identity collisions, failed writes, merges, and deletions cannot silently corrupt another record or discard prior state; every input has an outcome. Existing-store migration is reviewed against a copy.

### Stage C — Restore trustworthy evidence and presentation

Implement item 6, remove fixed claims in item 7, and align the UI/tool adapter with actual statuses. Validate the slice coverage/date parsing/metric rules before any new research run. Retain prior records with their historical labels; do not overwrite them with corrected results.

**Stop condition:** Resume and metric checks pass; no placeholder score is presented as a measurement; current interfaces have consistent inputs and errors. Model quality experiments remain separate from fixture tests.

### Stage D — Consolidate architecture and remove duplication

Implement items 10–18 and useful shared diagnostics from item 19. Migrate callers before removing their old implementations. Keep one saving path, one scoring contract, consistent configuration, optional model loading, and an isolated research area. Handle concurrency and process shutdown in the retained server.

**Stop condition:** Every retained feature has one authoritative implementation; disabling a component really disables its work; code removal does not break known callers.

### Stage E — Reduce workspace and installation clutter

Complete items 19–24. Replace current instructions, create minimal/optional install profiles, archive unrelated source and historical records, then remove proven disposable files. Restore-test the new environment before retiring the old one. Document extraction-cache/model-engine compatibility before clearing any cache.

**Stop condition:** A fresh installation can run the core offline checks and selected application workflow; every retained artifact has a purpose; deleted state has no unique unrecoverable information.

### Stage F — Revalidate optional features

Only after the preceding stages, separately validate real model, GPU/TensorRT, hosted extraction, upstream baselines, and optional agent transport in their selected profiles. Produce new run IDs with explicit configurations and complete coverage checks. Measure performance after correctness; do not carry old speed or quality claims forward automatically.

**Stop condition:** Claims for each optional feature have their own successful execution evidence and stated prerequisites.

## File-removal rules

| Disposition | Meaning |
|---|---|
| Keep and repair | Useful feature remains; faulty sections are replaced. |
| Consolidate then remove | Transfer required behavior and callers before deleting the redundant file/class. |
| Move out of core | Research/reference capability remains accessible, with optional dependencies. |
| Archive | Preserve history or unique records, remove from current documentation/runtime selection. |
| Delete after verification | Confirm no caller or unique state, then remove. |

The file-by-file appendix applies these decisions to every reviewed project source file and major artifact category. Static absence of a local reference is a removal candidate, not proof that an exported API has no external users.

## Review limitations and preserved evidence

This is a cleanup plan, not executed cleanup. The source review and new isolated checks support the listed defects. Real model/provider behavior and upstream services were not rerun, and the earlier full offline suite remains limited by unavailable models and environment setup. No claim of full neural-suite success is made.

Source files were left unchanged. Only review scripts, evidence files, and this plan were added under `report/`. Temporary diagnostic databases were created and removed by the diagnostic script. The known active data, credentials, raw research records, and earlier reports remain intact.
