# Evidence and unresolved items

Prepared October 18, 2026, Asia/Calcutta. Track 02 was confirmed directly by the user during drafting. The draft is based on the current working tree, retained reports, Git history, and the fresh fixture run below. Existing unrelated working-tree changes were preserved.

## Fact-check table

| Claim in the post | Supporting file or command |
| --- | --- |
| The approved budget changes from 1,000 to 600, preserves sources, flags `trip_plan`, and leaves completed `seat_note` without review. | Fresh command: `.\.venv\Scripts\python.exe scripts/demo_memory_lifecycle.py --report blog/evidence/lifecycle-20261018`; [results](evidence/lifecycle-20261018/results.json); [query output](evidence/query-results.json). All nine script checks passed. |
| The recorded Voyara flow uses seven hosted specialists and changes INR 200,000 to INR 120,000, while context accounting uses bytes. | `report/video_demo_20261018/recording.json`, `youtube-upload/voiceover-transcript-reviewed.txt`, `agents/memory_gateway/three_tier.py`, `DEMO.md`, and the two canonical screenshots. This website flow was not rerun for this draft. |
| New restrictions originally missed existing work; the graph now watches relevant requirements and traverses used claims/prerequisites. | `report/nvidia_memory_fixes_20261015/README.md`, `memory/lifecycle/service.py` (`_work_requirements`, `register_work`, `invalidate_work`, `handoff`), and commit `2a109e9` (`fix(memory): guard agent decisions and revalidate changing requirements`). |

## Fresh execution

- Existing script run successfully using the real cached `BAAI/bge-small-en-v1.5` model on CPU, embedded Qdrant, and the local FalkorDB service.
- Isolated graph: `lifecycle_demo_541ada2f305a`. Fixture export contains 41 nodes and 58 relationships. Those are fixture counts, not product-scale claims.
- Questions include `What is the traveller's current budget?`, with supported value 600 before the later proposal; a later conflicting agent proposal yields `disputed`. A phone-number query yields `missing`.
- Full outputs: [results](evidence/lifecycle-20261018/results.json), [graph export](evidence/lifecycle-20261018/graph.json), [query outputs](evidence/query-results.json).
- Reproduce read-only queries: `.\.venv\Scripts\python.exe blog/evidence/verify_queries.py`. This script reads the fixture's recorded graph name. It executes four queries present in the lifecycle service plus one explicitly diagnostic path query. It writes only its local JSON result file.
- The downstream-work query returns no rows in this fixture; it does not demonstrate a downstream dependency chain. The direct used-claim query returns `trip_plan`.
- The raw path query is structural. After the later 900 proposal, current eligibility must still be checked by recall/handoff rather than inferred from raw node properties or the variable named `current`.
- No new hosted inference, full website acceptance, destructive graph-removal experiment, performance benchmark, or cloud deployment was performed for the blog. No timing claims were added.
- The new isolated graph remains available for inspection. The fixture vector directory is ignored by the generated local `.gitignore`.

## Graph inventory

Actual storage labels: `Entity`, `Observation`, `MemoryClaim`, `MemorySource`, `MemoryContext`, `MemoryField`, `MemoryWork`.

Relationship types in the graph store and lifecycle layer: `RELATES`, `ABOUT`, `CONTRADICTS`, `SUPERSEDES`, `SUPPORTED_BY`, `IN_CONTEXT`, `ASSERTS_FIELD`, `RETRACTS_FIELD`, `REFERS_TO`, `CONFIRMS`, `RETRACTS`, `CANONICAL_ALIAS`, `IDENTIFIES`, `USES`, `DEPENDS_ON`.

Sources: `memory/graph/falkordb_store.py` and `memory/lifecycle/service.py`. These are implemented types, not a claim that every fixture contains every type. Claim supersession points replacement → earlier claim; the older Observation supersession API points earlier → replacement. The post's diagram/query uses MemoryClaim semantics only. Context cards and dashboard-derived nodes are not additional labels asserted here.

## Essential query operations

1. Read exact claim state: `MATCH(c:MemoryClaim {id:$id}) RETURN properties(c)`; `MemoryLifecycle.claim()`.
2. Find work using changed claims: `MATCH(w:MemoryWork)-[:USES]->(c:MemoryClaim) WHERE c.id IN $ids RETURN DISTINCT w.id LIMIT $limit`; `invalidate_work()`.
3. Traverse dependent work: `MATCH(w:MemoryWork)-[:DEPENDS_ON]->(p:MemoryWork) WHERE p.id IN $ids RETURN DISTINCT w.id LIMIT $limit`; `invalidate_work()` iterates a bounded frontier and marks affected work stale.
4. Fetch source evidence: `MATCH(s:MemorySource) WHERE s.id IN $ids RETURN properties(s)`; the lifecycle evidence-view code.
5. Select current scoped field candidates: `fetch_field()` matches `group_key`, recorded/effective time, acceptance time and end state, then calls `selected()` to apply lifecycle rules. See `memory/lifecycle/service.py:864`. This selection is exercised by the fresh demo; the separate read-only verification script does not log every internal query.

The post includes a second query that joins work, used claim, replacement and source for inspection. It was executed successfully and returned `trip_plan | 1000 | 600 | demo_new_budget | stale`. Full parameters and output are saved in `evidence/query-results.json`.

No shortest-path, PageRank, community-detection, or MCP-transport claim is made. `memory/tool_adapter.py` explicitly supplies an in-process Python adapter. `agents/memory_gateway/three_tier.py` and the website `agent_runtime.py` establish the connected context path; the older `engine_factory.py` retains a graph-unavailable development fallback.

## Other learning/limit sources

- Vector placement: `report/vector_placement_20261013_p5_paired/REPORT.md`. Measured architectural paths differ in deployment; the post avoids vendor-wide performance conclusions.
- Dashboard freshness: commit `9633f65`, `fix(dashboard): Detect stalled memory streams and reconnect`.
- Byte accounting: `_BytesConsumer` and `application_context_runtime()` in `agents/memory_gateway/three_tier.py`.
- Recovery boundary: `memory/storage.py`, `README.md`, `report/finalisation_20261018/RECOVERY.md`. No durable cross-store transaction or engine fix is claimed.
- Reuse timeline: `docs/hackathon_memory_direction.md`, `docs/memory_delivery_route.md`, README development history, and commit `0ee86c9` for the October 13 FalkorDB migration. The post acknowledges pre-event work.
- AI assistance: Git commits carry Codex co-author attribution; this blog was also drafted with an assistant. Keep the disclosure.

## Unverified items and collected NORTH questions

- [NORTH: Which public URL should readers use for the demo video? Replace TODO-demo-video above.] This is the open question in both post copies. The existing repository MP4 is tracked, but external browser retrieval did not confirm anonymous access. Verify it in a signed-out window or upload the video yourself.
- [NORTH: Have the organizers confirmed how the pre-event memory/FalkorDB implementation fits the event's new-work rule?] The official event page requires new event work while permitting general infrastructure reuse. The repository records an October 13 migration and later event-period integration. Eligibility and submission acceptance were not verified; the post does not claim them.
- The registered track is resolved: the user answered `track 2`. No other entered track is asserted.
- No public endpoint was reverified during blog drafting. The deployment branch has since been integrated; `deploy/voyara/README.md` records the earlier hosted endpoints and setup, separately from the local recording.
- The authenticated submission form was not inspected. A dedicated blog field and any mandatory Discord-sharing requirement remain unverified. The publishing guide states these conditions rather than inventing field names or requirements.
- The first-person descriptions are evidence-grounded but need the author's final read for personal intent and experience. No financial/time-loss statistics or general benchmark-accuracy claims were invented.

Sources checked online for publishing only: [official event](https://www.wemakedevs.org/hackathons/falkordb), [submission entry](https://www.wemakedevs.org/hackathons/falkordb/submit), [DEV editor guide](https://dev.to/p/editor_guide), [DEV publishing help](https://dev.to/help/writing-editing-scheduling), and [AI-assisted article guidance](https://dev.to/guidelines-for-ai-assisted-articles-on-dev).
