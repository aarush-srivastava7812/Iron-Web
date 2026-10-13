# Research evidence: changing memories and agent handoffs

Checked 13 October 2026. This is a scoped primary-source review for planning, not a systematic literature review or a novelty verdict. It does not select the final research contribution.

## Accessible finding

The promising question is not whether a graph can remember a correction. Existing systems already do that. A stronger question is whether agents reliably reconsider work that depended on corrected information, and hand over only the work and evidence that remain valid. We must test that claim against capable alternatives, including alternatives without a graph.

The hackathon can demonstrate this through one travel scenario. The paper needs a separate, frozen evaluation across several scenario families. The reusable memory service is the common artifact; a successful demonstration alone does not establish a scientific contribution or readiness for company deployment.

## Existing work and the boundaries it establishes

| Primary evidence | What already exists | What this means for this project |
| --- | --- | --- |
| [Zep paper](https://arxiv.org/abs/2501.13956), [Graphiti official repository](https://github.com/getzep/graphiti) | Temporal facts, provenance to episodes, retained invalidated facts, incremental ingestion and hybrid retrieval. The repository lists FalkorDB support. | Keeping old and new facts, time-aware retrieval, and a FalkorDB-backed temporal graph are established mechanisms. The current repository is not an exact reproduction of the 2025 paper. |
| [Mem0 paper, sections 2.1–2.2](https://arxiv.org/html/2504.19413v1) | Base memory selects ADD, UPDATE, DELETE or NOOP against similar memories. The graph variant describes conflict resolution that marks obsolete relationships invalid rather than physically removing them. | Do not claim that Mem0 necessarily erases all graph history. Memory consolidation and conflict handling themselves are not new. Evaluate a pinned implementation, not only the paper description. |
| [CoMemBench, September 2026 preprint](https://arxiv.org/html/2609.32192v1) | Collaborative workflows with dependency graphs, required handoffs, matched isolation challenges and revision boundaries. Measures include workflow success, verified progress, handoff success and isolation success. | Handoff reliability and stale/incompatible shared information already have direct prior evaluation. The paper says artifacts will be released; this review did not locate a verified project download. Treat reproduction availability as pending. |
| [GateMem paper](https://arxiv.org/abs/2606.18829), [official code](https://github.com/rzhub/GateMem) | Shared memory across multiple principals, incremental updates, authorization boundaries and explicit forgetting; released evaluator. | Per-user separation and shared institutional memory are substantive evaluation topics, not merely graph labels. Access control and forgetting must remain independently measurable. |

The candidate contribution therefore needs to be narrower than “graph memory with contradictions and handoffs.” Possible distinctions include dependency-driven revalidation after accepted corrections, safe partial updates, and version-aware handoff acceptance under races and interruptions. This is an inference about an evaluation opportunity, not proof that no previous system implements these features.

## Which benchmarks answer which questions?

| Benchmark and primary source | Useful coverage | Limits for the chosen paper |
| --- | --- | --- |
| [LongMemEval official repository](https://github.com/xiaowu0162/LongMemEval) | Knowledge updates, temporal reasoning, cross-session reasoning, extraction and abstention; evidence annotations permit retrieval checks separately from answer grading. | Conversational question answering does not by itself test task ownership, stale-plan execution or crash recovery. Use a fixed cleaned dataset revision. |
| [MemoryAgentBench official repository](https://github.com/HUST-AI-HYZ/MemoryAgentBench) | Incremental interactions and conflict resolution, including FactConsolidation; accurate retrieval, learning and long-range understanding. | A correct revised fact is not evidence that a second agent safely resumed dependent work. Preserve its official task-specific metrics; substring matching has different weaknesses from execution checks. |
| [LoCoMo official repository](https://github.com/snap-research/LoCoMo) | Long conversational histories, QA and event summarization. | Useful supporting recall test, not the principal proof of change-aware handoffs. Small conversation count and synthetic generation limit claims about customer reality. |
| [LongMemEval-V2 paper](https://arxiv.org/abs/2605.12493), [official repository](https://github.com/xiaowu0162/LongMemEval-V2) | Environment experience: dynamic state tracking, workflow knowledge, gotchas and premise awareness. Memories supply compact evidence for QA. | More relevant to procedural memory than profile recall, but evidence gathering is not a concurrent multi-agent handoff protocol. |
| CoMemBench and GateMem, above | Closest targeted checks of collaborative boundaries and governance. | CoMemBench reproduction must await verified assets; GateMem governance does not substitute for measuring duplicate execution or recovery. These are recent preprints, not guarantees of settled evaluation practice. |

There is already related work on deterministic current-value resolution: [“Don't Ask the LLM to Track Freshness”](https://arxiv.org/abs/2606.01435) evaluates version-aware aggregation. Its own abstract acknowledges jointly changed pipeline components and a weaker transfer result on broader updates. Include a deterministic newer-version baseline; “newest always wins” is unsuitable for unauthorized corrections, retrospective events or scope-specific preferences.

## Three candidate hypotheses, not final contribution choices

### H1: Follow accepted corrections into dependent work

**Question:** With the same agents, evidence and search budget, does explicit tracking of which claims a decision used reduce actions based on superseded claims?

Compare the proposed service with (a) the current implementation including its supported expiry and replacement behavior, (b) a flat meaning-search memory with explicit version filtering, and (c) a temporal graph baseline such as pinned Graphiti. Give all systems the same correction events and acceptance policy. Also implement dependency/version checks in a non-graph store: otherwise any gain could be due to the policy rather than the graph.

Remove only dependency propagation in one comparison. Measure stale-action rate, valid task completion, unnecessary rework and time from committed correction to affected-task detection. A travel budget changing mid-plan is a demonstration; withheld procurement and scheduling scenarios test reuse.

### H2: Check a handoff against current memory before resuming

**Question:** Do evidence-linked, version-checked handoffs reduce lost constraints, duplicate actions and stale resumption compared with an equally sized summary or shared history?

Keep the same task ownership and action safeguards across all methods. Compare summary handoffs, flat shared memory and graph-linked handoffs. Remove the version check and remove the evidence links separately. Repeat with one versus several handoffs, a change during the handoff, and interruption before or after an action result is recorded.

Measure required-constraint preservation, verified continuation success, stale-artifact reuse, duplicate action attempts, recovery success and cross-user exposure. Report whether an action is merely attempted or actually executed. A graph must not receive credit for duplicate prevention supplied by an unrelated ownership rule.

### H3: Test whether fuzzy acceptance adds useful reliability

**Question:** Once current eligibility, scope and source authority are enforced, does the fuzzy controller improve safe use of uncertain memories compared with a simple fixed scoring rule?

Compare no acceptance ranking, a simple recency/authority score and the frozen fuzzy controller. Keep hard permissions, explicit protection and accepted-change rules identical. Remove decay, conflict input and support input separately. Measure unsupported use, missed valid evidence, disputed-claim disclosure, abstention quality and task success. The controller might add no benefit; that is a valid result. A value of 1 is explicit protection, not a calibrated certainty probability or permission to execute.

## Fair comparisons and controlled fixtures

Run two evaluation layers. First supply every method the same prepared facts to isolate lifecycle and handoff behavior. Then ingest the same raw conversations automatically to measure the complete system. Publish both: manual preparation cannot stand in for ingestion performance.

Freeze scenario families, expected state transitions and checks before tuning. Keep some domains, paraphrases and event schedules withheld. Include partial confirmations, actual corrections, additive facts, uncertain identity matches, unauthorized assertions, event time differing from arrival time, duplicate delivery, simultaneous writers and interrupted handoffs. Define whether late-arriving events should revise history or current state. Controlled fixtures supplement external benchmarks with known execution expectations; they do not establish performance on real company data.

Match agent models, prompts, tool access, token budgets, retrieval limits, accepted-update policy and task safeguards. Record database/library/model versions, random seeds, costs, tail latency and event traces. Repeat matched scenarios and report uncertainty rather than only one headline percentage. Assess retrieval evidence, generated answers and completed actions separately; audit a sample of automatic grades against human review. Let independent reviewers check expected outcomes and scorer design.

The existing [local question report](/D:/Opencode_/reserchpaper/report/north_evolution/question_check/REPORT.md) is preliminary: 91 hand-prepared notes, evidence retrieval rather than generated answers, small question sets, and no automatic ingestion or multi-agent execution. Its 27/28 revised retrieval result is a debugging observation, not the paper's main result. The current implementation already supports explicit expiry; preserve that in its baseline instead of portraying it as unable to handle updates.

## Planning implications and unresolved evidence

For the two-person event, demonstrate accepted correction, dependent-plan recheck, restart persistence and an evidence-bearing two-agent handoff. Collect reproducible traces now; postpone a large benchmark campaign until the core behaves correctly. The teammate can build the travel interface against a stable service agreement while the memory core develops.

Before choosing the paper claim, verify the exact baselines' behavior with probes, inspect CoMemBench asset availability, estimate model/evaluation costs, and review additional recent work around dependency invalidation and concurrency. Commercial readiness additionally requires security, deletion, operational and customer validation; none is established by this review.

This evidence is saved on local branch `codex/research/memory-paper-evidence`. No remote is configured, so there is no pushed branch or pull request. No implementation was changed.
