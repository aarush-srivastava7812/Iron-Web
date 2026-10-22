# TinyFish memory integration: verification record

Date: 22 October 2026. Branch: `codex/tinyfish-memory-refresh`. Not merged or
deployed. Existing uncommitted work was preserved on branch creation.

## Presentation and real-site retest

The two root HTML guides now present six slides: overview, system, memory,
TinyFish, results and verification. Previous/next buttons, keyboard navigation,
a slide picker, fullscreen and horizontal touch gestures replace page scrolling.
The detailed versions and original generator were preserved under ignored
`.scratch/presentation-guide-backups/`.

`site-smoke.json` records actual localhost HTTP and browser checks with a fresh
synthetic traveler, followed by deletion of the exact test-owned SQL account.
The travel site passed eight checks: health, session ownership, homepage,
five-turn chat and reload persistence, dated itinerary with reconciled estimate,
trip retrieval, duplication and mobile layout. It records page-ready time,
individual chat-turn times and seeded itinerary API latency. These are not
end-to-end AI research timings.

The actual dashboard feed returned HTTP 503 because FalkorDB was unavailable.
Docker Desktop failed to start its inference manager because the local
`dockerInference` socket could not be accessed. The real outage screen, retry
button and mobile display passed; no substitute counts were shown.

`ui-tests.json` records the new verification run: 28 focused Python checks,
13 dashboard unit tests, both production builds, and four dashboard/compact-guide
browser cases. Dashboard data-view browser cases use explicitly labelled
fixtures; they do not establish live database connectivity. Current real site
timings and fixture/controlled measurements are labelled separately in the HTML.

## Measured improvement

`benchmark.json` records a controlled local ablation with mock Search/Fetch
transport and seeded source statements. Ten identical lookups made 20 HTTP
requests in an uncached loop versus two with evidence reuse: 90% fewer fixture
requests and nine saved-evidence recalls. Challenge cases excluded 20/20 stale
observations, flagged 10/10 changed-evidence plans, and rejected 10/10 quotations
absent from fetched source text. This is not a production cost, latency,
recommendation-accuracy or previous-release comparison.

`live-research.json` records one real generic public Jaipur lookup: 10 Search
sources, three fetched pages, 18.55 seconds. Extraction was disabled. It proves
provider connectivity for that run, not fact verification or a memory speedup.

## Passed checks

- 28 focused Python lifecycle/API/gateway-contract and presentation checks.
- 13 dashboard JavaScript unit checks.
- Four desktop/mobile browser acceptance cases covering the new dashboard,
  missing evidence, both HTML guides, navigation, citations and metric labels.
- Dashboard production build and static checks on the changed Python modules.

PNG screenshots are browser acceptance fixtures, explicitly labeled in the UI;
they are not screenshots of live provider activity.

## Remaining verification limits

The broader memory-gateway/application regression run could not connect to
FalkorDB at `127.0.0.1:6380`. Docker Desktop's service was stopped and Windows
denied a service-start request. Source-only graph writes and links have contract
tests and deferred-index recovery tests, but real FalkorDB round-trip acceptance
must be rerun once the existing database service is running.

Four existing TinyFish invalid-food tests also expect `failed` where the current
adapter returns `ok` with no food recommendations. The adapter file was already
modified on entering this task and was not edited by this task. This status
expectation mismatch remains visible; the broader suite is not reported green.

No merge, push, hosted deployment, real booking or private-data provider test was
performed.
