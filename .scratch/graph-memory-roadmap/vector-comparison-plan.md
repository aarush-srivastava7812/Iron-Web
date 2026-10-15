# Vector Comparison Plan

Planning asset, 2026-10-13. No benchmark has been run by this update. The task and final placement decision live in [FalkorDB Versus Qdrant: Vector Latency and Output Quality](issues/11-vector-comparison.md) and [Vector Placement Within the Existing Architecture](issues/07-reusable-core-and-storage-boundary.md).

## What is being compared

Keep the existing memory architecture and graph behavior. Change only where meaning-based search happens:

| Variant | Graph memory and relationship checks | Vector search |
| --- | --- | --- |
| Existing baseline | FalkorDB | Current Qdrant configuration |
| Candidate | The same FalkorDB graph content and checks | FalkorDB native indexed vector search |

Mem0, MemPalace and Zep are references. They are not extra stores, ingestion frameworks or different retrieval policies in this comparison. Benchmarking a completely different memory pipeline would not answer the vector-placement question.

The current configuration keeps Qdrant embedded locally. Compare that actual baseline first and label its search mode. A Qdrant server deployment would be a separate experiment. Likewise, ensure the candidate uses FalkorDB's vector index, rather than calculating similarity against every node and calling that an indexed-vector test. Record the actual queries/index use and pinned versions.

## The 5% condition

**Clarification pending:** the user requested 5% on latency and output metrics. The proposed interpretation below is a relative tolerance against Qdrant; it is not yet an accepted policy. If the user means a 5% significance level or a 5% sample, update this section before scoring a winner. A significance level and a practical tolerance answer different questions.

Under the proposed relative-tolerance interpretation:

- Every primary latency result must be at most **1.05 × Qdrant's corresponding latency**.
- Every primary higher-is-better output score must be at least **0.95 × Qdrant's corresponding score**.
- Apply these rules per required workload and metric. A good average must not hide an unacceptable slow-response or quality result.
- Zero-baseline quality scores cannot use a relative ratio; report them as uninformative for this gate and agree a meaningful absolute check before deciding.
- Inconclusive measurements do not count as a pass. Repeat matched runs and report the uncertainty; agree the confidence procedure before collecting decision-making results.

For example, if Qdrant's slower-response time is 100 ms, the proposed ceiling is 105 ms. If its evidence-completeness score is 80%, the proposed floor is 76%, a 5% relative reduction. It is not a five-percentage-point allowance.

Access separation, using the accepted current version, preserving history and handling missing answers remain correctness checks. A 5% retrieval allowance never permits cross-user exposure or breaking an already-supported memory rule. A baseline bug also remains a failure to fix; matching it does not make the behavior correct.

## Make the comparison fair

Freeze one set of memories, graph relationships, original sources, questions and reference answers. Give both variants identical stored embeddings and precomputed question embeddings, using the same model, dimensions and similarity measure. Keep the same candidate count, final evidence limit, graph-expansion budget, filters, current/historical rules and optional reranking configuration. Record ID mappings so the same evidence can be scored across stores.

Create explicit per-question reference evidence before the runs: which facts/sources are needed, which statements are obsolete or disputed, and whether the requested answer exists. Judge against those references, not against Qdrant's returned IDs. Different IDs/order are acceptable if they supply the correct evidence under the same budget.

Freeze the current configuration and code revision. Run on the same machine with a declared resource budget, comparable durability settings and no unrelated background load. Alternate run order, use identical workload traces and repeat runs to avoid favoring the first or second variant. Report the fact that the baseline and candidate may use different exact/approximate search methods.

Try a small predeclared set of candidate vector-index settings on a development set. Freeze the choice before the untouched evaluation. Record any quality-for-speed tradeoff; do not tune against the final questions or loosen the 5% rule after seeing results. Record index creation time, storage and memory use separately from search latency.

Use isolated graph names and vector collections/directories. The experiment must not replace the live service, rewrite current memories, or interfere with the parallel FalkorDB migration/application work.

## Measure two parts of retrieval

1. **Vector search alone:** start with the prepared question vector and finish with candidate IDs/scores. This isolates the storage/search contribution.
2. **The application's complete retrieval:** start with the question and finish with the evidence an agent would receive, including graph checks, filtering and ranking. Use identical processing outside the vector backend.

Report the typical response time (median/p50) and the slower-response boundary (95th percentile/p95: 95 of 100 requests finish by this time) for both parts. Count timeouts and errors; do not remove them silently. Also report completed requests per second and resource use. A fast vector query that makes complete retrieval slower does not establish a useful improvement.

If the application produces final answers, run a separate matched answer check with the same agent/model/settings and evidence limits. Score correctness and unsupported claims against the references. Report answer-generation latency separately so model variability does not conceal the vector comparison. Until that flow exists, describe output metrics as **retrieved evidence quality**, not generated-answer accuracy.

## Output metrics

Predeclare these primary retrieval metrics for the proposed 5% quality gate:

| Metric | Everyday meaning |
| --- | --- |
| Evidence completeness at the fixed budget | How much of the evidence needed for the question was actually returned |
| Evidence relevance at the fixed budget | How much of the returned evidence helps answer the question |
| Ranked evidence usefulness | Whether the important evidence appears early enough for the agent to use |

Record top-five results as a visible diagnostic, plus results at the application's actual evidence budget. “5%” does not mean five returned results. Include answerable, ambiguous and unavailable-answer questions in separately reported groups; a single overall average should not bury missing-answer failures.

Also report current/historical correctness, dispute visibility, source/evidence completeness and unavailable-answer correctness. These are exact labeled checks on the declared cases, not fuzzy similarity scores. If final answers are tested, declare their correctness score separately and apply the clarified quality rule to it; unsupported claims remain explicitly reported.

## Workloads

Use the existing 40-question demo as a smoke check, clearly labelled curated and previously seen. Add an untouched set with different wording, less convenient records and enough independent questions to make a 5% comparison informative. Determine sample size from a pilot's variability and reference-score granularity; a few questions cannot establish a small quality difference.

Before the scored runs, agree and record representative small, medium and larger memory sizes and expected per-user load. Include fresh content, accepted changes, retained old versions, disputes, aliases, missing details, relevant multi-step relationships and unrelated growth. Do not present duplicated filler as a realistic quality benchmark.

Run the same traces against both variants:

- One agent reading a fixed corpus.
- Several agents reading the same user space and separate user spaces.
- Concurrent reads while real new memories and accepted updates are arriving.

In the mixed workload, check when each acknowledged change becomes visible to retrieval and whether old vector hits are reconciled with the same current graph state. Record event receipt, interpreted-memory readiness and searchable visibility separately. The vector experiment measures the existing behavior; the later KG additions receive their own readiness and correctness checks.

Keep application cache settings unchanged and identical in both variants. **Cache research, tuning and architecture changes remain deferred**, as the user requested. No external cache research is part of this plan or this update.

## Required result and next decision

Preserve raw timings, returned evidence IDs, reference labels, settings, run instructions and workload traces. Produce a table with the corresponding Qdrant and FalkorDB values, relative differences, uncertainty and gate outcomes. Report run failures, drift and limitations openly.

The placement ticket uses that evidence:

- **Pass:** FalkorDB vectors are eligible for a placement decision. Consider the observed maintenance/resource tradeoff before adopting them.
- **Fail:** keep Qdrant for the first build and record the limiting metric.
- **Inconclusive:** keep Qdrant provisionally and describe the missing evidence or follow-up test.

Do not average primary metrics into one score to conceal a failure. Do not claim that this placement test proves fuzzy memory behavior, graph reasoning, multi-agent handoff reliability or broad production readiness. Those are the next additions and their own tests.

## What follows the comparison

After placement is settled, add the first pause's fuzzy/protected memory lifecycle and retained change links, then the second pause's explainable relation-aware retrieval and question evaluation. Connect accepted changes to affected work and handoffs within the existing architecture. Recheck retrieval quality and latency after those additions; the original placement result is a baseline, not a permanent performance guarantee.
