# Retrieval and Fuzzy Scores: Separate Responsibilities

Labels: wayfinder:grilling
Type: grilling
Status: resolved
Assignee: Codex
Parent: [Shared Agent Memory: Hackathon, Research and Reuse](../map.md)
Blocked by: 04

## Question

How should the two paused ideas become working, explainable graph-memory additions on the selected vector placement, and how will questions show whether they improve retrieval?

The user has asked to include both pauses after the vector test and placement choice. [Memory Changes, Evidence and Authority](04-memory-change-and-authority-contract.md) owns the change/protection contract. This ticket settles how to apply fuzzy rules and how graph retrieval uses the resulting memory state, without reopening that contract or replacing the architecture.

For the first pause, define a genuine fuzzy rule model: graded conditions such as fresh/stale and strong/weak support, explicit rules combining those conditions, and a resulting revisable-memory score. Keep an explanation of the contributing evidence and rules. A stored confidence number or simple recency weight alone is not the requested fuzzy controller. Protection, accepted supersession and dispute status remain explicit rules outside ordinary ranking. Decide parameter choices, minimal event scope and how score recalculation becomes visible to retrieval.

For the second pause, add meaningful relations and field-level evidence to the existing graph: what a claim describes, its context/conditions, its source, what it confirms or conflicts with, which version a decision used, and which tasks a change affects. Use bounded relevant expansion rather than returning an entire connected graph. Explain an answer with a short question → claim → source/current-state path. Related words alone do not establish a missing fact.

Compare KG-only, vector-only and combined retrieval on the same question set and retained memory history. Include paraphrases, identity aliases, several-step questions, partial confirmations, accepted changes, unresolved disputes, historical questions, scoped exceptions and absent answers. Keep a held-out question set. Separately test automatically ingested raw inputs; earlier hand-prepared fixtures are starting material, not automatic-ingestion evidence.

Keep acceptance, freshness, query relevance, current eligibility, protection and task ownership distinct. Decide which minimum additions must work for the event and which refinements can follow afterwards; both paused ideas remain in the staged route.

## Planned evidence

- Evidence completeness and relevance, unavailable-answer handling, current/historical correctness and understandable source paths.
- Ordinary decay, protected score 1, accepted protection transfer, unresolved contradiction, and unchanged unrelated memories.
- An accepted change invalidates only dependent work; a second agent receives current state and the retained reason/history.
- Ablations: disable fuzzy rules while retaining change rules, and disable relation-dependent retrieval while retaining the same text and vectors. Attribute benefits to the mechanism actually tested.
- Measured latency and bounded evidence size as memory grows, reusing the chosen vector configuration. Passing the earlier vector gate is not proof that these additions are fast or correct.

## Execution evidence

### 2026-10-14 — First working additions

Both paused additions are implemented under the user's execution authorization. The controller uses graded freshness, source quality, independent support and agreement with explicit fuzzy memberships/rules and an explanation. Protection and accepted state remain separate. Field-aware recall returns supported, disputed, unconfirmed, missing or unresolved-question evidence; explicit graph paths include claim, source and accepted identity evidence. Existing graph/vector/hybrid searches reconcile versioned hits with the graph before ranking. Work records the exact claims used; handoffs include current evidence and review requirements.

The [actual demo](../../../report/lifecycle_implementation_20261014_final/README.md) uses real cached BGE embeddings, FalkorDB and Qdrant. Regression checks cover all existing retrieval modes, retained versions, scope, aliases, missing fields, agent repetition and dependent work. This establishes the implemented behaviors on prepared fixtures. Keep this ticket open for a larger held-out comparison, mechanism ablations, calibrated defaults and measured growth/load; this is not evidence of general automatic extraction or answer quality.

The [final checkpoint](../../../report/lifecycle_implementation_20261014_final/IMPLEMENTATION.md) records 155 passing regression tests and local timing checks. Specific-field/path medians are approximately 19–93 ms; broad combined discovery is approximately 507 ms on this fixture. Optimization and representative growth/load remain necessary; the earlier vector experiment's corpus timings cannot be used as a before/after comparison for these new checks.


## Answer

The first retrieval/fuzzy implementation and controlled evaluation are complete. Graph, state-aware vector, combined, fuzzy-disabled and raw-vector controls use the same prepared data. Graph/combined discovery find required current sources in 24/24 answerable probes; field recall handles 36/36 probes, and stale source exposure is zero for the state-aware modes. The raw-vector control exposes obsolete sources in 16/24. The final fuzzy ablation has no source-recall benefit. Local grammar detects 14/16 explicit facts and invents none on six negatives; unsupported confirmed requirements are explicitly reviewed. These are development/regression findings, not blind/general agent accuracy.

[Implementation/evaluation contract](../../../docs/memory_research_protocol.md). [Actual shared-service evidence](../../../report/shared_memory_20261014_final/results.json).

### Decision source

The user's 2026-10-14 instruction, “all the steps in the wayfinder plan complete, if remaining then complete it”, delegates completion of remaining engineering work under the existing destination and accepted architecture/protection boundary. The documented first-contract defaults implement that authorization; they are engineering choices, not fabricated answers about customer identity, teammate commitments, scientific findings or production readiness.
