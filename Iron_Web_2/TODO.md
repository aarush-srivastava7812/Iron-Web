# Repository integration checklist

Source requirements: `updates.t.txt` (the supplied updates file).
Target: replace the previous memory backend with Iron Web 2 throughout the project.
Canonical travel records remain in the application database; memory supplies evidence and preferences.

- [x] Inventory all entry points, preserve existing edits, and define data migration/rollback.
- [x] Make Iron Web 2 the active engine behind agents, services, APIs and local tools.
- [x] Preserve authentication, tenancy, confirmation, event receipts/retries, source history and safe deletion.
- [x] Resolve the measured reranker regression and verify multilingual retrieval.
- [x] Connect website, chatbot, dashboards and inspection feeds to the active engine.
- [x] Implement structured travel constraints and hard-filter/soft-rank destination discovery.
- [x] Generate and validate feasible day-by-day itineraries, including arrival/departure and rest windows.
- [x] Calculate deterministic budgets, hidden transfer costs, assumptions and concrete alternatives.
- [x] Compare complete trip options with transparent fit scores and trade-offs.
- [x] Persist trip creation, retrieval, revision, duplication, status and deletion without losing edits.
- [x] Validate overlapping reservations, check-in/out, arrival, transport and city conflicts.
- [x] Add exhaustion-aware scheduling, contingencies and preference-conflict explanations.
- [x] Add alternatives/replanning and simulated reservations with explicit demo status.
- [x] Add nearby discovery, transport/accommodation suitability, collaboration, packing and readiness.
- [x] Learn explicit feedback/rejections as preferences without fabricating inferred facts.
- [x] Integrate TinyFish enrichment and shortlist research with sources, verification dates and unknowns.
- [x] Revalidate affected research after changes and provide missing/stale/high-impact research jobs.
- [x] Implement Geofabrik/OSM ingestion with entity matching, attribution and provenance.
- [x] Update dependency profiles, Docker, launchers and deployment configuration.
- [x] Run isolated migration, memory, authorization, API, frontend and browser verification.
- [x] Remove temporary test data and report completed work plus any external blockers.

No GitHub push or hosted deployment is included in this local implementation run.


Implementation and verification notes (2026-10-20):

- The active `memory.engine.MemoryEngine` now resolves to Iron Web 2. The explicitly named `LegacyMemoryEngine` remains for migration/rollback and baseline comparisons; it is not an application fallback.
- Authentication, tenant isolation, journal receipts, confirmation checks, context proofs, work dependencies and leases remain in the control plane. Native sources, claims, embeddings, decay, reinforcement and pins live in FalkorDB. Context dictionaries expose fixed_cache, hot_cache, persona and similar_memory; score types are labelled.
- Local model execution defaults to CUDA. The actual website interpreter was repaired and checked with CUDA; hosted CPU execution remains an explicit configuration. The application defaults to semantic ranking because the earlier cross-encoder ablation regressed on English; optional reranking remains available, without claiming that regression is solved in the model itself.
- Both existing SQL databases were backed up under ignored data/backups. The main website retained its 22 users, 16 conversations, five workspaces and 39 existing bookings. All 22 memory spaces were migrated, retaining 55 source events including explicit profiles. Comparison against the previous graph found zero current-answer differences across 104 fields. Deleted sources, effective dates and work references have dedicated migration handling.
- Trip APIs and the Travel Desk share revision-checked SQL workspaces. Discovery hard-filters known requirements, schedule edits reload catalog identities/prices, and budgets include return travel, transfers, meals, stays, activities, miscellaneous costs and contingency. Comparison includes interest fit, readiness, pace, cost and known transport effort.
- Cross-trip checks cover canonical booking requests and simulated trip reservations. Readiness notes, collaboration, explicit preference feedback, half-day/rest-day replanning and source-backed nearby places are persisted. Existing agents still run through their original workflow.
- TinyFish Search/Fetch was verified live (10 sources, three fetched pages), and optional NIM extraction produced three verbatim sourced season/permit statements. Research has bounded queues, private owner-scoped results, freshness windows, high-impact/missing-field inspection and reviewed entity candidates. Provider research is on demand; startup never replays chargeable jobs automatically.
- The India Geofabrik PBF was downloaded and checksum-verified. Streaming pyosmium import produced 10,563 tourism nodes/ways, matched to 18 existing catalog destinations. The website database contains those features and OSM attribution. Relation geometry is intentionally not synthesized; those features require an area-assembly extension.
- Verification: connected application/context/shared-service suites; existing website, checkout and dashboard tests; main.py API/migration checks; real headless desktop/mobile browser checks; dashboard build and 13 JavaScript tests; real GPU memory checks and 50 English/Hindi/Hinglish/adversarial prompt cases. Test cases and reports are in main.py rather than new loose report files.
- New tests use isolated SQL and graph data and delete their owned temporary stores. Original application data and the previous graph are retained for rollback.

Practical limits: prices remain clearly labelled sample estimates. Unknown opening hours, accessibility, permits, route availability and date-specific weather are not presented as verified facts. Source quotes are evidence to review, not automatic guarantees. No real supplier booking/payment, GitHub push or hosted deployment was performed. Hosted memory capacity/load validation is a separate deployment check; the multilingual FP32 model needs more headroom than the previous small English model.
