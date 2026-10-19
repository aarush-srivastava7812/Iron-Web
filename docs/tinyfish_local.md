# TinyFish travel research (local)

The existing authenticated memory gateway and workflow remain the owner of trip requirements. In TinyFish mode, four specialists research public destination information, stays, restaurants, and attractions with the TinyFish Agent API. Requirement parsing, itinerary assembly, exact budget arithmetic, validation, memory ownership and saved draft versions stay in the application. NVIDIA and explicit offline modes remain available.

## Local setup

Create the Git-ignored file `agents/.env`:

```dotenv
TINYFISH_API_KEY=your-private-key
VOYARA_AGENT_MODE=tinyfish
TINYFISH_TIMEOUT_S=480
```

Use the existing local FalkorDB service, build the frontend with `npm run build` in `stitch_ai_travel_booking_platform/frontend`, then start from the repository root:

```powershell
& .venv/Scripts/python.exe scripts/run_voyara.py --port 8094 --agent-mode tinyfish
```

Open `http://127.0.0.1:8094/#planner`, sign in using local demo access, and submit a trip. The explicit launcher argument selects TinyFish for that process only. Restart after editing the key. Keep credentials server-side; do not add the key to Vite variables, commit it, or include it in reports.

## Memory and result handling

- TinyFish receives only a generic public destination research task. Dates, budget, party size, personal preferences, scoped memory, and conversation history stay local. Local code applies the current destination, budget and dietary requirements to returned research. This means returned web rates are indicative, not quotes for the traveler’s exact dates.
- Requests use `/v1/automation/run-async`, followed by bounded `/v1/runs/{id}` polling. Timeout attempts to cancel the provider run. Creation is never automatically repeated, preventing duplicate billable tasks after an ambiguous failure.
- A completed provider run is accepted only if its result validates. Empty results, mismatched destinations, invalid source links, malformed prices, unknown price units and insufficient dietary evidence fail explicitly. There is no silent fallback to catalog results in TinyFish mode.
- Valid public research is cached for one hour under the local launcher's `.scratch/tinyfish-public-research` directory. Original source timestamps and provider run IDs are retained. Descriptive city labels and extra findings are normalized to a bounded shortlist; a different city remains a failure. Cache files contain public research, not trip memory or credentials.
- Expired memory proofs still require a new validation pass. Completed public research can be reused in that pass, while current private requirements are applied again. If research has already failed, an expired proof returns failure rather than automatically repeating paid tasks.
- Accepted findings carry source links, retrieval timestamps, and indicative-price caveats. They never acquire synthetic catalog IDs or become confirmed traveler facts. The existing memory gateway revalidates requirements before accepting a plan.
- Web stays are selected by source reference; the saved editor can switch between them without confusing missing catalog IDs. The UI labels TinyFish research separately from local calculations and historical offline/NVIDIA work.

## Verification

```powershell
$env:VOYARA_AGENT_MODE='offline'
& .venv/Scripts/python.exe -m pytest tests/test_tinyfish_agents.py tests/test_stochastic_agents.py tests/test_application_integration.py -q
```

These tests use simulated provider responses, real isolated FalkorDB/Qdrant stores, and explicit test embedding fixtures. They verify private context exclusion, provider lifecycle/failures, source and cost validation, current memory use, isolation, saved drafts, stay edits and stale-plan invalidation.

With the local TinyFish server running and a real key configured, this separate manual browser check uses hosted provider credit:

```powershell
& .venv/Scripts/python.exe scripts/check_tinyfish_local.py
```

It submits one Jaipur trip from the browser, checks four actual research executions, dates, budget, source links and saved draft readback. The report is under `report/tinyfish_local_20261019/`; no key or cookies are written there.

## Hosted deployment

The browser now starts owner-scoped background planning jobs (`message-jobs` and `confirm-jobs`) and polls short status requests. Job results persist in the application database and can be read after a browser refresh. Identical active retries reuse the job; different overlapping requests are rejected. The single-worker deployment bounds the queue to eight runs and executes one plan at a time. Interrupted jobs fail explicitly after process restart; paid provider work is never replayed automatically.

At most two TinyFish automations are submitted at once. The other specialists wait locally, before starting their provider timeout. This avoids spending the execution budget in TinyFish's queue. A cold destination can require two waves of research; the frontend polls for up to twenty minutes. Completed public findings remain reusable for one hour.

Compatible traveler engines share one process-wide embedding model with serialized inference; graph, vector, journal and private memory remain separately scoped. The container limits embedding and graph threads. Render still uses its existing free tier and ephemeral storage; server replacement can discard saved application data. No paid capacity or persistent disk is provisioned by this change.

Configure `TINYFISH_API_KEY` privately on Render and `VOYARA_AGENT_MODE=tinyfish`. Do not expose the key through Vercel frontend variables. `/health` checks process liveness; only a completed live planning run demonstrates provider access and memory/result validation.

For a controlled supplier research task, an optional source hint can be restricted to a destination using `TINYFISH_STAY_SOURCE_DESTINATION` and `TINYFISH_STAY_START_URL`. Other destinations keep normal web research. Local Jaipur acceptance uses the public Jai Niwas supplier brochure at `https://ebrochure.aryaniwas.com/pdfs/Jai_Niwas_25.pdf`; its advertised rate is indicative and does not establish availability for the travel dates. This targeted source test does not prove reliable hotel discovery for every destination.

API references: https://docs.tinyfish.ai/ and https://docs.tinyfish.ai/key-concepts/structured-output .
