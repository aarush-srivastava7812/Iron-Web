# Voyara architecture atlas

Open `architecture-atlas.html` in a browser. The seven navigable views are the system overview, interactive agent map,
TinyFish memory wiring, tool wiring, provider comparisons, local benchmarks,
and sources. The HTML embeds its data and scripts and makes no remote requests.

The existing six-slide presentation is preserved. All work remains on
`codex/tinyfish-memory-refresh`; no merge or deployment is involved.

## Published data

`published-comparison.json` records a selected six-provider snapshot from the
[OpenBenchmarks search-and-fetch coding-agent board](https://openbenchmarks.com/web-search-for-coding-agents),
updated 26 September 2026 and retrieved 22 October 2026. The publisher's
[harness](https://github.com/openbenchmarks-labs/web-search-for-coding-agents)
describes its protocol. Values are published results, not new measurements.

The board holds the model, tasks and runner fixed. Task tokens are median LLM
prompt plus completion tokens, not internal provider tokens. Median task time
and mean search-call time are different metrics. Completion is mean plus/minus
standard deviation. Rounded task-time values are taken from the published
table. Only the search-and-fetch board is used for the main comparisons.

A separate, collapsed chart uses the vendor-reported Search API p50 table from
[TinyFish's benchmark page](https://tinyfish.chat/benchmarks), labelled July 2026.
It is never combined with coding-task latency. API capability descriptions are
supported by the [TinyFish capability guide](https://tinyfish.chat/blog/which-tinyfish-api-should-you-use).

The comparison selector calculates token, time and completion differences from
the snapshot. It retains trade-offs, including alternatives with shorter task
times or higher completion. No universal provider superiority is claimed.

## Architecture and local measurements

Four solid direct links correspond exactly to `RESEARCH_ROLES` in
`agents/tinyfish.py`. Five dashed links represent shared evidence or workflow
coordination. Every agent has an implemented-connection description and a
separate recommendation. A dedicated TinyFish advisory/policy adapter for
Travel Support is explicitly proposed, not implemented. Indicative hotel rates
are not date-specific availability checks or booking confirmations.

Local measurements come from the existing `report/tinyfish_memory` receipts:
the controlled lifecycle experiment, real public provider connectivity check,
live localhost product smoke test and sampled memory retrieval evaluation.
The atlas does not sum independent probe durations. Full live trip-run latency,
Voyara's provider-comparison token savings and serial-versus-parallel speedup
remain unmeasured. No new paid research requests were submitted.

## Reproduction and validation

```powershell
.venv/Scripts/python.exe scripts/build_architecture_atlas.py
.venv/Scripts/python.exe scripts/check_architecture_atlas.py
```

`browser-checks.json` records 16 passing acceptance checks in installed Edge,
with runtime errors and outbound requests both zero. The tests cover all nine
agent selections, direct/shared filters, keyboard navigation, the complete role
matrix, chart values, comparison calculations, JSON download, deep links, local
citations, and seven views at five desktop/tablet/phone sizes. PNG captures are
actual renders of the generated HTML; published chart values remain attributed
external data rather than results of those browser checks.


## Three-tool wiring update

The central hub contains Search, Fetch and Agent controls. Search highlights
four discovery-role connections. Fetch highlights the three conditional venue
reading paths; Explorer's default discovery-only behavior is explained.
Destination-memory refresh separately uses Search + Fetch.

Agent highlights four amber dashed optional client paths. The dedicated tool
page shows URL + read-only goal + schema, async run creation, run ID/status
polling, structured output, and timeout cancellation. TinyFishClient exists and
can be explicitly injected; the runtime defaults to TinyFishSearchClient. This
change visualizes all three tools without claiming an automatic Fetch-to-Agent
fallback or submitting paid Agent requests. Its structured result checks are
separate from the memory service's exact-quote ingestion gate.


## TinyFish-to-memory wiring

The Memory wiring page traces the implemented destination-research memory path:
Search/Fetch payload -> external_memory.ingest exact-quote gate -> SQL
ExternalKnowledgeVersion/Event ledger -> sync_graph source-only FalkorDB
index -> latest/fresh/non-conflicting recall -> ThreeTierGateway
MemoryContext.external_evidence -> specialist context. Each handoff is selectable
and links to its implementing source file.

The diagram includes missing/stale/conflict background refresh, source-version
history, changed high-impact plan review, SQL availability during graph outages,
and the separate authority boundary around confirmed traveler preferences.
Four walkthrough controls explain fresh, stale, changed and graph-down behavior;
they do not execute provider calls, simulate measured performance or alter trips.

The optional Agent client is not automatically connected to this SQL ledger.
The page marks the missing bridge explicitly. Role-level discovery outputs also
must not be assumed to have become SQL evidence versions; the solid memory
write path shown is the destination-research service's completion/ingestion path.
