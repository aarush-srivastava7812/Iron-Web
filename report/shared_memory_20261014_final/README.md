# Completed core checkpoint

The remaining engineering work for the first memory-core contract is implemented and verified. The existing FalkorDB graph plus Qdrant vectors remain the baseline; a durable SQLite processing journal was added around them.

- [Live application](http://127.0.0.1:15451/): the authenticated reference UI sends actual events and creates version-bound plan drafts. Local credentials are private files under the ignored runtime directory; the application guide explains setup.
- [Actual graph](http://127.0.0.1:1306/): inspect the stored snapshot, source nodes, protected changes, disputes and dependent work. Its [complete export](graph.json) is real database data from the demonstration fixture.
- [Recorded walkthrough](walkthrough.webm): user requirement, planner draft, accepted change, reviewer handoff/revision and a separate private user.
- [Scripted results](results.json), [browser proof](browser-proof.json), and [second-domain reuse](reuse-proof.json).
- [Service and setup guide](../../docs/shared_memory_service.md), [research protocol](../../docs/memory_research_protocol.md), [pilot worksheet](../../docs/memory_pilot_readiness.md), [delivery route](../../docs/memory_delivery_route.md).

The final regression suite passed **174 tests**, with four optional neural/dataset tests deselected by the repository defaults. The local demonstration uses actual cached BGE embeddings on CPU, actual FalkorDB and embedded Qdrant. It exercises two authenticated agents, separate user spaces, a stored planning procedure, retained approved changes, affected-work review, unrelated completed work, missing answers, restart and bounded HTTP concurrency.

With eight clients submitting 24 events and 48 receipt reads, no receipt reads failed and all events became ready. Receipt median/p95 were **29.43/40.19 ms**; semantic readiness p95 was **4.64 seconds**, and completion throughput was **4.83 events/second** on this small fixture. Receipt latency and semantic readiness are different measurements. They are not enterprise scale promises.

The [controlled retrieval study](../memory_evaluation_20261014_final/results.json) covers 36 prepared probes: graph and combined retrieval find required current sources in 24/24 answerable probes and field-aware recall handles 36/36 statuses. Raw-vector discovery without state checks exposes older sources in 16/24 answerable probes. Combined retrieval median/p95 were about **144/158 ms** on that fixture. Fuzzy disabled has the same source recall: this experiment does not show a benefit from fuzzy ranking. Raw grammar recognition was 14/16 explicit facts with no invented claims on six negatives; unclear confirmed requirements now block stale actions instead of silently reapproving old state.

The initial experiment was used to fix failures, so these counts are regression evidence, not a blind external benchmark or model-generated answer accuracy. The synthetic maintenance example reuses the API unchanged; it is not an actual company pilot or maintenance guidance.

Killed-process tests cover receipt, vector write, graph publication and a missing vector after publication. Cold backup/fresh-target restore uses explicit graph records and closed vector files. A native binary restore experiment caused a database restart on the tested release; that failed path was removed. The original named application graph and demonstration graphs remained present, and the shipped explicit restore check passed. No universal power-loss or external-booking exactly-once claim is made.

The [Wayfinder tracker](../../.scratch/graph-memory-roadmap/frontier.md) has three open external/future items: real teammate-app integration/ownership, an actual customer pilot, and the final delivery gate depending on those. The real model-driven/blind research study and actual event submission remain later execution outcomes. They have not been marked complete merely because the local core works.
