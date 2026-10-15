# Travel-Agent Role-Play Audit — 15 October 2026

**The memory safeguards work for the tested changes, but the automatic briefs are incomplete for this travel scenario.** Important saved requirements can be missing even when context says `ready`. I would not treat this first implementation as sufficient on its own for unattended travel planning.

The same assistant played planner and reviewer, reading actual API outputs and making the decisions. This was not a run of independently configured generative agents. The underlying HTTP service, FalkorDB, Qdrant, BGE embeddings, RAM cache and CUDA-resident card matching were real. Queue processing was deliberately stepped by an audit-only harness to inspect pending states.

There were **67 recorded HTTP calls** and **21 scenario checks: 15 passed, 6 exposed gaps against the scenario's expectations**. Several gaps share one root cause; this is not a statistical accuracy score or six independent software bugs. **No implementation fixes were applied.** Hashes of 133 existing application/test/script/configuration files are unchanged.

## The travel scenario

All traveller identities, offers, hotel names, costs and access distances are fictional test fixtures. No availability, booking or live price was asserted.

Riya and her mother plan four nights in Goa, 10–14 December 2026, departing Delhi. The original total budget is INR 90,000, later reduced to INR 65,000. Requirements include vegetarian food, morning flights, step-free accommodation, no more than 500 metres walking, no boats, and at most one scheduled activity per day. Riya usually likes active holidays and boat rides; this particular trip should be relaxed.

| Draft | Flights for two | Four-night hotel | Transfers | Meals | Reserve | Activities | Total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Initial | 34,000 | 24,000 | 4,000 | 6,000 | 4,000 | 600 | **72,600** |
| Revised after lower cap | 28,000 | 16,000 | 4,000 | 6,000 | 4,000 | 600 | **58,600** |

The revised draft leaves INR 6,400 under the INR 65,000 cap. It uses morning flights and a step-free hotel, with one short beach visit and one seated food activity on separate days. The reviewer excluded the late-night flight, stairs-only hotel, hotel requiring a 900 m approach, boat cruise and beach requiring a 1200 m approach. These checks required additional long-term-memory lookups.

Later, the simulated user tightens walking to **50 metres**. The existing catalog then has no suitable hotel: even the closest approach is 80 m. The roleplayed reviewer stops and requests new suitable options. A separate deletion test subsequently removes the current budget; the core correctly reports it missing. The revised draft is a valid intermediate result under the earlier 500 m constraint, not an approved plan after these later changes.

## What worked

| Behavior | Actual observation |
| --- | --- |
| All three memory tiers | Distinct agent profiles and scoped briefs; actual RAM cache hit; selected cards in CUDA memory; source knowledge in graph/vector stores |
| Long-term recall | Hybrid search found the original trip; exact field recalls recovered walking, boat, activity, party and flight restrictions |
| Pending user changes | Old context and task completion returned HTTP 409 while the budget change was pending |
| Accepted budget replacement | New brief contained 65,000; old context proof became invalid; related work required review |
| Work ownership/history | Reviewed draft could be completed; another agent received `already_completed`; later changes preserved completion history while adding review requirements |
| User/trip isolation | Goa and Bengaluru kept their different budgets; Riya and Arjun kept separate preferences; cross-user context proof was refused |
| Deletion | Deleting the revised budget produced `needs_information`/`budget: missing`; neither 65,000 nor the old 90,000 was silently reused |
| Unclear intake safety | A complex message the local interpreter could not understand was preserved and blocked work rather than being guessed |

## Problems found

### 1. High impact: the automatic brief omits important stored restrictions

The [actual itinerary brief](09-planner-itinerary.md) says `ready` and includes Riya's general interest in **boat rides**, but omits the trip's explicit **no-boats rule**, **500 m walking limit**, **one-activity-per-day limit**, **party size**, and **step-free requirement**. The [flight brief](10-planner-flight.md) also omits the saved departure city, party size and morning-flight requirement. The [hotel brief](11-reviewer-hotel.md) includes step-free access but omits the walking limit and party size.

The facts were not lost: [walking recall](exchanges/15-recall-walking.json), [boat restriction recall](exchanges/16-recall-boats.json), and [hybrid discovery](exchanges/22b-hybrid-discovery.json) returned them. The problem is selection into the automatic brief/cards. The current [task field list](../../memory/context/runtime.py:21) allows a small fixed set of fields, and the [ready status](../../memory/context/runtime.py:176) checks the four built-in required fields. It does not establish that every important trip rule reached the agent. No model-generated bad booking was observed; the demonstrated failure is missing constraints, with a concrete unsafe recommendation risk.

### 2. High impact consequence: a change can escape review when work cites only brief-provided evidence

I registered two controls around the INR 58,600 draft. The reviewed version used **17** evidence IDs, combining the automatic context with the reviewer's additional recalls. The brief-only control used the **9** IDs supplied by context.

After the walking limit changed from 500 m to 50 m:

| Work record | Observed result |
| --- | --- |
| Reviewed version with the walking evidence | `can_continue: false`, `needs_review: true`; earlier completion retained |
| Brief-only control | **`can_continue: true`, `needs_review: false`** |

The [fresh automatic brief after the change](46-fresh-context-after-walking.md) still said `ready`, and still did not contain the new walking limit. [Direct recall](exchanges/47-direct-updated-walking.json) correctly returned 50.

This is an end-to-end coverage failure, not proof that graph updates were lost. The graph [tracks exact cited dependencies](../../memory/lifecycle/service.py:1354); it cannot flag an uncited requirement. The brief omitted the evidence needed to register that dependency. The deliberately brief-only control demonstrates what an agent relying on the provided brief/dependency list would miss.

### 3. Scope limitation: a trip mood does not carry into a session automatically

A trip-scoped `relaxed` mood existed and was current. With a normal session ID supplied, [the initial brief](09-planner-itinerary.md) showed `mood: missing` and selected no relaxed card. [The same trip without a session ID](exchanges/13-trip-mood-no-session.json) selected that card. An explicitly session-scoped mood later [worked](25-session-itinerary.md).

The [lookup uses exact session scope](../../memory/context/runtime.py:124); it does not inherit the trip mood. This matches the narrow implemented lookup policy, but is a gap if the agency expects a trip-wide mood to apply across ordinary agent sessions. It is not a claim that the trip mood was deleted or that permanent personality should override a session.

### 4. Language limitation: ordinary multi-part travel intake needs interpretation outside the local grammar

The initial natural-language message containing dates, people, currency and multiple requirements became `needs_review`, and the planner was blocked. To continue the scenario, the simulated user explicitly confirmed structured fields. The conservative [local interpreter](../../memory/shared/interpreter.py:13) is not a general travel-language agent. Blocking was correct; automatic understanding was not established. No hosted interpreter was configured or evaluated here.

### 5. Operational trade-off: an unrelated trip can pause the current trip

While a separate Bengaluru-trip event was pending for Riya, Goa context also returned HTTP 409. After processing, Goa's RAM cache was cold again despite its facts being unchanged. A pending event for **Arjun**, a different user, did not block Riya.

This is the intentionally conservative [per-user readiness/cache boundary](../../memory/shared/service.py:239). It preserves isolation and safety, but couples multiple simultaneous trips for one customer. It is an operational limitation, not evidence of cross-user leakage.

## Evidence and limits

- [All checks and coverage](results.json), [check table](checks.csv), [field coverage table](coverage.csv).
- [Planner/reviewer initial decisions](agent_decisions_initial.json), [revised decisions and arithmetic](agent_decisions_revised.json), [final reviewer stop](agent_decision_final.json).
- [Complete sanitized API transcript](transcript.ndjson), [synthetic travel fixture](travel_fixture.json), [audit-only harness](harness.py).
- [Source before](source_before.json) and [source after](source_after.json): identical hashes for 133 protected files. Only isolated audit fixtures, requests, reports and runtime data were added.

The ordinary queue was stepped manually for pending-state tests. This is one scenario plus an alternate trip and second user, not a load/crash study or an independently blinded agent benchmark. HTTP timings are recorded per exchange but are not a controlled CPU/GPU comparison. Host timestamps advanced substantially between later phases; the session mood had expired by the walking-limit phase, so mood-expiry observations are not treated as an independent controlled test. The earlier budget proof check occurred within its own fresh sequence.

One initial audit search used incorrect argument names (`top_k`/`mode`); the corrected `k`/`retrieval_mode` call succeeded. This harness call error is retained in the transcript and excluded from product findings.

The audit service has been stopped. Its isolated graph/vector evidence remains available locally. **No fixes or site integration were performed.**
