# Event Boundaries and FalkorDB Guarantees

Labels: wayfinder:research
Type: research
Status: resolved
Assignee: event_boundaries_research
Parent: [Shared Agent Memory: Hackathon, Research and Reuse](../map.md)
Blocked by: none

## Question

Which current organizer requirements and documented FalkorDB guarantees constrain a new Track 02 build, reuse of this research project, persistent memory, user isolation, and concurrent memory/task updates?

Distinguish verified rules from judging advice. Identify release-sensitive features and what the demonstration must actually test rather than assume. Explain the difference between a single atomic graph write and a series of writes or external actions. Recommend a small set of feasible storage choices for later human decisions, without selecting the final architecture.

## Comments

### Research context

Use official organizer pages, official FalkorDB docs/source and the current application specification. Write cited findings on a throwaway local research branch. This repository has no remote; record that publication is unavailable rather than inventing a push. Preserve existing application data.

## Answer

Resolved on 2026-10-13 by primary-source research; no runtime implementation or deployment was tested.

The organizer requires new main event work and a central FalkorDB role. Documented single-query atomicity, graph-scoped access permissions, persistence configuration and per-graph write serialization constrain the design. A sequence of commands must not be assumed to roll back fully after a runtime error. Pin and test the chosen release; documented capabilities are not measurements of this system's reliability or throughput.

The [research findings](../research-worktrees/event-boundaries/report/wayfinder/event-boundaries.md) hold the cited facts, qualifications, storage candidates and proposed tests. The remaining storage choice is covered by [Vector Placement Within the Existing Architecture](07-reusable-core-and-storage-boundary.md); service behavior and guarantees remain a human decision in [Live Ingestion, Shared Tasks and Private User Spaces](05-live-ingestion-coordination-and-user-spaces.md).

Evidence commit: `2dd35d077fcf4b15266047f14ebb833f7d33017a`, local branch `codex/research/memory-event-boundaries`. At research-branch creation no remote was configured, so the evidence was not pushed. This records the original publication limitation, not the repository's current remote state.
