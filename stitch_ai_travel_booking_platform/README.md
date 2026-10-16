# Voyara travel platform

Voyara now uses the supplied Iron Web.zip frontend design: responsive vanilla
JavaScript/CSS, bundled with Vite, backed by FastAPI and SQLAlchemy. The planner
and page concierge use the existing LangGraph travel agents and three-tier memory.

Follow the [frontend and Google sign-in guide](../docs/frontend_google_auth.md)
for installation, current Google Auth Platform setup, environment placeholders,
button-to-backend mapping and verification commands. The
[memory integration guide](../docs/application_memory_integration.md) describes
the underlying agent and memory contracts.

From the repository root, install requirements/application.txt, build frontend/
with npm ci and npm run build, start FalkorDB with docker compose, then run:

```powershell
.\.venv\Scripts\python.exe scripts/run_voyara.py --port 8088
```

Open http://127.0.0.1:8088/. Configure GOOGLE_CLIENT_ID in backend/.env using the
committed backend/.env.example template, and restart the backend to enable Google
sign-in. The ID-token flow uses Google Identity Services and needs no client
secret. The unconfigured state is explicit in the UI.

Saved items, booking requests, itineraries, conversations, preferences, enquiries
and subscriptions persist on the backend. My Trips exposes account records and
memory controls. Existing user data and per-user memory remain in their original
stores. The old React entry files have been replaced; the original Stitch exports
and transition assets remain available in this repository's history/assets.

The seeded catalog is illustrative. Booking requests need provider confirmation,
no payment is collected, and outbound email is not configured. Google login needs
your real Web client ID. The connected agents use deterministic catalog logic and
real memory; no hosted generative model is claimed.

Backend API docs are served at /docs. Backend HTTP tests run from backend/ with
python -m pytest tests -q. Root tests cover the memory and connected application.
The live browser walkthrough is scripts/check_voyara_browser.cjs.
