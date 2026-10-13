# Post-cleanup benchmark reevaluation

Date: 13 October 2026 (Asia/Calcutta).

The revised system was evaluated with real BGE embeddings and the BGE cross-encoder on an RTX 4050. Both live model sessions used CUDAExecutionProvider. Five percent was run first for LoCoMo, DMR and LongMemEval; twenty percent was then run for LoCoMo and DMR. LongMemEval was excluded from twenty percent as requested.

## Inputs and settings

Question IDs follow the retained frozen twenty-percent cohorts. Five percent uses floor(source questions × 0.05); twenty percent keeps the historical question counts. These are release-order subsets, not random representative samples. Full selected conversation histories were reconstructed from the original local inputs. LoCoMo twenty percent requires 16 additional sessions: 37 selected questions referenced evidence outside the old 54-session corpus. Original frozen files and raw historical results were read without modification.

| Sample | Benchmark | Questions | Sessions/documents |
|---|---|---:|---:|
| 5% | locomo | 99 | 19 |
| 5% | dmr | 25 | 125 |
| 5% | longmemeval | 25 | 1213 |
| 20% | locomo | 397 | 70 |
| 20% | dmr | 100 | 500 |

Three profiles use the same selected store per cohort: vector retrieval, current default hybrid retrieval with reranking disabled, and hybrid retrieval with reranking explicitly enabled. Top-k is 10; hybrid candidate limit is 100, graph hops 2, and graph node limit 50. Hosted extraction is disabled in all profiles, matching the current application default. No entities or facts were fabricated; these runs consequently do not measure hosted extraction or graph-enrichment quality. The local first-context-line generator is used for answer metrics; these are not official upstream answer scores.

The existing environment had a CUDA 13 ONNX Runtime wheel with CUDA 12 DLLs and fell back to CPU. Evaluation selected an isolated ONNX Runtime 1.23.2 installation with CUDA 12 runtime, FFT and linker DLLs. The main environment was unchanged. Runtime compatibility reference: [ONNX Runtime CUDA requirements](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html#requirements). Exact observed versions and providers are recorded in preflight.json.

## New results

Scores are proportions. Retrieval metrics exclude examples without annotated evidence; answer metrics exclude missing answers. Every attempted query completed without an error.

| Sample | Benchmark | Profile | Recall@10 | Precision@10 | MRR | NDCG@10 | AP@10 | Token F1 | Mean retrieval ms | p95 ms |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 5% | locomo | vector | 0.7885 | 0.1082 | 0.4440 | 0.5102 | 0.4038 | 0.0210 | 7.44 | 9.38 |
| 5% | locomo | default_hybrid | 0.7885 | 0.1082 | 0.4440 | 0.5102 | 0.4038 | 0.0210 | 18.43 | 20.72 |
| 5% | locomo | reranked_hybrid | 0.8830 | 0.1206 | 0.6383 | 0.6807 | 0.5957 | 0.0164 | 484.77 | 491.29 |
| 5% | dmr | vector | 0.1600 | 0.0160 | 0.0680 | 0.0897 | 0.0680 | 0.0283 | 8.59 | 10.30 |
| 5% | dmr | default_hybrid | 0.1600 | 0.0160 | 0.0680 | 0.0897 | 0.0680 | 0.0283 | 26.92 | 31.33 |
| 5% | dmr | reranked_hybrid | 0.2400 | 0.0240 | 0.0557 | 0.0981 | 0.0557 | 0.0486 | 2431.73 | 2444.04 |
| 5% | longmemeval | vector | 0.8800 | 0.0880 | 0.6991 | 0.7427 | 0.6991 | 0.0089 | 27.81 | 32.36 |
| 5% | longmemeval | default_hybrid | 0.8400 | 0.0840 | 0.6848 | 0.7224 | 0.6848 | 0.0089 | 58.60 | 63.48 |
| 5% | longmemeval | reranked_hybrid | 0.9200 | 0.0920 | 0.7100 | 0.7616 | 0.7100 | 0.0120 | 1310.33 | 1441.30 |
| 20% | locomo | vector | 0.7854 | 0.0972 | 0.4772 | 0.5362 | 0.4440 | 0.0230 | 12.79 | 16.41 |
| 20% | locomo | default_hybrid | 0.7854 | 0.0972 | 0.4772 | 0.5362 | 0.4440 | 0.0230 | 28.49 | 32.52 |
| 20% | locomo | reranked_hybrid | 0.8962 | 0.1086 | 0.7174 | 0.7456 | 0.6844 | 0.0203 | 575.64 | 853.49 |
| 20% | dmr | vector | 0.0900 | 0.0090 | 0.0414 | 0.0526 | 0.0414 | 0.0452 | 10.62 | 13.84 |
| 20% | dmr | default_hybrid | 0.0900 | 0.0090 | 0.0414 | 0.0526 | 0.0414 | 0.0452 | 38.00 | 42.69 |
| 20% | dmr | reranked_hybrid | 0.1400 | 0.0140 | 0.0316 | 0.0568 | 0.0316 | 0.0338 | 2558.20 | 2656.43 |

## Comparison with the saved old hybrid system

The old predictions were matched by question ID and exact query text, then rescored against current evidence annotations using the same exact-ID and answer metrics as the new runs. Recorded old scores are also preserved in historical_rescoring.json. Old five-percent values are subsets of saved twenty-percent executions, not separate historical five-percent executions.

| Sample | Benchmark | Old rescored recall@10 | New default recall@10 | New reranked recall@10 | Old MRR | New default MRR | New reranked MRR |
|---|---|---:|---:|---:|---:|---:|---:|
| 5% | locomo | 0.7617 | 0.7885 | 0.8830 | 0.5755 | 0.4440 | 0.6383 |
| 5% | dmr | 0.1200 | 0.1600 | 0.2400 | 0.0214 | 0.0680 | 0.0557 |
| 5% | longmemeval | 0.3200 | 0.8400 | 0.9200 | 0.1436 | 0.6848 | 0.7100 |
| 20% | locomo | 0.7168 | 0.7854 | 0.8962 | 0.5532 | 0.4772 | 0.7174 |
| 20% | dmr | 0.1200 | 0.0900 | 0.1400 | 0.0316 | 0.0414 | 0.0316 |

These differences describe the saved executions; they do not isolate the effect of cleanup. Context size, conversation scoping, extraction policy and the first-line answer behavior differ. Historical category names were corrected when rescoring. Historical timings come from the old recorded latency field and were measured in a different runtime and process. They are not a controlled speed comparison. No statistical significance claim is made for these deterministic subsets.

## Performance and coverage

| Sample | Benchmark | Profile | Evidence-scored queries | Answer-scored queries | Peak sampled total VRAM MB | Newly ingested docs | Ingestion seconds | Wall seconds |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 5% | locomo | vector | 97 | 99 | 3435.0 | 19 | 0.76 | 3.61 |
| 5% | locomo | default_hybrid | 97 | 99 | 3431.0 | 0 | 0.10 | 3.00 |
| 5% | locomo | reranked_hybrid | 97 | 99 | 4460.0 | 0 | 0.09 | 49.73 |
| 5% | dmr | vector | 25 | 25 | 4456.0 | 125 | 4.72 | 5.37 |
| 5% | dmr | default_hybrid | 25 | 25 | 4455.0 | 0 | 0.71 | 1.78 |
| 5% | dmr | reranked_hybrid | 25 | 25 | 4458.0 | 0 | 0.64 | 61.97 |
| 5% | longmemeval | vector | 25 | 25 | 4447.0 | 1213 | 85.60 | 87.45 |
| 5% | longmemeval | default_hybrid | 25 | 25 | 4447.0 | 0 | 8.19 | 10.79 |
| 5% | longmemeval | reranked_hybrid | 25 | 25 | 4452.0 | 0 | 8.15 | 42.04 |
| 20% | locomo | vector | 395 | 328 | 4448.0 | 70 | 3.99 | 17.62 |
| 20% | locomo | default_hybrid | 395 | 328 | 4447.0 | 0 | 0.61 | 21.30 |
| 20% | locomo | reranked_hybrid | 395 | 328 | 4448.0 | 0 | 0.56 | 239.73 |
| 20% | dmr | vector | 100 | 100 | 4445.0 | 500 | 23.78 | 26.07 |
| 20% | dmr | default_hybrid | 100 | 100 | 4445.0 | 0 | 5.39 | 10.35 |
| 20% | dmr | reranked_hybrid | 100 | 100 | 4451.0 | 0 | 4.59 | 261.93 |

VRAM is sampled device-wide every two seconds and includes display/other processes. It is not model-only memory or a guaranteed peak. Both models remain loaded across profiles, including vector-only runs; this does not measure the memory of a standalone vector-only deployment. Models are loaded and checked before the matrix; preflight records that duration. Ingestion occurs once in the vector profile; subsequent profiles validate and reuse identical stored documents. Their ingestion times measure the unchanged-record checks rather than fresh throughput. Mean, p50, p95, p99 and maximum query latency are included in the CSV; model initialization is excluded from query times. Old generation and total-pipeline latency are unavailable and remain unscored. No-memory or removed experimental architectures were not treated as current application features.

## Evidence

- all_metrics.csv / all_metrics.json: recall, precision and NDCG at 1, 3, 5 and 10; MRR; AP@10; exact match; token F1; substring match; latency and ingestion statistics.
- comparison.csv / comparison.json: every matched old/new retrieval, answer and latency metric with numeric differences.
- historical_rescoring.json: original recorded scores, corrected scores, source paths, checksums and category breakdowns.
- p*_metrics.json: corrected metrics and current category breakdowns for each of 15 runs.
- raw/: every question result plus source/data/configuration-bound manifests and summaries.
- input_plan.json, preflight.json, verification.json: coverage, input/result hashes, runtime evidence and completion checks.

Final validation: 105 offline regression tests and four actual-dataset tests passed. All 15 source/input/configuration fingerprints were independently reconstructed, all selected result identities were checked, and recomputed scores matched the saved summaries. Eight original input hashes matched their preserved provenance. The five isolated stores contained exactly the selected document IDs and observation counts. Verified summary copies are available to the existing dashboard; original active stores were not used.

Total completed query executions: 1938. Failed query executions: 0. LongMemEval twenty-percent executions: 0.
