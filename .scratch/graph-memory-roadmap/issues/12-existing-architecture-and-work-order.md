# Existing Architecture, Reference Use and Work Order

Labels: wayfinder:grilling
Type: grilling
Status: resolved
Assignee: Codex
Parent: [Shared Agent Memory: Hackathon, Research and Reuse](../map.md)
Blocked by: none

## Question

Should the current architecture remain the baseline, with Mem0, MemPalace and Zep used as references, a FalkorDB-versus-Qdrant vector test first, and both paused ideas added to the graph memory system afterwards?

## Comments

### 2026-10-13 — Claim and direct user instruction

Claimed before updating the map. The user explicitly asked to keep the already-good architecture, use the three researched systems as references, compare vector placement on latency and output metrics at 5%, and then add both paused ideas. This session records that direction; it does not choose a vector backend or settle the remaining memory rules.

## Answer

### Decision source

The user's live instruction settles the baseline and order: “right now the architecture is very good, already, only the change that can happen would be adding vector inside falkor or not” and “first test vector of falkor ... when vector is qdrant ... also then add both the pause ideas to the KG graph system.”

Keep the existing architecture. The planned storage decision is vector placement: retain Qdrant or place vectors inside FalkorDB after a controlled comparison. Mem0, MemPalace and Zep/Graphiti supply reference ideas and comparison context; this route does not adopt any of them as another memory core.

The core work order is vector comparison, vector-placement decision, then both graph additions: evolving fuzzy memories with retained contradiction/supersession history, and explainable graph retrieval with question-based evaluation. Additive support for ingestion, sharing and handoffs extends this core rather than reopening the architecture. The teammate's application work can continue in parallel.

The user requested a 5% condition on latency and output metrics. Its exact meaning is awaiting clarification in [FalkorDB Versus Qdrant: Vector Latency and Output Quality](11-vector-comparison.md). No threshold interpretation, benchmark result, vector winner, detailed fuzzy policy, or completed implementation is implied by this resolution.

### Updated route asset

[Proposed Route: One Memory Core, Three Outcomes](../route-outline.md) reflects this ordering. Later tickets retain their unresolved details.
