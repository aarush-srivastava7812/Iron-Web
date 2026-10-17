# Voyara hackathon build plan and decisions

This is a local hackathon application. No publication or deployment is included.
The supplied *Travel Platform Competitive Research & Build Blueprint* (17 October
2026) informs the priorities, particularly its structured itinerary, dynamic quote,
saved-version and constrained-AI recommendations on pages 8–14. The report's
commercial architecture and ten-week scope are recommendations, not user instructions.

The [Wayfinder map](../.scratch/hackathon-travel/map.md) contains the questions and
their resolutions. The user authorized answering those questions and implementing
the selected changes, overriding the skill's usual human-interview and planning-only
defaults. Existing user changes in the repository are preserved.

## Highest-return choices

| Priority | Decision | Demo value | Scope |
| --- | --- | --- | --- |
| 1 | Real stochastic specialist tool loops | Show independent contributions, evidence and handoffs instead of agents represented only by labels | Existing NVIDIA key, existing LangGraph and three-tier memory |
| 2 | Editable saved schedule with exact repricing | Change an activity, meal or stay and see a persisted cost delta | Current single-destination catalog; no new supplier integration |
| 3 | Inspectable team work, version comparison/restore and text export | A judge can understand who did what and reopen the result | Conversation-scoped plan versions and responsive UI |

Keep the existing Python backend, SQL database, JavaScript frontend, authentication,
discovery and simulated checkout. A database/framework rewrite, commercial inventory,
real payments, forex, visas, enterprise operations, and a new routing/map provider have
too little return for this demo. Add only six fictional Goa listings so swaps and
specialist comparisons have meaningful alternatives.

## The team

| Specialist | Working style and responsibility | Actual tool | Temperature |
| --- | --- | --- | --- |
| Mira, trip editor | Exact about confirmed requirements; notices gaps | inspect_brief | 0.35 |
| Atlas, destination scout | Curious; connects destinations to interests | discover_destinations | 0.85 |
| Haven, lodging specialist | Practical; compares amenities and value | compare_stays | 0.55 |
| Saffron, dining specialist | Varied food choices; respects supported diets | find_food | 0.75 |
| Roam, experience specialist | Culture and pace; selects catalog experiences | find_experiences | 0.80 |
| Weaver, itinerary planner | Combines the specialists' choices and checks conflicts | build_schedule, review_schedule | 0.65 |
| Ledger, budget reviewer | Skeptical about totals and exclusions | calculate_budget | 0.35 |
| Anchor, support specialist | Preparation and disruption guidance; runs when requested | check_preparation | 0.50 |

The standard plan invokes seven specialists; support is routed only when relevant.
Independent catalog specialists run in parallel; itinerary construction consumes their
selected candidates, and the budget calculation consumes the selected schedule/stay.
Every model agent chooses actions, receives real observations, can revise its choices,
and calls finish. Candidate selection is validated against observed indices; names,
prices, evidence and confirmed brief fields come from server-owned results. The
planner must run a schedule review before finishing. Error feedback enters subsequent
bounded revision attempts. Shared memory remains scoped to the authenticated user/trip.

Nonzero sampling temperatures and no fixed seed make model decisions stochastic.
Repeated valid runs can still choose the same options. We do not inject randomness
into money, dates, requirements, evidence or access checks. Individuality means
different responsibilities, working styles and tools, rather than a claim of independent
model weights or consciousness. The tool observations and concise decisions are
displayed; hidden model reasoning is never displayed or saved.

## Provider setup

The key already exists in the repository root `.env`. It is read server-side with
priority: process environment, agents/.env, root .env. No key is copied into tracked
files or returned to the browser.

The default agent model is `openai/gpt-oss-20b` through NVIDIA NIM. Agent calls use
validated JSON actions with a bounded work log. Native tool calls remain optional;
live checks exposed malformed Harmony function-name suffixes and empty follow-up
content in the hosted native parser. The JSON work-log protocol avoids those observed
failures while executing the same allowlisted Python tools. There is no fake model
fallback on a failed hosted run. A tested alternate model returned an end-of-life
response, so availability was checked directly against the provider as well as docs.

| Setting | Meaning |
| --- | --- |
| NVIDIA_API_KEY | Existing server-side credential |
| VOYARA_AGENT_MODE=auto | Use NVIDIA when a key exists; visibly labelled offline catalog demo otherwise |
| VOYARA_AGENT_MODE=nvidia | Require NVIDIA; missing/failed provider stops the agent |
| VOYARA_AGENT_MODE=offline | Explicit deterministic demo/testing mode; also disables hosted brief refinement |
| NIM_AGENT_MODEL | Override the agent model separately from requirement extraction |
| NIM_AGENT_PROTOCOL=json | Default schema-validated tool actions; native is optional |
| VOYARA_AGENT_MAX_TURNS=5 | Bounded decisions per specialist, constrained to 2–8 |
| MAX_INFERENCE_CONCURRENCY=2 | Bounded concurrent provider requests |

[NVIDIA tool-calling documentation](https://docs.nvidia.com/nim/large-language-models/latest/function-calling.html)
describes provider tool support; [sampling documentation](https://docs.api.nvidia.com/nim/reference/openai-gpt-oss-120b-infer)
describes the compatible sampling API. Live provider results govern the selected model/protocol.

## Editor behavior and limits

Successful generated plans save structured server-owned snapshots into a new
`plan_versions` table; no existing tables or data are migrated or removed. The
planner and the conversation page load the latest version. Users can replace/remove
meals and activities, move their contents between chronological slots, select another
shortlisted stay, compare totals, restore a version and export a text itinerary.
Every accepted edit creates a new version and reuses the exact budget calculator.
Clients send operations and indices, never amounts or arbitrary plan objects.
Concurrent edits use expected-version checks and a database unique constraint.

Changing trip details, profile preferences or saved preference snapshots makes older
versions stale. Stale versions remain available as history and require a fresh plan
before editing/restoring. Ownership checks apply to reading and editing versions.

The estimate covers the listed scheduled activities, one daily meal, one assumed
room and an allowance. Room occupancy, extra meals, intercity transport, taxes,
opening hours and routing are unverified. Schedule checks detect time conflicts;
they do not establish real-world route feasibility. All inventory remains a labelled
synthetic hackathon catalog. No agent can book, pay or manufacture supplier confirmation.

Memory context diagnostics still measure the existing byte-budgeted structured
context, not hosted-model token usage. The bounded agent prompts/work logs are separate;
this change does not claim exact hosted tokenizer accounting.

## Local demo and verification

Start using the existing command:

```powershell
.\.venv\Scripts\python.exe scripts/run_voyara.py
```

Open the AI Trip Planner, choose Goa, three days, two travellers and an ample INR
budget. Generate the draft; inspect each specialist's actual work; swap a meal or
stay; compare/restore versions; reload the conversation and export the itinerary.
Change the saved budget and generate again to demonstrate current-memory handoff.

Offline regression checks intentionally avoid paid/network inference:

```powershell
$env:VOYARA_AGENT_MODE='offline'
.\.venv\Scripts\python.exe -m pytest tests/test_stochastic_agents.py tests/test_hackathon_plan_editor.py tests/test_application_integration.py agents/tests/test_agents.py agents/tests/test_orchestration.py agents/tests/test_routing.py agents/tests/test_validators.py -q
```

The optional live check uses real NVIDIA decisions, a synthetic catalog, isolated
real memory stores and the test suite's explicitly declared offline embedding fixture:

```powershell
$env:VOYARA_LIVE_CHECK='1'
.\.venv\Scripts\python.exe -m pytest tests/test_hackathon_live_nvidia.py -q -s
```

Results and scope are recorded under `report/hackathon_travel_20261017/`.
