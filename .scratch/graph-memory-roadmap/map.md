# Shared Agent Memory: Hackathon, Research and Reuse

Labels: wayfinder:map
Status: open
Tracker: local Markdown; Wayfinder fallback

## Destination

An agreed, staged build plan for a focused FalkorDB Track 02 travel entry and a reusable graph-memory core, with a credible research path on memory changes and handoffs and a later path to company pilots and commercialization.

The decision map is complete when the decisions needed to hand off that plan are resolved. The user has now authorized applying the plan; execution evidence can be attached to the relevant tickets without claiming unresolved decisions or later research/product outcomes are complete.

## Notes

- User-confirmed goals: a competitive hackathon application and a well-made reusable memory system; the latter should support both a research paper and use in other companies/applications, potentially as a commercial offering.
- Two-person team. The user can commit at least eight hours per event day. Initial direction is user-led memory core and teammate-led application development in parallel, but roles are not fully divided. Teammate capacity remains unconfirmed.
- User accepted a focused travel scenario that demonstrates memory across sessions, an accepted correction, and a two-agent handoff. The memory core should improve first while the teammate builds the application in parallel. Define the shared app/core contract early.
- User accepted memory-change and handoff reliability as the paper's main direction. Retrieval and fuzzy scores are supporting mechanisms. A testable contribution and novelty remain unestablished pending research and later decisions.
- The user has settled the architecture baseline and work order; see [Existing Architecture, Reference Use and Work Order](issues/12-existing-architecture-and-work-order.md). Preserve the current architecture, compare vector placement first, then include both paused ideas as graph-memory additions in the planned build.
- Mem0, MemPalace and Zep are references for this route. The research does not select or integrate an additional memory framework. [Reference findings](../../report/memory_architecture_research_20261013/README.md) provide context, not an instruction to replace the architecture.
- The user requested 5% on vector latency and output metrics. Its meaning is pending clarification in [FalkorDB Versus Qdrant: Vector Latency and Output Quality](issues/11-vector-comparison.md); the [comparison plan](vector-comparison-plan.md) labels the proposed relative-tolerance interpretation explicitly.
- The comparison is the first core task. Travel scenario/team discussion can proceed in parallel; memory lifecycle and retrieval additions follow the vector-placement decision.
- The earlier cache deferral was superseded on 2026-10-14: the user requested a three-tier design before combining the travel agency site. [Three-Tier Agent Memory Before Travel Site Integration](../three-tier-memory/map.md) contains the autonomous architecture decisions. The first core was implemented and tested incrementally on 2026-10-15; [verification](../three-tier-memory/implementation.md) records 215 ordinary checks, two actual CUDA checks and the real-model demonstration. Binding the actual site's consumer/runtime and agent flow remains the next integration boundary.
- Execution checkpoint, 2026-10-14: “ok implement” accepts the recommended first build. Both paused additions now have a working implementation on the selected placement; see the [guide](../../docs/memory_evolution.md) and [actual graph demo](../../report/lifecycle_implementation_20261014_final/README.md). Wider policy/evaluation and application/service tickets remain open.
- Completion directive, 2026-10-14: the user asked to complete all remaining plan steps. This explicitly overrides the skill's one-ticket-per-session pacing for authorized engineering work. Use existing decisions and reasonable documented defaults; do not invent a teammate's commitments, actual customer, provider access, research result or submitted entry. Completed first-contract decisions may be resolved together with concrete execution evidence.
- Communicate in plain language. Distinguish current capabilities, proposals, experiment observations and user decisions. Do not guarantee winning, research novelty, production readiness or market demand.
- Execution authorized by “start applying the plan” on 2026-10-13. Start with the isolated vector comparison; extend the core in the stated order as prerequisite decisions become settled. Check organizer timing/reuse rules before treating preparation work as submission implementation. Preserve the current application and stored memories.
- Consult [Wayfinder](C:/Users/User/.codex/skills/wayfinder/SKILL.md), [Grilling](C:/Users/User/.codex/skills/grilling/SKILL.md), [Domain Modeling](C:/Users/User/.codex/skills/domain-modeling/SKILL.md), and [local tracker operations](C:/Users/User/.codex/skills/setup-matt-pocock-skills/issue-tracker-local.md). Research tickets additionally use [Research](C:/Users/User/.codex/skills/research/SKILL.md).
- Local issues are one file per ticket. Only wayfinder labels are used. Claim before working; resolve through an appended answer; open unblocked unclaimed children form the frontier. A charting session resolves no human decision tickets.
- At the original research-branch creation no remote was configured, so those research results stayed on local branches. Later repository publication and the parallel FalkorDB migration belong to other authorized work; this map update does not push, merge or open a pull request.
- Baseline context: [current specification](../../docs/specification.md), [architecture](../../docs/architecture.md), [previous direction](../../docs/hackathon_memory_direction.md), [question-demo evidence](../../report/north_evolution/question_check/REPORT.md), [domain glossary](../../GLOSSARY.md).
- Discussion asset: [Proposed Route: One Memory Core, Three Outcomes](route-outline.md). This is a proposal with explicit open decisions, not a second store of resolved decisions.
- Query view: [Next Work and Decisions](frontier.md) is a generated dependency/frontier snapshot, refreshed with `refresh_frontier.py`; open children are queried there rather than listed in this map.

## Decisions so far

<!-- One gist and link per resolved child; detailed evidence and answers live only in those children. -->

- [Event Boundaries and FalkorDB Guarantees](issues/01-event-rules-and-falkordb-guarantees.md): organizer boundaries and documented storage guarantees are checked; the selected release still needs runtime verification.
- [Existing Research and a Testable Paper Contribution](issues/02-paper-gap-and-comparison-evidence.md): the broad mechanisms already have prior work; narrower hypotheses and fair alternatives are available for the later paper decision.
- [Existing Architecture, Reference Use and Work Order](issues/12-existing-architecture-and-work-order.md): preserve the architecture, use the researched systems as references, test vector placement first, then add both paused KG ideas.
- [FalkorDB Versus Qdrant: Vector Latency and Output Quality](issues/11-vector-comparison.md): the 149-question 5% subset comparison found identical evidence and slower native-vector retrieval; the placement decision now has measured evidence.
- [Vector Placement Within the Existing Architecture](issues/07-reusable-core-and-storage-boundary.md): retain FalkorDB graph authority and embedded Qdrant; implement the paused graph additions on this baseline.
- [Memory Changes, Evidence and Authority](issues/04-memory-change-and-authority-contract.md): first contract implemented, including retained retractions, independent evidence groups, explicit authority and pending/unclear-change safeguards.
- [Live Ingestion, Shared Tasks and Private User Spaces](issues/05-live-ingestion-coordination-and-user-spaces.md): receipt-first authenticated service, private spaces, ownership/prerequisites, notification/history and tested local recovery are implemented.
- [Retrieval and Fuzzy Scores: Separate Responsibilities](issues/06-retrieval-and-fuzzy-score-responsibilities.md): same-data controls and raw-input checks expose limitations; named-subject/revision checks and batched evidence improve the first build.
- [Research Hypothesis and Fair Evaluation](issues/08-research-hypothesis-and-fair-evaluation.md): a falsifiable reliability protocol is defined; blind/model-driven studies and scientific conclusions remain later outcomes.

## Not yet specified

- The second application and the first company pilot will reveal which memory capabilities truly need to be reusable and which integration differences need explicit contracts.
- Customer evidence will sharpen packaging, support expectations, deployment options and any pricing proposal. Commercial intent is known; a buyer and a paid problem are not.
- Literature and the first controlled experiment will sharpen the paper's final claim, venues and larger evaluation scope.
- Measured failures will determine refinements beyond the included fuzzy/protection and retrieval additions, including memory consolidation and long-term procedural learning.
- Scale targets beyond the demonstration will become concrete after the first users, workload and operating costs are known.

## Out of scope

- Changing production vector placement before the comparison and placement decision, or replacing the architecture contrary to the user's stated baseline.
- Solving every travel feature before demonstrating the track's memory and coordination behaviors.
- Declaring a sales-ready product, pricing it as validated, or promising revenue without pilot evidence.
- Claiming that database choice alone establishes scientific novelty or that small curated retrieval counts establish general quality.
- Replacing the agreed architecture or stacking Mem0, MemPalace and Zep as competing authoritative memory systems.
- Researching or redesigning caching before the user resumes that topic. The user resumed it on 2026-10-14; the [new map](../three-tier-memory/map.md) now owns that prerequisite work.

## Comments

### 2026-10-13 — User destination clarification

The user selected a focused entry with a reusable core, clarified the two-person parallel-development direction, reported at least eight hours daily during the event, and selected memory changes and handoffs as the main research direction. These establish the destination and standing preferences; they do not close the child decisions below.

### 2026-10-13 — Architecture and sequence revision

The live instruction is recorded in [Existing Architecture, Reference Use and Work Order](issues/12-existing-architecture-and-work-order.md). The vector test is a new first core task; the placement choice precedes both planned KG additions. This session updates the plan only and runs no benchmark or implementation work.
