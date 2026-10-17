# Iron Web demonstration — 18 October 2026

The original FalkorDB volume crashes during persisted-log replay and is preserved.
An explicitly approved recovery copy is now active and fresh hosted acceptance
passed after cutover. Recovery diagnostics and limitations are in
`report/finalisation_20261018/RECOVERY.md`. Use the override below on this workstation;
plain Compose names the failing original volume. Do not reset or delete it.

1. Follow README dependency/private environment setup. From repository root run
   `docker compose -f compose.yaml -f compose.recovery.yaml up -d --wait falkordb`, then
   `.\.venv\Scripts\python.exe scripts/preflight.py --mode start`.
2. In three separate terminals run
   `.\.venv\Scripts\python.exe scripts/run_live_dashboard.py website`,
   `.\.venv\Scripts\python.exe scripts/run_live_dashboard.py dashboard`, and
   `.\.venv\Scripts\python.exe scripts/run_live_dashboard.py frontend`.
   Run preflight with `--mode running` in another terminal. Stop on failures.
3. Open website `http://127.0.0.1:8000/` and dashboard
   `http://127.0.0.1:5174/` side by side. Sign in using the local developer/demo
   traveler button. This ordinary account alone is published by the local launcher.
4. In AI Trip Planner create a fresh Kerala trip: 1 December 2026, three days,
   two travelers, INR 200,000, relaxed pace. Choose **Create my trip outline**.
   Allow the hosted workflow to finish; inspect all seven specialist results.
   A provider error is a failed run, not an offline replacement.
5. Confirm the saved plan is current, export/download its Travel Book PDF, and
   inspect the same trip's actual memory events, claims and captured contexts in
   the dashboard. Registered actors, observed actors and current readers differ.
6. Open `/catalog/kashmir_trip/kashmir_catalog.html` and
   `/catalog/kerala_trip/kerala_catalog.html` on the website. Inspect the regional
   SVG illustrations and map presentation. They do not prove live supplier inventory.
   Open the Kashmir booking review, enter valid contact/date details and consent,
   review the synthetic selection, and submit a booking **request**. Confirm
   `requested`; no reservation or payment is performed. Hosted catalog review is
   one model, not independent supplier verification. An unavailable review must
   remain visibly unavailable.
7. Lower the trip budget in Trip details and inspect the resulting event and
   stale/revalidation state before accepting a revised plan. A too-low budget
   should pause visibly. For conflict, use profile dietary restrictions such as
   `no nuts` with a trip vegetarian requirement and inspect the actual hard-rule
   review; do not substitute the old fixture conflict.
8. Inspect an owner-scoped event, forget it through the website and confirm
   redacted/forgotten state in dashboard history. Same-ID no-resurrection and
   cross-user denial are separately covered by isolated HTTP/service tests;
   arbitrary event-ID injection is not a website control. Use a different
   authenticated account to verify it cannot read the original private trip.
9. Finish with Architecture/Resources: three tiers, current versus captured
   historical contexts, actual measured token counts, and unavailable metrics.
   No-memory savings, GPU utilization, supplier verification and guaranteed
   fulfillment are unsupported claims.

For repeatable real-browser acceptance (makes NVIDIA calls and saves a synthetic
booking request), from the root set a new output directory and run:

```powershell
$env:IRONWEB_ACCEPTANCE_REPORT_DIR='report/my_new_acceptance'
node dashboard/frontend/tests/live-flow.mjs
$env:IRONWEB_TEST_TRIP_ID='<trip ID from acceptance.json>'
$env:IRONWEB_TEST_DESTINATION='Kerala'
$env:IRONWEB_LIVE_REPORT_DIR='report/my_new_acceptance/layout'
npm --prefix dashboard/frontend run test:browser
```

The browser checks require installed Edge and the three running services. Do not
reuse historical evidence directories. Fresh hosted acceptance passed after
cutover. Live website/dashboard checks also passed for budget staleness/rebuild,
conflict pause, isolation and UI forgetting after feed refresh. Exact same-event-ID
replay remains an isolated service test because the website cannot inject IDs.

For hosting, use exact HTTPS origins and test viewer cookies/SSE on your chosen
domains. Keep provider keys, publication grants and viewer secrets server-side;
only the relay API URL is public Vite configuration. Maintain persistent storage,
one memory owner, and coordinated backups. No cloud deployment was performed.
