# Vector Placement Within the Existing Architecture

Labels: wayfinder:grilling
Type: grilling
Status: resolved
Assignee: Codex
Parent: [Shared Agent Memory: Hackathon, Research and Reuse](../map.md)
Blocked by: 01, 11, 12

## Question

Given the measured comparison, should vectors stay in Qdrant or move inside FalkorDB while the existing architecture remains the baseline?

Use [FalkorDB Versus Qdrant: Vector Latency and Output Quality](11-vector-comparison.md), including latency, output quality, concurrent updates and the clarified 5% rule. A passing result makes FalkorDB vectors eligible; it does not itself replace Qdrant. If evidence is failing or inconclusive, retain Qdrant for the first build and record why. If both pass, decide whether the observed operational benefit justifies the change.

The user has already chosen to preserve the architecture and use the three researched systems as references. Do not reopen a wholesale architecture/framework decision. Keep FalkorDB central to the graph's memory history, evidence relationships and shared work regardless of vector placement. The later graph additions use the selected placement and preserve the app/core boundary.

## Comments

### 2026-10-13 — Narrowed by user direction

This ticket previously asked a broader reusable-core/storage-boundary question. [Existing Architecture, Reference Use and Work Order](12-existing-architecture-and-work-order.md) narrows it to the remaining vector-placement choice. No placement has been selected.

### 2026-10-13 — First experiment available

The [paired comparison report](../../../report/vector_placement_20261013_p5_paired/REPORT.md) finds identical ranked evidence and slower native-vector retrieval on the retained 5% subsets. Recommendation: retain the existing Qdrant placement for this build, preserving the user-approved architecture. This is a recommendation from measured facts, not an unrecorded human decision. The exact meaning of the user's 5% condition is still pending clarification; there is no evidence-based reason to replace the baseline now.

## Answer

Keep FalkorDB as the graph authority and embedded Qdrant for vectors. The measured comparison did not justify moving vectors. Both paused additions have now been implemented on this placement; the [implementation guide](../../../docs/memory_evolution.md) describes the interfaces and limits, and the [final isolated demo](../../../report/lifecycle_implementation_20261014_final/README.md) retains the actual graph.

### Decision source

On 2026-10-14, the user said “ok implement” after the recommendation to keep the existing placement and implement the paused additions, with protection limited to explicit confirmed user instructions/rules. This accepts that concrete recommendation within the earlier “start applying the plan” authorization. It does not clarify the previously proposed interpretation of 5%, authorize a wholesale architecture change, or establish production readiness.
