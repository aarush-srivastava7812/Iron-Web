# TinyFish local integration acceptance — 19 October 2026

**Local Jaipur acceptance passed. No GitHub push or deployment was performed.**

Local application: http://127.0.0.1:8094/#planner

## Change

Four research specialists use TinyFish: destination exploration, stays, restaurants, and attractions. Authenticated memory, current requirements, itinerary assembly, exact budget arithmetic, validation, saved draft versions and ownership remain local. The existing NVIDIA and explicit offline modes remain available.

Only generic public destination research leaves the application. Dates, budget, traveler count, preferences and scoped memory are not sent to TinyFish. Local code filters the findings. Web rates are indicative, not date-specific availability or booking confirmations. No booking/payment was made.

Findings retain source links and provider run IDs. The UI distinguishes TinyFish research from local calculations. The editor and Travel Book handle web stays without assigning fake catalog IDs, including two hotels listed on one source page.

## Verified

- **55 local tests passed** across TinyFish contracts, stochastic-agent regressions, authenticated memory/workflow, plan editing and Travel Book tests. Real isolated graph/vector stores were used with declared test embedding fixtures and simulated provider responses.
- Frontend production build passed. Targeted Ruff and whitespace checks passed.
- Actual TinyFish research was executed with the user's privately configured key.
- Final browser test passed in **16.94 seconds** using cached, actual provider research. The preceding successful generation used three cached real findings and one fresh targeted hotel run, returning the accepted orchestration after **74.97 seconds**. Its harness subsequently failed on a trip-ID lookup; that harness issue was corrected before the final passing run.
- Jaipur, **1–3 December 2026**, **2 travelers**, **INR 90,000 budget**: three dated itinerary days, all four research specialists completed, local consultant/planner/calculator completed, **INR 22,550 indicative listed-item estimate**, saved itinerary and authenticated draft readback.
- TinyFish labels and research links rendered in the browser. **Zero uncaught page errors**.
- Test key file `agents/.env` is Git-ignored. Reports contain no API key or session cookies.

Actual provider runs used in the accepted draft:

| Research | Run ID |
| --- | --- |
| Destination | `02acfb7a-e8cb-463b-bb9c-7dcfd7b4e528` |
| Food | `29e12b37-cd68-4117-b521-9b488eb4d1e3` |
| Attractions | `478b0330-dc61-40c1-b33c-d8a496072f8c` |
| Stay | `377ddfee-a108-4ff2-9fa0-2a04723b2e84` |

## Limits and failures retained

Initial broad web research was slow/queued and exceeded the initial four-minute deadline. Provider outputs also exceeded the requested shortlist size and used descriptive city labels. The adapter now normalizes bounded results while rejecting genuinely different destinations and invalid price/source data. Transient status polling failures retry without creating duplicate research runs.

Long calls exposed expiring memory proofs that could cause repeated research. Completed public findings are now cached for one hour and can be reused in a fresh memory-validation pass; failed research with expired context returns an explicit failure instead of automatically repeating paid work. Active test-owned runs were cancelled when this issue was identified. No memory proof checks were disabled.

The successful hotel acceptance used a targeted public supplier brochure, `https://ebrochure.aryaniwas.com/pdfs/Jai_Niwas_25.pdf`, scoped to Jaipur in the ignored local configuration. Its Jai Niwas rate was used as an indicative room rate. This proves integration with real supplier research; it does **not** establish reliable broad hotel discovery in every destination or a fully fresh simultaneous four-run latency guarantee.

The final browser acceptance reused actual, completed public research, not synthetic catalog substitutes. Earlier failures are retained in `first_live_browser.json`, `second_live_browser.json` and the intermediate `live_provider_completion.json`. The authoritative final acceptance is `live_browser.json` and `planner.png`.

The previously observed production Render RAM limit and Vercel proxy deadline have not been changed. Production rollout still requires resource work and asynchronous application-level planning requests. This task changed and tested the local application only.

Setup and behavior: `docs/tinyfish_local.md`. Manual browser harness: `scripts/check_tinyfish_local.py`.
