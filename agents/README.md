# Iron Web × Travel Agency — Multi-Agent System

Implementation of `agents/architecture.txt` and the specs in
`Iron_Web_Individual_Agent_Specs/`. **Iron Web stays the shared long-term
memory backbone** — this package adds orchestration around it, not a new
memory layer.

## Layout

```
agents/
  orchestrator.py            # Travel Orchestrator facade (single entry point)
  trip_consultant.py         # requirements → structured TripBrief (+clarification)
  stay_agent.py              # accommodation shortlist + trade-offs
  tour_guide_agent.py        # attractions/experiences matched to interests
  food_guide_agent.py        # cuisine/restaurant picks honoring dietary needs
  explore_agent.py           # destination discovery, diverse + relevant
  itinerary_planner.py       # day-wise schedule with bounded revision
  budget_booking_agent.py    # itemized estimates, gated booking flow
  travel_support_agent.py    # packing, disruption, emergency guidance
  schemas.py                 # typed contracts for everything
  config.py                  # agents/.env settings (NVIDIA_API_KEY manual)
  orchestration/             # LangGraph state, routing, graph, checkpointing
  memory_gateway/            # the ONLY path agents may use to reach Iron Web
  travel_tools/              # provider-independent tools (live + mock backends)
  resource_manager/          # shared NIM client, inference scheduler, monitor
  validation/                # budget / itinerary / result validators
  api.py                     # FastAPI service (port 8100)
  tests/                     # pytest suite (real MemoryEngine, isolated stores)
  scripts/cleanup_shared_graph.py
```

## Quick start

```powershell
# 1. FalkorDB (compose.yaml at repo root)
docker compose up -d

# 2. (optional) travel data backend for live catalog data
cd stitch_ai_travel_booking_platform/backend
..\\..\\.venv\\Scripts\\python.exe seed.py
..\\..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000

# 3. agents service (venv-cpu has the memory stack)
cd <repo root>
.venv-cpu\\Scripts\\python.exe -m uvicorn agents.api:app --port 8100

# 4. ask for a plan
POST http://127.0.0.1:8100/agents/query
{"request": "Plan a 3 day trip to Goa for 2 with a budget of 50k",
 "user_id": "demo-user", "session_id": "s1", "page": "plan"}
```

Endpoints: `GET /agents/health`, `POST /agents/query`, `GET /agents/memory/{user_id}`,
`GET /agents/resources`, `POST /agents/validate`.

## Page → agent mapping (from the architecture)

| Page | Agents |
|---|---|
| Stays | Trip Consultant, Stay Agent (+ Budget when pricing) |
| Tour Guide | Trip Consultant, Tour Guide Agent (+ Planner on route asks) |
| Food Guide | Trip Consultant, Food Guide Agent (+ Explore for discovery) |
| Explore | Trip Consultant, Explore Agent (+ specialists as needed) |
| Plan | full pipeline: Consultant → Explore/Stay/Tour/Food (parallel) → Itinerary → Budget → validation |
| Support | Trip Consultant, Travel Support Agent |

Only needed agents run; independent research runs as parallel LangGraph
branches; validation failures trigger a bounded revision loop (max 2).

## Memory rules implemented

- All reads/writes go through `MemoryGateway`; agents never touch Qdrant/FalkorDB.
- Ownership metadata (`user_id`, `session_id`, `agent_id`, `kind`) on every record;
  retrieval filters by user before returning anything.
- Duplicate-safe writes: deterministic ids + near-duplicate similarity guard;
  retries never create copies.
- Selective writes only: durable preferences, decisions, outcomes — never chat
  noise, credentials, or intermediate reasoning (policy: `policies.py`).
- Temporal retrieval uses Iron Web's `temporal_mode` ("now"/"historical").
- Tests run against an isolated FalkorDB graph name + temp Qdrant path.

## LLM / resources

- One shared NVIDIA NIM client (`resource_manager/model_registry.py`), enabled by
  `NVIDIA_API_KEY` in `agents/.env` (paste manually). Without a key every agent
  uses its deterministic fallback — the system works fully offline.
- Inference concurrency bounded by a semaphore (`scheduler.py`); device status via
  `resource_monitor.py` / `GET /agents/resources`.

## Tests

```powershell
.venv-cpu\\Scripts\\python.exe -m pytest agents/tests -q          # 39 passed
.venv-cpu\\Scripts\\python.exe -m pytest tests -q                  # existing Iron Web suite
```

Note: two pre-existing collection errors in `tests/` require the optional
`openai` package (`requirements/nim.txt` profile); they are unrelated to this
package and fail identically on a clean checkout without the NIM extra.
