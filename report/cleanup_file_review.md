# Iron Web — File-by-File Cleanup Decisions

**Historical review:** This document describes the pre-cleanup baseline, Git commit `724c551`. See [current implementation](../docs/specification.md) and [applied cleanup report](cleanup_implementation_report.md) for the updated behavior.

Review date: 12 October 2026

[Prioritized plan and plain-language explanations](D:/Opencode_/reserchpaper/report/cleanup_plan.md)

All 69 original project source files are covered below. Priority numbers refer to the plan's 24 items. Removal is proposed, not performed. Public callers must be migrated before exported interfaces are retired.

## Application, research tools, tests, and UI

| File | Lines | Decision | Priority items | Specific scope |
|---|---:|---|---|---|
| [datasets/acquire_datasets.py](D:/Opencode_/reserchpaper/datasets/acquire_datasets.py:1) | 297 | Repair and simplify | 6, 19, 23 | Keep reproducible data acquisition; remove unused requests import, hard-reset update behavior, path mismatches and unpinned download assumptions. |
| [memory/__init__.py](D:/Opencode_/reserchpaper/memory/__init__.py:1) | 63 | Keep and narrow | 10, 15, 22 | Expose the supported facade/contracts; remove eager imports and legacy aliases after callers migrate. |
| [memory/contradiction/detector.py](D:/Opencode_/reserchpaper/memory/contradiction/detector.py:1) | 398 | Keep useful detection; replace resolver | 3, 5, 18, 22 | Fix identity/direction/time handling; move scan-all experiments; remove unused threshold/branches and incompatible chain resolver. |
| [memory/device.py](D:/Opencode_/reserchpaper/memory/device.py:1) | 181 | Keep and simplify | 7, 15, 21, 22 | Retain required Windows setup and real telemetry; centralize initialization, report TensorRT accurately, remove unenforced safety claims. |
| [memory/embeddings/embedder.py](D:/Opencode_/reserchpaper/memory/embeddings/embedder.py:1) | 162 | Keep and repair | 12, 15, 21, 22 | Retain local embeddings; determine actual dimension, honor or remove provider/batch arguments, unify device selection. |
| [memory/engine.py](D:/Opencode_/reserchpaper/memory/engine.py:1) | 893 | Keep facade; replace unsafe internals | 1–5, 9–17, 22 | Canonical record identity, recoverable writes, validated requests, one ingestion path; remove duplicate serialization and comparison dispatch. |
| [memory/evaluation/ablation_runner.py](D:/Opencode_/reserchpaper/memory/evaluation/ablation_runner.py:1) | 285 | Consolidate then retire old runner | 6, 11, 18 | Transfer needed bootstrap/latency analysis; remove placeholder config serialization and no-op CLI. |
| [memory/evaluation/ablations.py](D:/Opencode_/reserchpaper/memory/evaluation/ablations.py:1) | 127 | Move to experiment registry | 11, 13, 18 | Keep component experiments; replace letter labels and variants that do not isolate the named stage. |
| [memory/evaluation/baselines.py](D:/Opencode_/reserchpaper/memory/evaluation/baselines.py:1) | 108 | Consolidate then remove | 11, 18, 22 | Older factories/loaders are superseded by adapters/registry; migrate any supported external use first. |
| [memory/evaluation/baselines_comparison.py](D:/Opencode_/reserchpaper/memory/evaluation/baselines_comparison.py:1) | 89 | Remove from runtime; archive historical text | 7, 17, 20 | Contains fixed product assertions and numbers rather than identified run records. |
| [memory/evaluation/contrastive_sweep.py](D:/Opencode_/reserchpaper/memory/evaluation/contrastive_sweep.py:1) | 488 | Move to experiments and repair | 11, 13, 18, 21 | Preserve sweeps/Optuna research; remove no-op CLI, isolate dependencies, record actual configuration and evaluation split. |
| [memory/evaluation/harness/__init__.py](D:/Opencode_/reserchpaper/memory/evaluation/harness/__init__.py:1) | 38 | Keep and narrow | 11, 15, 22 | Retain shared research contracts; reduce unnecessary eager imports and export only retained API. |
| [memory/evaluation/harness/base.py](D:/Opencode_/reserchpaper/memory/evaluation/harness/base.py:1) | 229 | Keep contracts and canonical metrics | 6, 11, 22 | Fix absent-evidence/duplicate-unit treatment; separate scoring from data contracts if needed; remove copied metric implementations elsewhere. |
| [memory/evaluation/harness/dmr_adapter.py](D:/Opencode_/reserchpaper/memory/evaluation/harness/dmr_adapter.py:1) | 91 | Keep and repair | 6, 11 | Retain MSC conversion access; verify evidence/session scope, input path and timestamps; keep adapter-specific behavior. |
| [memory/evaluation/harness/evaluator.py](D:/Opencode_/reserchpaper/memory/evaluation/harness/evaluator.py:1) | 256 | Keep and repair | 6, 8, 11 | Keep stage separation; declare generator type, corpus scope and errors; ensure time settings and summary keys follow actual examples. |
| [memory/evaluation/harness/locomo_adapter.py](D:/Opencode_/reserchpaper/memory/evaluation/harness/locomo_adapter.py:1) | 196 | Keep and repair | 6, 11 | Keep official input conversion; correct date/category handling, deduplicate evidence and respect conversation scope. |
| [memory/evaluation/harness/longmemeval_adapter.py](D:/Opencode_/reserchpaper/memory/evaluation/harness/longmemeval_adapter.py:1) | 186 | Keep and repair | 6, 11 | Keep official histories/queries; fix date parsing, evidence-complete slicing and question-specific haystack constraints where required. |
| [memory/evaluation/harness/runner.py](D:/Opencode_/reserchpaper/memory/evaluation/harness/runner.py:1) | 168 | Keep as canonical runner; repair | 6, 11 | Aggregate all persisted results, expose failures, bind resume to actual dataset/configuration, avoid reinserting unchanged documents. |
| [memory/evaluation/metrics.py](D:/Opencode_/reserchpaper/memory/evaluation/metrics.py:1) | 225 | Consolidate then remove duplicate layer | 6, 11, 18, 22 | Transfer unique AP/MAP or judge capability if required; remove differing duplicate metrics and direct-client assumptions. |
| [memory/evaluation/official_corpora.py](D:/Opencode_/reserchpaper/memory/evaluation/official_corpora.py:1) | 51 | Consolidate then remove | 6, 11 | Use canonical adapters instead of a second conversion path with empty LoCoMo evidence and different metadata. |
| [memory/evaluation/report_generator.py](D:/Opencode_/reserchpaper/memory/evaluation/report_generator.py:1) | 422 | Keep rendering only; replace fixed content | 7, 20 | Remove preset conclusions/architecture claims; generate tables from identified results; retain LaTeX only with valid escaping/conversion. |
| [memory/evaluation/scenarios.py](D:/Opencode_/reserchpaper/memory/evaluation/scenarios.py:1) | 278 | Split fixtures from actual experiments | 6, 11, 18 | Move the 12 sample scenarios to tests/demo; replace overlapping dataset loaders with adapters; retain useful scenario categories. |
| [memory/graph/__init__.py](D:/Opencode_/reserchpaper/memory/graph/__init__.py:1) | 21 | Keep minimal exports | 15, 21, 22 | Keep Kuzu; remove unsupported-backend impression and redundant factory/alias if no supported caller needs them. |
| [memory/graph/kuzu_store.py](D:/Opencode_/reserchpaper/memory/graph/kuzu_store.py:1) | 998 | Keep store; repair ownership and queries | 1, 5, 9, 14, 22 | Explicit source-memory lookup, directional conflict records, correct traversal filters, parameterized queries, actual index/migration checks. |
| [memory/ingestion/__init__.py](D:/Opencode_/reserchpaper/memory/ingestion/__init__.py:1) | 24 | Keep supported exports | 3, 10, 15, 22 | Stop exporting obsolete pipeline/mock as ordinary application tools after migration; retain explicit testing capability. |
| [memory/ingestion/cached_nim_extractor.py](D:/Opencode_/reserchpaper/memory/ingestion/cached_nim_extractor.py:1) | 92 | Keep and repair | 3, 9, 12 | Preserve real extraction cache; version prompt/schema identity, validate cache input, avoid competing temporary writes. |
| [memory/ingestion/extractor.py](D:/Opencode_/reserchpaper/memory/ingestion/extractor.py:1) | 155 | Keep validation; simplify capability contract | 3–5, 9, 18 | Remove invented generic knowledge, temporary global IDs and invalid interval repair masquerading as valid extraction; separate unrelated judging requirements. |
| [memory/ingestion/mock_nim_extractor.py](D:/Opencode_/reserchpaper/memory/ingestion/mock_nim_extractor.py:1) | 131 | Move to explicit fixtures/demo | 3, 8 | Retain deterministic testing; remove automatic production/research substitution and fixed judge scores from real paths. |
| [memory/ingestion/nim_extractor.py](D:/Opencode_/reserchpaper/memory/ingestion/nim_extractor.py:1) | 410 | Keep model adapter; repair contracts | 3, 4, 9, 12, 18 | Bound JSON parsing, explicit extraction errors, stable entity mapping and aligned skill response shape; move optional evaluation judges to research boundary. |
| [memory/ingestion/pipeline.py](D:/Opencode_/reserchpaper/memory/ingestion/pipeline.py:1) | 319 | Consolidate then remove duplicated writer | 4, 10 | Transfer file/supplied-extraction/conflict functions; repair splitter; replace duplicated save logic with the canonical ingestion service. |
| [memory/maintenance/maintenance.py](D:/Opencode_/reserchpaper/memory/maintenance/maintenance.py:1) | 595 | Keep manual maintenance; repair destructive steps | 1, 2, 5, 9, 12, 22 | Complete merge replacements, preserve source links, eliminate invented generic skills/repeated synthesis, fix explicit-task behavior and memory accumulation. |
| [memory/mcp_server.py](D:/Opencode_/reserchpaper/memory/mcp_server.py:1) | 213 | Rename/simplify tool adapter; repair | 9, 12, 16 | Keep usable Python calls, fix maintenance arguments, validate schemas; remove complete-server claim unless real transport is separately implemented. |
| [memory/models.py](D:/Opencode_/reserchpaper/memory/models.py:1) | 88 | Keep used contracts; simplify | 1, 5, 9, 22 | Validated inputs, truthful storage state, supported unbounded validity; connect or deprecate unused exported query/metadata models. |
| [memory/ranking/reranker.py](D:/Opencode_/reserchpaper/memory/ranking/reranker.py:1) | 195 | Keep optional reranker; simplify | 12–15, 21, 22 | Lazy loading, declared budget/truncation, live provider choice; remove unused pair API after caller check or implement its actual supported convention. |
| [memory/ranking/scorer.py](D:/Opencode_/reserchpaper/memory/ranking/scorer.py:1) | 234 | Keep one actual scoring contract | 5, 12, 13 | Remove unpopulated inputs/default conflicts; correct recency naming/future handling; keep RRF utility only for experiments that use it. |
| [memory/retrieval/competitors.py](D:/Opencode_/reserchpaper/memory/retrieval/competitors.py:1) | 204 | Move out of engine and rename | 7, 17 | Preserve optional project comparison mechanisms; remove product identity/capability overstatements and ordinary runtime dispatch. |
| [memory/retrieval/contrastive.py](D:/Opencode_/reserchpaper/memory/retrieval/contrastive.py:1) | 203 | Move to experiments | 13, 18, 22 | Keep research sampling if required; remove duplicate inference/search work and unused margin plumbing from normal retrieval. |
| [memory/retrieval/hybrid.py](D:/Opencode_/reserchpaper/memory/retrieval/hybrid.py:1) | 457 | Keep hybrid mechanism; simplify ordering | 1, 5, 9, 13–15, 18, 22 | Canonical candidates, final validity, declared mode behavior, graph participation, remove trace-only fusion and legacy subclasses. |
| [memory/retrieval/vector.py](D:/Opencode_/reserchpaper/memory/retrieval/vector.py:1) | 124 | Keep and consolidate shared formatting | 5, 10, 22 | Request-specific time filtering; one precomputed-vector route and result converter; retire baseline letter alias. |
| [memory/temporal/filter.py](D:/Opencode_/reserchpaper/memory/temporal/filter.py:1) | 172 | Consolidate into one temporal policy | 5, 22 | Retain useful time operations; remove unused incompatible alternative selection rules and duplicate wrappers after caller migration. |
| [memory/vector_store/qdrant_store.py](D:/Opencode_/reserchpaper/memory/vector_store/qdrant_store.py:1) | 336 | Keep storage wrapper; repair | 1, 9, 12, 15, 22 | Protect payload fields, exact outcomes, avoid unnecessary embedding loads and ineffectual local payload-index setup. |
| [scripts/audit_retrieval_modes.py](D:/Opencode_/reserchpaper/scripts/audit_retrieval_modes.py:1) | 36 | Merge into diagnostics | 17, 19 | Retain execution-path inspection; remove fixed corpus/query and obsolete product-mode coupling. |
| [scripts/build_dmr_benchmark.py](D:/Opencode_/reserchpaper/scripts/build_dmr_benchmark.py:1) | 42 | Keep data conversion; repair evidence contract | 6, 19 | Retain reproducible conversion; verify final-session evidence assignment and source revision/format. |
| [scripts/capture_screenshots.py](D:/Opencode_/reserchpaper/scripts/capture_screenshots.py:1) | 84 | Keep optional demo tooling | 7, 19, 21 | Use isolated demonstration store; validate actual content/status, make dependency optional and remove implicit user-memory mutation. |
| [scripts/export_official_20percent_slice.py](D:/Opencode_/reserchpaper/scripts/export_official_20percent_slice.py:1) | 59 | Keep manifest export; repair selection | 6, 11 | Replace disconnected document/question prefixes with explicit corpus protocol, parsed times, coverage and immutable versioning. |
| [scripts/freeze_official_slices.py](D:/Opencode_/reserchpaper/scripts/freeze_official_slices.py:1) | 71 | Keep verification; consolidate manifest utilities | 6, 11, 19 | Keep hashes; add evidence/config provenance and protection against accidentally replacing a frozen dataset. |
| [scripts/official_upstream_preflight.py](D:/Opencode_/reserchpaper/scripts/official_upstream_preflight.py:1) | 80 | Keep in research diagnostics | 6, 19, 21 | Inspect actual selected profile/input rather than treating hardcoded totals as fresh validation. |
| [scripts/populate_kuzu_longmemeval.py](D:/Opencode_/reserchpaper/scripts/populate_kuzu_longmemeval.py:1) | 70 | Retire after coherent ingestion exists | 3, 6, 10, 19 | A second graph-building step currently produces ambiguous hybrid state; preserve old run/checkpoint records before retirement. |
| [scripts/profile_hybrid_latency.py](D:/Opencode_/reserchpaper/scripts/profile_hybrid_latency.py:1) | 44 | Merge into diagnostics | 13–15, 19 | Keep repeat timing/trace, select store explicitly and distinguish warm-up/provider configuration. |
| [scripts/run_ablation_matrix_frozen.py](D:/Opencode_/reserchpaper/scripts/run_ablation_matrix_frozen.py:1) | 206 | Thin experiment profile over shared runner | 6, 11, 18 | Keep hash checks/mode matrix; eliminate duplicate orchestration and run IDs that do not capture configuration changes. |
| [scripts/run_ablations_phase7.py](D:/Opencode_/reserchpaper/scripts/run_ablations_phase7.py:1) | 192 | Consolidate then retire phase runner | 6, 11, 18 | Replace duplicated mode loop with experiment registry/profile; preserve raw history and labels. |
| [scripts/run_benchmarks_phase6.py](D:/Opencode_/reserchpaper/scripts/run_benchmarks_phase6.py:1) | 153 | Consolidate then retire phase runner | 6, 11 | Shared runner/profile replaces duplicate setup/report loop; create only selected adapters and declared clean corpus. |
| [scripts/run_competitor_benchmarks.py](D:/Opencode_/reserchpaper/scripts/run_competitor_benchmarks.py:1) | 242 | Consolidate and accurately label research | 6, 7, 11, 17, 19 | Migrate internal mechanism baselines; remove unconditional hybrid highlighting, stale limits and nonexistent Excel hook. |
| [scripts/run_mempalace_gpu.py](D:/Opencode_/reserchpaper/scripts/run_mempalace_gpu.py:1) | 47 | Keep thin optional upstream launcher | 19, 21 | Retain real Windows runtime preparation when needed; share setup with other research launchers rather than dropping the capability. |
| [scripts/run_official_upstream_benchmarks.py](D:/Opencode_/reserchpaper/scripts/run_official_upstream_benchmarks.py:1) | 726 | Split adapters from shared runner; repair | 6, 10, 11, 17, 21 | Preserve true SDK adapters; remove copied metrics, silent service failures and hidden vector-only hybrid ingestion; record exact versions/configuration. |
| [scripts/test_gpu_paths.py](D:/Opencode_/reserchpaper/scripts/test_gpu_paths.py:1) | 65 | Retire after checks migrate | 8, 19 | Move meaningful provider/init checks to optional tests; remove printed-success behavior after caught failures. |
| [scripts/test_imports.py](D:/Opencode_/reserchpaper/scripts/test_imports.py:1) | 138 | Retire after checks migrate | 8, 19 | Shared import/packaging check replaces repeated try/print blocks with no reliable failure exit. |
| [scripts/verify_gate2_nim.py](D:/Opencode_/reserchpaper/scripts/verify_gate2_nim.py:1) | 32 | Move to explicit optional diagnostics | 3, 8, 19 | Retain real hosted-extraction validation with credential protection; shared import/bootstrap instead of special direct-loader path. |
| [server.py](D:/Opencode_/reserchpaper/server.py:1) | 291 | Keep local server; repair and narrow | 7, 9, 12, 15, 16, 22 | Validated JSON/errors, controlled shared engine, truthful status/results, no placeholder metrics, one shutdown/device sample. |
| [tests/test_ablations.py](D:/Opencode_/reserchpaper/tests/test_ablations.py:1) | 114 | Keep intent; replace weak fixtures/assertions | 8, 14, 17 | Prove actual mode isolation and graph participation; move comparison tests to research and use offline fixture models. |
| [tests/test_benchmark_harness.py](D:/Opencode_/reserchpaper/tests/test_benchmark_harness.py:1) | 210 | Keep and strengthen | 6, 8 | Assert preserved resume aggregates, dataset/date/evidence rules and correct metric bounds; separate dataset-dependent tests. |
| [tests/test_hybrid_retrieval_logic.py](D:/Opencode_/reserchpaper/tests/test_hybrid_retrieval_logic.py:1) | 256 | Keep and strengthen | 1, 5, 8, 14 | Construct actual graph edges and conflicting facts; verify direction/time/flags, evidence selection and call-order independence. |
| [tests/test_kuzu_counts.py](D:/Opencode_/reserchpaper/tests/test_kuzu_counts.py:1) | 44 | Keep regression coverage | 8, 22 | Directed edge counts and cache freshness are useful; replace legacy-path-only smoke assertion after conflict lookup is unified. |
| [tests/test_maintenance.py](D:/Opencode_/reserchpaper/tests/test_maintenance.py:1) | 331 | Keep and strengthen | 2, 8 | Prove complete canonical graph links, genuine contradiction guards, retained provenance, repeat idempotency and local preview behavior. |
| [tests/test_memory_engine.py](D:/Opencode_/reserchpaper/tests/test_memory_engine.py:1) | 226 | Keep and strengthen | 1, 4, 8, 15 | Offline models; whole-state failure assertions, reserved-field protection, neighboring IDs, batch coverage and unloaded-component checks. |
| [tests/test_storage_persistence.py](D:/Opencode_/reserchpaper/tests/test_storage_persistence.py:1) | 306 | Keep core store coverage | 1, 8, 15 | Avoid incidental model loading; preserve reopen/shared-entity/count tests and extend exact ownership/delete checks. |
| [web/app.js](D:/Opencode_/reserchpaper/web/app.js:1) | 194 | Keep live interaction; repair | 7, 9, 12, 15 | Load identified results, display actual state, safe text rendering, preserve zero values and remove GPU assumptions. |
| [web/index.html](D:/Opencode_/reserchpaper/web/index.html:1) | 662 | Keep useful UI; remove fixed claims | 7, 16, 17, 20 | Retain search/ingestion/telemetry; replace typed benchmark/comparison tables and overstated integration/privacy labels. |
| [web/style.css](D:/Opencode_/reserchpaper/web/style.css:1) | 629 | Keep; prune only after UI changes | 22 | Current layout is functional; no reason to replace CSS wholesale. Remove unused styles only when retired panels no longer need them. |

## Settings, instructions, and saved state

| File or group | Proposed treatment |
|---|---|
| config.yaml | Keep one validated settings contract; remove unused declarations and mismatched defaults (12). |
| requirements.txt | Remove unused Neo4j declaration; separate core, development, GPU/TensorRT and research profiles; retain required transitive dependencies (21). |
| pytest.ini | Keep discovery/configuration; add explicit optional-test groups only as needed for offline checks (8). |
| .env | Preserve; never include credential values in reports or archives without a secure credential-specific policy. |
| architecture_plan.md | Archive as prior design; retain relevant decision history in the current specification (20). |
| roadmap.txt | Archive completion statements; replace with evidence-backed current task status (20). |
| hybrid_long_term_ai_memory_full_project_plan.txt | Archive prior scope/design; migrate still-relevant decisions into the current architecture record (20). |
| UPDATES_REQUIRED.md | Archive as earlier audit; its specific historical findings should not override current code (20). |
| docs/index.md | Replace current instructions and unsupported completion/stack/target claims (7, 20). |
| docs/phase1_baseline_a.md through phase11_writeup.md | Archive all eleven phase examples/plans; extract necessary current guidance into a small supported documentation set (20). |
| docs/implementation_audit.md | Preserve historical measured profiles with date and prerequisites; remove current-guarantee interpretation (7, 20). |
| report/hybrid_memory_report.md and .tex | Preserve historical artifacts; remove preset conclusions from current generated reporting (7, 20). |
| report/full_specification_report.md, source_reference.md, evidence/inspection files | Preserve as dated review evidence; update current specification after actual implementation (20, 24). |
| New cleanup report/scripts/evidence | Preserve this proposal and its reproduction evidence; these are documentation-task artifacts, not added application features. |
| datasets/README.md and provenance.json | Keep origin/revision/license/hash records; repair instructions/path inconsistencies (6, 20, 23). |
| datasets/dmr/msc_self_instruct.jsonl | Preserve original benchmark input and hash. |
| datasets/locomo and datasets/longmemeval | Preserve selected original data, provenance, licenses, required official evaluator reference; archive unrelated checkout code after path migration (23). |
| datasets/letta | Archive unused external application checkout; preserve any required licensing/provenance reference (23). |
| data/benchmarks | Preserve versioned derived inputs and their source/conversion hashes; regenerate corrected slices as new versions (6, 24). |
| data/official_upstream/slices and freeze_manifest.json | Preserve frozen evidence; create new corrected versions rather than overwrite (6). |
| data/qdrant and data/kuzu/memory.db | Preserve active memory; migration/reconciliation is required before changing record ownership (1). |
| data/kuzu other .db files | Check exact ownership/use; archive experiment stores; candidate test_fresh*.db only after disposability verification (24). |
| data/extraction_cache | Preserve real hosted extraction; migrate cache versioning rather than discard useful responses (3, 24). |
| data/tensorrt_cache | Optional hardware cache; remove only when unused/incompatible or reproducibly recreatable with accepted rebuild cost (21, 24). |
| data/benchmark_run, benchmark_runs_competitors, ablation_run, ablation_matrix_frozen | Archive by run manifest; remove redundant databases only after reconstructability/unique-state check (24). |
| data/official_upstream other stores/checkpoints/input files | Preserve unique upstream experiment state; consolidate current runner and version checkpoint formats before archive/cleanup (6, 24). |
| data/batch_conflict_probe*.db, gpu_probe_*, qdrant_gate4_probe | Scratch-state removal candidates; verify no unique records or active caller first (24). |
| data/cache | Trace remaining callers and provenance; no blanket cache deletion (24). |
| results, metrics, data/results | Preserve raw records; organize by input/config/metric version; withdraw invalid current claims while keeping historical evidence (6, 24). |
| researchpapers/*.pdf | Preserve research references. |
| screenshots/*.png | Keep useful dated screenshots; do not treat their fixed labels as fresh execution proof (7, 24). |
| .venv | Preserve until a replacement environment is built and verified; then remove the nonportable copy (8, 21, 24). |
| __pycache__, .pytest_cache | Recreating these does not require research inputs or credentials; safe cleanup candidates (24). |

## Evidence boundaries

The structural scan identifies candidates, not automatic deletions. No class is marked unnecessary solely because it is large. No external package is removed solely because it lacks a direct application import. Graph storage, neural reranking, real extraction caches, and source research records retain specific purposes.
