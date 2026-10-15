# Three-Tier Memory: Verified First Implementation

2026-10-15. The user requested tests at every implementation stage. [The incremental log](../../.scratch/three-tier-memory/implementation.md) records checks introduced before implementation and the failures they caught. [The usage guide](../../docs/three_tier_memory_usage.md) explains configuration and the API.

## What was exercised

- Real FalkorDB and embedded Qdrant in fresh, isolated runtime/graph names.
- Real BAAI/bge-small-en-v1.5 neural embeddings, using a retained local model; no synthetic embedding substitute in this demonstration.
- The cached Mistral-7B-Instruct-v0.1 tokenizer, identified by its file hash, for a declared plain-text consumer contract. No generative model or hosted provider was invoked.
- Actual CUDA-resident card vectors and GPU matrix matching, with the loaded ONNX Runtime 1.23.2/CUDA 12 profile. The separate device tests also compare 64 candidate vectors across 12 queries and revoke deleted handles through the actual service.
- Identical final prompt and claim dependencies across uncached equivalent, RAM/CPU and RAM/GPU modes.
- A confirmed budget change from INR 100,000 to INR 60,000: warm reads block while pending, then rebuild; the earlier proof becomes invalid.
- Two private user spaces, graph-backed handoff dependencies, and deletion of the revised budget without resurrecting the earlier one.

All declared demonstration checks passed. [Machine-readable results and source fingerprints](results.json) include raw samples, runtime versions and the isolated graph names. Only synthetic demonstration text is exported; credentials/context proofs are excluded.

Final ordinary regression: **215 passed**, with 6 optional tests deselected. Separate actual CUDA verification: **2 passed**. The source fingerprints in the demonstration match the final implementation modules. Lint and 66 local documentation/report links also passed verification.

## Context preparation timings

Fifteen repetitions of the same request per mode. Lower is better. This measures context preparation, including current-state checks and card selection, rather than response-model prefill/generation.

| Mode | Median | 95th percentile | First context rebuild |
| --- | --- | --- | --- |
| Uncached equivalent | 232.86 ms | 248.06 ms | 237.83 ms |
| RAM cache + CPU matching | 15.34 ms | 17.38 ms | 237.39 ms |
| RAM cache + GPU matching | 15.82 ms | 17.36 ms | 1058.20 ms |

The uncached equivalent repeatedly compiles the **same context and evidence** from tier 3 and rebuilds the card index. It is not an old-system final-answer benchmark. First rebuild excludes initial neural-model loading; the first GPU rebuild includes its device/session setup. The tiny active catalog has one 384-dimensional card vector: 1536 device bytes, with 3076 peak accounted owned tensor bytes including query/output estimates. These numbers do not include CUDA context/library workspace or other processes.

CPU remains the operational default. GPU is a verified option, and this small run does not establish a general GPU speed advantage. Earlier runs overlapped regression activity; none of these local samples supplies a held-out research result or a workload-wide latency guarantee.

## Inspect the behavior

- [Original context](original.md): INR 100,000 requirement and exact source references.
- [Changed context](changed.md): current INR 60,000 requirement.
- [After deletion](redacted.md): budget is missing; neither earlier amount is silently reused.
- Full context structures: [original](original.json), [changed](changed.json), [redacted](redacted.json).

The ordinary integration suite additionally covers pending/unclear states, request races, scope separation, profile fallback, expiry without writes, expiry during assembly, restart, agent proposals, prompt overflow/deduplication, and handoffs. [Final ordinary-suite record](../three_tier_final_suite_20261015.xml) and [actual CUDA checks](../three_tier_cuda_tests_20261015.xml) retain the verification outputs.

## Scope still ahead

The travel site's actual consumer model/tokenizer/chat template and flow are not connected by this work. The core exposes the context/validation API and a response-only generator helper with bounded rebuilding; its real HTTP race test uses a declared callback rather than a hosted model. Representative many-user load, hosted interpretation, final-answer quality, and booking/payment execution remain separate integration/acceptance work.
