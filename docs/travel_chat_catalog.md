# Voyara conversational catalog and Travel Book

The hackathon experience now connects destination discovery, a floating NVIDIA
chatbot, manual catalog selections and a personal HTML/PDF Travel Book to the
same authenticated trip. The supplied implementation plan and three images
informed the scope and navy, teal and saffron presentation. These are local demo
features; there is no publishing, payment or supplier reservation integration.

## Highest-value demo flow

1. Open **Discover Kerala** at `http://127.0.0.1:8088/#destination/Kerala`.
2. Sign in and open **Voyara AI Travel Team**. Describe a five-day Kerala trip
   starting 12 December 2026, two travellers, INR 100000 total, from New Delhi.
3. Answer follow-up questions and inspect the pending draft. Ask for stays or
   experiences; recommendations reference actual matching catalog records.
4. Review the exact dates and budget, choose options, then confirm to run the
   specialist team. Explicit preference memory is optional.
5. Open the personal Travel Book. Edit details, select catalog items or use
   **Browse & edit** links to flights, hotels and experiences in this same trip.
   Refresh the outline after changes. The existing versioned itinerary editor
   also remains available.
6. Download the branded PDF. Its private links reopen this trip for editing;
   previously downloaded PDFs remain fixed snapshots. Reopen trips from the
   dashboard or their saved conversations.

The regional catalog adds Alleppey, six Kerala stays and six experiences, with
matching agent-tool records and vegetarian kitchens. Kerala discovery includes
Kochi, Munnar and Alleppey. The public catalog exposes twelve hotels and twelve
experiences overall. The regional route illustration is inspiration, not verified
driving directions.

## NVIDIA and actual agent work

The existing server-side `NVIDIA_API_KEY` is reused. No key is shipped to the
browser. Chat first extracts pending facts with temperature 0.35, performs a
server catalog lookup, then writes a conversational response with temperature
0.65. Recent history and explicit saved preferences provide context. The server
validates fields, calculates inclusive dates and validates recommendation IDs.
Model output cannot directly confirm a trip or create reservations.

Confirming the draft invokes the existing stochastic specialist workflow:
the trip consultant, destination researcher, food guide, stay selector, tour
guide, itinerary planner and budget agent have distinct tasks, tools and outputs.
Their bounded decisions, tool results and handoffs are
visible in the plan. See [the agent build plan](hackathon_travel_plan.md).
**Build from my choices** is an explicit manual alternative and labels its
execution accordingly. Chat always requires NVIDIA; outages preserve the draft
and allow retry rather than impersonating a successful model response.

## Shared data and pricing

`TripWorkspace` holds pending details, selections and optimistic revisions.
Confirmed facts enter the existing trip memory only after review. Enduring
preferences are saved only when explicitly requested. Successful outlines use
the existing `PlanVersion` history; detail or selection changes invalidate the
current outline until regenerated.

Budget chat receives the same authoritative snapshot as the Travel Book. Cost
questions include server-formatted line items and totals. The model must not
average catalog rates or assume unselected options. The estimate covers listed
activities/meals, one assumed room and the planner's allowance. Only an explicitly
selected outbound sample flight is added, multiplied by the party size. Return
flights, extra meals, transfers, taxes, room occupancy and availability remain
unverified. The spending cap is distinct from the estimate. Unsupported mandatory
conditions stop confirmation; an over-budget flight selection stops PDF export.

`TravelBook` stores an immutable snapshot and PDF bytes. Identical snapshots reuse
the same export. Ownership checks protect draft, selection, preview and PDF
endpoints; edit links and QR codes convey no public access permission.

The PDF includes a cover photograph, regional guide, dated itinerary, selected
accommodation and outbound flight, food/experiences, itemized estimate and private
edit links. The local Kerala photograph is from Unsplash,
`photo-1602216056096-3b40cc0c9944`, already used by the supplied catalog, and is
attributed in the PDF. All supplier inventory and rates are synthetic demo data.

## Run and verification

Install the application dependencies (including ReportLab), build the frontend,
then use the existing local launcher:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements/application.txt
# From stitch_ai_travel_booking_platform/frontend: npm run build
.\.venv\Scripts\python.exe scripts/run_voyara.py --port 8088
```

Focused regression coverage is in `tests/test_journey_chat_book.py`, alongside
the existing plan editor, application integration and website catalog tests.
It exercises pending facts, date arithmetic, explicit confirmation, shared
selections, exact estimates, stale edits, provider failures, private immutable
PDFs and unsupported requirements. Tests use isolated actual memory stores with
declared offline embedding fixtures.

`VOYARA_JOURNEY_LIVE=1` enables `tests/test_journey_live_nvidia.py`: real NVIDIA
conversation, confirmed specialist work and PDF export. The embedding fixture
remains offline in this test; it does not claim live embedding verification.
`scripts/check_voyara_journey.cjs` checks the isolated local browser fixture,
real NVIDIA chat, manual planning, deep links, PDF download, responsive widths
320/390/768/1440, provider recovery, history and logout isolation.

Evidence and sample artifacts are under
`report/travel_chat_catalog_20261017/`. Sample PDFs use a test trip; their private
links do not identify an actual user's holiday.
