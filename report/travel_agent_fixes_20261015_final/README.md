# Travel memory fixes and verification — 15 October 2026

The gaps demonstrated in the [original audit](../travel_agent_review_20261015/README.md) have been addressed. The final-source replay passes **24 of 24 scenario checks** using real HTTP calls, BGE embeddings, FalkorDB, Qdrant, RAM caching and CUDA card matching. The original failing audit is preserved.

## What changed

| Original problem | Implemented behavior | Replay evidence |
| --- | --- | --- |
| Important saved restrictions missing from a `ready` brief | Discover the exact trip/session's saved atomic fields. Every active rule/instruction is mandatory for every travel task, including unfamiliar field names. Protected profile rules also survive selection. | [Itinerary](09-planner-itinerary.md), [flight](10-planner-flight.md), [hotel](11-reviewer-hotel.md) |
| Brief-only plans did not notice a walking change | The brief now supplies the walking rule and its exact evidence ID. Both work controls use only context-provided evidence and require review after 500 m changes to 50 m. | [Brief-only handoff](exchanges/45-brief-only-handoff-after-walking.json) |
| Trip mood disappeared when a session ID was supplied | An empty session mood inherits the trip mood with its actual scope label. Explicit, disputed, expired or retracted session mood is not silently replaced by a trip mood. Reads do not extend its lifetime. | [Inherited trip mood](09-planner-itinerary.md), [explicit session](exchanges/25-session-itinerary.json), assembly regressions |
| Original multi-part travel intake required manual structuring | Local grammar recognizes all 14 atomic fields in the original message. An unsupported, conflicting or conditional clause still sends the whole confirmed message to review. | [Intake status](exchanges/03-raw-status.json), [intake brief](04-raw-blocks-planner.md), [ambiguous status](exchanges/69-ambiguous-status.json), [blocked ambiguous input](exchanges/70-ambiguous-blocks.json) |
| Bengaluru updates paused Goa and discarded its cached brief | Readiness/invalidation use explicit claim scopes. Goa stays available and warm while Bengaluru is pending and after processing. Relevant/global changes still block. Work gates also inspect cited evidence/prerequisite scopes. | [While pending](exchanges/50-goa-blocked-by-other-trip.json), [after processing](exchanges/53-goa-after-other-trip.json) |

Two adjacent problems were also reproduced and fixed during incremental checks: dropping an oversized optional card now preserves its source facts in additional evidence, and a trip preference/session field cannot hide a protected profile rule. Different values for a hard requirement across scopes require clarification rather than an inferred exception. Mandatory overflow produces a visible capacity error.

The new snapshot check hashes relevant claims, sources, identity links and durable event state. It still notices direct graph changes and does not treat unrelated task ownership updates as changed travel facts. Structured claims determine relevance even when their event envelope names another trip.

## Travel result

The same assistant simulated planner and reviewer. The checks use the actual returned brief and the original fictional supplier catalog. There was no independent generative-agent model or external booking.

| Stage | Simulated decision | Total |
| --- | --- | --- |
| Initial INR 90,000 cap, 500 m walking limit | Morning comfort flights, accessible resort, two activities on separate days | INR 72,600 |
| Reduced INR 65,000 cap, 500 m limit | Morning saver flights, accessible garden hotel, same two activities | **INR 58,600**, leaving INR 6,400 |
| Walking reduced to 50 m | **Pause**: no catalog hotel qualifies; the closest approach is 80 m | No approved replacement |
| Current budget deleted | Memory reports `needs_information`, `budget: missing`; neither old cap is reused | Await reconfirmation |

The reviewer rejects stairs-only accommodation, long approaches, boats and late-night flights from the fixture. Saved general interests in boat rides remain identifiable as profile preferences; the trip's no-boats rule takes precedence. The new brief includes all 12 scenario-critical fields for each task, and the planner does not need extra restriction lookups for these decisions.

`ready` establishes usable memory for the declared fields. It does not establish that a suitable supplier offer exists. The 50 m brief correctly contains that limit, and the simulated reviewer correctly stops when the catalog cannot satisfy it.

## Verification

- **236 ordinary tests passed**, with 6 optional tests deselected: [JUnit](../three_tier_fixes_full_suite_20261015.xml).
- **2 actual CUDA tests passed**: [JUnit](../three_tier_fixes_cuda_20261015.xml).
- Edited application modules and regression tests passed Ruff checks.
- **24/24 recorded scenario checks passed**: [results](results.json), [check table](checks.csv).
- New regressions were first run to reproduce each failure, then rerun after the corresponding fix. See the [incremental log](../../.scratch/three-tier-memory/implementation.md).
- [Final source hashes](implementation_hashes.json), [sanitized HTTP transcript](transcript.ndjson), [replay runner](replay.py), [result checker](review_results.py).

The first post-fix replay is retained in `../travel_agent_fixes_20261015/`. Its extra audit status call used an incorrect route and returned 404; the pending-context response independently contained the required `needs_review` receipt. The final-source replay corrects that harness call and receives HTTP 200 from `/v1/events/status`. No product finding is based on that harness error.

## Limits and operating state

This is one synthetic family trip plus an alternate trip and a second user. It establishes the tested behavior, not general language accuracy, supplier feasibility or production-load readiness. The local grammar remains deliberately bounded; unsupported language needs review or a separately evaluated interpreter. Trip/date parsing currently covers the explicit same-month format tested here.

Journal fingerprinting streams a tenant's event history, and temporal-boundary checking remains conservative across the graph. These paths have not been optimized or evaluated for a large multi-user deployment. Unscoped discovery, global/identity updates, and profile-only/unknown work dependencies retain conservative blocking. GPU card storage still holds one active catalog, so changing tasks/users can replace it.

Work tracks exact cited evidence. It cannot infer arbitrary uncited assumptions; agents should obtain fresh context for new decisions and revalidate after generation. Protected cross-scope differences may be compatible in reality, but this implementation requests clarification rather than guessing that they are exceptions.

The audit service was stopped after the replay. Isolated evidence remains local. The travel site was not integrated, no external action was performed, and existing application configuration was preserved.
