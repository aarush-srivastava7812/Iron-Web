# Ironweb memory capability audit — Phase 0

Date: 2026-10-17. This is a source audit, not a runtime or browser verification.
No UI code, memory model, application data, or `events.json` was changed in this phase.

## Scope and current truth

The source inventory covers 180 active files and 36,325 lines across `memory/`,
`agents/`, the dashboard frontend/backend, and the travel frontend/backend. Python
classes/functions and source fingerprints are recorded in
[capabilities-inventory.json](capabilities-inventory.json). Dependencies, generated
bundles, historical archives, and secret configuration are excluded. Detailed
implementation review follows the real travel workflow, memory service, context
compiler, store adapters, maintenance, instrumentation, and current UI components.
Research reports are historical measurements, not live application metrics.

The React dashboard currently fetches `/events.json`, validates only three mock
agents and four action types, and constructs a synthetic file hierarchy. Its 40
events contain 21 writes, 11 reads, 7 updates, and 1 forget. Event 27 is a rejected
stale update. Its six fields are `timestamp`, `agent`, `action`, `memoryPath`,
`before`, `after`; no resource metrics are present.

The actual website owns a `SharedMemoryService` per traveler, using FalkorDB,
embedded Qdrant, SQLite receipts, and a shared context runtime. `PROFILES` in
`agents/memory_gateway/three_tier.py` registers nine actors: orchestrator,
consultant, explore, stay, food, tour, itinerary, budget, and support. Registration
is different from observed use or current activity. Actual claims and sources
are identified by real IDs and scopes, not the mock Markdown filenames.

The existing separate dashboard relay already exposes snapshot/events/stream,
agents, tiers, graph, shared-memory, vectors and credential metadata. The React
UI does not consume it. The preserved plain inspection page does; its existence
does not mean the React UI is connected.

## Operations and where they appear today

**MOCK ONLY** means the operation is illustrated with fixture data in the React
UI, rather than observed from the live memory system. **NOT SHOWN** refers to
that React UI. A method being implemented does not mean a trip executes it.

| Operation | Actual implementation and limitations | React visibility today |
| --- | --- | --- |
| Read a saved memory | `MemoryEngine.get`, authenticated shared recall/search/context APIs | MOCK ONLY: graph pulses, activity, inspector |
| Write / ingest | `MemoryEngine.add/add_batch`, shared submit/process journal; confirmed application intake | MOCK ONLY: write events and version history |
| Update / supersede | Immutable typed sources; confirmed supersede/correct/retract lifecycle changes. Ordinary engine records also have update | MOCK ONLY: fixture before/after diffs; does not represent real lifecycle semantics |
| Forget / delete | Engine delete, shared forget/redaction, trip/source forgetting; invalidates cached contexts | MOCK ONLY: event 36 removes a graph node |
| Promote / demote between tiers | No general durable tier-transition operation was found. Hot context/cards are derived bounded views over durable claims; optional CUDA copies card vectors | NOT SHOWN; do not invent promote/demote events or treat copying as authority transfer |
| Consolidate | `MemoryConsolidation.consolidate_window`, invoked explicitly through engine maintenance; provenance retained; extractor-dependent | NOT SHOWN; not established as an automatic travel-trip step |
| Deduplicate stored records | Exact text/type/validity merge with temporal/contradiction safeguards in maintenance | NOT SHOWN |
| Suppress duplicate proposals | Standalone `WriteManager` uses deterministic IDs and near-duplicate checks. Connected three-tier gateway rejects inferred preference proposals instead | NOT SHOWN; do not attribute standalone proposal outcomes to the connected path |
| Decay importance | Explicit age-based exponential maintenance; synchronizes graph/vector importance; idempotent against original importance | NOT SHOWN as real activity. Explorer retention bars are an illustrative UI formula |
| Detect conflicting facts | Lifecycle recall/selection and contradiction handling identify disputes and invalid evidence | MOCK ONLY: stale-write conflict, which is a different mechanism |
| Resolve / correct / retract | Confirmed user sources, lifecycle history and protected-rule checks; ambiguous mandatory fields pause planning | NOT SHOWN as live resolution or blocked planning |
| Reject generated fact writes | `ThreeTierGateway.propose_writes` emits `inferred_writes_rejected`; confirmed intake remains authoritative | NOT SHOWN |
| Create relationships / provenance | Typed claim/source/reference links and graph ingestion; real FalkorDB relationship types | MOCK ONLY: path hierarchy and payload references, not the database KG |
| Vector retrieval | Qdrant discovery plus vector retriever; bounded filters and candidates | NOT SHOWN |
| Hybrid graph retrieval and reranking | Bounded expansion, temporal/lifecycle reconciliation, optional reranker, weighted scores, traces | NOT SHOWN; connected structured context reads do not imply this pipeline ran |
| Exact structured recall | Subject/predicate/scope resolution and required-field status; current trip takes precedence over permitted profile fallbacks | NOT SHOWN |
| Temporal eligibility / historical recall | Valid-from/until, recorded/known-at time, supersession/retraction/identity support | NOT SHOWN |
| Assemble hot context | `ContextRuntime.compile`: bounded agent instructions and traveler essentials, required-field checks | MOCK ONLY: a generic tier label/list |
| Build and select task/mood cards | Source-derived templates, token bounds, matching; mood expiry; provenance IDs | MOCK ONLY: generic context-card files; no actual selected-card contents |
| Pack context within budget | `ContextRuntime.assemble`: avoids repeated field lines, enforces evidence/prompt/output bounds, removes optional cards when needed | NOT SHOWN |
| CPU/CUDA card ranking and fallback | `CardRouter` / `CardIndex`: actual CPU ranking, optional bounded CUDA tensor, explicit fallback reason | NOT SHOWN; tier storage text is not a hardware measurement |
| Payload caching / reuse | `PayloadCache`: TTL + byte/entry quotas + LRU; context uses source/configuration fingerprints | NOT SHOWN |
| Cache eviction / expiry | LRU removal at quota, expired-entry removal, rejection of oversized entries | NOT SHOWN; no per-eviction event emitted today |
| Cache invalidation / stale-proof validation | Context source stamps, signed validation, scoped purge on source changes; app may rebuild stale work up to twice | NOT SHOWN |
| Durable receipt queue / recovery / retry | SQLite event states, attempts, idempotent source IDs, pending gates and retry/recovery | NOT SHOWN |
| Work dependencies / leases / handoff | Shared work APIs and lifecycle work records support claim/complete/lease/dependency flow | NOT SHOWN; not proven used by this website execution path |
| Selective specialist orchestration | LangGraph routing and parallel specialist branches; profiled context reads; validation and bounded revisions | MOCK ONLY: three schematic agents/tools, not real workflow actors |
| Hosted tool-agent execution / offline mode | `agents/agentic.py` selects NVIDIA mode from configuration, otherwise explicitly labeled offline results | NOT SHOWN |
| Store consistency / compensation | `coordinated_write` graph publication + vector snapshots/compensation; process consistency, not crash atomicity | NOT SHOWN |
| Tenant/trip isolation and publication grants | Authenticated principals, owner checks, scoped sources, read-only dashboard HTTP grant | NOT SHOWN beyond a synthetic session name |
| Inspection / reconnect / feed gaps | Read-only snapshot and SSE; boot IDs and bounded-log gap/reset reporting | NOT SHOWN; React has a local file reload only |
| Local model loading / device selection | Lazy embedding/reranker/extractor initialization and provider status | NOT SHOWN |

## Measurements available now

“Available” below means implemented output, not that this audit sampled a running
instance. Scope, unit, timestamp, and measured/derived source must remain visible.

| Metric / evidence | Existing producer | Correct interpretation / integration work |
| --- | --- | --- |
| KG nodes and edges | `memory/dashboard.py`: actual graph pages, labels, relationships and store counts | Page counts differ from whole-store counts; honor paging/truncation |
| Qdrant points and vectors | Vector snapshot; optional numeric vector values, dimensions and cursor | Real point payloads; do not synthesize vector coordinates |
| Claims, validity, provenance, lifecycle state | Shared-memory snapshot / lifecycle APIs | Candidate/history records are not all currently usable facts |
| Durable receipt status and attempts | Snapshot receipt rows and shared journal | Recent page is bounded to 60; pending/failed/redacted states are distinct |
| Registered / observed / reading / recently active agents | `agent_summary` | Retained-window counts; reading means outstanding request seen within 60 seconds, not lifetime or continuous CPU usage |
| Per-agent context reads and cache hits | `context_assembled` observations and agent summary | Hit rate = hits / completed reads, labeled retained window; zero reads means N/A |
| Current context content and claim IDs | Captured context packets | Agent/traveler text, fields, selected cards, extra evidence and provenance are real observed reads |
| Context counts and configured limits | Packet `tokens.agent/traveller/prompt/reserved_output`; policy | Default consumer counts exact UTF-8 bytes under `voyara-deterministic-utf8-v1`, despite fields named tokens. A configured tokenizer changes the unit. These are not hosted LLM prompt-token totals |
| Context capacity status / missing fields | Packet status / required issues | Explain why an agent was blocked without claiming execution succeeded |
| Retrieval/context assembly latency | `ThreeTierGateway.retrieve` emits `latency_ms` on success/failure | Actual elapsed gateway context call; not end-to-end workflow latency |
| Context cache occupancy and quotas | Snapshot cache entries/payload bytes/max entries/max payload bytes | Whole application context runtime; serialized payload quota, not process RSS or per-tier durable storage quota |
| Card device residency and budget | Captured packet residency: device, bytes, tensor peak, card budget and fallback | Owned card tensors only, not all GPU VRAM; CPU path can have zero CUDA resident bytes |
| Context proof validation outcomes | `context_validated`: valid and packet count | Actual freshness outcome; never publish proof tokens |
| Rejected inferred writes | `inferred_writes_rejected`: count | Measures proposals rejected by policy; does not mean duplicate memory was removed |
| Database status and configuration | Snapshot database and model sections | Identifies FalkorDB graph, embedded Qdrant collection, journal and configured models; does not prove model inference happened |
| Hybrid ranking scores and stage times | `HybridRetriever.retrieve`: `retrieval_trace` | Scores/ranks/candidate counts/vector/graph/conflict/lifecycle/rerank stage times exist on search results, but are not captured by the live dashboard feed |
| Maintenance results | Explicit decay/dedupe/consolidate return dictionaries | Actual outcomes only when invoked. Need event capture to show them over time; do not invoke maintenance just by opening the dashboard |
| Standalone resource snapshot | `ResourceMonitor.snapshot`, `MemoryEngine.get_device_status` | Process RSS on supported Windows path and optional VRAM/provider observations exist, but are not in the connected dashboard feed or a retained time series |
| Agent result latency and work log | `AgentResult.latency_ms`, `AgentExecution` / orchestration result | Hosted agent path records elapsed work and tool names/observations. Not currently published as memory-dashboard events; not a per-NIM-call token bill |
| Feed inspection latency | Snapshot `inspection_ms` | Dashboard read time only; never label it memory retrieval latency |

## Measurements requiring instrumentation or a defined baseline

| Requested metric | Missing piece / honest empty state |
| --- | --- |
| No-memory baseline and token-saving percentage | Define exactly the full-history prompt, same tokenizer/model/template/tools and request; record its count alongside actual. Until then show “baseline unavailable,” not an invented saving |
| Hosted input/output/cache-read/cache-write token counts | Retain provider response usage per request and associate it with workflow/agent. Current NIM client consumes choices and discards usage; context cache hits are not provider prompt-cache hits |
| Exact hosted context breakdown (system/hot/retrieved/history/tools) | Instrument the actual hosted prompt construction and serialization, tokenizer identity and model limit. Current packets count a separate consumer, and `ToolAgent` renders memory lines into its own prompt |
| Complete end-to-end latency and stage attribution | Correlate request/workflow/agent/provider/tool/context timings, including retries and parallel overlap |
| Historical RAM/VRAM/GPU utilization sparklines | Timestamp samples from the process/device actually serving the request. GPU utilization percentage is not emitted by the current resource monitor |
| Used/budget bars for all three tiers in bytes | Hot/card policy limits use consumer units; durable storage has no configured tier-byte budget. Publish like-for-like payload bytes and actual configured limits; absent durable quota is N/A |
| Eviction thresholds and per-eviction markers | Cache limits exist; threshold and remove-reason events do not. Add explicit expiry/quota/invalidation events only if approved |
| Lifetime agent/access counts | Bounded observations reset and drop old events. Persist counters or label them retained-window observations |
| Per-event graph before/after replay | Live snapshots and receipt status do not contain complete historical graph diffs. Capture mutations/snapshots; never infer write diffs from adjacent polling snapshots and claim exact history |
| Promotion / demotion histories | No general tier-transition model exists. Choose whether the product means derived context selection, card residency, or an actual new operation |
| Maintenance and dedupe savings over time | Capture changed IDs, retained/deleted counts and actual size deltas at operation time; aggregate counts alone do not prove token/context savings |
| Retrieval score explanations for real trip reads | Preserve real query traces only when the relevant search/ranker ran. Structured exact-field lookup should explain eligibility/provenance, not pretend it has semantic scores |
| Cost / money saved | Actual provider usage plus correct configured pricing and baseline. No cost estimates should be represented as measured billing |
| Per-metric measured/estimated/simulated source badges | Add optional event metadata plus field-level units/source where mixed. Missing metrics stay null/N/A; do not replace missing values with zero |

## Ranked NOT SHOWN priorities

Ranking criterion: does this let a judge see *why the existing system is efficient*,
with the least additional instrumentation? This ranking is a proposal, not approval
to add these panels or new event kinds.

| Rank | Proposal | Why it matters | Evidence readiness |
| --- | --- | --- | --- |
| 1 | Context X-ray and used/limit meter, including selected claim/card provenance | Shows what each agent actually receives and how bounded selection avoids resending unrelated memory | Existing captured packets; label byte/token units correctly; do not add a savings claim |
| 2 | Context cache hit/miss path and quota occupancy | Shows reuse and bounded payload storage; distinguishes reuse from recomputation | Existing hit flags and cache totals; retained-window hit rate can be derived |
| 3 | Freshness/provenance trail and invalidation outcome | Shows how changed facts invalidate old context and prevent an obsolete plan | Captured claim IDs, field status and validation events; exact invalidation reasons need more instrumentation |
| 4 | Real agent → context read → durable source event trail with latency | Connects actual trip-building work to observed reads across the nine real actors | Existing observation kinds and context-call timings; hosted work logs need publication |
| 5 | Why this memory was retrieved / why another was excluded | Explains relevance and protected-rule/temporal filtering | Field support exists; detailed hybrid traces need feed capture when that pipeline runs |
| 6 | Without-memory comparison | Strongest quantitative efficiency demonstration once a valid baseline exists | New baseline and actual hosted prompt accounting required; until then unavailable |
| 7 | Actual dedupe / maintenance outcomes | Could show reduced redundancy or retained procedural knowledge | Operations exist, but not automatic on this path or captured in feed |
| 8 | Optional CUDA/CPU residency and fallback | Explains bounded acceleration and honest CPU fallback | Residency available; full hardware histories are missing |
| 9 | Receipt lifecycle and recovery | Explains reliability under queued/failed/retried writes | Existing receipt states; additional detail can stay in inspector |
| 10 | Promotion/eviction animation and cost ticker | Visually attractive but cannot currently be justified as a measured efficiency claim | Needs an explicit operation model / capture or provider usage and pricing; defer |

Recommendation: approve ranks 1–3 as the first additions; keep one primary visual
and at most one secondary in each view. Hardware/receipt detail belongs behind
selection/expansion. Do not add every possible operation to every screen.

## Blockers to a truthful live connection (source findings)

1. Replace React's fixture-only loader and hard-coded three-agent validator with
   a live snapshot/observation adapter. Keep optional fixture fields backward
   compatible if `events.json` remains a development/test artifact. Remove the
   fixture from normal application rendering; never fall back to it on feed errors.
2. Preserve actual kinds, IDs, timestamps, graph relationships, scope and receipts.
   A `context_assembled` or `memory_processed` observation is not automatically a
   fabricated file write or complete before/after change.
3. Correct `memory/dashboard.py:credential_status`: it unconditionally reports
   deterministic agents, inactive NIM and zero hosted calls. Current
   `agents/agentic.py`, `ToolAgent` and website runtime can execute NVIDIA agents.
   Configured/masked key metadata can be shown; real invocation counts require
   observations. Never show full credentials or claim a configured key was used.
4. Select the intended authenticated traveler's publication scope. The current
   dashboard is a scoped viewing surface, not an all-users admin console. Do not
   expose unrelated namespaces or share source grants in frontend environment vars.
5. Keep Qdrant and journals owned by the website process. Use the separate HTTP
   relay/SSE rather than opening embedded stores from a second application.
6. Preserve failure, stale, boot-reset and dropped-window states. Retained
   observations are bounded to 500; captured contexts to 256. State this rather
   than presenting complete historical playback or lifetime totals.
7. The website catalog is explicitly synthetic supplier/listing evidence even
   when real agents run. Removing dashboard mock memory does not turn catalog
   listings into verified live travel inventory. Do not delete this factual label
   to satisfy a cosmetic “no demo” request.

## Sequencing and review checkpoint

The direct request groups the work into (1) UI/live connection work and (2)
browser trip testing, with a change report before testing. Within the first
step, the pasted plan explicitly requires Phase 0 first and says “wait for my OK
before adding any.” This audit and ranked proposal are that review artifact.
No UI features, metrics, live publication configuration, or trip creation were
applied during this checkpoint.

After approval, implement the selected UI phase and prepare its live adapter.
Report changed behavior and show 1440x900 / 1280x720 screenshots before the
requested browser trip flow. Browser testing must open the real website and
dashboard, use normal authentication, build a draft trip (no booking/payment),
and match observed memory events/IDs/scope against the resulting dashboard.
If the browser plugin cannot reach local services or needs a login, report that
specific limitation rather than fabricate a successful test.

Baseline screenshots from the preceding layout review (unchanged UI):
- [1440x900](../report/dashboard_layout/1440x900.png)
- [1280x720](../report/dashboard_layout/1280x720.png)
