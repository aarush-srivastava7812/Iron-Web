# Proposed Route: One Memory Core, Three Outcomes

Updated for discussion, 2026-10-13. The user has confirmed a focused hackathon entry, a two-person team, at least eight hours per event day for the user, a paper direction centered on memory changes and agent handoffs, and preservation of the existing architecture. The remaining storage choice is vector placement. Detailed roles, benchmark threshold interpretation, memory-rule parameters, final research experiments and commercial target remain open. No benchmark or implementation is performed by this plan update.

## The destination in everyday language

Build a memory core that can support more than one application. Use a focused travel application to demonstrate it at Track 02. Afterwards, establish stronger reliability evidence for the research paper and for a second application/company pilot. Commercialization is an outcome to validate, not a property conferred by a working demo or a paper.

The two goals share one foundation but have separate success criteria:

| Outcome | What success would mean | What it does not prove |
| --- | --- | --- |
| Hackathon entry | A working, understandable, compelling demonstration of persistent memory and shared agent work, with FalkorDB central | Winning is guaranteed, the paper is novel, or companies will buy it |
| Research outcome | A reproducible, fair investigation of a precise reliability claim, including failures and comparisons | The system is automatically safe to deploy commercially |
| Reusable/company offering | Another application can use the core and a real pilot satisfies agreed operating/support needs | Demand, pricing and broad scalability are established without customers and measurements |

## First compare vectors, then add both paused ideas

Keep the current FalkorDB graph memory architecture. Mem0, MemPalace and Zep inform the design as references. The user has narrowed the route to one storage choice followed by additive graph-memory work; see [Existing Architecture, Reference Use and Work Order](issues/12-existing-architecture-and-work-order.md).

The memory-core sequence is:

1. **Compare vector placement first.** Use the same memories, questions, embeddings, graph behavior and evidence budget. Compare FalkorDB graph plus Qdrant vectors with FalkorDB graph plus native FalkorDB vector search. Measure typical/slow response times, complete-retrieval latency and output evidence quality, including reads while new memories arrive. The requested 5% condition is included; a relative tolerance is currently proposed pending clarification. See [Vector Comparison Plan](vector-comparison-plan.md).
2. **Choose from the results.** Select vector placement in [Vector Placement Within the Existing Architecture](issues/07-reusable-core-and-storage-boundary.md). Passing makes FalkorDB vectors eligible, not automatically adopted. Keep Qdrant if results fail or are inconclusive. Preserve the rest of the architecture in either case.
3. **Add the first pause to the KG.** Give revisable memories an explainable fuzzy value, explicit protected value 1, and retained contradiction/supersession links. Resolve acceptance, scope and authority before deciding which version is current. Keep both versions and trace affected work.
4. **Add the second pause to the KG.** Make relationships, conditions and source paths explainable. Use the graph to gather the needed evidence and check current state, disputes and unavailable answers. Test KG-only, vector-only and combined retrieval with varied questions and unseen raw inputs.
5. **Prove the additions together.** A changed memory updates only dependent work; another agent receives the current requirements and retained history. Repeat latency/output checks after the additions, and compare their individual contributions for the paper.

The comparison task comes first on the core lane. The teammate can continue travel-app/scenario work in parallel. This sequence brings the paused ideas into the build plan; their standalone prototypes are not silently merged or treated as finished production behavior. Cache research remains deferred.

## Two-person parallel work

The proposed division is user-led memory core and teammate-led travel experience/agent behavior. The user said the final role split is not complete; confirm who owns deployment, integration, the evidence log, tests, demo recording and submission.

Before deep work, agree a small exchange contract: what an application tells memory, what memory returns, what “saved”, “ready”, “uncertain” and “outdated” mean, and what an agent receives during a handoff. The teammate can work against clearly labelled development examples until the real service is ready. Replace those examples early in the event; no fixture should appear as real memory behavior in the submission.

The travel app should contribute its own travel-specific steps and information. The memory core should understand generic sources, events, facts, conditions, tasks, changes, users and handoffs. Prove this separation later by connecting a second application without rewriting the memory rules.

## Suggested event-day route

Times are planning estimates, not an approved allocation. The user stated at least eight hours per day, giving a minimum 32 hours across four days before accounting for integration and interruptions. Teammate availability is not established, so this plan does not assume another 32 hours.

| When | User/core lane | Proposed teammate/app lane | Evidence gate |
| --- | --- | --- | --- |
| October 13–14: preparation | Prepare the vector comparison, clarify 5%, agree the exchange contract and new-work boundary, and preserve the existing baseline | Agree scenario, independent development inputs, tools/data and shared responsibilities | A reproducible comparison plan and one shared demonstration contract; groundwork distinguished from event implementation |
| October 15: first core gate and working connection | Run the vector comparison as the first core task and decide placement; retain Qdrant if failing/inconclusive. Start the event's memory additions and real app connection on that choice | Build one focused travel flow and connect it to the real memory service | Recorded latency/output evidence and a placement decision; a real app write can be read in a later session |
| October 16: first paused idea and handoff | Add scoped fuzzy/protected memories, accepted changes, retained contradiction/supersession history and links to affected work; connect shared task/handoff state | Exercise the changed requirement and agent continuation in the travel flow | Score/rule explanations, protected behavior and both versions are visible; affected work is checked and the second agent resumes |
| October 17: second paused idea and reliability | Add explainable relation-aware retrieval; run KG/vector/combined question checks, missing-answer/dispute tests, repeat latency checks and test sharing/recovery/isolation | Refine the visible explanations and demonstration story; exercise end-to-end integration | Useful evidence paths, honest missing answers and measured graph benefits; the first pause still works through retrieval and handoff |
| October 18: freeze and submit | Fix the highest-impact failures, freeze the supported scope, verify clean setup and preserve final evidence | Finish demo video, explanation and submission packaging with assigned ownership | A reproducible final scenario, accurate feature claims, working setup and a submission buffer before the organizer deadline |

Verify official event times, submission requirements and permitted reuse through [Event Boundaries and FalkorDB Guarantees](issues/01-event-rules-and-falkordb-guarantees.md). Decide scenario/ownership through [Focused Travel Demonstration and Two-Person Boundary](issues/03-focused-demo-and-team-boundary.md). Final timings/cuts belong to [Staged Route, Integration Gates and Cut Lines](issues/10-staged-route-and-cut-lines.md).

## Proposed smallest complete memory proof

Use two agents working for the same user, and a second isolated user to test separation. The application needs enough travel functionality to make the memory behaviors meaningful, but the core proof is:

1. A message and tool result are saved with their original source and can be found in a new session.
2. A confirmed fact/preference, a past episode and a conditional procedure retain their distinct meanings.
3. An accepted requirement change preserves both versions and identifies which decision/task used the earlier version.
4. The next agent receives current requirements, completed/pending work, evidence and disagreements.
5. A dispute or pending authoritative change prevents an unsupported confident action.
6. Two agents trying to claim the same work do not both become the owner; repeated delivery does not repeat completed effects.
7. The second user's memories are inaccessible to the first user's agents.
8. A missing requested detail remains missing even if related notes were found.
9. Restart recovery preserves data and the relevant operating state; any unknown completion status is visible.
10. Removing relation-dependent processing loses a specific supported change/handoff behavior while retaining the same underlying text, rather than merely removing the graph picture.

This is a proposed scope. Set the precise acceptance checks in the memory, coordination, retrieval and core-boundary tickets rather than declaring these behaviors implemented.

## How the two pauses become work in this route

**Evolving memories:** after the vector gate, settle acceptance, authority, scope, time and history, then implement the smallest actual fuzzy rule model needed for the entry. Ordinary memories may decay or weaken and are capped at 0.99; protected accepted memories stay at 1 until an accepted direct change ends their current status. Keep old and new nodes, explicit change links, prior values and explanations. An unresolved conflict does not automatically promote the newest statement. Rule weights and half-lives need validation rather than inheriting the demo's arbitrary values. A high score must never authorize access or decide who owns a task. See [Memory Changes, Evidence and Authority](issues/04-memory-change-and-authority-contract.md) and [Retrieval and Fuzzy Scores: Separate Responsibilities](issues/06-retrieval-and-fuzzy-score-responsibilities.md).

**Retrieval:** extend the existing graph with useful claim/field, condition, evidence, change and dependency relationships. Combine discovery by words/meaning with bounded graph checks for current state, scopes, companion evidence and disputes. Show why evidence supports an answer. Separate “related result found” from “requested detail available”. Compare KG-only, vector-only and combined retrieval, then test automatic ingestion and final responses separately. Existing question checks are starting fixtures, not proof of a complete system. See [Retrieval and Fuzzy Scores: Separate Responsibilities](issues/06-retrieval-and-fuzzy-score-responsibilities.md) and [Research Hypothesis and Fair Evaluation](issues/08-research-hypothesis-and-fair-evaluation.md).

## Post-event research route

First select a narrow claim after reviewing what already exists. Candidate direction: whether explicit links from memory versions to decisions/tasks reduce stale decisions and incomplete handoffs after updates. This is a hypothesis to test, not a novelty claim or an adopted paper title.

Then compare matching agents and data with different memory mechanisms. Capture update errors, use of obsolete facts, missing handoff information, repeated work, unsupported answers, retrieval completeness, processing delays and resource costs. Hold models, input evidence and budgets constant where possible. Include negative findings and a separate untouched test set.

Keep the vector-placement experiment separate from the memory-policy experiment. Use the selected vector configuration consistently when evaluating the fuzzy and graph additions. Compare the hard change rules with and without fuzzy scoring, and relation-aware retrieval with a matching alternative that retains the same information. A faster backend alone does not explain better change or handoff reliability.

Use suitable existing memory datasets for the behaviors they actually cover, and controlled shared-task scenarios for behaviors they do not cover. Evaluate unseen raw inputs separately from hand-prepared notes. Publish or preserve enough configuration/data/code information to reproduce the findings subject to appropriate data access.

The final comparison plan and supported claim belong to [Research Hypothesis and Fair Evaluation](issues/08-research-hypothesis-and-fair-evaluation.md), informed by [Existing Research and a Testable Paper Contribution](issues/02-paper-gap-and-comparison-evidence.md).

## Post-event reuse and company route

Connect a second application first. Record which core functions it can reuse unchanged and which application-specific rules/data it supplies. This is the first practical test of “domain independent”.

Identify one actual company problem and a pilot partner. Agree what the pilot must do, its data/access boundaries, deployment preference, how to recover/delete/export data, observable failures, support ownership and an operating budget. Improve the core against those acceptance criteria.

Choose packaging and payment only after this evidence. Possible directions include a supported self-hosted component or a managed memory service, but the user has not chosen either and demand has not been established. The core may also be used internally without being sold.

The first pilot and readiness requirements belong to [First Company Pilot and Product Readiness](issues/09-first-company-pilot-and-product-readiness.md). Detailed pricing and broad scale targets remain outside the visible frontier until a buyer/workload becomes concrete.

## Suggested cuts if the event becomes tight

Preserve the complete restart → accepted change → related-work check → handoff story and truthful evidence of separation/recovery. Prefer a smaller working memory flow over many unsupported travel features.

Candidate deferrals: advanced automatic procedure learning; fuzzy refinements beyond the first working rule model; maintaining multiple selectable vector backends after the comparison; real payment/booking integrations; many travel suppliers; large-scale performance promises; billing and enterprise administration. The vector comparison and both paused additions are explicitly in the route; their minimal supported depth and fallback cuts remain a human decision.

Do not defer the truthfulness of the demonstration, actual persistence, the application's real memory connection, visibility of unresolved state, or the access boundary that is being claimed.
