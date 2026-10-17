# Reliability audit — 15 October 2026

**The complete system is not ready to approve travel plans. The second check found genuine memory-lifecycle gaps as well as model, intake-adapter and evaluator mistakes.** The previous “22/22 memory checks passed” remains a description of that run, but is insufficient evidence of memory reliability. This audit supersedes its broad interpretation; the original captures are preserved.

No memory implementation, agent implementation or original evaluator was repaired. New files contain research, diagnostic probes, captured model responses and this report. No travel was booked or executed.

## What was checked again

| Check | Result | Meaning |
| --- | --- | --- |
| Existing offline suite | **241 passed**, 6 deselected; 107.58 s | Existing scenarios still pass; they missed the new cases below. Offline model fixtures are used. |
| New targeted audit probes | **23 reproduced**, 7.84 s | These tests deliberately assert the observed bad behavior and protective controls. “Passed” here means the counterexample was reproduced, not that the defect is fixed. |
| Actual CUDA tests | **2 passed**, 23 deselected; 4.18 s | Real device residency, selection parity and service behavior still work. |
| Fuzzy direction sweep | **21,606 score evaluations** | 8 quality-direction reversals and 63 conflict-direction reversals on the sampled grid. No aging/support direction reversals on that grid. These are controlled calculations, not accuracy percentages. |
| Fresh NVIDIA calls | **8 calls, 250.66 s** | Three same-prompt direct/thinking pairs plus two natural-language update checks. One observation per condition, not a statistical benchmark. |
| Primary-source research | **6 sources** | Official NVIDIA model/docs plus original multi-agent, self-correction and arithmetic-tool papers. |

Evidence: [existing suite](existing-suite.xml), [audit probes](probes.xml), [CUDA checks](gpu-tests.xml), [probe code](probes.py), [individual results](probe-results/), [fuzzy sweep](fuzzy-sweep.json), [fresh calls](live/summary.json), [research](primary-source-research.md).

The new probes use real isolated FalkorDB graphs, embedded Qdrant and the normal shared-memory/context code, with deterministic fixture embeddings. Their graphs are cleaned by the existing test fixture. Model-prompt comparisons replay previously captured, correctly scoped memory; they do not claim to re-run the entire ingestion/GPU benchmark. Two new intake calls do use the real NVIDIA model and the unchanged intake adapter. A simulated wrong extraction is clearly identified below.

## Confirmed problems, largest consequences first

### 1. A newly added restriction does not invalidate existing work — high severity, memory core

**Example:** create a trip plan, then add “avoid boats” as a new confirmed rule. The old context proof correctly becomes invalid, and a fresh context correctly includes `avoid_boats`. However, the old work's handoff still returns `can_continue: true`. The agent can acquire it and mark it **completed after the new restriction**.

**Why:** work tracks exact claims it previously used. Ingestion invalidates work when those claims are replaced or contradicted. A brand-new field has no old claim to replace and is absent from the old work's `USES` edges. Work completion does not require a fresh context proof covering the current set of trip requirements. The saved plan description is just text; the service does not interpret a boat trip itself.

This is a gap between two paths: fresh context validation behaves correctly, while continuing existing work can bypass the newly added requirement. A caller that always obtains and validates fresh context has more protection than one relying on handoff/work status alone.

Evidence: [new-restriction probe](probe-results/new-restriction.json). Relevant code: [ingestion invalidation](D:/Opencode_/reserchpaper/memory/lifecycle/service.py:511), [work handoff](D:/Opencode_/reserchpaper/memory/lifecycle/service.py:1386), [completion gate](D:/Opencode_/reserchpaper/memory/shared/service.py:583).

### 2. An expired prerequisite does not stop its dependent work — high severity, memory core

**Example:** task A checks an access requirement valid for another 100 seconds, then completes. Task B depends on A and uses another current claim. Advance the test clock beyond the access claim's expiry. Asking about A returns `can_continue: false` and evidence status `expired`; asking about B still returns `can_continue: true`.

**Why:** handoff rechecks the requested task's own evidence. It checks a prerequisite's stored status/validation flag but does not recursively re-evaluate that prerequisite's evidence at the current time. Expiry is computed on read and does not itself persist a stale flag through the dependency graph. The earlier tests covered explicit replacements, which do propagate stale flags, and did not cover this time-driven dependency case.

This uses an advanced query clock, not 100 seconds of actual waiting. Evidence: [expired prerequisite](probe-results/expired-prerequisite.json), [prerequisite checks](D:/Opencode_/reserchpaper/memory/lifecycle/service.py:1417).

### 3. A mistaken extraction can become a protected “1.0” rule — high severity, intake integration

**Fault-injection example:** raw text says “My total budget is INR 65000.” A deliberately faulty model stub returns `budget: 90000`. The unchanged intake/service path accepts 90,000 as protected, with fuzzy score 1.0.

**Why:** shape/type checks do not verify that the extracted number is supported by the original words. `confirmed=True` applies to the source event; all extracted rule claims inherit that authority. Protection expresses current user authority. It cannot prove that a language model copied the user's meaning correctly. Fuzzy scoring is bypassed for a current protected rule, so it cannot repair this error.

This demonstrates an absent safeguard, **not an observed NVIDIA 65,000-to-90,000 misread in the fresh calls**. The generic core trusts its interpreter; the travel integration currently has no field-to-source grounding check. Evidence: [fault injection](probe-results/extraction-grounding.json), [rule protection](D:/Opencode_/reserchpaper/memory/lifecycle/service.py:311), [service interpretation](D:/Opencode_/reserchpaper/memory/shared/service.py:354).

### 4. Natural wording breaks update handling — medium severity, travel adapter, confirmed live

| Source wording | What the NVIDIA model extracted | What the unchanged adapter sent onward |
| --- | --- | --- |
| “Please change my total trip budget to INR 65000.” | Correct value, `supersede` | Changes it to `assert` |
| “Change my total trip budget to INR 65000 and my maximum walking distance to 50 metres.” | Both correct values, both `supersede` | Budget supersedes; walking becomes `assert` |

**Why:** the adapter only recognizes change verbs at the beginning of the message and chooses a single changed field, giving budget precedence over walking. It also forces dietary changes and other fields to `assert`. In this case the model understood the request and application code damaged its meaning.

The service integration probe confirms the polite budget update becomes a **dispute** against the old protected budget, blocking context rather than applying the requested replacement. That fail-closed behavior is a useful protection, but makes ordinary updates unreliable. It is not evidence of silent use of an old value.

Evidence: [fresh intake outputs and normalizations](live/summary.json), [polite-update service result](probe-results/polite-change-integration.json), [action logic](D:/Opencode_/reserchpaper/examples/nvidia_memory_agents.py:225).

### 5. Field types are only partly validated — medium severity, travel adapter

The adapter plus `ClaimInput` accept fractional/negative traveller counts, negative walking/budget, a fractional daily activity limit, a list as the destination, a plain string as interests and `not a date` as dates. These are synthetic malformed-extraction probes, not claims about their frequency in real traffic. Empty extracted fields are discarded individually, so a partial extraction can appear successful even when a source clause was not understood.

**Why:** `ClaimInput.value` intentionally supports arbitrary JSON for the generic memory engine. The travel adapter checks numeric/bool types for some fields but lacks complete travel-domain validators, bounds, integer checks and a completeness check against the source. A schema-valid generic memory claim is not necessarily a meaningful travel fact.

Evidence: `invalid-*` and `partial-extraction.json` in [probe results](probe-results/), [adapter checks](D:/Opencode_/reserchpaper/examples/nvidia_memory_agents.py:164), [generic value contract](D:/Opencode_/reserchpaper/memory/lifecycle/models.py:63).

### 6. Agents remember the right limits but still calculate and decide incorrectly — high severity, application behavior

The fresh direct-answer calls repeated the original failures:

- Initial selected offers cost **34,000 + 24,000 + 600 + 14,000 = INR 72,600**. The model again wrote **76,600**.
- With the current **65,000** cap visible, it again chose those 72,600 offers and wrote **76,000**, acknowledging the overrun instead of choosing a compliant plan.
- At least two feasible fixture combinations exist under 65,000: comfort flight + garden hotel at **64,600**, or saver flight + garden hotel at **58,600**, including the same two activities and fixed costs.
- The fresh initial reviewer again returned budget **76,600**, even though its prose mentioned the true **90,000** limit. Its reject label did not demonstrate that it understood the arithmetic error.

**Why the system permits this:** the model generates a plan in text/JSON; no mandatory application calculation/constraint check gates `TravelAgent.respond()` returning ready. It validates memory freshness only. The evaluation's independent checker scores results afterward, and its lifecycle probes register/complete work even when the itinerary fails or the reviewer rejects it. A completed work record therefore proves neither feasibility nor reviewer approval. No booking was performed.

Planner/reviewer share model weights, and the reviewer sees the draft. Their repeated mistakes establish unreliable review, but do not isolate whether the cause is candidate anchoring, the model, prompt ambiguity or several factors. Source research supports external checks; it does not prove a single cause for this model. [MAST](https://arxiv.org/html/2503.13657v3), [PAL](https://arxiv.org/abs/2211.10435).

Evidence: [fresh call captures](live/), [original decisions](../nvidia_multi_agent_20261015_verified/decisions.json), [response status](D:/Opencode_/reserchpaper/examples/nvidia_memory_agents.py:338), [unconditional work probe](D:/Opencode_/reserchpaper/scripts/evaluate_nvidia_memory.py:474).

### 7. Fuzzy scores have small directional inconsistencies — medium severity, memory scoring

The earlier five examples behaved as expected, but the wider grid found counterexamples:

- At age 30 days, quality 0.1 and two independent groups, increasing conflicts **4 → 5** raises the score **0.3898049664 → 0.3911392686**.
- With age 30 days, one group and three conflicts, increasing source quality **0.25 → 0.26** slightly lowers the score **0.3685163220 → 0.3685050127**.

**Why:** the minimum firing-strength rule and normalization change several rule weights together. Individually sensible rule outputs do not guarantee that the final weighted controller is monotone. The sweep held other inputs fixed and independently reproduced a conflict reversal in pytest.

These are small ranking inconsistencies. They did not cause the observed protected-budget planning failure: protected/current rules bypass this controller, disputed hard fields are blocked, and agent prompts do not receive the full fuzzy calculation. The score is explicitly **not a probability of truth**, does not choose the cache tier, and was never statistically calibrated. No aging/support reversal was found on the sampled grid; that is not a proof for all inputs.

Evidence: [all sampled reversals](fuzzy-sweep.json), [exact reproduction](probe-results/fuzzy-conflict-reversal.json), [aggregation](D:/Opencode_/reserchpaper/memory/lifecycle/fuzzy.py:40).

### 8. Card source-event metadata is incomplete — low severity, provenance

Fresh integration checks again produce cards with empty `source_event_ids`, even when the originating receipt is known. The compiler reads `sources[*].event_id`; persisted source properties omit that top-level field. The receipt remains inside `metadata_json.service_receipt`, and claim/source IDs still resolve, so this is a missing convenience link, not loss of the original evidence.

Evidence: [fresh source/card comparison](probe-results/source-provenance.json), [compiler lookup](D:/Opencode_/reserchpaper/memory/context/compiler.py:30), [stored source properties](D:/Opencode_/reserchpaper/memory/lifecycle/service.py:294).

## Mistakes in the test itself

The independent checker also needs scrutiny. These new counterexamples all use its unchanged code:

| Counterexample | Observed result | Cause/consequence |
| --- | --- | --- |
| Otherwise valid plan with `decision: "banana"` | Every plan check passes | Any decision except `pause` falls into the plan branch; there is no decision enum gate. |
| Activity dated `2026-12-110` | Every plan check passes | Date bounds use string comparison instead of calendar parsing. |
| `pause` with a cruise activity and total 999,999 | Every pause check passes | Pause checks hotel/flight IDs but omit activities and the required null total. |
| Valid hotels exist, but total budget is INR 100 | A sensible pause is called incorrect | Feasibility is inferred from hotel walking/access alone; affordability/flights are not considered in the pause test. |
| JSON contains `NaN` | JSON-object parser accepts it | Standard parser permits a non-standard numeric constant by default. **The core claim validator does reject it**; this probe did not find persisted NaN claims. |

Evidence: [probe results](probe-results/), [checker](D:/Opencode_/reserchpaper/examples/nvidia_memory_agents.py:347). These flaws did not erase the originally observed arithmetic and budget failures, which can be recomputed directly from the supplier prices.

Other limits of the original evaluation:

- **46/50 is not 92% real-world reliability.** The checks are correlated and cover one synthetic trip, not 50 independent users/plans. Do not pool this audit's counterexamples into that score.
- A reviewer returning `reject` is not proof of a correct explanation. A `reject` instead of `pause` at the 50 m limit was a classification error; both roles actually stopped approving travel.
- Existing citation checks only ensure nonempty known claim IDs. They do not prove that a particular conclusion is supported or that every important requirement was cited.
- The date-boundary mistake and catalog contamination from earlier attempts were already disclosed. The contaminated attempt remains excluded, and its future budgets were not sent in the verified run or these paired replays.
- The original run fixed the source commit string in code and did not record thinking-off explicitly in each call artifact. Source and hashes establish that flag; this audit records it per call. The provider's precise serving revision/precision is unknown.
- Synthetic fixture availability does not establish real supplier availability, visas, weather, medical accessibility advice, currency conversion, or real booking correctness; none was claimed or tested.

## Reasoning-mode comparison: what it did and did not establish

NVIDIA's model card supports reasoning on/off, defaults to on, and recommends temperature 1.0/top_p 0.95. That makes reasoning mode worth checking, but does not establish that temperature zero or reasoning off caused these failures. Self-correction research is mixed, including evidence that temperature zero can help under particular prompts. [NVIDIA model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16), [Huang et al.](https://arxiv.org/abs/2310.01798), [Liu et al.](https://arxiv.org/abs/2406.15673).

The paired calls kept captured messages identical within each pair, temperature 0, top_p 0.95 and maximum completion tokens 5,000. Order alternated. The original baseline used 2,200 completion tokens and did not explicitly set top_p, so fresh-to-original comparisons are descriptive; the new direct/thinking pairs are the controlled comparison.

| Exact captured task | Direct-answer mode | Reasoning mode |
| --- | --- | --- |
| Initial planner | 8.29 s; completed, wrong 76,600 total | 72.88 s; hit 5,000-token limit, 4,852 reasoning tokens; no accepted complete response |
| Revised planner | 13.88 s; completed, over budget and wrong 76,000 total | 78.30 s; hit limit, 4,304 reasoning tokens; no accepted complete response |
| Initial reviewer | 12.48 s; completed, wrong budget field | 61.84 s; hit limit, 5,000 reasoning tokens; no accepted complete response |

The two direct-mode intake calls took 1.20 and 1.78 s and exposed the adapter mistakes above. All 8 calls together took **250.66 s**. Full configuration, provider usage, answer text and timing are retained; private reasoning text is not saved. The evaluation correctly rejected truncated responses.

**Conclusion of this comparison:** simply enabling reasoning within this bounded allowance was not a working remedy. It increased cost/latency and yielded no usable complete answer in these three cells. Because those responses were truncated, this comparison cannot determine answer quality with a sufficiently larger reasoning budget, or performance under NVIDIA's recommended sampling. It does not establish a general failure rate or the best possible configuration.

## What still looks sound within the tested scope

The new-restriction probe correctly invalidates the old context proof and renders the new rule in a fresh brief. The polite-update dispute correctly blocks a ready brief. Existing tests still cover tenant/actor isolation, pending receipts, accepted replacement, evidence expiry on directly requested work, cache rebuilding, ownership and rollback. The real CUDA checks still pass. These protections are meaningful even though they do not cover the two work-lifecycle holes.

Tier 1's “two halves” are equal **token caps**, not equal allocations of bytes. Tier 2 keeps card **vectors** in local VRAM; Markdown stays in host RAM. It is not NVIDIA's hosted generative cache. Templates, important fields and routing rules are application-configured, not a learned universal sorter. Tiers contain overlapping derived copies of durable data.

The original two-card measurement showed warm CPU **62.3 ms** versus warm CUDA **65.2 ms**, so no GPU latency advantage was established. Exact physical graph memory remains unresolved: the reported graph JSON is a logical serialization, not RAM consumption; the generic 64 B Redis wrapper is not the graph footprint. These measurement limitations were disclosed in the original report and were not silently treated as successes here.

## Repair priorities for a later implementation

No fixes were implemented. The evidence points to this order:

1. Make existing work account for new scoped requirements and recheck prerequisites when time changes their evidence.
2. Require a complete, current requirement set plus deterministic business checks before accepting/completing an itinerary. Model review can supplement those checks.
3. Validate source grounding and travel-domain types; handle each requested update independently of sentence wording.
4. Strengthen the evaluator with strict enums/calendar dates/pause feasibility and separate memory, model, review and test-harness outcomes.
5. Repair event links and investigate monotonic fuzzy aggregation with property checks; preserve protection/currentness outside scoring.
6. Then evaluate untouched holdout trips, varied phrasing, currencies/party sizes, negative controls, repeated runs and concurrent agents. Tune model configuration using complete answers, not only favorable samples.

The complete research explanation and its six sources are in [primary-source-research.md](primary-source-research.md). Reproduction scripts are [probes.py](probes.py), [fuzzy_sweep.py](fuzzy_sweep.py) and [live_comparison.py](live_comparison.py). Use `NVIDIA_API_KEY` only through a private process environment for the live script; no credential file is needed. The [verification record](verification.json) records implementation hashes and artifact checks.
