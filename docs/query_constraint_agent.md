# Query Constraint Agent — demo

The agent runs when a traveler sends a message in **Plan with Voyara**. It
separates firm trip facts, mandatory supplier conditions, and optional wishes.
The chat review shows **Facts & firm constraints** and **Preferences**. The same
private workspace persists both groups across reloads and manual edits.

Start from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/run_query_agent_demo.py
```

Open http://127.0.0.1:8000, select **Continue as Demo Traveler**, and open
**Plan with Voyara**. The launcher uses separate persistent SQLite and memory
files in `.scratch/query-agent-demo/`, so the existing website on port 8094 can
remain running. FalkorDB must be running on port 6380; preserve the existing
recovery volume described in `DEMO.md`. The normal website launcher also uses
this feature after restarting its web process and rebuilding the frontend.

Use this fictional example:

> Kerala, 1 December 2026 for three days, two adults, INR 200000 total;
> I prefer nature and quiet hotels; ideally a window seat

Expected result: Kerala; 1–3 December; two travelers; total spending ceiling
INR 200,000. Nature, quiet hotels and a window seat are preferences, and do not
become mandatory supplier conditions. Try **Reduce my budget by INR 10000**,
then **Show my trip summary**, then reload. The ceiling becomes INR 190,000;
the preferences remain. **Trip details → Optional preferences** lets you edit
or remove wishes manually.

For a separate mandatory-condition example, send **Avoid boats**. It appears
under firm constraints. Unverified mandatory supplier conditions prevent plan
confirmation until resolved; preferences alone do not. Confirmation is still
required before research or durable traveler-memory updates. This work does
not create reservations or payments.

## Natural conversation

The demo now enables `--dialogue-mode auto`. A lightweight conversational agent
uses `NIM_DIALOGUE_MODEL` (default `nvidia/nemotron-3.5-lightning-30b-a3b`), recent
messages, validated trip facts and actual destination descriptions to speak
naturally. It does not receive state-writing, booking or research tools.
Ordinary advice uses at most one hosted request, with an eight-second timeout
and a 60-second cooldown after a provider outage. Explicit choices, protected
edits, saved budget summaries and research status use their direct local paths.
Use `--dialogue-mode local` to disable hosted conversational phrasing entirely.

For example, **I want to go ot the place where I can feel relax, for a solo trip
with 50k** now saves a relaxed pace, one traveler and INR 50,000, and immediately
offers places to unwind. **Suggest some places** retains those preferences;
**why Munnar** explains the recommendation without changing the destination;
**the second one** selects the second offered option. Catalog tags and source
descriptions determine the recommendations. Guide prices cannot establish a
whole-trip cost without dates and a starting city. The constraint review is
collapsed by default under **How I understood your trip**.

`node scripts/check_conversational_demo.cjs` replays these turns in Edge and
records real model use, response latency, desktop/mobile screenshots and
contextual selection in `report/conversational_travel_20261022/`.

## Starting city, fare calculations, and more destinations

Discovery now asks **Which city will you be starting from?** while showing the
first recommendations. A plain city answer, **I'm currently in Mumbai**, or
**My current location is Mumbai** is saved as the origin, not the destination.
The app asks before completing trip intake even if a destination was already
provided. It does not request device geolocation.

Each destination card shows **Why this fits you**, linking supported catalog
descriptions/tags to the requested pace and interests. Budget and solo/group
fare assumptions are explicit. **See more destinations** loads the next three
without repeating previously shown destinations; the browsing history persists
through reloads. The last batch states when the sample catalog is exhausted.

Destination guide prices are separate from travel fares. Travel previews and
the Travel desk use the cheapest matching sample route for each direction,
filtered by starting city, destination/gateway, transport preference, travel
time limit, available seats, and party size. Outbound and return fares are
multiplied by traveler count. **Travel fare breakdown** shows the legs/modes.
Changing the starting city recalculates these previews. The original demo
catalog remains synthetic: exact dates, taxes, baggage and live availability
require supplier confirmation.

The detailed calculator no longer inserts a flat INR 2,500/person/leg when a
city or route is unknown. Unknown legs are excluded from the known subtotal,
`trip_total_inr` and `within_budget` stay null, and the Travel desk labels the
amount **Known subtotal · travel incomplete** instead of a complete trip cost.

`node scripts/check_origin_recommendations.cjs` verifies starting-city
collection, different Mumbai/New Delhi fares, explanation cards, more-options
browsing, destination selection, reload persistence and mobile layout. Its
evidence is in `report/origin_recommendations_20261022/`.

## Extraction modes

The default demo uses **local deterministic extraction**, labeled in the review.
It handles the demonstrated date/count/INR forms and common preference cues
without a model request for extraction. The separate conversational agent
phrases its response; unknown or provisional trip facts still need clarification.
TinyFish remains the configured research provider after confirmation.

To use the actual NVIDIA semantic extraction agent independently of research:

```powershell
.\.venv\Scripts\python.exe scripts/run_query_agent_demo.py --query-agent-mode nvidia
```

This requires the existing private `NVIDIA_API_KEY`. Alternatively set
`VOYARA_QUERY_AGENT_MODE=nvidia` with the normal launcher. `auto` retains the
existing provider-specific intake behavior; `local` explicitly selects local
extraction. Hosted failures remain visibly unavailable; they do not claim a
successful model result. The live non-sensitive model probe during development
timed out, so the live hosted path is not verified by that probe.

The existing authenticated `/api/assistant/conversations/{id}/chat` and
`/{id}/workspace` responses include `workspace.constraint_analysis` with
`facts`, `preferences`, `hard_constraints`, `soft_preferences`, `evidence` and
machine-readable `constraints`. A budget constraint uses `operator: "lte"`
and `unit: "INR_total"`. Dates and per-person arithmetic use the typed parser,
then the existing draft validator and planner. Optional preferences also reach
the confirmed `TripBrief.preferences` and rank catalog options using actual
catalog words; absent amenities are not invented.

## Repeat the checks

```powershell
$env:FALKORDB_PORT='6380'
$env:VOYARA_AGENT_MODE='offline'
.\.venv\Scripts\python.exe -m pytest tests/test_query_constraint_agent.py tests/test_conversation_intake.py tests/test_tinyfish_chat.py tests/test_chat_dialogue.py tests/test_journey_chat_book.py tests/test_context_configuration.py -q
node --test stitch_ai_travel_booking_platform/frontend/constraint-review.test.mjs
npm --prefix stitch_ai_travel_booking_platform/frontend run build
node scripts/check_query_constraint_demo.cjs
```

The browser check uses the already installed `dashboard/frontend` Playwright
dependency and Edge. It creates fictional draft data in the isolated demo,
checks desktop/mobile rendering, correction arithmetic and reload persistence,
and writes its result and screenshots to `report/query_constraint_agent_20261022/`.
It does not start research.
