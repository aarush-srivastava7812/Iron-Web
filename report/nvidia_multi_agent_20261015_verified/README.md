# Live NVIDIA multi-agent memory evaluation — 15 October 2026

**Memory state handling passed the tested controls; the complete agent system is not reliable enough to approve travel plans.** Real NVIDIA model responses still contained arithmetic, budget-use and review errors. This replaces the earlier assistant roleplay with actual hosted inference.

The final controlled run took **114.81 seconds**, including local setup, API calls, memory benchmarks and restart checks. It made **15 model calls**: 8 intake calls and 7 calls across two distinct planner/reviewer roles using `nvidia/nemotron-3.5-lightning-30b-a3b`. The same model weights serve both roles. There were **22/22 automated memory checks** and **24/28 agent/output checks** passing: **46/50 combined checks**, not a statistical accuracy estimate. One further metadata gap was found by inspection.

## Measured time

| Operation | Median | p95 | Samples |
| --- | ---: | ---: | ---: |
| Build context without RAM reuse, CPU cards | 550.3 ms | 587.1 ms | 12 |
| Warm context, CPU cards | 62.3 ms | 85.2 ms | 12 |
| Warm context, CUDA cards | 65.2 ms | 107.7 ms | 12 |
| NVIDIA complete response, all call roles | 5.89 s | 11.67 s | 15 |
| Save ingestion receipt | 14.9 ms | 26.3 ms | 8 |
| Validate current context proof | 41.1 ms | 70.5 ms | 9 |

Median NVIDIA time to first visible token: **421.7 ms**. Local startup: **1.13 s**. Hybrid search: **308.8 ms**, one sample. Sum of remote call durations: **81.72 s**. Receipt acknowledgment is not completed interpretation; intake-ready times below include the hosted interpretation and durable write.

The same prompt and evidence were checked across all three context modes. RAM reuse reduced local median preparation time by about **8.8×** in this small run. GPU matching did not beat CPU for the two-card catalog. First GPU-mode context after resetting its adapter took 726.4 ms. These sequential 12-sample runs are descriptive, not a load benchmark.

Provider usage: **19131 input + 5066 output = 24197 tokens**; provider-reported cached input tokens: **0**. Our RAM cache avoids rebuilding the brief; it does **not** avoid sending that brief to NVIDIA. Local counts use NVIDIA's official matching tokenizer; provider counts additionally include complete role instructions, supplier catalog and chat formatting. The model disables thinking for this evaluation; reported reasoning-token counts were zero.

## Data stored in each tier

These are overlapping representations, not three disjoint partitions. Bytes are exact for the stated serialization/tensor/file measurement, not total machine memory.

| Tier | After initial ingestion and warming | At end of the scenario |
| --- | --- | --- |
| 1: accounted RAM cache payload | 37,891 B, 3 cached contexts | 18,118 B, 2 contexts |
| 1: agent/traveller hot text within it | 445 / 2,869 B | 298 / 1,118 B |
| 2: unique cached Markdown card text | 822 B, 4 card versions | 706 B, 3 versions |
| 2: active CUDA card vectors | **3,072 B**, 2 × 384 float32 dimensions | **3,072 B**, 2 active cards |
| 3: graph logical JSON size | 49,444 B; 46 nodes, 83 edges | 110,615 B; 66 nodes, 153 edges |
| 3: vectors | 3 vectors, 4,608 B raw | 8 vectors, 12,288 B raw |
| 3: vector payload JSON | 2,988 B | 6,241 B |
| 3: Qdrant files, primary user | 25,104 B | 53,776 B |
| Auxiliary SQLite journal, while open | 329,416 B incl. WAL/shared-memory files | 659,016 B incl. WAL/shared-memory files |

The final graph contains **8 source records, 27 claims, 3 scopes, 17 field definitions and 2 work records**. Entire closed local runtime files occupied **132,129 B**, including the empty second-user isolation control; this excludes the graph hosted in Docker. The SQLite WAL is checkpointed on close, so open-file totals cannot be added to the closed-runtime total.

The ordinary process working set reached approximately **767.8 MiB**, far larger than the cache payload because Python, the official tokenizer, local BGE encoder, ONNX/CUDA libraries and clients also consume memory. Tier 2 retains a 3,072 B CPU fallback matrix; peak owned card/query/result tensors were 4,616 B. CUDA provider/context overhead is separate. The 32 MiB provider arena value is a configured limit, not a measured allocation.

Card text remains in host RAM; CUDA holds its matching vectors, not Markdown files, model weights or a generative KV cache. RAM payload accounting includes card/field copies, so adding its total to card-text totals double-counts data. The final RAM counts include the empty second-user context used for isolation testing.

FalkorDB's native memory command reported integer MB values of zero for this tiny graph; the generic Redis key counter reported a 64 B wrapper. Neither establishes that the graph occupies zero/64 B. Its exact physical footprint remains unresolved; the table deliberately reports logical serialized size and object counts. [Native counter evidence](native-graph-memory.json), [all snapshots](storage.json), [closed files](closed-runtime-files.json).

## What was ingested

**8 raw source messages, 747 UTF-8 bytes, produced 27 atomic claims.** Every message used `/v1/events` with text, authenticated actor, subject and scope. No caller chose a memory tier or directly wrote cache/persona files.

| Message | Scope/actor | Claims | Saved receipt | Ready, incl. model |
| --- | --- | ---: | ---: | ---: |
| usual-preferences | `{}` / user | 4 | 29.2 ms | 2.92 s |
| goa-intake | `{'trip_id': 'goa-family'}` / user | 15 | 20.9 ms | 8.86 s |
| trip-mood | `{'trip_id': 'goa-family'}` / user | 1 | 6.5 ms | 1.10 s |
| lower-budget | `{'trip_id': 'goa-family'}` / user | 1 | 6.6 ms | 1.74 s |
| walking-change | `{'trip_id': 'goa-family'}` / user | 1 | 8.3 ms | 1.87 s |
| other-trip | `{'trip_id': 'bengaluru'}` / user | 3 | 16.2 ms | 2.36 s |
| repeated-seat-planner | `{}` / planner | 1 | 13.8 ms | 1.40 s |
| repeated-seat-reviewer | `{}` / reviewer | 1 | 16.0 ms | 2.70 s |

Messages covered usual vegetarian/active/aisle/interests preferences; the Goa dates, two adults, Delhi departure, INR 90,000 cap, step-free access, 500 m walking, no boats, morning flights and one activity per day; explicit relaxed mood; budget reduction to 65,000; walking reduction to 50 m; a separate Bengaluru trip; and two agents repeating the user's aisle preference. [Exact text and normalized claims](ingestion.json).

The fictional supplier offers/prices are external per-call task data, **not ingested semantic memory**. Their compact catalog contains 1,865 B of JSON. Expected future budgets and test answers were excluded from the final agent prompts. [Fixture](travel_fixture.json), [complete captured model requests/responses](model-latency.json).

## How automatic routing and persona construction work

1. The application supplies authenticated identity, subject and explicit trip/profile scope. It does not infer identity or trust from prose. Nemotron extracts named travel values; a small application schema supplies permitted field types and source-grounded change actions. This schema and its canonical labels are configured, not learned.
2. **Tier 3 receives every retained source and claim first.** Each message gets a 384-dimensional BGE vector. The graph keeps facts, protection, changes, scopes, sources and work dependencies. The SQLite journal tracks whether interpretation is ready.
3. **Tier 1 is built on request.** Up to 1,024 tokens describe the authenticated agent role; another 1,024 hold required trip fields and saved rules, then optional important preferences if they fit. Missing/conflicting hard requirements block readiness. General preferences inherit only through the configured scope rules.
4. **Tier 2 is a derivative view.** Configured task templates render evidence-backed Markdown from current fields. Explicit relaxed mood admits the relaxed template; it is not a psychological inference. The system embeds eligible card text and ranks it using the request, with up to three selected cards. Reads do not renew the source mood's expiry. [Actual relaxed card](persona-cards/relaxed.md), [itinerary card](persona-cards/itinerary_details.md).
5. Source/configuration/time changes invalidate derivatives and old context proofs. Restart emptied the volatile tiers and rebuilt them from retained tier-3 data. There is no exclusive 'move this fact to cache and remove it from storage' operation.

**Fuzzy scoring does not currently choose cache tiers.** Tier inclusion follows field importance, rule status, scope, task templates and token budgets. Fuzzy scoring contributes reliability/ranking within the durable memory layer. Persona/role/template definitions are application-owned; free-form input alone does not invent new specialist agents or card types.

## Fuzzy logic results

| Control | Score |
| --- | ---: |
| Actual current aisle preference | 0.846786 |
| After both agents repeated it | 0.846786 |
| Same ordinary preference at +0 days | 0.846786 |
| Same ordinary preference at +30 days | 0.614630 |
| Same ordinary preference at +90 days | 0.356571 |
| Same ordinary preference at +365 days | 0.036196 |
| Mathematical control: fresh_one_source | 0.846804 |
| Mathematical control: three_independent_sources | 0.954360 |
| Mathematical control: conflicting_source | 0.779979 |
| Mathematical control: older_90_days | 0.356577 |
| Mathematical control: lower_quality | 0.668604 |
| Current user-confirmed budget rule | 1.000000 |
| Superseded budget | 0.000000 |

Ordinary scores blend freshness, source quality, independent support and disagreement using overlapping low/medium/high memberships. Time then reduces ordinary relevance. Agents repeating one source did not count as independent corroboration; the tiny score difference above is elapsed time. Confirmed protected rules bypass decay while current, and superseded versions cannot become current through a high score. Scores are **not calibrated probabilities**. The day and source-quality comparisons are controlled calculations, not days of elapsed observation or additional real independent witnesses. [Full membership and fired-rule traces](fuzzy-results.json).

## Agent behavior and problems

| Stage | Actual model response | Independent finding |
| --- | --- | --- |
| Initial plan | Comfort flight + resort; claimed total **INR 76,600**, cap 90,000 | Correct selected-offer total is **72,600**. The model added its own numbers incorrectly. Both activity dates are distinct and inside the trip; the evaluator's original arrival-day exclusion was corrected. |
| Initial reviewer | Rejected, but returned `budget_inr: 76600` | It confused the candidate total with the saved **90,000** cap, even though the current memory contained 90,000. Its detailed comments repeatedly called items compliant despite the reject decision. |
| Revised plan | Read the new **65,000** cap but retained comfort + resort; claimed **79,000** and admitted exceeding the cap | Actual selected cost is still **72,600**, over budget. A compliant fixture alternative exists at **58,600**. Good memory retrieval did not force the model to obey the constraint. |
| Revised reviewer / deliberately bad control | Rejected both | It caught the overspend and rejected a deliberately injected late-flight/stairs/boat candidate. Some explanations still repeated bad arithmetic or invented additional walking concerns. |
| 50 m walking limit | Planner paused with no supplier IDs; reviewer said reject | Both read 50 m and stopped approving travel. The reviewer failed the requested `pause` response classification. Both repeated an invented 'morning means before 09:00' reason; the real reason to pause is that all hotels require at least 80 m walking. |

The memory controls passed: relevant pending changes blocked reads; accepted budget changes revoked old proofs and marked completed work for review; context-only work detected the later walking change; unrelated trips remained warm/current; another user saw no trip data; source recall/search and cold reconstruction worked; GPU/CPU modes returned the same evidence. All seven responses cited existing claim IDs, but this check does not establish that every relevant claim was cited or obeyed.

Work records in this evaluation were deliberately registered/completed by the runner to probe version/dependency behavior, using the complete context-provided claim list. **A completed work status validates ownership/evidence state, not travel arithmetic or feasibility.** The real agents did not successfully produce an approved compliant revised plan. No itinerary was executed.

### Intake and provenance gaps

Unrestricted model extraction was not reliable by itself. Earlier attempts promoted a preference to a rule, produced case-only value differences, copied descriptions into enum fields and invented a supersession with no active target. The core rejected these cases without partially applying them. The final intake adapter adds deterministic canonical types, removes empty extracted values, keeps usual preferences distinct from hard rules, and allows budget/walking supersession only when grounded in an explicit change request. This is a bounded travel adapter, not general automatic understanding. [Normalization log](intake-normalizations.json).

The actual card metadata has **empty `source_event_ids` arrays**. Claim IDs still resolve to graph sources, and the receipt ID is retained inside the source's `metadata_json.service_receipt`, so source evidence was not lost. The convenient direct card-to-event list is missing and needs a follow-up core fix. This evaluation did not modify the memory core.

## Metadata actually retained

| Location | Examples from this run |
| --- | --- |
| Source | source/memory IDs, original text, user/agent origin, actor ID, confirmation, source quality, evidence group, recorded/received timestamps, immutable digest, receipt/interpreter/session metadata |
| Claim | predicate/value, fact/preference/rule kind, subject and exact scope, source/group IDs, validity, accepted/protected flags, action/reason, half-life, score at creation, replacement/end metadata and references |
| Vector payload | original source text, timestamps, entity IDs, importance, claim/source IDs, versioned-memory and extraction markers |
| Cached fields/cards | current status, value, exact claim IDs, scope/location, required/hot flags, template version, mood/task tags, generation/expiry, tokenizer identity and token counts; direct source-event lists currently empty |
| Work/journal | cited versions, prerequisite IDs, owner/lease and completion/review state; durable event receipt, queue status, attempts, prepared interpretation and errors |

Current fuzzy score, memberships and fired rules are computed on read; they are not all stored as independent permanent facts. Context/lease credentials are redacted in public artifacts. The supplied NVIDIA key was held only in process memory/environment and was not written to report or source files. [Actual metadata sample](metadata-sample.json).

## All attempts and reproducibility

| Attempt | Time | Model calls | Disposition |
| --- | ---: | ---: | --- |
| [nvidia_multi_agent_20261015](../nvidia_multi_agent_20261015/results.json) | 25.14 s | 3 | Stopped: preference/rule and capitalization conflict |
| [nvidia_multi_agent_20261015_normalized](../nvidia_multi_agent_20261015_normalized/results.json) | 139.57 s | 15 | Completed diagnostic; catalog accidentally exposed future budget, excluded from final agent assessment |
| [nvidia_multi_agent_20261015_final](../nvidia_multi_agent_20261015_final/results.json) | 24.06 s | 2 | Stopped: model emitted description text in kind enum |
| [nvidia_multi_agent_20261015_evaluated](../nvidia_multi_agent_20261015_evaluated/results.json) | 16.49 s | 2 | Stopped: model invented a hotel supersession with no target |
| [nvidia_multi_agent_20261015_verified](../nvidia_multi_agent_20261015_verified/results.json) | 114.81 s | 15 | Completed supplier-only, schema-guarded controlled run |

Total measured execution across these five attempts: **320.07 s**, **37 model calls**. This excludes coding, tokenizer downloads, model-list probes and offline test time. None of the failed or contaminated runs is counted as a successful controlled agent run.

The first catalog probe found the older Mistral endpoint listed but inaccessible for this account; Nemotron's endpoint worked. The final run uses NVIDIA's official 17.1 MB tokenizer and config. An earlier Mistral tokenizer was also downloaded during model selection; no hosted-model weights were downloaded. [NVIDIA API reference](https://docs.api.nvidia.com/nim/reference/llm-apis), [official model/tokenizer](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16). The tokenizer's SHA-256 is recorded in `results.json.consumer_tokenizer`.

Implementation: [small agent classes](../../examples/nvidia_memory_agents.py), [runner](../../scripts/evaluate_nvidia_memory.py), [offline evaluator tests](../../tests/test_nvidia_memory_evaluation.py). The final evaluator/context contract check passed **23 tests**; Ruff passed for new source/tests. [JUnit](evaluator_tests.xml). Original source/core hashes are retained; no `memory/` module changed during this request. The date-boundary correction only re-evaluated captured responses; it did not rerun or repair model answers and did not change the aggregate 46/50 result.

```powershell
$env:NVIDIA_API_KEY = <set privately in your process>
$env:PYTHONPATH = <your compatible CUDA/ONNX runtime paths>
& '.\.venv\Scripts\python.exe' scripts/evaluate_nvidia_memory.py --report report/FRESH_RUN --tokenizer PATH_TO_OFFICIAL_TOKENIZER --gpu
```

The local service has been stopped; isolated graph/vector evidence remains. Model responses, raw latency samples, storage snapshots, corpus, fuzzy traces and failures are all retained in this directory. This was a single synthetic scenario, same-model agents, sequential calls, explicit orchestration and a deliberately small catalog. Larger workloads, autonomous tool selection and production answer reliability were not established.

[Machine-readable results](results.json) · [analysis](analysis.json) · [all checks](checks.csv) · [model timings](model-latency.csv) · [full local API transcript](http-transcript.json)
