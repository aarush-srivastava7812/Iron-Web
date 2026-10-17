# Supplied frontend, backend actions and Google sign-in

The 2026-10-16 frontend uses the supplied `Iron Web.zip` design. It was inspected
at desktop and mobile sizes before implementation. The ZIP's README described a
prototype; its fake authentication, sample chat handlers and localStorage trip
records were replaced with backend calls. Instructions in that file were treated
as source material rather than as user instructions.

## Run

From the repository root:

```powershell
docker compose up -d falkordb
.\.venv\Scripts\python.exe -m pip install -r requirements/application.txt
cd stitch_ai_travel_booking_platform/frontend
npm ci
npm run build
cd ../..
.\.venv\Scripts\python.exe scripts/run_voyara.py --port 8088
```

Open `http://127.0.0.1:8088/` or `http://localhost:8088/`. The new frontend uses
hash routes, such as `/#planner` and `/#dashboard`. Existing `/destinations`,
`/explore`, `/stays`, `/plan` and `/support` entry links are redirected locally to
their new route equivalents. Vite development runs on port 5173 and proxies
`/api` to port 8000 by default; change `BACKEND_PROXY_TARGET` in frontend/.env.local
if the backend is on another port. Browser API requests remain on the same origin.

The application database remains `data/voyara_app/travel.db`; private memory
remains `data/voyara_memory/`. The launcher performs additive table creation and
upgrades the favorites key while preserving existing rows. It does not import
prototype localStorage data into a user's account.

## Configure Google using current console names

For local development while Google setup is pending, set `DEV_LOGIN_ENABLED=true`
in backend/.env and restart. The login page then offers **Continue as Developer**.
It opens a dedicated ordinary account named **Voyara Developer**, preserving that
account's saved trips and memory between sessions. No password is needed. This
option defaults to false, rejects remote/proxied requests and non-local hosts,
requires a same-origin browser action, and is disabled with secure deployment
cookies. Leave `DEV_LOGIN_ENABLED=false` on deployment.

The committed template is
`stitch_ai_travel_booking_platform/backend/.env.example`. The local ignored
`backend/.env` already contains the requested placeholder and a generated session
secret. For a new installation, copy the template to `.env` and generate a long
random `SECRET_KEY` before enabling Google sign-in.

```dotenv
GOOGLE_CLIENT_ID=YOUR_WEB_CLIENT_ID.apps.googleusercontent.com
SECRET_KEY=replace-with-at-least-32-random-characters
COOKIE_SECURE=false
```

1. In Google Cloud Console, select your project. Under **Google Auth Platform →
   Branding**, configure the application name, support email and applicable
   homepage/privacy links. Configure your **Audience**, including test users when
   applicable to your project's testing status.
2. Open **Clients → Create client**, and choose **Web application**. Under
   **Authorized JavaScript origins**, add each exact origin you use. For local
   development Google's guide recommends `http://localhost` and the origin with
   its port, for example `http://localhost:8088`. Add `http://127.0.0.1:8088` if
   using that host, and `http://localhost:5173` if using Vite there. A different
   hostname or port is a different origin. Add your exact HTTPS deployment origin
   when deploying.
3. Copy the **Client ID** into `GOOGLE_CLIENT_ID` in backend/.env and restart the
   backend. The client ID is public configuration; keep `SECRET_KEY` private.
   Set `COOKIE_SECURE=true` on HTTPS deployments.

This uses **Google Identity Services** with its JavaScript callback and the
official `https://accounts.google.com/gsi/client` SDK. No Google client secret or
redirect URI is needed for this chosen ID-token authentication flow. It requests
sign-in identity only; it does not request Gmail or mailbox access.

The backend verifies the credential's signature, audience, issuer and expiry
through `google-auth`. A short-lived single-use database nonce is tied to an
HttpOnly browser cookie and checked against the token. Google `sub` is the stable
identity. Existing local accounts are linked by email only when Google is
authoritative for that email (Gmail or a verified Workspace domain). A linked
account cannot be reassigned to another Google subject. Inactive accounts cannot
sign in.

The browser receives an HttpOnly application session cookie, not a Google token
in localStorage. Cookie-authenticated mutations require the matching CSRF header.
Sign out clears the browser session. The existing bearer APIs remain compatible
with API clients. Session lifetime follows `ACCESS_TOKEN_MINUTES` (60 by default).

With the placeholder intact, the login page explains that setup is pending and
does not render a fake sign-in button. Actual Google login needs the configured
Web client and a Google account; it has not been live-tested with the placeholder.

Official documentation checked on 2026-10-16:

- [Google Identity Services setup and current console names](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid)
- [Render the Google sign-in button](https://developers.google.com/identity/gsi/web/guides/display-button)
- [Verify Google ID tokens on the server](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token)
- [JavaScript API configuration, callback and nonce](https://developers.google.com/identity/gsi/web/reference/js-reference)

## What each control does

| Frontend action | Backend or result |
| --- | --- |
| Navigation, destination/package details | Hash router; public `/api/website/catalog` inventory |
| Region/category filters, sorting, hotel search | Filter the loaded server catalog; combined filters are preserved |
| Home search | Validates the catalog destination; carries date/party into planning and origin/destination/date into route search |
| Package/stay heart, save for later | Authenticated `/api/favorites`; state reloads from the account |
| Plan a trip, create outline | Confirms exact dates, total INR budget, party size, pace and interests through the existing requirements endpoint; calls the real agents and saves a successful itinerary |
| Start a new trip conversation | Creates a separate trip on the next planning/chat action, retaining saved account preferences |
| Concierge send/suggestions | Existing authenticated assistant conversation/messages API, using the current trip memory; bounded intake asks for clarification when needed |
| Package plan/book, view rooms, book experience | Booking details → authenticated server quote → explicit confirmation → persisted `requested` booking |
| Flight search/select | Queries stored routes by origin/destination and seat count, supports outbound/return request dates and Economy; selection reaches the same review flow |
| Review/edit/confirm | Authoritative backend prices, date validation, explicit traveler consent, price-change checks and idempotent request keys |
| My Trips cancel | Authenticated cancellation; transport inventory is restored once |
| My Trips saved itinerary/delete | Existing owner-scoped itineraries API |
| Open conversation & memory | Persisted chat, current fields and memory event receipts |
| Forget event/delete conversation | Existing memory lifecycle deletion, followed by SQL chat deletion when successful |
| Save preferences | Profile API; supported preferences reach the existing memory runtime |
| Contact form | Validated enquiry saved to the database, with a reference; five enquiries per email per hour |
| Newsletter | Validated, idempotent subscription stored in the database |
| Google sign-in/account/sign out | Verified Google ID token, server session, current-user API and session-cookie cleanup |
| Menu, FAQ, privacy | Responsive navigation, expandable answers and information about stored account/memory data |

The original fake social links and placeholder telephone address were removed.
The footer privacy link opens actual privacy information. Unknown destinations
and routes show a useful state rather than silently substituting Kashmir.

## Practical limits

The supplied catalog and the existing seed data are illustrative, not a live
supplier integration. A booking is a request requiring provider confirmation;
no payment or airline reservation is made. Flight dates are requested dates, not
verified schedules. Outbound enquiry/newsletter email is not configured; the UI
states that submissions are saved. Travel agents remain the connected
deterministic catalog-backed agents, with real graph/vector memory. No hosted
generative model is implied by this frontend replacement.

Free-text requests use conservative intake. Additional planner requests can
produce a clarification instead of a plan; exact confirmed fields remain saved.
Only successful (`ok`) plans become saved itineraries. My Trips can inspect or
forget trip events, delete conversations/itineraries and cancel requests.

## Validation

Run root memory/integration tests with `.venv/Scripts/python.exe -m pytest -q`.
Run the separate HTTP/auth tests from backend/ with
`../../.venv/Scripts/python.exe -m pytest tests -q`.
Build from frontend/ with `npm ci` and `npm run build`.

`node scripts/check_voyara_browser.cjs` exercises the supplied UI against a running
local backend and real FalkorDB/Qdrant memory. It needs Playwright in Node's module
path and uses installed Edge by default (`PLAYWRIGHT_CHANNEL` can override it).
It bootstraps an isolated API-created test session; this does not substitute for
a real Google login. Screenshots and machine-readable results are written under
`report/frontend_integration_20261016/`.
