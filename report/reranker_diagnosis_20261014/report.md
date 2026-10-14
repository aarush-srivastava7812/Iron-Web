# Reranker diagnosis and tested measures

Analysis date: 14 October 2026. Latency values measure the reranking stage only.

## Findings

The main cost is repeated local transformer inference. The current reranker is a cross-encoder: it reads the question together with every candidate document and performs a separate relevance calculation for each pair. [The BGE model card](https://huggingface.co/BAAI/bge-reranker-base) describes this query/passage scoring behavior. No network request or graph database command occurs inside this model stage.

The cached model has 278,044,417 parameter elements, 12 layers, 768 hidden dimensions and float32 weights. Its file occupies 1,112,459,588 bytes. The tokenizer permits 512 tokens per question/document pair. The original export runs attention using separate matrix operations. Operator profiling placed all observed heavy MatMul, FusedMatMul and Gemm operations on CUDA. The CPU operators were small shape operations such as Gather, Unsqueeze and Reshape.

The application sends complete conversation documents to the tokenizer and scores the whole candidate pool. DMR scores 100 candidates per query, LoCoMo 19–32, and LongMemEval 38–56. With batch size 16, DMR requires seven model calls. The final result limit of ten is applied after scoring; changing only top_k does not reduce the number of documents sent to the model.

## Test scope

The experiments retain all 597 questions from the previous 20% cohorts and their exact candidate pools. Each of three variants scores every question: 1,791 measured reranking requests. The original variant reproduces every previously returned ID, ordering and predicted answer. All 17 quality metrics were recomputed. DMR and LongMemEval each have 100 scored questions. LoCoMo has 397 questions, 395 retrieval-scored examples and 328 answer-scored examples; missing/empty references are excluded from the corresponding metric denominators.

The application source is pinned to the revision used in the preceding latency report. The current reranker file has no working-tree changes. Newer lifecycle/shared-memory changes are outside this experiment. Candidate pools come from private copies of the original embedded vector stores. The verified benchmark graphs have no entities or edges, so graph lookup is represented as empty when constructing those pools. Original baseline output equality verifies that this reconstruction gives the same reranked results on every question.

BAAI/bge-reranker-base runs locally with ONNX Runtime 1.23.2 on the RTX 4050 Laptop GPU. Model loading, conversion, embedding, vector search, Redis checks, graph operations and result generation/scoring are excluded from reranking latency. All variants use the same deterministic shuffled question order, two warm-up requests, and one complete measured pass. The FP32 variants run first; the session is released before loading FP16 to avoid holding two large sessions. This fixed variant order does not control thermal/power conditions. GPU snapshots are retained in full_telemetry.jsonl; they are instantaneous samples, not kernel timings or peak memory.

## Time inside the original reranker

| Dataset | Total ms | Tokenize | Build inputs | ONNX run | Other |
| --- | --- | --- | --- | --- | --- |
| dmr | 1717.07 | 34.83 | 7.78 | 1668.69 | 5.77 |
| locomo | 394.05 | 17.57 | 1.89 | 372.53 | 2.05 |
| longmemeval | 940.67 | 113.19 | 3.90 | 815.01 | 8.57 |

ONNX run includes model execution, input/output transfers and synchronization. Tokenization runs on the CPU and processes the supplied text before limiting the encoded input. Other includes constructing pairs, collecting scores, sorting and timer overhead. The operator profile records provider placement and host node durations; it does not use CUPTI and must not be interpreted as a separate GPU kernel time breakdown.

| Dataset | Mean model batches | Mean padded tokens | Mean active tokens | Padding share |
| --- | --- | --- | --- | --- |
| dmr | 7.00 | 50411 | 36107 | 28.4% |
| locomo | 2.00 | 11287 | 11215 | 0.6% |
| longmemeval | 3.47 | 24676 | 24090 | 2.4% |

## Full-cohort measures tested

Original uses FP32, batch 16, 512-token inputs and the full candidate pool. The candidate limit scores the first 20 candidates in the original vector retrieval order; remaining candidates are omitted. Fused FP16 keeps every candidate and the same 512-token limit, but uses an offline optimized mixed-precision model.

| Dataset | Original ms | 20 candidates ms | Fused FP16 ms | FP16 reduction |
| --- | --- | --- | --- | --- |
| dmr | 1717.07 | 333.96 | 564.46 | 67.1% |
| locomo | 394.05 | 344.86 | 137.30 | 65.2% |
| longmemeval | 940.67 | 401.56 | 367.93 | 60.9% |

The optimizer fused 12 Attention, 12 BiasGelu and 24 SkipLayerNormalization operators. The converted file occupies 556,137,378 bytes. This experiment combines operator fusion and reduced precision, so it does not isolate their individual speed contributions. [ONNX Runtime's transformer optimizer](https://onnxruntime.ai/docs/performance/transformers-optimization.html) supports offline fusions and mixed precision when normal session optimization leaves some patterns unfused. The initial generic FP16 conversion did not pass model type validation; only the ONNX Runtime transformer conversion was successfully benchmarked.

## Quality changes

Values below are fractions, with each variant compared against the original model. The full quality_metrics.csv includes all 17 metrics and their numerical differences. A change in ordering can occur even when aggregated quality values remain unchanged.

| Dataset | Variant | Recall@10 | MRR | nDCG@10 | Token F1 | Exact top ten |
| --- | --- | --- | --- | --- | --- | --- |
| dmr | baseline | 0.1400 | 0.0316 | 0.0568 | 0.0338 | 100/100 |
| dmr | cap20 | 0.1100 | 0.0259 | 0.0456 | 0.0437 | 0/100 |
| dmr | fp16_optimized | 0.1400 | 0.0316 | 0.0568 | 0.0338 | 81/100 |
| locomo | baseline | 0.8962 | 0.7174 | 0.7456 | 0.0203 | 397/397 |
| locomo | cap20 | 0.8913 | 0.7124 | 0.7402 | 0.0201 | 311/397 |
| locomo | fp16_optimized | 0.9046 | 0.7182 | 0.7481 | 0.0203 | 324/397 |
| longmemeval | baseline | 0.9455 | 0.7562 | 0.7982 | 0.0253 | 100/100 |
| longmemeval | cap20 | 0.9630 | 0.7666 | 0.8102 | 0.0256 | 9/100 |
| longmemeval | fp16_optimized | 0.9455 | 0.7570 | 0.7990 | 0.0260 | 48/100 |

cap20: 40 of 51 dataset/metric values changed by more than 1e-12. The exact deltas are exported, including changes in both directions.

| Dataset | Metric | Difference |
| --- | --- | --- |
| dmr | average_precision@10 | -0.005643 |
| dmr | mrr | -0.005643 |
| dmr | ndcg@10 | -0.011262 |
| dmr | ndcg@3 | +0.005000 |
| dmr | ndcg@5 | -0.011789 |
| dmr | precision@10 | -0.003000 |
| dmr | precision@3 | +0.003333 |
| dmr | precision@5 | -0.006000 |
| dmr | recall@10 | -0.030000 |
| dmr | recall@3 | +0.010000 |
| dmr | recall@5 | -0.030000 |
| dmr | substring_match | +0.010000 |
| dmr | token_f1 | +0.009915 |
| locomo | average_precision@10 | -0.005819 |
| locomo | mrr | -0.005024 |
| locomo | ndcg@1 | -0.005063 |
| locomo | ndcg@10 | -0.005386 |
| locomo | ndcg@3 | -0.007654 |
| locomo | ndcg@5 | -0.007806 |
| locomo | precision@1 | -0.005063 |
| locomo | precision@10 | -0.000253 |
| locomo | precision@3 | -0.004219 |
| locomo | precision@5 | -0.002532 |
| locomo | recall@1 | -0.005063 |
| locomo | recall@10 | -0.004852 |
| locomo | recall@3 | -0.010759 |
| locomo | recall@5 | -0.012025 |
| locomo | token_f1 | -0.000197 |
| longmemeval | average_precision@10 | +0.009560 |
| longmemeval | mrr | +0.010377 |
| longmemeval | ndcg@10 | +0.011980 |
| longmemeval | ndcg@3 | +0.012961 |
| longmemeval | ndcg@5 | +0.024361 |
| longmemeval | precision@10 | +0.001000 |
| longmemeval | precision@3 | +0.010000 |
| longmemeval | precision@5 | +0.012000 |
| longmemeval | recall@10 | +0.017500 |
| longmemeval | recall@3 | +0.023333 |
| longmemeval | recall@5 | +0.053333 |
| longmemeval | token_f1 | +0.000322 |

fp16_optimized: 13 of 51 dataset/metric values changed by more than 1e-12. The exact deltas are exported, including changes in both directions.

| Dataset | Metric | Difference |
| --- | --- | --- |
| locomo | average_precision@10 | +0.000981 |
| locomo | mrr | +0.000759 |
| locomo | ndcg@10 | +0.002522 |
| locomo | ndcg@3 | -0.000594 |
| locomo | ndcg@5 | -0.000016 |
| locomo | precision@10 | +0.001013 |
| locomo | precision@3 | -0.000844 |
| locomo | recall@10 | +0.008439 |
| locomo | recall@3 | -0.000633 |
| longmemeval | average_precision@10 | +0.000746 |
| longmemeval | mrr | +0.000746 |
| longmemeval | ndcg@10 | +0.000766 |
| longmemeval | token_f1 | +0.000667 |

## Smaller pilot experiments

Eight deterministic questions per dataset were also used to test batches of 8 and 32, a 40-candidate limit and a 256-token limit. These pilot timings are descriptive, not confidence intervals. Variants were executed in separate blocks, so small timing differences can reflect changing runtime conditions. Shorter input limits and reduced candidate pools change the information available to the reranker.

| Variant | DMR ms | LoCoMo ms | LongMemEval ms |
| --- | --- | --- | --- |
| baseline | 1690.44 | 357.86 | 947.97 |
| batch8 | 1567.52 | 348.53 | 935.18 |
| batch32 | 1728.91 | 367.32 | 977.17 |
| cap20 | 344.36 | 391.75 | 405.32 |
| cap40 | 681.85 | 364.56 | 768.42 |
| length256 | 712.83 | 155.46 | 441.19 |
| fp16_optimized | 554.70 | 127.24 | 363.09 |

## Measures in priority order

1. Use a validated fused FP16 model on CUDA as the first performance candidate. It keeps the same model family, candidate pool and input limit. Numerical changes and observed quality deltas still need an explicit acceptance criterion before changing the default. Cache the converted model once, identify it by source-model/runtime hashes, verify finite scores, and keep the original FP32 model available for CPU execution. The prototype already produces and measures the optimized artifact; production loading is unchanged.

2. Add a separate configurable number of candidates to rerank before inference. A final result limit alone does not reduce model work. The measured 20-candidate variant shows the latency/quality tradeoff; apply a cap only where the full metric/category results meet the intended quality requirement. Graph-derived candidates would also need an explicit inclusion policy; these observation-only benchmarks do not test that case.

3. Reduce repeated text preparation by storing relevant passages or caching document tokens with model/tokenizer and document-version keys. This matters especially for LongMemEval after inference is faster. Simply cutting a character prefix is not equivalent to the current tokenizer and could remove relevant evidence. Chunk selection and token caching were not measured in this run.

4. Make reranking optional for requests whose latency requirement is more important than its measured ranking benefit. An adaptive rule based on query/candidate confidence needs calibration and quality evaluation. Cache scores for repeated identical query/document pairs where versions and model identity match; this helps repeats rather than new prompts.

5. Investigate a smaller cross-encoder if a stricter response-time target remains unmet. This changes the model and requires evaluation on the actual memory tasks. No smaller model speed or quality result is claimed here. Batch tuning can be revisited after model optimization; the current pilot does not support increasing batch size as the main fix.

6. For simultaneous requests, move expensive model execution out of the graph lease only after defining consistent snapshot/revision behavior. The previous latency report measured substantial mutex waiting because the existing lock covers the entire request. This changes concurrency semantics and was not applied or tested here.

## Reproduction

Install the isolated inspection dependencies into data/reranker_diagnosis/runtime. Run scripts/diagnose_reranker.py with --phase prepare, then --phase optimize, then --phase full --variants baseline,cap20,fp16_optimized. Run scripts/build_reranker_report.py to recompute quality and generate this document. The retained inputs, original vector stores, pinned source checkout and model cache are required. Large converted models and candidate texts remain under ignored data; report files contain measured summaries and per-query records. No live graph, original corpus or application setting was changed.

## References

[BGE model behavior](https://huggingface.co/BAAI/bge-reranker-base), [ONNX Runtime transformer optimization](https://onnxruntime.ai/docs/performance/transformers-optimization.html), [float16 and mixed precision](https://onnxruntime.ai/docs/performance/model-optimizations/float16.html), [profiling limitations](https://onnxruntime.ai/docs/performance/tune-performance/profiling-tools.html).
