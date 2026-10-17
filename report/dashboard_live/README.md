# Real website → memory dashboard verification

The final full browser flow completed successfully. The normal dashboard uses
actual application memory; no events.json data or mocked API feed was used.

## Actual trip

- Trip: `553a7cb2-21c4-4873-9760-d0ebcd91dcdd`
- Goa, 1–3 December 2026, 2 travelers, INR 100,000, relaxed pace.
- Submitted through the website's planner form after normal local developer sign-in.
- HTTP 200, `agents_connected`, orchestration status `ok`; itinerary saved to My Trips.
- Seven NVIDIA specialists completed successfully: consultant, explore, food,
  stay, tour, itinerary planner and budget. The orchestration reader is an eighth
  observed memory actor; support was registered but not needed.
- No travel booking, payment, direct memory insertion or fabricated event occurred.

## Dashboard evidence

- 29 retained runtime observations, 8 observed / 9 registered agents.
- 8 captured agent contexts, 36 claim/history records,
  63 real FalkorDB nodes, 150 KG relationships,
  6 Qdrant points on the inspected page.
- Provider: NVIDIA NIM, `openai/gpt-oss-20b`.
- Process measured 18 HTTP inference requests;
  18 successful responses;
  30739 reported input tokens and
  1418 reported output tokens.
- Provider counts include retries and are process-scoped, not lifetime or
  per-tenant counts. Context packets use exact UTF-8 byte accounting separately.
- The graph exposes real relationships plus explicitly derived context/card
  links. Historical replay uses captured contexts; KG/store snapshots remain live.

`trip-result.json`, `snapshot.json`, `summary.json`, and `page-errors.json` retain
machine-readable evidence. The final full flow has zero browser page errors.
`verified-snapshot.json` / `verified-errors.json` record interaction verification.
Screenshots cover all five views at 1440x900 and 1280x720 plus the narrow drawer layout.

## Verification

- Production frontend build passed.
- 12 Node tests passed, including fixture compatibility and live projection semantics.
- 19 memory-dashboard/application integration tests passed against actual isolated
  stores, with explicit offline provider mode for deterministic regression checks.
- 2 tool-protocol tests passed: retry an invalid provider action without repeating
  successful tool work, and fail safely if no valid action arrives within the cap.
- 2 local Edge browser checks exercise the real feed, source/vector inspection,
  filtering, replay, follow-live, inspector tabs, both target viewports, drawers
  and reduced motion.
- Final complete planner → real NVIDIA agents → dashboard flow passed independently.

The Browser Use plugin was invoked as requested, but its isolated browser could
not reach 127.0.0.1:8000 or 127.0.0.1:5174. The local browser bridge also failed to
initialize. Actual end-to-end verification therefore used installed Microsoft
Edge through Playwright against these local services. No tunnel or deployment
was created to expose the application externally.

## Issues found and fixed

1. A second website process already owned embedded memory; the local website was
   restarted with a single owner. Existing database files were preserved.
2. An empty feed could create a graph target without an event. It now waits for
   an actual target/event and displays an honest empty state.
3. A hosted model sometimes returned no valid JSON tool action after a successful
   catalog call. The agent now retries that exact protocol failure within the
   existing bounded turn budget. It never substitutes an offline result, skips
   validation or approves an incomplete plan. The failed repeat is preserved as
   `trip-protocol-failure.json`; the final subsequent full run succeeded.
4. Closely connected labels and chapter captions overlapped. Tier anchors,
   collision-aware label visibility and alternating chapter labels fix this.
5. Provider metadata previously claimed zero calls/local execution regardless of
   actual NVIDIA activity. It now records and reports observed HTTP usage.
6. Captured context history is purged for forgotten scopes; proof/credential
   secrets remain redacted. Public provider token counts are retained correctly.

## Deliberately unavailable / scope

No equivalent no-memory prompt baseline, GPU-utilization series, per-tier durable
byte quota, provider-cache token split, cost baseline or tier-promotion event
stream exists. These display N/A or an explicit explanation; they were not
invented. The website's supplier catalog remains honestly identified as sample
inventory. The agents, memory reads/writes and measured provider calls are real.

## Open locally

- Website: http://127.0.0.1:8000/#trip/553a7cb2-21c4-4873-9760-d0ebcd91dcdd
- Dashboard: http://127.0.0.1:5174/
- Read-only relay: http://127.0.0.1:8200/

The processes remain running. See `dashboard/README.md` for restart/deployment
configuration. This is a local verification, not a Railway/Vercel deployment.
