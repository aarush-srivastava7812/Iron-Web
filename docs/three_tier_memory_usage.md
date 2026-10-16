# Using the Three-Tier Memory Core

Implemented on 2026-10-15. The core supports authenticated profiles, exact trip/profile/session fields, evidence-backed Markdown cards, equal tier-1 limits, a bounded RAM cache, current-state proofs, and optional actual CUDA card matching. The travel site was connected on 2026-10-16; see the [application integration guide](application_memory_integration.md).

The durable stores retain source knowledge. Card templates and agent profiles are application-owned configuration; generated cards are disposable views. Cards are returned as readable Markdown in JSON rather than accumulated as independent memory events or durable duplicate persona files. Restart rebuilds the views from retained claims and configured templates.

## Configure the service

Add a `context` object to a private shared service configuration. Keep the existing `runtime`, `namespace`, `principals` and interpreter settings. Tokenizer paths are resolved relative to that configuration file. Setup requires an existing local tokenizer file and performs no model download.

```json
{
  "context": {
    "tokenizer_path": "C:/path/to/the/consumer/tokenizer.json",
    "tokenizer_id": "consumer-model-and-revision",
    "profiles": [
      {"actor_id": "planner", "version": "1", "instructions": "Plan practical trips using current supported requirements."},
      {"actor_id": "reviewer", "version": "1", "instructions": "Review plans against current supported requirements."}
    ],
    "use_gpu": false,
    "policy": {
      "half_tokens": 1024,
      "card_tokens": 512,
      "max_cards": 3,
      "context_limit": 8192,
      "output_tokens": 1024
    },
    "prompt_prefix": "",
    "prompt_suffix": ""
  }
}
```

Agent profile IDs must match the authenticated actors that will request context. Profile descriptions do not grant permissions. The context API accepts authenticated agents with configured profiles; user credentials still submit confirmed changes through the existing event API.

The tokenizer file hash participates in the runtime identity. Its truncation/padding are disabled for accounting. Prefix/suffix allow a declared plain-text model wrapper; the complete returned prompt, including labels and wrapper, is counted with output space reserved. A hosted chat integration must account for its actual chat template and tool overhead before claiming the same context limit. This implementation does not guess a provider's hidden formatting.

The current task types are `flight`, `hotel`, and `itinerary`. Each requires supported exact-trip `destination`, `dates`, `budget`, and `currency`. The service also discovers every saved active atomic field in the exact trip/session: rules and instructions are mandatory in every task brief, including unfamiliar field names; other saved facts enter the hot block, cards or additional evidence. Protected profile rules also apply. Missing/disputed/unconfirmed mandatory fields block readiness. Unlike values for the same field across scopes, where one is a hard requirement, produce `scope_conflict` for clarification. The service does not guess whether they describe an intended exception.

Only explicitly configured ordinary preferences can fall back to the same subject's global profile scope `{}`, and only when the trip field is missing. General interests never authorize bypassing a trip restriction. Mandatory information that exceeds the equal hot-half limit produces a visible capacity error; optional cards can be removed, but their source fields remain in additional evidence or cause a visible capacity error.

The local `travel_grammar_v2` adapter understands the tested multi-clause travel intake, including explicit same-month dates, currency/total budget, party count, vegetarian food, flight origin/time, step-free hotels, walking/boat/day limits and a relaxed trip. Every clause must be recognized; unknown, conditional, conflicting or question wording yields no partial semantic acceptance and confirmed messages require review. This is a bounded grammar, not general language understanding. Use validated structured claims or a separately evaluated provider for unsupported language.

An explicit `mood` claim is read in `{...trip_scope, "session_id": "..."}` when a session is supplied. If that scope has no mood history, the trip mood is inherited and labelled `[trip]`. An explicit, disputed, expired or retracted session mood does not fall back to an older trip mood. Its derivative expires at source time plus 30 minutes, or an earlier declared validity end. Reads do not renew it. Default mood guidance covers explicitly stated `relaxed`; additional application-owned templates can specify other explicit mood tags.

## Request and use context

```python
from memory.shared.client import SharedMemoryClient

client = SharedMemoryClient("http://127.0.0.1:3351", agent_credential)
request = dict(subject="Traveller", scope={"trip_id": "summer"},
               task_type="itinerary", session_id="session-1",
               query="A restful trip with beaches and vegetarian meals")
packet = client.context(**request)
```

The response includes both tier-1 blocks, selected card Markdown/source IDs, required-field issues, exact used claim IDs, token accounting, expiry, cache hit/residency diagnostics, and an actor-bound `context_token`. `needs_information` means required facts are missing/disputed/unconfirmed; it is not authorization to continue with a guess. Pending, failed or unclear changes continue to raise the existing HTTP 409 `pending_memory` state.

For a response-only generator:

```python
result = client.generate_current(request, generate=lambda packet: model(packet["prompt"]))
```

The helper checks readiness/current state after generation and discards an outdated response. It allows at most two rebuilds, then returns `context_changed`. `generate` must only produce a response; it is retried and is not a booking/payment execution hook. Applications that assemble/generate themselves call `/v1/context/validate` with `context_token` before emitting a response or using its evidence. Validation establishes state at that check, not immunity to later user changes.

Use returned claim IDs with existing `/v1/work`, ownership, completion and handoff operations. Cached text never transfers an execution lease or replaces the core's prerequisite/evidence checks.

Readiness and cached-context fingerprints are trip-aware. A queued change to another explicitly scoped trip does not block this context or discard its RAM entry. Structured claim scopes take precedence over a misleading event envelope. Global, unscoped and identity changes remain conservative blockers. Work checks include the scopes of its cited evidence and prerequisites; profile-only or unknown dependencies keep the global gate. Unscoped discovery search also keeps the global gate.

Proofs hash the relevant claim/source state and identity links as well as relevant journal rows, runtime identity and time expiry. Direct local graph changes remain detectable; unrelated work ownership updates do not invalidate travel facts. Journal rows are streamed while hashing, so this path still scans a tenant's event history and has not been established as a many-user performance design. Future temporal boundaries are conservatively checked across the graph. The exact dependency contract remains: work must cite the evidence it used; arbitrary uncited assumptions are not inferred.

## GPU and bounds

The standard context configuration defaults to CPU selection. In a separate GPU environment, install `requirements/context-gpu.txt` and set `use_gpu: true` in the context object. The tested optional profile uses ONNX Runtime 1.23.2/CUDA 12 and retained NVIDIA libraries. The existing installed ONNX Runtime 1.31.0 expects CUDA 13; simply requesting GPU there does not supply its missing libraries. Existing application GPU/CPU configuration is unchanged.

CUDA holds normalized card retrieval vectors and performs matrix matching. Selected original text is supplied to the consumer. The adapter retains a CPU matrix for fallback and numerical parity checks; it is not a generative KV-prefix cache. It holds one bounded active catalog, replacing and clearing older device slices on owner/catalog changes. This simple eviction strategy can churn across users/tasks and is not a large-scale GPU database.

Initial limits are 32 MiB accounted RAM payload / 256 entries, at most 4096 active card vectors, and 64 MiB for owned tensors plus the configured provider arena. CUDA context/library workspace and total process RSS are outside those accounting scopes. Admission reserves at least 512 MiB free-device headroom. Allocation/execution failure selects the equivalent CPU path and reports its reason. Deletion invalidates host/device views and in-flight proofs; released handles cannot resolve reused storage. Clearing owned slices is not a forensic device-erasure guarantee.

## Verification and evidence

Focused checks were introduced and run before their corresponding implementation pieces, then rerun after each change. The [implementation log](../.scratch/three-tier-memory/implementation.md) records the stages and issues caught. [Real-model demonstration results](../report/three_tier_20261015_verified/results.json) use real BGE embeddings, a cached Mistral tokenizer, isolated FalkorDB/Qdrant stores and real CUDA allocations. [Readable results](../report/three_tier_20261015_verified/README.md) explain the timing scope.

The subsequent [travel-audit fixes and final-source replay](../report/travel_agent_fixes_20261015_final/README.md) cover mandatory rule discovery, brief-only dependency invalidation, mood inheritance, multi-clause intake and trip-local readiness/cache behavior. Final checks: 236 ordinary tests, 2 actual CUDA tests and 24/24 scenario checks passed. The original findings-only audit remains available for comparison.

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_context_contracts.py tests/test_context_journal.py tests/test_context_cache.py tests/test_context_assembly.py tests/test_context_configuration.py tests/test_context_service.py tests/test_card_residency.py
& '.\.venv\Scripts\python.exe' -m pytest tests/test_card_residency.py tests/test_context_service.py -m gpu
```

The GPU command requires actual CUDA libraries and the optional dependencies. Ordinary tests use declared offline embedding fixtures plus actual temporary stores; GPU tests exercise real device memory, and the independent script additionally exercises real neural embeddings. The script `scripts/check_three_tier_memory.py --help` lists reproducible local-model demonstration options and refuses to overwrite an existing report.

This is a tested first core implementation. Actual travel-site generation, provider/template binding, representative many-user load, hosted interpretation and external actions remain integration/acceptance work; no research novelty or general answer-quality result is claimed.
