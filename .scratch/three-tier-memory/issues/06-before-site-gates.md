# Problems to Demonstrate and Gates Before Site Integration

Labels: wayfinder:task
Type: task
Mode: AFK
Status: resolved
Assignee: Codex
Parent: ../map.md
Blocked by: 04, 05

## Question

What concrete failure cases, implementation sequence and acceptance checks must be satisfied before the travel agency site can use the three-tier core?

## Answer

**The architecture decisions are complete; implementation is pending.** This Wayfinder session produces the resolved route and problem cases, not a claim that tiers 1/2 now run. The user's sequence is core first, travel site integration after acceptance. Application development can continue independently.

[Problems the Three-Tier Design Must Solve](../problem-view.md) gives concrete counterexamples. The most serious is an apparently successful warm-cache recommendation using an old budget while the user's accepted change is pending or already applied. Other major risks are scope leakage, unsupported personality inference, pretending GPU bytes reach a hosted model, context overflow, lost deletions and GPU overhead that exceeds its benefit.

### Implementation order and ownership boundaries

| Step | Core work to implement | Completion evidence |
| --- | --- | --- |
| 1 | Versioned agent profile, structured card schema/compiler, exact trip/profile scope rules and required-field catalog | Evidence-backed Markdown rendering; no invented claims; missing/disputed fields retained |
| 2 | Durable journal state generation, coherent context snapshot/validation, source/time/deletion invalidation | Deterministic races and failures demonstrate cache hits cannot bypass current service gates |
| 3 | Equal-partition RAM cache, CPU card router and bounded context assembler/client API | Measured token accounting, cache miss/rebuild/handoff/overflow behavior |
| 4 | Optional dependency profile and GPU residency adapter, bounded allocations, handles/eviction/CPU fallback | Actual resident tensors and peak bytes; same evidence selection; no global config switch required |
| 5 | Isolated demonstration and matched benchmark against tier-3-only and RAM/CPU routing | Raw correctness cases, timings, token counts, resource accounting and source/config fingerprints |
| 6 | Connect the site to the verified context/validation API and existing event/work APIs | Actual app end-to-end memory use after core acceptance; separate integration work |

New modules can live under `memory/context/` (contracts/compiler/assembler) and `memory/cache/` (RAM/residency), extending `memory/shared/service.py`, `journal.py` and `client.py`. These are proposed locations. Keep the existing `MemoryEngine`, stores and public embedder contract intact. Gate optional GPU imports and do not initialize/download models on module import or status requests.

### Acceptance gates before combining the site

- Warm tier 1/card under a confirmed INR 100,000 budget; submit a confirmed structured replacement to INR 60,000 with its currency and exact trip scope. Pending/failed/unclear states stop usable cached context. After `ready`, tiers 1/2 and work dependencies reflect the new claim while history retains the old one.
- The planner starts generation; a requirement changes before emission. Final validation rejects the old snapshot and rebuilds. Expiry/time-boundary tests cover state changes without graph writes. A missed notification still causes a miss through source generation checks.
- Two users share identical trip/task/mood labels; another trip for the same user differs. Context blocks, cards, CPU results and GPU handles never cross those boundaries. Cross-scope fallback cannot fill missing mandatory trip fields.
- A user generally likes hikes but requests a quiet trip. Explicit task requirements govern the result; temporary mood expiry does not rewrite enduring preferences. Unstated mood is absent rather than inferred.
- An agent proposal cannot become a confirmed requirement/profile through compilation. Source text resembling instructions cannot rewrite agent role or tool privileges. Every factual card line is source-linked.
- Redaction invalidates host/GPU/persisted derivatives and in-flight contexts; old GPU slot handles cannot resolve reused rows. Cold start cannot restore a deleted or superseded value. Eviction/restart loses no source preferences.
- Equal tier-1 caps, actual model token accounting, full prompt/output reservation and mandatory overflow behavior are checked. Required constraints are never silently clipped or displaced by soft persona text.
- Two agents hand off work using exact claim versions; only affected work needs review. Cached context neither transfers an execution lease nor reruns completed work.
- CUDA allocations, peak adapter bytes, OOM, device absence and LRU eviction are observed. The GPU path is genuinely resident; it is not merely a GPU embedder returning NumPy. CPU fallback preserves eligible evidence; near-tied ranks use the same declared final tie-break.
- Run the existing relevant shared/lifecycle regression suite, plus focused new cache/context tests. Isolated runtime/graph names and fixtures must preserve current user data and existing reports. Regression evidence from prior work does not count as new-tier validation.

### Measurements and stop conditions

Use identical source histories, agent/task inputs, consumer model/tokenizer, card definitions and source permissions in three modes: tier-3-only, RAM/CPU cards, and RAM/GPU cards. Keep required information equivalent so caching is not rewarded for dropping evidence. If no hosted/local travel generator is configured, measure context construction and label generation/answer evaluation unmeasured rather than use an unrelated first-line answer proxy.

Record cold start, warm stable reads, accepted changes, concurrent same-user and different-user requests, deletion and forced GPU pressure. Separate lookup, readiness/revision validation, compilation, transfer/ranking, model prefill/generation and write/interpretation delays. Report p50/p95, hit/rebuild rate, stale-use count, cross-user/scope errors, hard-constraint violations, missing-answer behavior, CPU/GPU selected evidence, token counts, host accounted bytes and peak VRAM.

Hard gate: **zero observed stale, unauthorized or cross-scope use in the declared acceptance scenarios**, correct source/deletion/overflow behavior, and passing relevant regressions. This is a test acceptance threshold, not proof of zero failures for every workload. Actual GPU residency and safe fallback must be demonstrated before integration. No fixed speedup is promised; retain CPU selection as the operational default if measured GPU overhead loses, while preserving the demonstrated GPU option requested by the user.

Tier caching cannot remove graph-copy ingestion costs documented in the [latency report](../../../report/latency_breakdown_20261014/report.md). Do not call faster context lookup a faster write pipeline or a new scientific result.

### Remaining execution gates

All new module work, focused checks, GPU proof, benchmarks and site integration above remain pending. The consumer model/runtime and actual site contract must be bound at implementation setup; they do not prevent selecting a transport-neutral context contract now. No external booking, public deployment or research claim is part of this map's destination.

## Execution checkpoint — 2026-10-15

The user's next instruction authorized building with tests at every part. The first context/cache/card implementation, authenticated API/client, durable journal generation, CUDA adapter and scoped failure checks are now implemented; see [incremental implementation and checks](../implementation.md). Actual-store integration tests and real CUDA checks passed, and a real-embedding demonstration records changes, deletion, isolation and handoff behavior. The earlier Answer above preserves the planning checkpoint rather than claiming these later outcomes existed on 2026-10-14.

The next integration boundary is the actual site's consumer model/tokenizer/template and agent flow. Representative production load, hosted-language/answer quality and external provider action guarantees remain unestablished. The new core does not itself combine or deploy the travel site.
