# Voyara travel platform

The signed-in travel helper is now connected to the LangGraph agents and the
three-tier memory core. Follow the [connected application guide](../docs/application_memory_integration.md)
to run the complete hackathon flow, confirm Trip details, and resume saved trips.
The historical standalone setup below also requires the memory/application
dependencies for the connected helper.

Voyara is organized as a React application and a FastAPI service:

- `frontend/` — React 18, Vite, TypeScript, Tailwind CSS and lucide-react.
- `backend/` — FastAPI, SQLAlchemy 2 and SQLite for local development; PostgreSQL is supported with the psycopg driver.
- `image/images.json` — responsive Unsplash catalog for places, stays and food.
- `transitions/` — airplane, train, journal and compass-loader animation assets.

This folder is the runnable Voyara application. Its React landing page implements the supplied Stitch travel-booking design and connects to the FastAPI service. The original Stitch exports remain under `stitch_ai_travel_booking_platform/`; sign-in, saved trips, booking requests, profile preferences, itineraries and the site-wide travel helper are part of the React application here.

The current repository does not contain a provisioned Bolt Database project or Bolt auth credentials. The app therefore uses its existing SQLAlchemy database and bearer-token auth. Personal records are scoped to the authenticated user, and PostgreSQL row-level-security policies are supplied for deployment.

## Run locally

In one PowerShell window, from the repository root:

```powershell
cd stitch_ai_travel_booking_platform\backend
python -m pip install -r requirements.txt
python seed.py
python -m uvicorn app.main:app --reload
```

In a second window:

```powershell
cd stitch_ai_travel_booking_platform\frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173/`. Vite proxies `/api` and the transition assets to FastAPI at port 8000. API documentation is at `http://127.0.0.1:8000/docs`.

The frontend proxy defaults to `http://127.0.0.1:8000`. To use a different backend, copy `frontend/.env.example` to `frontend/.env.local` and change `BACKEND_PROXY_TARGET`; `VITE_API_BASE_URL` can point the built app at an API host when deployed separately.

To serve the frontend from FastAPI instead of Vite, build it with `npm run build` in `frontend/`, then open `http://127.0.0.1:8000/`. The server requires this build for its web routes; the retired static starter has been removed.

## Persistence and deployment

The seeded catalog includes destinations, stays, food, transport and guides. SQLite is the local default. For PostgreSQL, set `DATABASE_URL` to a SQLAlchemy URL such as:

```text
postgresql+psycopg://voyara:password@localhost:5432/voyara
```

Start the service once so SQLAlchemy creates the tables, then apply `backend/migrations/001_user_data_rls.sql` using the deployment database role. The API writes a transaction-local `voyara.user_id` value from its verified access token; the policies use that identity for profiles, bookings, itineraries, assistant conversations, messages and memory. Catalog data remains publicly readable. Protect the database connection string and use a non-superuser application role in production.

The `users` table is queried by the authentication routes to register and sign in; all user-owned application records are protected by both owner-filtered API queries and the PostgreSQL policies.

## Application capabilities

- Landing page and browse/search/filter/detail pages for destinations, stays, food, transport and guides, with primary navigation available at mobile sizes.
- Email/password signup and sign-in, profile preferences, booking history and saved itineraries.
- A persistent trip request planner with item-level dates, time, duration and quantity, a schedule overview, and overlap checks. Checkout creates `requested` bookings; it does not take payment or claim that a provider has confirmed.
- A site-wide helper with manual catalog search and memory-backed agent advice. Confirm Trip details, ask for a plan, resume previous trips, and update the current budget without reusing stale preferences. Messages remain in `ai_conversations` and `ai_messages`.
- A documented adapter in `backend/memory_adapter.py` for optionally ranking catalogs with your own cross-session preference service. Configure `MEMORY_SERVICE_URL` and optionally `MEMORY_SERVICE_TOKEN` in `backend/.env`.
- Responsive Unsplash images with 400/800/1200/1600 pixel `srcset` choices and thumbnail fallback; reduced-motion-aware page-turn-style route transitions and compass loaders. Original Stitch transition assets are retained under `transitions/`.

The assistant connection point is `POST /api/assistant/conversations/{conversation_id}/messages`. It returns `connection_status: "agents_connected"` and structured agent results when the connected runtime is available. Pending/unavailable memory pauses planning. See the connected guide for requirements and memory-event endpoints.

Run backend tests from `backend/` with `python -m pytest`. The frontend production type-check and build are `npm run build`.
