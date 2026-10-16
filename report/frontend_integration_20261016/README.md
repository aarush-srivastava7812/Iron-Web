# Supplied frontend integration verification

Verified locally on 2026-10-16, Windows, installed Edge via headless Playwright.

- Root suite: **323 passed**, 6 optional tests deselected. Includes authenticated
  application → real LangGraph → isolated FalkorDB/Qdrant integration with the
  suite's declared offline embedding fixture.
- Backend suite: **38 passed**. Covers existing API behavior, Google identity and
  account linking, nonce/cookie binding, unverified credentials, expired/reused
  sign-ins, CSRF, inactive users, quote tampering, duplicate requests, ownership,
  package/stay/activity/round-trip requests, cancellation inventory restoration,
  subscription/enquiry persistence and existing SQLite favorites migration.
- `npm ci` and the production Vite build passed. npm reported zero vulnerabilities.
- The live browser walkthrough passed **18 checks** and recorded **zero browser
  errors**. See [browser-check.json](browser-check.json) for individual results.
  This used live CPU BGE neural embeddings, actual FalkorDB/Qdrant and the
  connected deterministic travel agents.

The supplied desktop/mobile site was inspected before code changes using an
isolated reference server. The new app preserves that layout, fixes the original
booking query routing, and replaces local fake submissions with backend actions.

The browser check bootstraps an isolated API-created test account into an
HttpOnly session cookie. It verifies the deliberately unconfigured Google screen,
but **does not claim a live Google login**. Google ID-token verification is tested
at the backend boundary; a real Web client ID is still required for live Google
account testing. No live supplier reservation, payment or outbound email is claimed.

Screenshots: [desktop homepage](desktop-home.png), [mobile homepage](mobile-home.png),
[connected agent plan](connected-plan.png), [account dashboard](desktop-dashboard.png).

Reproduce using [the setup guide](../../docs/frontend_google_auth.md) and
`node scripts/check_voyara_browser.cjs` against the running local app.
