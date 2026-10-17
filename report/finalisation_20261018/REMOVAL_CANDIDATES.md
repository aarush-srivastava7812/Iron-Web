# Removal candidates — before deletion

18 October 2026. No referenced subsystem is approved for removal by this table.
Commands below were run locally; raw Ruff JSON is in the ignored evidence directory.

| Candidate | Evidence / reason | Risk | Recommendation |
| --- | --- | --- | --- |
| `dashboard/frontend/public/events.json` | `rg -n events.json dashboard/frontend/tests` finds fixture reads in memory/graph-layout tests; live browser test asserts it is never requested. `src/main.jsx` imports `LiveApp.jsx`. | Test coverage loss if removed. | KEEP as fixture. |
| `src/App.jsx`, `src/components/*`, `memory.js`, `graphLayout.js`, legacy CSS | Legacy mock application imports components; fixture/unit tests and historical browser suites refer to behavior/layout. Current entry imports LiveApp. | Referenced fixture/history code. | KEEP pending explicit archival approval; no live import proves only exclusion from current bundle, not zero value. |
| `dashboard/frontend/tests/legacy/*.fixture.js` | Referenced legacy fixture UI; Playwright config matches only `*.spec.js`. | Historical coverage/reference loss. | KEEP, labelled legacy. |
| `server.py` / `web/` | Root README startup, `tests/test_api.py`, specification and maintenance interfaces reference standalone memory APIs. | Runtime/test references. | KEEP. |
| `shared_server.py` | `docs/shared_memory_service.md`, setup/client examples and shared-service HTTP/recovery tests reference it. | Authenticated shared-service interface and recovery workflows. | KEEP. |
| `research/` and upstream adapters | Research README and evaluation scripts/tests explicitly use project mechanisms and real-package adapters. | Evaluation reproducibility. | KEEP; not required for live demo is not proof of dead code. |
| `report/` historical outputs | Current architecture/README/system report cite dated results and limitations. | Evidence/provenance loss. | KEEP; label stale evidence rather than deleting. |
| Imported GLM setup guide | Credential exposure plus prose inconsistent with code defaults. | References exist; historical setup notes. | REPLACE sensitive section in place (explicitly authorized Phase 1); no file deletion. |
| Tracked `.scratch/graph-memory-roadmap/` and `.scratch/three-tier-memory/` Markdown | `git ls-files .scratch` finds 26 historical design notes despite ignore rules; `docs/three_tier_memory_usage.md` references implementation notes. No tracked env/session credential files found. | Referenced design/history. | KEEP pending approval to relocate/untrack; cannot claim `.scratch` is entirely untracked. |
| Booking review `_fallback_reviews` | `website.py` calls it after provider failure; canned text claims verified amenities/taxes, invented scores and successful multi-agent assessment. | Runtime reference; misleading fallback is a real risk. | REPLACE with visible unavailable error and remove canned function ONLY after approval. |
| `Evidence` imports in explore/stay, `AgentStatus` in support, unused gateway in agents API | Ruff F401; symbol has no references in each importing module. Imported schema/gateway modules already used elsewhere; no required import-time registration identified. | Low. | DELETE only unused import names. |
| Unused `os` in five catalog builders, `random` in benchmark script, `HTTPException` in offers | Ruff F401; no references in the importing module. Standard-library/FastAPI symbols have no necessary import side effect here. | Low. | DELETE unused import names only. |
| `ToolResponse` / `get_tools` in travel_tools/__init__ | Ruff F401 but package-level imports may be public reexports. | Public import contract. | KEEP; do not treat as zero-risk. |
| `COMMON_CSS` imports in regional generators | Ruff F401, but imported builder module may perform generation at import time; source needs separate side-effect audit. | Generation behavior. | KEEP. |
| Assigned-but-unused locals and broad exception handlers | Ruff F841 / grep `pass`, prints and exception paths. Some right-hand calls or cleanup guards have behavior. | Removing expressions can change execution. | KEEP unless independently proven safe; no blanket autofix. |
| Python/npm dependencies, env/config keys | Core config validates unknown keys; requirements split runtime, GPU and research profiles. No comprehensive dynamic usage proof for optional packages yet. | Breaking optional evaluation/GPU paths. | KEEP; unused-dependency removal remains unverified. |

Evidence commands: `python -m ruff check agents memory dashboard scripts tests
stitch_ai_travel_booking_platform/backend/app --select F --output-format json`;
`rg -n 'events.json|server.py|shared_server.py|ResearchEngine|MemoryToolAdapter'
dashboard/frontend/tests tests scripts docs research/README.md README.md`;
`git ls-files .scratch`. No data model, provider, or agent/tool contract change is
proposed. No referenced file deletion or Git history rewrite has been performed.
