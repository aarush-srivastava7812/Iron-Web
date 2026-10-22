# TinyFish memory: measured presentation

22 October 2026. Branch `codex/tinyfish-memory-refresh`; unmerged.

The two root HTML files are identical six-slide offline presentations: overview,
research agents, memory/freshness flow, TinyFish lifecycle results, memory
benchmarks, and Voyara tests. Diagrams and measured charts replace long prose.
Keyboard, touch, fullscreen, slide selection and print support remain available.
The report dialog holds methodology and linked JSON receipts.

## Test 1: memory retrieval

`memory-benchmarks.json` is a fresh run of the current Iron Web 2 engine with
real cached CPU embeddings and FalkorDB. It contains input fingerprints,
per-question retrieved/gold document IDs, recall@5, hit@5, MRR and latency.

| Dataset | Questions | Complete selected sessions | BM25 recall@5 | Memory recall@5 | Memory median ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| LoCoMo | 20 | 19 | 60.8% | 43.3% | 96.2 |
| Project DMR / MSC | 20 | 100 | 0.0% | 30.0% | 112.1 |
| LongMemEval | 5 | 253 | 100.0% | 60.0% | 100.5 |

Questions are the first in release order, chosen before results were available.
All selected histories are preserved, including distractors. LoCoMo and
LongMemEval apply their declared conversation scope; DMR retains all five
sessions per selected conversation with cross-conversation distractors. The
BM25 baseline uses identical documents/scopes (k1=1.5, b=0.75). No reranker,
answer generator, historical query-time filtering or TinyFish request is used.
This is a small source-retrieval probe, not official full-dataset answer accuracy
and not a TinyFish-caused improvement. Negative comparisons are retained.
Unique test graphs were deleted after measurement; user graphs were untouched.

Reproduce: `.venv/Scripts/python.exe scripts/measure_memory_presentation.py`.

## TinyFish lifecycle experiment

`benchmark.json` was rerun using mock Search/Fetch HTTP transport and exact
seeded source statements. Ten identical lookups made 20 requests without recall
and 2 with recall (90% reduction), with 9 saved-evidence reuses. Separate seeded
challenges excluded 20/20 stale cases, rejected 10/10 unsupported quotations,
and flagged 10/10 changed-evidence plans. These results are not measured live
provider savings, factual accuracy, or comparisons with the previous release.

`live-research.json` remains a separately dated real public Jaipur Search/Fetch
receipt: 10 source results, 3 fetched pages, 18.55 seconds, extraction disabled.
It establishes connectivity for that recorded run, not quote/answer accuracy.
No new paid provider request was needed for the presentation refresh.

## Test 2: Voyara travels

`site-smoke.json` is a fresh actual localhost HTTP/browser test, with no mocked
dashboard feed. **19/19 checks passed**, including 8 travel checks, 10 dashboard
checks and browser runtime error verification. It covers five chat turns with
reload persistence, a seeded dated three-day itinerary and budget reconciliation,
save/retrieve/duplicate, three authenticated live feed samples, eight dashboard
views, Follow live, owner isolation and mobile layout. Browser runtime errors: 0.
The exact synthetic SQL account was removed. No paid research was started.

Docker's stale runtime socket folder was preserved and recreated, restoring the
existing FalkorDB container. The earlier HTTP 503 outage is resolved. Screenshots
prefixed `actual-dashboard` are now from the real feed. `dashboard-desktop` and
`dashboard-mobile` remain explicitly labelled UI-fixture screenshots; older
`actual-dashboard-outage` captures document the earlier outage.

## Build and presentation checks

`ui-tests.json` records 28 focused Python checks, 13 dashboard unit checks, both
production builds, and four browser tests passing. The two HTML cases verify
navigation, fullscreen, methodology links, receipt-backed chart numbers and all
six slides at five viewports. Dashboard fixture tests establish UI behavior;
actual database connectivity is established separately in `site-smoke.json`.

The broader application suite is not certified by this focused run. Earlier
invalid-food adapter status expectation mismatches remain outside this change.

Rebuild: `.venv/Scripts/python.exe scripts/update_tinyfish_guides.py`.
Run site checks: `.venv/Scripts/python.exe scripts/check_presentation_sites.py`.
Run focused verification: `.venv/Scripts/python.exe scripts/run_presentation_checks.py`.
