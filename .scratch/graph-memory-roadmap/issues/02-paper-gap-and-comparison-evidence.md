# Existing Research and a Testable Paper Contribution

Labels: wayfinder:research
Type: research
Status: resolved
Assignee: paper_evidence_research
Parent: [Shared Agent Memory: Hackathon, Research and Reuse](../map.md)
Blocked by: none

## Question

What existing primary-source work already addresses changing graph memories, temporal contradictions, multi-agent shared memory and handoffs, and what narrower research hypotheses could this project credibly evaluate?

Find a small, high-quality set of relevant papers and official implementations. Propose candidate comparisons and failure measures, identify what existing datasets can and cannot test, and distinguish novelty candidates from established mechanisms. The user chose memory-change and handoff reliability as the direction; do not decide the final claim or promise novelty. Small hand-prepared question checks are preliminary evidence only.

## Comments

### Research context

Read current evaluation notes and the prior KG fixtures; use primary papers and official source/docs for external claims. Save cited findings on a throwaway local research branch. This repository has no remote; publication cannot happen yet. Avoid creating or modifying implementation code.

## Answer

Resolved on 2026-10-13 as a scoped evidence review, not a systematic novelty verdict.

Existing temporal graph systems already cover incremental updates, provenance and retained invalidated facts. Recent shared-memory evaluations also address handoffs and access boundaries. A defensible paper must therefore test a narrower mechanism and include capable alternatives, including non-graph versions of equivalent dependency/version policies. Suitable candidate studies concern dependent-work revalidation, version/evidence-checked handoffs, and whether fuzzy acceptance adds benefit beyond hard rules. No final contribution was selected.

The [research findings](../research-worktrees/paper-evidence/report/wayfinder/paper-evidence.md) hold the primary sources, benchmark coverage/limits, candidate hypotheses and matched comparisons. Choosing the final claim remains in [Research Hypothesis and Fair Evaluation](08-research-hypothesis-and-fair-evaluation.md). Availability of some newly described benchmark assets and deployed baseline behavior still need verification when selecting experiments.

Evidence commit: `5fd48807abf3bf77db80858d3e7530cbdf58273b`, local branch `codex/research/memory-paper-evidence`. At research-branch creation no remote was configured, so publication remained local. This records the original publication limitation, not the repository's current remote state. The existing hand-prepared question checks remain preliminary evidence.
