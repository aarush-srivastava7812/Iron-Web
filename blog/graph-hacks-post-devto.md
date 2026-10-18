---
title: "My travel agents recheck the plan when the budget changes"
description: "Iron Web uses FalkorDB to connect travel requirements, their sources, and the agent work that must be reviewed when those requirements change."
tags: falkordb, ai, agents, hackathon
published: false
---

**TL;DR:** I built Iron Web, shared agent memory demonstrated through the Voyara travel planner, for Track 02: Agent Memory and Coordination.
FalkorDB connects versioned requirements, source evidence, and dependent work so a changed budget can trigger review.
[Repository](https://github.com/aarush-srivastava7812/Iron-Web) · [Demo video](TODO-demo-video) · Local setup is in the README.

## The budget changed. Which work is still usable?

In the recorded Voyara walkthrough, a traveler requests Kerala for December 1–3, two people, a relaxed pace, and an INR 200,000 budget. The agents produce a plan. Then the traveler lowers the budget to INR 120,000.

For someone planning a trip, repeating that change to every specialist is tedious. Reviewing an itinerary built around the old limit wastes more time. The question I wanted the system to answer was: **which requirements apply now, which work used an older version, and what evidence supports the replacement?**

A stored conversation contains both numbers. Retrieving a relevant paragraph does not establish which number is authorized for the current trip or which decisions need another look.

## Why I connected requirements to work

Iron Web's memory layer uses FalkorDB as the primary graph database, with Qdrant for vector discovery and a private SQLite journal for receipts. The graph holds accepted claims and their relationships; application code checks their scope, validity, disputes, and sources before use.

The dependency chain is concrete: a work record `USES` a particular budget claim; a replacement claim `SUPERSEDES` that version; other work can `DEPENDS_ON` the affected task. Each claim is `SUPPORTED_BY` a source.

Vector similarity helps find candidates. It cannot, by itself, authorize a replacement or determine which recorded work depended on it. A relational implementation could represent these relationships too; I have not established that joins are inherently inadequate. Here, I made those relationships explicit in the graph and built the review behavior around them.

## The model preserves the earlier statement

This is the claim-and-work portion of the graph:

```text
MemoryWork --------USES--------> MemoryClaim (earlier)
     |
     +-----------DEPENDS_ON---> MemoryWork (prerequisite)

MemoryClaim (replacement) --SUPERSEDES--> MemoryClaim (earlier)
MemoryClaim --------------SUPPORTED_BY--> MemorySource
MemoryClaim -------------------ABOUT--> Entity
MemoryClaim --------------IN_CONTEXT--> MemoryContext
MemoryClaim -----------ASSERTS_FIELD--> MemoryField
```

A claim has a subject, field, value, and scope. Keeping the source and scope separate lets me preserve the original statement while changing what is currently eligible. A trip-specific instruction must not silently replace a requirement for another trip.

The underlying memory store also retains `Observation` nodes. The diagram focuses on the lifecycle layer; the full label and relationship inventory is available in the source.

## Following one change through real stored evidence

I reran `scripts/demo_memory_lifecycle.py` against an isolated FalkorDB graph and embedded Qdrant, using the cached BGE embedding model on CPU. This is a synthetic memory demonstration, separate from the hosted website recording.

The fixture starts with an approved budget of 1,000. A planner records `trip_plan` against that exact claim. It separately completes `seat_note`, which uses an aisle-seat preference. The user then approves a budget of 600.

The question sent to field recall is: **“What is the traveller's current budget?”** The returned status is supported, with value `600` and its source evidence. The handoff marks `trip_plan` for review; `seat_note` remains completed without review.

This is the actual dependency lookup used by `invalidate_work()`:

```cypher
MATCH(w:MemoryWork)-[:USES]->(c:MemoryClaim)
WHERE c.id IN $ids
RETURN DISTINCT w.id LIMIT $limit
```

With `$ids` containing the earlier budget claim, my read-only verification returned `trip_plan`.

I also ran this inspection query over the resulting graph, with `$work_id = 'trip_plan'`:

```cypher
MATCH (w:MemoryWork)-[:USES]->(old:MemoryClaim),
      (current:MemoryClaim)-[:SUPERSEDES]->(old),
      (current)-[:SUPPORTED_BY]->(source:MemorySource)
WHERE w.id = $work_id
RETURN w.id, old.value_json, current.value_json,
       source.memory_id, w.validation_state
```

The returned row was:

```text
trip_plan | 1000 | 600 | demo_new_budget | stale
```

That row shows the used version, replacement, supporting source, and review state together. This structural inspection explains the stored result; eligibility still comes from lifecycle checks. It is not generated Cypher from the agent.

The fixture then adds an unaccepted agent proposal of 900. Recall reports a dispute instead of treating the proposal as a new user instruction. Asking for an absent phone number returns missing evidence. All nine scripted checks passed on this rerun.

## How the website agents receive that context

Voyara's website binds memory access to the authenticated traveler and trip through `ThreeTierGateway`. Its `retrieve()` call requests context from the shared service. A packet that is not ready stops planning with a request for information.

Hot instructions and traveler essentials form the first tier; task context cards form the second; durable evidence forms the third. Captured context carries claim identifiers. After generation, `validate_current()` rechecks the context proofs so changed requirements can invalidate the result.

The recorded website route uses seven hosted specialists for consultation, discovery, stays, food, experiences, itinerary construction, and budgeting. Their allowlisted tools include `compare_stays`, `build_schedule`, and `calculate_budget`. They receive graph-backed context through Python interfaces. The memory tool adapter also exposes recall and handoff operations; it is an in-process adapter rather than an MCP transport.

In the recorded budget change, saving INR 120,000 makes the older plan stale. Regeneration captures the revised budget and evidence, while the earlier context remains inspectable.

![Budget agent context with the original INR 200,000 limit](TODO-screenshot-before)

![Budget agent context with the approved INR 120,000 limit](TODO-screenshot-after)

*Upload the existing context-budget-before.png and context-budget-after.png screenshots here. Show the budget values and their supporting claim/source fields.*

## What breaks if I remove FalkorDB?

The website's shared-memory engine requires the graph for claim eligibility, history, context evidence, and dependency review. Removing that storage removes the implemented basis for deciding whether remembered requirements and related work remain usable.

The repository also contains a vector-only development fallback in the older agent gateway. Basic retrieval in that mode does not demonstrate these graph-backed guarantees. This paragraph describes the code boundary; I have not run a controlled graph-removal ablation for the complete website.

## What changed my implementation

**A new rule can invalidate work without replacing an old field.** The October 15 audit found that adding a restriction did not stop existing work. I added subject/scope requirement watches and current prerequisite checks. Tracking only previously used claims missed newly introduced constraints.

**I kept Qdrant after testing another placement.** The retained paired experiment compared the existing embedded vector path with native indexed FalkorDB vectors. Its measured complete-retrieval results supported keeping Qdrant for that configuration. That experiment does not establish a universal database ranking.

**An open connection can still display stale information.** A stalled-stream check found that the dashboard could report live status after heartbeats stopped. The fix marks retained data stale and reconnects. Freshness needs an observable check.

**Context allocation needs an honest unit.** The application's default consumer profile counts UTF-8 bytes. Hosted model tokens are reported separately. I cannot turn those byte allocations into a claim about token savings.

## What I still need to establish

The travel catalog and costs are illustrative. Agents cannot make payments or confirm supplier reservations; checkout creates a booking request. Larger load studies and controlled end-to-end ablations remain future work.

Cross-store recovery compensates caught failures; it is not a crash-atomic transaction across FalkorDB and Qdrant. The recovery report also records a persisted-log replay crash and an activated recovery copy. It does not establish an engine durability fix.

The repository records memory work before the event and later application integration. Coding assistants contributed to the build and this draft; I remain responsible for understanding and verifying the work.

## Try it and inspect the evidence

- [Repository and setup](https://github.com/aarush-srivastava7812/Iron-Web)
- [Local demonstration steps](https://github.com/aarush-srivastava7812/Iron-Web/blob/main/DEMO.md)
- [Memory lifecycle implementation](https://github.com/aarush-srivastava7812/Iron-Web/blob/main/memory/lifecycle/service.py)
- [Recorded demo MP4 in the repository](https://github.com/aarush-srivastava7812/Iron-Web/blob/main/youtube-upload/ironweb-voyara-2m58-final.mp4)
- Public demo link: [NORTH: Which public URL should readers use for the demo video? Replace TODO-demo-video above.]
- Live deployment: local demonstration; no cloud deployment is claimed.
