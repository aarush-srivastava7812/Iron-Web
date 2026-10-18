# Ironweb dashboard feature report

Prepared on 18 October 2026. Features are ordered by their importance for understanding and reviewing the application, rather than by the position of their tabs.

## What the dashboard is about

Ironweb shows how the Voyara travel application remembers traveler information and supplies it to its planning agents. It helps answer four practical questions: What does the system know? What did an agent actually read? What changed? Is that information still current?

The dashboard combines a knowledge graph, captured agent contexts, an activity history, and measured resource information. Its main value is traceability: a reviewer can move from an agent action to the information used and then to the claims and sources supporting it.

The monitored system has three memory tiers:

| Tier | What it contains | Why it matters |
| --- | --- | --- |
| Hot context | Bounded agent instructions and traveler essentials supplied for work | Keeps immediate requirements available to an agent |
| Context cards | Selected, task-specific summaries derived from retained information | Supplies relevant context within configured limits |
| Durable evidence | Facts, relationships, source records, and receipt/lifecycle state in FalkorDB, embedded Qdrant, and a SQLite journal | Preserves the evidence behind current and derived information |

The travel website creates plans and changes memory. The dashboard provides read-only inspection of the published memory scope. The five main tabs are **Memory graph, Agent wiring, Activity, Architecture, and Resources**.

## Current observed state

A read-only live snapshot captured on **18 October 2026 at 16:01:16 IST** reported:

| Observation | Captured value | Interpretation |
| --- | --- | --- |
| Published scope | One traveler's shared memory, with no trip restriction | Covers that published traveler's trips; it is not a view across all users |
| Retained events | 27 | The current observation window, rather than lifetime activity |
| Registered agents | 9 | Actors configured with the memory service |
| Observed agents | 8 | Actors represented in the retained activity |
| Currently reading memory | 0 | No outstanding recent read at capture; this does not mean agents never used memory |
| Latest context captures | 8 | Captured agent contexts available for inspection |
| Displayed durable graph nodes | 120 | The graph page is truncated; this is not the whole graph |
| Relationships on that page | 189 | Connections between the displayed graph nodes |
| Stored memories | 22 | A separate store measure, distinct from graph-node count |
| Cache occupancy | 8 entries and 66,325 payload bytes | Application-wide context cache; limit 256 entries and 33,554,432 bytes |
| Provider identity | NVIDIA NIM | Provider metadata; actual use is assessed through recorded requests/responses |
| Context accounting | UTF-8 bytes | The active deterministic consumer profile does not count hosted model tokens |

The event window included eight context requests, eight assembled contexts, seven agent completions, one freshness validation, one rejection of inferred writes, and workflow start/end events. Counts will change with activity or reset after a memory-owner restart.

## Features in order of importance

### 1 Inspecting the information an agent actually used

**Where:** Resources > Context, together with the right-hand Memory inspector.

Context X-ray shows each captured agent context as a bar against its configured limit. It separates agent instructions, traveler information, and the remaining framing, cards, and evidence. Expanding an agent row reveals context fields, their status, and clickable supporting claim IDs. An expandable payload shows the exact observed context and its accounting unit.

Selecting a linked claim opens the inspector. Supporting field details expose claim IDs, scopes, and source-event IDs, allowing a reviewer to follow the evidence behind an instruction or requirement.

**Why this ranks first:** A successful-looking plan alone cannot explain whether an agent received the right budget, dates, or restrictions. This feature provides the most direct evidence of what was supplied to the agent.

**Interpretation:** Context capture demonstrates information supplied to execution. It does not prove that the model followed every instruction or that the resulting travel recommendation is correct.

### 2 Exploring the memory graph

**Where:** Memory graph.

The graph combines actual paged FalkorDB nodes and relationships with explicitly derived nodes representing captured hot contexts and selected cards. Derived links explain which claims were read, which cards were selected, and which claims those cards came from.

Its main controls and visual features are:

- Tier colors: orange for hot context, yellow/olive for context cards, and slate gray for durable evidence.
- Clickable nodes that synchronize with the explorer and inspector.
- Highlighting of a selected node and its immediate connections.
- Node sizing by observed access count, with a uniform-size alternative.
- Zoom in, zoom out, background dragging to pan, and Fit to restore the default framing.
- Selective labels at normal zoom, with additional labels revealed on zoom.
- Agent cursors, relationship pulses, and conflict highlighting tied to observed events.
- Counts separating durable knowledge-graph nodes from derived context nodes.

**Why it matters:** The graph makes the relationship between stored facts and agent context visible. It helps explain how multiple agents can use evidence from the same memory service.

**Interpretation:** Node size represents accesses in retained observations. It is not a confidence score, lifetime popularity measure, or guarantee of correctness. The displayed graph is a bounded page, so missing nodes or links can reflect pagination.

### 3 Checking changes and context freshness

**Where:** Inspector > Diff, History, and Links; conflict markers in Activity and the replay dock.

The Diff tab displays the current stored value, a captured card/context, or the selected event's details. When an event captured committed changes, it shows the affected field, the before value when available, the after value, the action, and the source receipt identifier.

Freshness and failure markers call attention to invalid contexts, failed reads, failed statuses, and captured disputes or conflicts. A failed freshness check explains that the application must validate the context again. History lists matching retained events and lets the reviewer jump to them. Links lists actual or source-derived relationships and provides navigation to connected records.

**Why it matters:** A traveler can change a budget or requirement after planning begins. These features help explain why previously used information may no longer be suitable and which recorded changes led to that state.

**Interpretation:** The dashboard reports application validation outcomes. It does not itself resolve the conflict, edit the requirement, regenerate a plan, or perform deletion. Missing historical before values remain explicitly unavailable.

### 4 Replaying the sequence of activity

**Where:** Activity and the shared replay dock at the bottom.

Activity displays separate rows for the application and registered actors, with cells representing the most recent 100 events. Colors distinguish Planning, Research, and Review; attention markers identify conflicts or failures. Clicking a cell selects its event and updates the inspection state.

The replay dock works across all five views. It provides previous/next event controls, play/pause, reset to the first retained event, a position slider, and playback speeds of 0.5, 1, 2, or 4. It groups actors into Planning, Research, and Review lanes. Chapter buttons target actual recorded event kinds: Intake, Recall, Validation, Agent results, and Latest when those events exist.

Follow live tracks new observations. Clicking an event pins inspection, making it possible to examine a specific point without selection immediately moving to the newest event. Event IDs, timestamps, and the current position remain visible. Dashboard event times are displayed in UTC.

**Why it matters:** Event order makes it easier to understand whether requirements were saved, recalled, validated, and used before work completed.

**Interpretation:** Playback advances through observations; it is not a recording of model reasoning or an exact reconstruction of elapsed execution time. Captured context can be replayed historically, while graph/store state and hardware/provider aggregates remain latest snapshots. The interface labels this distinction as historical context with the latest knowledge graph.

### 5 Understanding agent roles and connections

**Where:** Agent wiring, the Agents menu, and Activity.

Agent wiring connects registered actors to the shared memory service and shows three operation categories: Read context, Commit intake, and Forget source. Selecting an actor filters or emphasizes that actor across relevant views. Selecting the shared memory store opens durable evidence in the graph. Pulses correspond to the selected observed event; static connections describe registered wiring.

| Actor | Role in the travel workflow |
| --- | --- |
| Orchestrator | Coordinates routing, shared context, and results |
| Consultant | Collects and clarifies trip requirements |
| Explore | Researches destinations and activities |
| Stay | Finds accommodation options |
| Food | Finds food options with relevant requirements |
| Tour | Researches attractions and experiences |
| Planner | Builds the itinerary sequence |
| Budget | Reviews listed costs and budget fit |
| Support | Provides travel support when routed |

The header shows observed/registered counts. The agent menu lists per-agent reads in the retained window and offers Show all agents.

**Why it matters:** It reveals which actors actually participated and how they share memory. Nine registered actors does not mean nine concurrent model calls. The documented full planning flow uses seven hosted specialists plus an orchestration memory reader; support is used when needed.

**Interpretation:** The tool boxes describe memory operations. They are not buttons for invoking those operations from the dashboard.

### 6 Reviewing context cache provider hardware and latency metrics

**Where:** Resources, with five subviews.

| Subview | What it displays | What the reviewer can learn |
| --- | --- | --- |
| Context | Captured context allocation, configured limits, field status, and supporting claims | Whether supplied context fits its budget and has traceable sources |
| Cache | Completed context reads through the selected event, cache hits, hit rate, latest payload occupancy, and entry quotas | Whether the application reused assembled context and how much cache capacity is occupied |
| Provider | Observed inference HTTP requests, successful responses, and reported input/output tokens | Which provider usage was actually recorded |
| Hardware | Website-process RAM, observed device VRAM, latest captured CUDA card allocation, and device/residency details | Which runtime memory measurements are available |
| Latency | Up to 18 recent measured events through the selected event, with latency in milliseconds | Where recorded context assembly or agent work took time |

The top bar also summarizes selected context utilization and retained-window cache hit rate. Measurement/configuration labels and unavailable states help explain the figures.

**Why it matters:** These metrics support diagnosis of context size, reuse, and slow operations. They should be read after understanding what activity and evidence produced them.

**Interpretation:** Context-packet bytes and provider tokens are different units. Cache hit rate concerns the application's context-payload cache, not NVIDIA prompt caching. Cache occupancy is the latest application-wide snapshot; provider counters cover the website process since startup. Parallel agent latencies must not be added into an assumed end-to-end duration. Device VRAM can include other processes, and shared CUDA allocations are not summed across agents.

No equivalent no-memory prompt was captured, so savings versus a no-memory baseline is N/A. Provider cost and cache-read/cache-write token breakdowns are not recorded. GPU utilization, durable byte quotas, and eviction reasons are unavailable unless instrumented.

### 7 Understanding the three memory tiers

**Where:** Architecture.

Architecture shows the three tiers with their names, storage descriptions, observed amounts, and configured allocations where available. Hot context is measured in the consumer's actual unit; context cards are counted against configured card slots across captured contexts; durable evidence shows stored memories and the number of knowledge-graph nodes on the current page.

Selecting a tier opens its contents in the inspector. This gives a simpler introduction to the system before exploring individual graph relationships.

**Why it matters:** It explains how immediate instructions, selected summaries, and durable source evidence work together. Hot context and cards are derived views of authoritative information. The architecture view does not establish observed promotion or eviction events, which are not instrumented.

### 8 Finding records and navigating between views

**Where:** The persistent Memory explorer and synchronized selection controls.

The explorer groups nodes under Hot context, Context cards, and Durable evidence, with counts and collapsible groups. Search matches displayed node labels and IDs. Rows show their identity and available access count; selecting a row updates the inspector and graph selection. Agent filtering narrows agent-associated records while retaining shared records where applicable.

The URL records the view and available event/memory selection using `view`, `event`, and `mem`. This allows the current inspection position to be revisited while its records remain available. The brand/home control returns to the graph and enables follow-live.

**Why it matters:** Persistent navigation connects overview screens to supporting records without requiring the reviewer to locate the same item again.

**Interpretation:** Search operates on the loaded graph projection. It is not a semantic search across the complete durable database. A URL does not archive an event beyond the observation retention window.

### 9 Inspecting the data source and connection state

**Where:** The connection-status control and Source & credentials.

The connection dialog exposes the published traveler/trip scope, database metadata, store counts, graph-page truncation indicators, Qdrant point payloads, and recent SQLite receipts. Inspect numeric vector performs a read-only request for actual vector values. Provider and credential identity are shown with masked fingerprints rather than full keys.

The frontend initially loads a snapshot, then receives Server-Sent Events from a separate relay. The relay normally emits snapshots every two seconds. After ten seconds without a snapshot/error heartbeat, the frontend marks retained data stale and reconnects. Source errors and connection interruptions are visible; unavailable data is not replaced with sample events.

Remote viewer access supports a secret-entry form and an HttpOnly session cookie. Publication authorization remains server-side. The relay reads from the website's inspection adapter, so it does not open embedded stores or become a second memory writer.

**Why it matters:** A reviewer needs to know which account is being inspected, whether the feed is fresh, and where records originated before relying on what is displayed.

**Interpretation:** Relay process health alone does not establish database health. A recent displayed snapshot can still be retained data during an outage; the stale indicator must be considered.

### 10 Using the dashboard on smaller screens and with keyboard controls

The desktop layout contains a top status bar, explorer, central visualization stage, inspector, and one replay dock. Below 1280 pixels, the explorer and inspector become drawers with explicit open/close controls. Reduced-motion preferences suppress animated cursor and connection movement. Controls include accessible names and state labels.

| Key | Action |
| --- | --- |
| Space | Play or pause replay |
| Left and right arrows | Previous or next event |
| 1 through 5 | Switch the five visualization views |
| F | Toggle follow-live |
| / | Focus memory search, opening the explorer drawer when needed |
| Escape | Close panels/dialogs and clear selection |

A help dialog documents the shortcuts and selectable items. These features make repeated inspection easier; their presence is not a claim of a complete accessibility certification.

## Recommended order for presenting the dashboard

Start with Architecture to explain the three tiers, then use Memory graph to connect an actual claim to a captured context. Open Context X-ray and the inspector to show the supporting sources. Use Activity and replay to follow the sequence of reads, validation, and completion. Explain the participating agents in Agent wiring, then finish with Resources and the connection/scope details.

This presentation order introduces the concepts before the detailed evidence. The feature ranking above places traceability first because it provides the strongest practical basis for assessing the system.

For a change demonstration, use a real website requirement update, then inspect its observed change and freshness result. Only demonstrate conflict, deletion, or other outcomes when the corresponding activity has actually been captured.

## Limits that affect every view

- The memory owner retains up to 500 events and 256 latest context entries. These observations reset on owner restart; durable memory and receipts have separate persistence.
- Graph, claim, vector, and receipt inspection is bounded. APIs provide paging metadata; the React source dialog shows counts and truncation rather than a complete database export.
- Publication selects one traveler, optionally restricted to a trip and inherited profile data. Store totals describe the published traveler's whole store; cache totals cover the application runtime.
- Captured event context is historical evidence. Graph/store state and resource aggregates do not become historical database snapshots when replay moves backward.
- Forgetting invalidates or clears affected retained context/change payloads. A historical selection is not a way to recover forgotten content.
- Proposed retrieval-score explanations and a maintenance-impact ribbon are not implemented as fully traced features. Source/field support is available; comprehensive reasons for semantic retrieval/exclusion and promotion/eviction are not.
- The dashboard observes agent and memory activity. Synthetic travel listings do not become verified supplier inventory because an agent used them.

## Evidence and review method

This report is based on the active React entry point and current implementation, project documentation, and fresh read-only HTTP checks. The frontend returned HTTP 200, the relay health endpoint reported a configured source, and the live snapshot returned schema `iron_web_dashboard_v1`.

The feature inventory was checked against the active `LiveApp` implementation rather than the older fixture-based UI. No trip generation, paid inference, memory changes, or booking actions were performed for this report. Browser-rendered layout was not newly verified during this review; responsive and visual behavior is described from the implementation and retained project documentation.

Primary local references:

- [Dashboard guide](../../dashboard/README.md)
- [Active frontend entry point](../../dashboard/frontend/src/main.jsx)
- [Application layout and live feed](../../dashboard/frontend/src/LiveApp.jsx)
- [Inspector wiring activity architecture and source dialog](../../dashboard/frontend/src/LivePanels.jsx)
- [Resource metrics and replay controls](../../dashboard/frontend/src/LiveResources.jsx)
- [Graph controls and rendering](../../dashboard/frontend/src/LiveGraph.jsx)
- [Projection event definitions and unit handling](../../dashboard/frontend/src/liveData.js)
- [Read-only relay access scope and API limits](../../dashboard/backend/README.md)
- [Implemented and proposed feature choices](../../docs/dashboard_features.md)
- [Retained finalisation and verification evidence](../finalisation_20261018/README.md)
