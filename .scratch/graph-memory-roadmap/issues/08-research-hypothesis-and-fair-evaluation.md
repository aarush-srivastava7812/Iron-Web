# Research Hypothesis and Fair Evaluation

Labels: wayfinder:grilling
Type: grilling
Status: resolved
Assignee: Codex
Parent: [Shared Agent Memory: Hackathon, Research and Reuse](../map.md)
Blocked by: 02, 04, 06

## Question

Which falsifiable claim about graph-based memory changes and handoffs will the paper test, against which comparisons, and what evidence would support or reject it?

The user selected reliability as the main direction. Decide automatic-ingestion evaluation, update correctness, obsolete-decision use, handoff completeness, task duplication, missing-answer behavior, retrieval and final-answer assessment. Keep initial hand-prepared observations separate from blind tests, and hold model/data/budget conditions constant where appropriate. Specify which experiment records should be captured from the event and which controlled studies belong after it.

Use the vector-placement comparison as a separate baseline experiment, not the paper's novelty claim. Once placement is chosen, hold it constant when evaluating both paused additions. Separate the effects of fuzzy scoring from accepted-change rules, and graph evidence/dependency processing from merely having the same stored text. Mem0, MemPalace and Zep remain references; product-level comparisons require their actual relevant features to be enabled and validated rather than assuming the current wrappers represent them fully.


## Answer

The reliability hypothesis and fair evaluation protocol are defined, centered on obsolete completions and incomplete handoffs after changes. It requires a matched state/dependency-check ablation, a strong same-information flat ledger, independent fuzzy control, untouched scenarios and separate raw interpretation/retrieval/final-agent-answer metrics. Current prepared studies are exploratory evidence. No novelty, publication, statistically supported superiority or hosted-model results are claimed.

[Implementation/evaluation contract](../../../docs/memory_research_protocol.md). [Actual shared-service evidence](../../../report/shared_memory_20261014_final/results.json).

### Decision source

The user's 2026-10-14 instruction, “all the steps in the wayfinder plan complete, if remaining then complete it”, delegates completion of remaining engineering work under the existing destination and accepted architecture/protection boundary. The documented first-contract defaults implement that authorization; they are engineering choices, not fabricated answers about customer identity, teammate commitments, scientific findings or production readiness.
