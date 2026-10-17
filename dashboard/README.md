# Ironweb live memory dashboard

The **website** is the Voyara travel application. The separate **dashboard**
monitors its actual three-tier memory through a read-only HTTP relay. The normal
React entry point never loads `events.json` or silently falls back to sample data.
The old fixture and replay helpers remain intact for compatibility tests only.

## Local run

Use the existing environment and running FalkorDB (`docker compose up -d`). Keep
one website process per embedded Qdrant/journal directory. From repository root,
start each service in its own terminal:

```powershell
.\.venv\Scripts\python.exe scripts/run_live_dashboard.py website
.\.venv\Scripts\python.exe scripts/run_live_dashboard.py dashboard
cd dashboard/frontend
npm run dev
```

- Website: http://127.0.0.1:8000
- Dashboard React UI: http://127.0.0.1:5174
- Separate read-only relay: http://127.0.0.1:8200

The local launcher reuses the application's SQL/memory locations and publishes
only the ordinary `voyara_local_developer` account. Sign in using **Continue as
Developer** in the local website, build a trip, and open the dashboard. It stores
the private publication/session grants in ignored `.scratch/ironweb-live/.env`.
It does not replace user records or delete existing data. Local developer login
is loopback-only; do not use this launcher as a public deployment command.

For a different existing website/account use the server-side publication settings
in [the backend guide](backend/README.md). The relay never opens embedded stores.
On Vercel set public `VITE_DASHBOARD_API_URL` to the separate Railway dashboard
backend origin. Set the dashboard origin in `DASHBOARD_CORS_ORIGINS`. Keep all
publication grants and NVIDIA keys on the servers. The source grant selects one
intended viewing account; this is not a cross-tenant administrator view.

## What is shown

- A 56px top bar, full-height explorer/stage/inspector, one replay dock, side
  drawers below 1280px, and five views: Graph, Agent wiring, Activity,
  Architecture, Resources.
- Real FalkorDB nodes/relationships plus explicitly derived captured context/card
  nodes. Colors identify tiers. Size reflects claim accesses in retained events.
  Labels are selective, with halos/collision avoidance; zoom reveals all labels.
  Cursors and edge pulses map to actual events; reduced motion disables movement.
- Registered, observed and currently reading agent counts are distinct. The
  current application registers nine memory actors; the tested full plan uses
  seven hosted specialists plus the orchestration memory reader.
- Inspector Diff/History/Links, observed before/after values where captured,
  claim provenance, field support and clickable history. Forgetting clears
  retained captured context/change payloads for the forgotten scope.
- Context X-ray with exact consumer units and source links; cache hits/quotas;
  provider input/output usage; actual supported RAM/VRAM observations; per-event
  context/agent latency. GPU utilization, no-memory savings, durable byte quota,
  provider prompt-cache token breakdown and unrecorded measurements show N/A.
- Source details inspect actual Qdrant point payloads/numeric vectors and SQLite
  receipts. Credentials are masked with model/fingerprint identity, never a key.

## Replay semantics and limits

Follow-live selects new observed activity. Clicking an event pins replay;
Space plays/pauses, arrows step, 1–5 change views, F toggles follow, / opens search,
and Escape closes panels/clears selection. URL state uses `view`, `event`, `mem`.
The dock groups the nine agents into Planning/Research/Review workstreams; the
Activity view shows every actual actor separately. Chapters target actual event
kinds, rather than fabricated milestones.

Context history is captured per event and can be replayed. The graph/claim store
and hardware/provider aggregates are latest snapshots, not a fabricated complete
historical database. The UI labels historical context versus the latest KG.
Observations retain 500 events and 256 latest contexts and reset on owner restart.
Graph/vector/receipt pages are bounded; source details expose counts/truncation.
The existing synthetic travel catalog remains honestly labeled by the website;
actual agents and actual memory operations do not make supplier listings live.

## Verify

```powershell
npm --prefix dashboard/frontend run build
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run test:browser
$env:VOYARA_AGENT_MODE='offline'
.\.venv\Scripts\python.exe -m pytest tests/test_memory_dashboard.py tests/test_application_integration.py -q
```

Browser checks require the live services and a completed trip; they use the actual
feed, not mocked memory. `tests/live-flow.mjs` performs website sign-in and submits
a real plan, which can make paid/provider requests under the existing NVIDIA
configuration. It does not book or pay for travel. Superseded mock UI browser
checks are archived under `tests/legacy`; unit fixture compatibility is retained.

See [audit](../docs/capabilities.md), [creative feature choices](../docs/dashboard_features.md),
and [live verification](../report/dashboard_live/README.md).
