# Memory reliability fixes — 15 October 2026

**The confirmed defects are fixed and tested.** The full hosted-agent scenario now passes **52/52 application controls**. This is a result for the tested synthetic workflow, not a claim of perfect language-model accuracy or production travel readiness.

The important change is that remembering the right information and accepting a travel decision are now checked separately. The model proposes an answer; code verifies the current requirements, prices, dates and evidence. A bad proposal is replaced with a clearly labelled, verified catalog option or paused when none fits. Raw model answers remain in the evidence.

## What changed

| Audited problem | Fix | Regression evidence |
| --- | --- | --- |
| A new restriction did not stop existing work | Work stores the subjects/scopes and mandatory fields known when it was registered. Handoff discovers newly active requirements, including future-dated and session rules, and requires review. Claim/completion also enforce this check. | New trip/global/session restrictions, unrelated trips, future activation and completed-work reuse tests. |
| Expired prerequisites did not stop dependent work | Handoff recursively rechecks prerequisite evidence at the current time. Reviews are bounded to 64 tasks, and cycles fail closed. | Parent/child/grandchild expiry test. |
| A wrong extracted number could become protected | Intake requires a verbatim field quote, numeric/value agreement with the source, correct units, types/bounds and completeness checks. An invalid interpretation writes no semantic claims; the original receipt remains available and blocks action. | Injected 90,000-for-65,000 error, dropped qualifiers/negation, malformed values and zero-partial-write tests. |
| Polite/multi-field updates became assertions | Each field gets its own source-grounded update action. Polite requests and coordinated updates supersede both existing rules; an explicit “keep” clause does not inherit another field's change. | Unit/integration tests and two fresh NVIDIA update calls. |
| Unsupported or incomplete information slipped through | Missing/empty/unknown fields, unsupported hard requirements and incompatible quote terms stop for review. Conditional wording is preserved as an episode for review. | Invalid dates/counts/distances, omitted clauses, unsupported requirements, currencies/party/date mismatch tests. |
| Model arithmetic and review errors could reach work | The small catalog calculator uses exact decimal arithmetic and current structured memory. A complete context proof and a review of the exact plan are required by `complete_reviewed()`. No rejected/paused/stale plan is registered as accepted travel work. | Manual expected totals, deliberate corruptions, changed-during-generation and changed-after-review tests; live HTTP workflow. |
| Fuzzy scores sometimes moved the wrong way | Product conjunction replaces minimum conjunction in the complete Sugeno rule base. Ordered rule centers now preserve directional behavior. Protection/currentness remain separate hard rules. | The original 21,606-evaluation grid now has zero quality, conflict, age or support reversals. |
| Card message links were empty | New sources retain `event_id`. Old service sources use their retained receipt metadata as a fallback when compiling cards. | Fresh and legacy source/card tests plus live metadata inspection. |
| Evaluator accepted malformed plans/pauses | Strict decision/type/selection checks, real calendar dates, duplicate detection, null/empty pause checks and actual affordability checks replace permissive branches. Both flight directions and food metadata are checked. JSON rejects duplicate keys, nonfinite constants and numeric overflow. | Counterexamples from the audit plus added return-flight, food, decimal-date and stream-stall cases. |

Implementation: [memory lifecycle](../../memory/lifecycle/service.py), [authenticated work binding](../../memory/shared/service.py), [grounded intake](../../examples/travel_intake.py), [catalog checks/solver](../../examples/travel_planning.py), [guarded agents](../../examples/nvidia_memory_agents.py), [live runner](../../scripts/evaluate_nvidia_memory.py).

## Final verification

| Check | Result |
| --- | --- |
| Final default pytest suite | **313 passed**, 6 opt-in tests deselected; 149.42 seconds |
| Actual CUDA checks | **2 passed**; 4.45 seconds |
| Final guarded-agent follow-up | **26 passed**; 19.11 seconds, including safe retries of already-completed reviewed work |
| Completed three-tier NVIDIA run | **52/52 controls**, no run error; **148.03 seconds**, 15 hosted calls |
| Additional natural-language update checks | **2/2 passed** against NVIDIA, including polite + two-field wording |
| Fuzzy direction grid | **21,606 evaluations**, zero sampled directional reversals |
| Static checks | Ruff and Windows-aware Git whitespace checks pass |
| Independent outcome check | Captured supplier totals recomputed without importing the application checker; pause, negative rejection, provenance and core hashes verified |

Evidence: [full pytest results](full-suite.xml), [CUDA results](gpu-tests.xml), [completed live run](live_run_5/results.json), [update checks](live-update-check.json), [fuzzy sweep](fuzzy-sweep.json), [independent verifier](verify_run.py), [verification record](verification.json).

The full-run application controls reuse the application checker. They are supplemented by independent expected-total tests and the separate captured-result verifier; 52/52 should not be read as 52 independent measures of general planning accuracy. Source hashes for the memory core match the completed live run. The final strict numeric-overflow client guard is covered by the final pytest suite and subsequent live update checks. A final review added idempotent handling of already-completed work; its full guarded-agent test group was rerun afterward. [Follow-up tests](final-agent-tests.xml).

## What the agents actually did

| Stage | Accepted application result | Raw model behavior |
| --- | --- | --- |
| Initial 90,000 budget | Comfort flight + resort + two activities; **72,600**; approved after program checks | Price/constraints were correct, but citations were incomplete. The explicitly labelled catalog solver supplied the accepted result. |
| Budget reduced to 65,000 | Comfort flight + garden hotel + two activities; **64,600**; approved | The model proposal passed the current checks, including complete evidence. |
| Deliberately bad plan | **Rejected** | The raw reviewer rejected it but used an outdated budget field. Program review used the current 65,000 cap. |
| Walking reduced to 50 metres | **Paused**, no suppliers/activities/cost selected | The planner paused correctly. The raw reviewer said `reject`; program review correctly returned `pause`. |

This distinction matters: the underlying model can still make mistakes. The fix makes those mistakes unable to become accepted output in this bounded example. Reviewer decisions are explicitly labelled `deterministic_constraint_review`; they are not presented as independent model agreement. [Accepted decisions](live_run_5/decisions.json), [raw model requests/responses](live_run_5/model-latency.json), [per-role checks](live_run_5/agents/).

Only checked, reviewed initial/revised plans are completed through the application acceptance method. Source changes subsequently invalidate their use. Completed history remains retained. Generic `/v1/work` remains a memory/ownership API; the travel application must use the guarded acceptance method for business approval.

## Timing and memory after the fixes

| Operation | Median | p95 | Samples |
| --- | ---: | ---: | ---: |
| Context without RAM reuse, CPU cards | 507.9 ms | 528.7 ms | 12 |
| Warm context, CPU cards | 55.8 ms | 77.5 ms | 12 |
| Warm context, CUDA cards | 56.4 ms | 104.6 ms | 12 |
| Hosted NVIDIA complete response | 7.18 s | 19.87 s | 15 |

The completed scenario took 148.03 seconds including setup, ingestion, generation, program/work validation, memory checks and restart. Timings are a small sequential diagnostic, not a load/SLA benchmark. The two-card catalog still shows no established GPU speed advantage. [All timing samples](live_run_5/results.json).

At the final scenario snapshot:

- **Tier 1:** 18,351 bytes of accounted cached payload, across two contexts. This includes the empty second-user isolation control and is not total process RAM.
- **Tier 2:** 3,072 bytes of active CUDA vectors for two cards; 706 bytes of unique cached Markdown text across three versions, in host RAM. The CPU fallback matrix is another 3,072 bytes. Configured GPU arena limits are not measured allocations.
- **Tier 3:** 8 source records, 28 claims, 3 scopes and 2 work records; 67 graph nodes and 157 edges. Graph logical JSON size is 113,511 bytes. Eight vectors contain 12,288 raw float32 bytes; Qdrant files occupy 53,776 bytes.

The graph JSON is a logical measurement. The generic 64-byte Redis key wrapper in raw snapshots is **not** graph physical memory. Journal open-file sizes change after checkpoint/close. Tier data overlaps, so these figures must not be added as a single physical footprint. [Full storage snapshots](live_run_5/storage.json).

All eight source messages entered through the same authenticated event API; no caller selected a cache tier. The retained source text totals 747 UTF-8 bytes. The second trip's explicit currency was also extracted, giving 28 claims instead of the prior run's 27. Card/template routing remains configured by field importance, task, mood, scope and budgets; fuzzy scoring does not choose tiers. The synthetic supplier catalog remains task data, with explicit route/date/party/currency/food metadata, not a source of future test answers. [Ingested text/claims](live_run_5/ingestion.json), [clean supplier catalog](../../examples/fixtures/travel_catalog.json).

## Intermediate failures were retained

The implementation was checked incrementally. Four early post-fix attempts stopped safely; they are not counted as successful agent runs:

| Attempt | What stopped it | Resolution |
| --- | --- | --- |
| [Run 1](live_run_1/results.json) | Model added unsupported `meta` keys | Explicit server-guided schema; local strict validation retained. |
| [Run 2](live_run_2/results.json) | Model returned interests as a string | Predicate-specific schema types; local domain checks retained. |
| [Run 3](live_run_3/results.json) | New unit check mistook “activity per day” for a per-day budget | Restrict unit checks to the budget's clause, preserving decimal amounts; regression tests and replay of captured intake. |
| [Run 4](live_run_4/results.json) | Model emitted formatting whitespace until the output limit | Compact field-quote prompt, bounded guided whitespace and a client stall guard. Truncated output remained rejected. |
| [Run 5](live_run_5/results.json) | Completed | 52/52 application controls; raw-model faults still disclosed above. |

NVIDIA's documented schema and whitespace mechanisms were checked against the actual endpoint, including an opposing-format schema probe. Schema controls output shape; source/value and business checks remain application responsibilities. [Schema probe](schema-probe.json), [NVIDIA structured generation](https://docs.nvidia.com/nim/large-language-models/1.15.0/structured-generation.html), [NVIDIA guided-whitespace notes](https://docs.nvidia.com/nim/large-language-models/1.13.0/troubleshoot.html).

## Compatibility and limits

Existing work created before requirement snapshots now requires a fresh reviewed work version. It is not automatically declared safe against today's rules; completed history is preserved. Newly compiled cards can resolve older service receipts without rewriting original source content. Ordinary fuzzy scores change under the versioned v2 method and remain ranking signals, not calibrated truth probabilities.

The sample travel validator supports the supplied INR, two-person, four-night catalog and declared constraints. Unsupported requirements/quote terms stop for review. It does not establish universal free-text understanding, real supplier availability, a booking system, or production-scale concurrent performance. Conditional wording is intentionally conservative. No itinerary was executed and no travel website was integrated.

The NVIDIA credential was used only through transient process environments. Public artifacts redact context/lease credentials; the verification script scans them. This change includes the implementation and its captured test evidence. The head and dirty-worktree fields in the verification record describe the source state when testing was performed, before publication.
