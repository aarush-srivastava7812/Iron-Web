# Context Assembly, Card Routing and Bounded Resource Use

Labels: wayfinder:task
Type: task
Mode: AFK
Status: resolved
Assignee: Codex
Parent: ../map.md
Blocked by: 03, 04

## Question

How does a request select and consume cards, retrieve missing evidence, respect context/RAM/VRAM budgets, and continue when the GPU is unavailable?

## Answer

Use one proposed `assemble_context` operation inside `SharedMemoryService`, exposed later through a bounded `/v1/context` endpoint and reusable client. It returns the two tier-1 blocks, selected cards, additional evidence, missing/disputed fields, claim dependencies, a snapshot token and residency diagnostics. This endpoint and a matching context-validation operation are additions, not existing API capabilities.

### Request path

1. Resolve authenticated principal, explicit subject, exact trip/session scope, agent-profile version and task type. The application/agent supplies task type; an uncertain classifier cannot silently substitute another trip/task.
2. Check readiness and acquire a consistent source snapshot. Reuse valid tier-1 views or compile from supported field recall. Required task fields are configured explicitly: for example, flight recommendation needs destination, travel dates and a budget with its currency; if any are missing/disputed/unclear, return that state rather than pretend the persona answers it. The current interpreter does not already extract all these fields.
3. Apply tenant/subject/scope/task/time eligibility **before** card ranking. Require explicit mood evidence for a mood-specific card. Rank compatible cards using deterministic task match first, explicit mood match second, optional semantic similarity third; tie-break by canonical card ID. Mood affects optional ranking, not feasibility or authority.
4. Use normalized embeddings for semantic selection on GPU when admitted. Use a bounded, equivalent CPU dot-product route when not admitted. Semantic candidates are discovery, so look up current handles and evidence before serialization. Do not copy an entire embedding matrix back to CPU per query; return a bounded candidate/score set and materialize selected text. Because floating-point backends can differ, use a declared score tolerance and a common final ordering/CPU tie-break near the selection boundary.
5. Retrieve missing task-specific evidence from tier 3 using bounded vector/graph discovery and authoritative field/path recall. A hit in tiers 1/2 does not eliminate all tier-3 checks; revisions/readiness remain required. Recompute any decision-used fuzzy-score metadata at the request time, rather than returning a frozen cached belief score.
6. Assemble labelled, deduplicated context: trusted agent instructions; supported user/trip essentials; selected card text; additional evidence and current request. Source-derived text remains data and cannot become tool permissions or agent instructions. Return the exact claim dependency union so later work registration can cite it.
7. Validate the snapshot again before response emission or dependent work. GPU failure changes residency, not evidence authority or readiness.

### Initial configurable resource bounds

| Resource | Proposed first bound | Overflow behavior |
| --- | --- | --- |
| Tier-1 prompt text | 1024 agent + 1024 traveller/trip tokens | Move soft detail to cards; mandatory overflow is a visible capacity failure |
| Selected tier-2 cards | At most 3, at most 512 tokens each | Select fewer or compile focused cards; do not silently clip constraints |
| Additional tier-3 prompt evidence | At most 2048 tokens | Narrow the task/return capacity state when mandatory evidence cannot fit |
| Hot host payload cache | 32 MiB global accounted text/manifest payload; at most 256 entries | Weighted LRU for whole entries; this does not bound Python/model/store process RSS |
| Active card catalog | At most 4096 cards; at most 512 rendered tokens per active card | Admit task-specific working sets; durable definitions can be longer and stay outside the hot tier |
| Card-owned GPU allocations | At most 64 MiB plus separate measured runtime reserve | Admission, LRU eviction and CPU fallback; no allocation ceiling claimed for all models |
| Mood derivative / general cache lifetime | 30-minute idle mood expiry / at most five-minute cache residence | Explicit shorter expiry/next validity boundary wins; reads do not renew mood state |

All defaults are design decisions to verify, not measurements or implemented configuration. Counting includes source labels and provenance included in prompts, not just prose. If the consumer runtime/tokenizer is unknown, require it at setup before claiming a token cap; UTF-8 byte bounds are only an additional transport/storage limit.

The context assembler must satisfy `system_and_tools + current_turn_and_history + tier1 + cards + extra_evidence + reserved_output <= model_context_limit` with the **actual** consumer tokenizer/chat template. The maximum memory portions above total 5632 tokens and are ceilings, not a requirement to fill them. Reduce optional cards/history before protected requirements; if the model's context is too small, report capacity/narrow the task. Longer prompts can increase prefill latency even when lookup is faster.

The 64 MiB cap concerns GPU allocations owned by the card adapter, including temporary/copy buffers. For reference, 4096 x 384 float32 embeddings contain 6 MiB of raw payload before handles, duplicates and workspace. Existing vector dimensionality is 384; model/version/dimension are part of the index identity. Actual allocator accounting and OOM admission must be measured. GPU ranking for a small catalog may lose to CPU transfer/kernel overhead; do not predict a speedup.

The semantic GPU representation is required to demonstrate the requested VRAM path before integration, but **correctness and useful operation must not depend on GPU availability**. The existing CPU model profile remains supported. Local generative KV-prefix caching is a later independent adapter, not required for this context contract.
