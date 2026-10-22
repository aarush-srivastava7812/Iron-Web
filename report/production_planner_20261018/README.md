# Production trip planner verification — 18 October 2026

**Result: failed.** The website and basic API connection work; complete trip planning through the public website did not pass.

Website: https://voyara-travel-taupe.vercel.app/#planner
Backend: https://voyara-api-kyb2.onrender.com

## Verified behavior

- Production Vercel deployment is ready. The existing local CLI could inspect it even though the connector's explicit-team deployment listing returned 403.
- Backend `/health`: HTTP 200.
- Public judge demo configuration, sign-in, authenticated identity, catalog, and conversation creation passed through Vercel.
- Render has a nonempty NVIDIA credential configured and `VOYARA_AGENT_MODE=auto`. No credential values were logged or saved.
- No local website was listening on port 8088, so the current local application could not be compared by running the same UI test. Earlier checked-in acceptance evidence records successful local execution of seven NVIDIA specialists; that is historical evidence.

## Test 1: browser and API sessions

The public browser test signed in with **Continue as Judge**, selected Jaipur, 12 November 2026, two travelers, INR 30,000, and Culture/Food. The origin and requested end date were entered in notes because those controls were unavailable in that test. The planner showed **“The request failed. Please try again.”** after approximately 40 seconds. No completed itinerary or live agent execution appeared. Static agent cards alone do not prove execution.

The overlapping API test used a separate isolated judge account, Jaipur, 12–15 November 2026, two travelers, INR 30,000, moderate pace, and Culture/Food. Saving confirmed requirements returned HTTP 502 after 8.437 seconds, before an agent request was sent from that session. See `api_failure.json`.

Render service events confirm **`server_failed` → `oomKilled` → `memoryLimit: 512Mi`** at `2026-10-18T18:00:19.719694Z`, followed by recovery at `18:00:55.480078Z`. See `render_events.json`. The event and logs confirm the backend restart, rather than merely inferring it from a 502.

Source inspection shows separate memory engines and embedding model instances are retained for each active traveler. This allocation pattern is a plausible contributor to exhausting the small instance; no memory profile was collected to isolate its exact share of peak usage.

## Test 2: sequential retry after recovery

With the browser test finished, a new API test successfully saved the same structured trip requirements (16.172 seconds) and read current trip memory (4.656 seconds).

`POST /api/assistant/conversations/{id}/messages` with `{"content":"Plan my trip","page":"plan"}` returned HTTP 502 after **120.141 seconds**, with **`ROUTER_EXTERNAL_TARGET_ERROR`**. Backend health still returned 200. This confirms that the public request did not finish; it does not establish whether backend agent work eventually completed after the proxy stopped waiting. No successful agent execution trace or persisted completed draft was retrieved. See `api_result.json`.

## Next implementation work

1. Share immutable embedding model resources across traveler engines while preserving separate graph/vector/journal data and authenticated ownership. Measure the resulting peak memory under multiple judge sessions before releasing it.
2. Move long planning runs behind an asynchronous start/status/result API so the browser does not depend on one external proxy request completing within the observed 120-second limit. Measure actual NVIDIA response time and surface useful failure/progress states.
3. Re-run single-session and multiple-session planning, saved draft reload, and trip-input validation through the public website. Increase service capacity only with the owner's approval if measured memory still exceeds available capacity.

No application code, deployment, paid plan, provider setting, booking, or payment was changed. Test accounts/conversations were created as part of this authorized test. One restart discarded the earlier sessions on the service's ephemeral filesystem; the sequential test's conversation may remain. `check_live.py` is a manual test script, not an unattended job, and never persists cookies or tokens.
