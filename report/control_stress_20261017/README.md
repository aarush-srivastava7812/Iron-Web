# Voyara control and stress test — 17 October 2026

106/106 browser checks passed; 0 failures remain. The backend suite passed 47 tests, including a deterministic five-request favorite-save race regression. Vite production build passed.

The audit captured 1707 rendered control entries across 42 page/state snapshots. Shared navigation and repeated fields occur in several snapshots; this is an inventory count, not a count of unique buttons. Tests exercised the action families and catalog entries listed below.

| Suite | Passed | Failed | Evidence |
| --- | ---: | ---: | --- |
| Catalog, navigation, validation and concurrency | 61 | 0 | [Controls and inventory](controls.json) |
| Concierge, planner, chat and memory | 19 | 0 | [Agent checks](agents/checks.json) |
| Flights, preferences, retry and authentication | 8 | 0 | [Edge checks](edges/checks.json) |
| Complete connected journeys | 18 | 0 | [Connected journeys](connected/browser-check.json) |

## Coverage

- Clicked 76 visible homepage/header/footer/agent links and all five search-category buttons. Verified desktop and mobile navigation, including selecting the current route, and browser back/forward.
- Opened all 10 destination cards and all 10 package detail/booking links; saved and removed each destination/package and each of the six hotel entries. Opened every hotel room and all six experience booking buttons.
- Checked every package category/sort combination, every destination region/experience combination, hotel category/text search combinations, and all experience categories, including empty results.
- Searched all 240 distinct airport pairs: clicked 60 stored flight-route Select buttons and verified 180 empty route results. Also tested round trips, invalid airports/dates and recovery when a selected flight is refreshed.
- Checked all eight planner interest toggles and all 10 stored preference combinations. Ran all three concierge suggestions and Send on each of 11 page contexts against the real agent backend.
- Persisted package, hotel, experience and round-trip flight requests with server quotes; edited reviews, confirmed requests, opened accounts, cancelled requests, and deleted test itineraries/conversations and memory events.
- Created a real trip outline with private graph/vector memory, updated the budget in chat, reloaded the conversation, expanded/collapsed memory details, and checked trip screens at 1440, 390 and 320 pixels.
- Checked FAQ mouse/keyboard interaction, required/invalid inputs, newsletter/contact submissions, local developer sign-in, sign-out, anonymous guards, expired sessions, and boot/dashboard retry buttons.
- Injected temporary API failures into quote, confirmation, favorites, catalog, dashboard, contact, newsletter and chat requests. Verified visible feedback, preserved drafts where applicable and enabled retries. These intentional 503 responses are marked as injected in the evidence.

## Defects fixed and verified

| Defect | Change | Regression evidence |
| --- | --- | --- |
| Rapid favorite clicks issued repeated requests | Block repeated saves of the same item while pending and disable its visible controls | Rapid favorites click check |
| Concurrent favorite saves could cause a server error | Recover the existing row after a concurrent unique-key insert | Five concurrent live saves plus backend barrier test |
| Concierge replies accumulated duplicate follow-up links | Replace the previous follow-up link | Repeated suggestions and Send across 11 contexts |
| Selecting the current mobile route left the menu open | Close navigation on every navigation link click | Mobile menu/current-route check |
| Repeated newsletter submit events sent duplicate requests | Guard the form while a submission is pending | Five immediate submission events produce one request |
| Booking details could be edited during confirmation | Disable Edit while saving and restore it after failure | Delayed confirmation failure and retry check |

## Bounded local load

Sixty authenticated reads at concurrency five completed without failed requests. Measured p95 latency was 32 ms and maximum latency was 33 ms for this run. Five concurrent retries of one booking key produced one booking; five duplicate subscriptions succeeded; five concurrent favorite saves produced one saved item. Rapid planner and chat submissions produced one request. This is a local functional stress check, not a production-capacity benchmark.

## Configuration limits and test data

Google live sign-in awaits a configured Google client ID. Its unconfigured state, local developer sign-in, session protections and backend Google verifier tests passed. No live Google account consent or production-domain redirect was tested. Flights and prices are sample inventory; provider reservations, payments and outbound email are unconfigured.

Mutations used isolated test accounts. Personal trips and memory were not changed. Test trip conversations/itineraries were removed and created booking requests were cancelled. Test accounts, cancelled requests, enquiries/subscriptions and some test-account preferences/favorites remain as diagnostic records; no outbound email was sent.

Initial exploratory JSON/screenshots are retained as before-fixes evidence. They also contain early harness timing/filter-reset failures; the final suite JSON and summary above determine the current result.

## Individual checks

### Catalog, navigation, validation and concurrency

| Check | Result |
| --- | --- |
| Inventory and link audit: home | passed |
| Inventory and link audit: destinations | passed |
| Inventory and link audit: packages | passed |
| Inventory and link audit: tours | passed |
| Inventory and link audit: hotels | passed |
| Inventory and link audit: planner | passed |
| Inventory and link audit: flights | passed |
| Inventory and link audit: about | passed |
| Inventory and link audit: contact | passed |
| Inventory and link audit: privacy | passed |
| Inventory and link audit: login | passed |
| Inventory and link audit: dashboard | passed |
| Every visible header/footer/home/agent link navigates | passed |
| All five home search-category buttons | passed |
| Home search invalid input, keyboard submit and trip fields | passed |
| Destination/package controls: Kashmir | passed |
| Destination/package controls: Manali | passed |
| Destination/package controls: Jaipur | passed |
| Destination/package controls: Goa | passed |
| Destination/package controls: Kerala | passed |
| Destination/package controls: Udaipur | passed |
| Destination/package controls: Varanasi | passed |
| Destination/package controls: Rishikesh | passed |
| Destination/package controls: Andaman | passed |
| Destination/package controls: Darjeeling | passed |
| All package filter and sort combinations | passed |
| Every destination region/experience filter combination | passed |
| Every hotel type, text-search and reset | passed |
| Hotel save and room button: The Cedar House | passed |
| Hotel save and room button: Lakeview Palace Stay | passed |
| Hotel save and room button: Palm Grove Retreat | passed |
| Hotel save and room button: Coast & Cove | passed |
| Hotel save and room button: The Pink Courtyard | passed |
| Hotel save and room button: Snowline Lodge | passed |
| Every experience category | passed |
| Experience booking button: Himalayan hiking | passed |
| Experience booking button: Old Jaipur walk | passed |
| Experience booking button: Kerala backwater cruise | passed |
| Experience booking button: Ganga sunrise ceremony | passed |
| Experience booking button: River rafting | passed |
| Experience booking button: Coastal food trail | passed |
| All eight planner interest toggles | passed |
| All FAQ mouse and keyboard expand/collapse | passed |
| Required/invalid forms block accidental requests | passed |
| Booking review, edit, quote failure, retry, rapid confirm | passed |
| Flight invalid airports/dates, empty state, route select and refresh | passed |
| Saved cards can be removed from My Trips | passed |
| Error page retry and boot retry | passed |
| Back/forward navigation restores functional forms | passed |
| Mobile menu: every header link, close, account and footer | passed |
| Rapid favorites click is a single mutation | passed |
| Favorite failure displays feedback and permits retry | passed |
| Bounded API load: 60 reads, concurrency five | passed |
| Concurrent booking retries preserve one request | passed |
| Concurrent duplicate subscriptions are idempotent | passed |
| Concurrent favorite saves preserve one item | passed |
| Malformed and unknown routes have working escape links | passed |
| Logout and signed-out guards for favorites/planner/bookings | passed |
| Test-data cleanup | passed |
| No uncaught browser exceptions | passed |
| No unexpected server failures | passed |

### Concierge, planner, chat and memory

| Check | Result |
| --- | --- |
| All concierge suggestions and Send: packages | passed |
| All concierge suggestions and Send: tours | passed |
| All concierge suggestions and Send: hotels | passed |
| All concierge suggestions and Send: destination/Darjeeling | passed |
| All concierge suggestions and Send: package/Kashmir | passed |
| All concierge suggestions and Send: planner | passed |
| All concierge suggestions and Send: flights | passed |
| All concierge suggestions and Send: about | passed |
| All concierge suggestions and Send: contact | passed |
| All concierge suggestions and Send: booking?place=Kashmir | passed |
| All concierge suggestions and Send: dashboard | passed |
| Concierge failure keeps draft and permits retry | passed |
| Start a new conversation preserves the previous one | passed |
| Planner repeated submissions create one itinerary | passed |
| Trip chat, saved memory panels and reload | passed |
| Trip chat failure and rapid retry | passed |
| Login account links and sign out button | passed |
| Isolated trip cleanup | passed |
| No uncaught chat/browser errors | passed |

### Flights, preferences, retry and authentication

| Check | Result |
| --- | --- |
| Every stored flight route Select button | passed |
| Every saved-preference option and persistence | passed |
| Newsletter failure, retry and repeated submit | passed |
| Contact failure, retry and repeat-submit guard | passed |
| Booking cannot be edited while confirmation is in flight | passed |
| Expired session clears account and returns to sign-in | passed |
| Local developer sign-in and logout | passed |
| No uncaught edge-case exceptions | passed |

### Complete connected journeys

| Check | Result |
| --- | --- |
| google_unconfigured_ui | passed |
| account_favorites_persist | passed |
| package_request | passed |
| filter_sort_composition | passed |
| stay_request | passed |
| experience_request | passed |
| round_trip_route_request | passed |
| enquiry | passed |
| newsletter | passed |
| saved_preferences | passed |
| connected_plan_and_real_memory | passed |
| concierge_memory_update | passed |
| conversation_persists | passed |
| forget_memory_event | passed |
| cancel_requests | passed |
| delete_itinerary_and_trip_memory | passed |
| mobile_menu_and_layout | passed |
| logout | passed |
