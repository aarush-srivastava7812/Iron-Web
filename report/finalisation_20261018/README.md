# Iron Web finalisation — 18 October 2026

Branch: `finalise/2026-10-18`. Starting revision:
`245829251f5222fbabe0d1c25b00170e9edabd1c`. Local changes only; no push, merge,
history rewrite, provider switch, cloud deployment or memory-model change.
Previously modified dashboard report images/snapshot were preserved separately.

## Current operational status

**Approved recovery active; fresh hosted acceptance passed.** The first outage
drill found that FalkorDB v4.20.7 exits 139 during `GRAPH.EFFECT` replay. The original
`iron_web_falkordb_data` volume and a verified pristine backup are preserved.
The user approved progressively scoped fixture-only repairs on separate copies,
then a separate live cutover to a verified activation copy. The website and relay
were restarted from current source. New hosted acceptance and live consistency
checks passed; dated evidence is in `post_recovery/`. The original crash and failed
trials remain recorded rather than being overwritten. Website/relay process
health must not be mistaken for memory health or a general durability guarantee.
Final database restart, relay stop/stale/reconnect and every preflight check passed.

User-approved recovery work is confined to copies. Every persisted file in
`iron_web_falkordb_recovery_20261018` matched the original by SHA-256. An ephemeral
network-isolated replay reproduced the crash without changing either volume.
The RESP log is well-framed, not proven semantically valid. Two approved trial
filters (ten effects, then all `test_app` operations) still failed on other
fixture rollback keys. A final approved fixture-only trial excludes operations
whose keys all use the fixture-proven `test_` or `agents_test_` namespaces.
Its exact scope is in `recovery-test-fixtures.json`; all non-test command bytes
are retained. The separately approved live activation is documented in `RECOVERY.md`
and `compose.recovery.yaml`; the trial itself remains stopped.
Existing base-snapshot test graphs can remain; excluding log history does not
mean every test graph has been deleted from a trial database.

A related upstream crash is documented at
[FalkorDB issue #2201](https://github.com/FalkorDB/FalkorDB/issues/2201).
This is a similar failure class, not proof of an identical trigger. Local replay
does not depend on `LOAD CSV`. No AOF reset, RDB-only rollback, image upgrade or
application-data discard has been performed. FalkorDB 6.0 uses an incompatible
effects format according to its
[upgrade notes](https://github.com/FalkorDB/FalkorDB/releases/tag/6.0.0);
changing the image is not a demonstrated recovery fix.

## Changes by phase

| Phase | Commit | Change / evidence |
| --- | --- | --- |
| 0 | baseline recorded in `293ab6a` | `BASELINE.md`; tests completed before source edits. |
| 1 | `293ab6a` | Remove exposed guide key and hardcoded launcher signing secret; generate private local secret; equivalent tree/history scanner and ignore evidence. |
| 1 | `4155c1f` | Viewer gate covers HTTP and SSE; direct loopback-only exemption, remote fail closed, signed HttpOnly cookie, exact origins, rotation/expiry checks. |
| 1 | `7da5f35` | Developer login additionally refuses forwarded/proxied requests. |
| 2 | `1d8fe80` | Reject unsupported cabins, restore newsletter acknowledgment, use direct booking-item annotation; correct outdated undated-food expectation. |
| 2 | `1a7d51c` | With explicit approval, remove fabricated hosted-review fallback; auth required; absent/partial reviews visibly return 503, quote remains available. |
| 3 | `ce246cf` | Remove nine unused leaf import names; retain referenced fixtures/interfaces/reports/adapters. |
| 4 | `79ce775`, `7c44873` | Preflight deps/ports/graph module/private setup checks; restrictive Docker build context and deployment notes. |
| 4 | `7d36549` | Repair dashboard fixture collection; add offline isolated full-flow smoke plus stale-budget/conflict/forget/isolation and preflight tests. |
| 4 | `bd76df4` | Report latest captured CUDA card allocation rather than summing overlapping captures or inventing zero when unavailable. |
| 2/4 | `73512d6` | Regional live browser acceptance and layout tests accept fresh trip/output settings; avoid historical Goa/evidence coupling. |
| 4 | `19dacf9` | Limit browser evidence exports to counts, not raw snapshots; resolve report paths from repo root. |
| 4 | `9633f65` | Fix confirmed stale/live misreport when a proxy keeps a dead SSE stream open; timed heartbeat/reconnect and actual-feed browser regression. |
| Recovery | `3091669` | Record approved fixture-only repairs, preserved original/backup, validated restart and explicit live-volume override. |
| 4 | `eb3bf8e` | Initialize default SQLite directory; verify actual clean-source startup and explicit database override with two regressions. |

Final documentation/evidence is in the subsequent documentation commit; use
`git log finalise/2026-10-18` for its hash. The user-approved branch name is
intentionally retained. No source change to `events.json`, memory data model,
default provider/model, or hosted agent/tool contracts was needed.

## Removed and retained

The pre-removal table is `REMOVAL_CANDIDATES.md`. Nine F401 import names were
removed from leaf modules/scripts; package reexports and imports with uncertain
side effects were kept. The canned booking-review function was runtime-referenced
and removed only after explicit user approval. It had asserted verified amenities,
taxes, scores and agent success following failed inference.

Maintained plaintext guide/launcher secrets were replaced. No subsystem, fixture,
dataset, historical report or application data was deleted as cleanup. Legacy
`server.py`/`web/`, `shared_server.py`, research adapters, mock UI fixtures and
their tests remain because references exist. Optional-dependency pruning remains
unverified. Twenty-six historical Markdown design notes under `.scratch/` are
tracked despite ignore rules and have documentation references; they were kept.
Actual env, session and exported credential files were not found tracked.
Approved recovery-copy log exclusions are a separate diagnostic operation,
documented above; they do not modify source or original data.

## Before versus after verification

| Suite | Baseline | Final scoped result |
| --- | --- | --- |
| Root backend + agent tests | Root 341 passed, 2 skipped, 6 deselected, 4 fixture errors; agents 41 passed | **397 passed, 2 skipped, 6 deselected**, two warnings; offline provider, temporary embedded stores, separate real FalkorDB on 6389. |
| Website backend | Root invocation: four import/collection errors; corrected PYTHONPATH: 45 passed, 2 failed | **51 passed**, explicit offline mode and backend/root PYTHONPATH. |
| Dashboard frontend | 12 passed | **13 passed**, including unavailable/overlapping captured allocation. |
| Dashboard build | Passed | Passed; fresh archived-source install/build also passed using cached npm dependencies. |
| Website build | Not part of original baseline command | Passed; fresh archived-source npm install/build passed. |
| Real-feed browser suite | Two passed against retained pre-restart feed | **Three passed after recovery**, including a new stalled-transport regression using actual memory snapshots. |
| Viewer browser exercise | No viewer gate | Passed: password prompt, signed HttpOnly cookie, actual unauthorized-to-authenticated relay path, visible unconfigured-source error, secret absent from DOM. |
| Relay Docker image | Not built in baseline | `docker build -f dashboard/backend/Dockerfile -t ironweb-finalise-relay:local .` passed; no deployment. |
| Restart/outage | Not exercised | Original persistence restart **failed**; approved repaired volume subsequently restarts and retains current claims. See `post_recovery/outage.json` for database and relay drill details. |
| Clean checkout startup | Old loaded processes | Fresh archived-source npm installs/builds and all three launchers passed after fixing the default SQLite directory; actual isolated feed, developer login and dashboard verified in explicit offline mode. Existing Python environment reused; fresh Python dependency installation **unverified**. |

The full post-cleanup root/agent batch passed 390 tests before further test
additions. The final 397-test run used a disposable **nonpersistent** test
FalkorDB, not a recovered production volume. Test success does not establish
persistence durability. Two skips/six deselections are not counted as passes.
Private JUnit/logs remain ignored; they can contain ephemeral authentication
material and must not be published. `clean-source.json` identifies the exact
archived revision, which predates the final allocation/UI test-script changes;
normal builds passed again after those changes.

A later clean-source check at `3091669` plus the startup-directory fix found and
reproduced a missing `data/voyara_app` parent in the live launcher. The fix creates
it before seeding; two regression cases exercise actual SQLite opening and an
explicit database override. Repeating fresh startup passed developer sign-in,
actual isolated HTTP relay data and dashboard rendering, with zero provider calls
and no env/session/runtime files copied. Both frontends installed/built from cached
dependencies. `clean-startup-before-fix.json` and `clean-startup.json` preserve the
failure and pass. This supersedes the earlier blocked clean-source attempt;
it does not prove a new Python installation. Live services were restored afterward.
The tested launcher patch is committed as `eb3bf8e`; its bytes match the file used
in the fresh checkout. `restored-live.json` verifies the original-root services
after restoration: all seven specialists completed using NVIDIA and the current
INR 80,000 plan; the dashboard captured 27 actual trip observations. The three
browser tests then passed again. No new booking request was made in this final
restored-plan check.

### Fresh hosted acceptance

After restarting services from source and rebuilding both frontends, normal
website developer sign-in created Kerala trip
`4f52cbcd-fdf4-4ceb-ab5a-ed965144d0e3` (1–3 December 2026, two travelers,
INR 200,000, relaxed). All **seven hosted NVIDIA specialists** completed using
the unchanged **`openai/gpt-oss-20b`** model. The plan was saved/current, PDF export
returned 553,620 bytes, both regional catalogs rendered (33/34 SVGs), Kashmir
booking review rendered, and checkout returned 201 with `requested`.

The dashboard observed 29 events for that trip, nine registered/eight observed
actors. Process counters at capture: 19 provider responses, 33,044 input and
2,044 output tokens. They include the optional one-model booking review and are
not per-trip savings or a specialist count. Zero page errors were recorded.
See `acceptance.json`, `fresh-dashboard.png` and regional/review screenshots.
This first acceptance preceded subsequent hardening commits and the restart
failure. A second fresh hosted acceptance after approved cutover passed using
trip `a00621b6-bfc2-479a-953c-7a4207038d13`: seven successful NVIDIA specialists,
saved/current plan, 553,676-byte PDF, both catalogs, Kashmir review and requested
booking. Its capture reports 29 trip events and process totals of 17 responses,
30,480 input/1,816 output tokens. See `post_recovery/acceptance.json`. These totals
precede later consistency/revalidation requests. Initial selector and later
harness failures remain explicitly labeled rather than overwritten.

Budget lowering invalidates old proofs/draft freshness and a current rebuild is
tested. An unsupported hard dietary rule from profile against a trip rule pauses
for review. Owner/stranger checks, event forgetting and replay of the same event
ID without resurrection passed through actual isolated HTTP/service/store tests
(`tests/test_finalisation_acceptance.py`). Both website APIs and the dashboard
adapter were inspected. Exact event-ID replay uses the existing service envelope;
the website does not expose arbitrary event injection. After recovery, live
checks changed the budget to INR 80,000, observed stale-plan/dashboard supersession,
paused actual planning on a hard-rule conflict with a visible website reply,
denied an authenticated stranger (404 private APIs/401 publication source),
clicked **Forget this event**, verified removal from claims/vectors after feed
refresh, then restored the test profile and completed a current hosted rebuild.
The relay intentionally publishes its selected demo account; local published reads
are not a cross-tenant authenticated user session. See `post_recovery/consistency.json`.
Exact same-ID replay remains isolated service coverage. Offline smoke covers auth, seven specialists,
saved plan, PDF, requested booking and the actual ASGI relay with isolated stores.

### Reproduction commands

Use README/DEMO.md for startup. For isolated tests, set `FALKORDB_PORT=6389`
and `VOYARA_AGENT_MODE=offline` **in a test shell only**, then run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests agents/tests -q
$env:PYTHONPATH="$PWD\stitch_ai_travel_booking_platform\backend;$PWD"
.\.venv\Scripts\python.exe -m pytest stitch_ai_travel_booking_platform/backend/tests -q
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run build
npm --prefix stitch_ai_travel_booking_platform/frontend run build
```

The disposable test service uses the existing pinned image, loopback port 6389,
tmpfs `/data`, `BROWSER=0`, `REDIS_ARGS=--appendonly no --save ""`, and no production
volume. The committed `live-flow.mjs` itself passed after recovery. Live consistency
checks used actual supported website APIs and rendered UI. Browser plugin startup
failed twice with a sandbox helper error, so local Edge/Playwright provided browser
verification. Three browser tests include a controlled SSE stall with actual
initial/recovered snapshots, real-feed layout/interactions, drawers/reduced motion.
The moving-node check clicks its current position without requiring a force-layout
node to be stationary. No mock memory or raw snapshot export is introduced.

## Bug log

| Symptom | Root cause | Fix / verification |
| --- | --- | --- |
| Current documentation exposed NVIDIA credential; launcher had fixed signing key | Imported guide and constant secret | Remove maintained values; private generated local secret; tree/history scan. Rotation remains owner's action. |
| Anyone reaching relay could read published scope | CORS without viewer authorization | Gate HTTP/SSE, signed browser session, auth/origin/expiry/rotation regression tests and browser exercise. |
| Forwarded requests could reach enabled developer path | Incomplete forwarded-header rejection | Refuse Forwarded/XFF/XFH; explicit regression tests. |
| Business request returned Economy | Ignored cabin parameter | Economy-only literal rejects unsupported input with 422; existing cabin test passes. |
| Newsletter call returned null | Missing return after route insertion | Restore subscription acknowledgment; website suite passes. |
| Whole root suite had four setup errors | Fixture defined in another test module was not imported | Explicit fixture import; whole final suite passes. |
| Undated-food test expected accepted booking | Old assertion contradicted current dated-request validation | Correct expectation to 422; dated requested booking still covered. |
| Failed hosted review claimed verification and agent success | Canned fallback with invented values | Approved removal; unavailable 503 and visible notice; auth, missing/partial result tests. |
| CUDA allocation total overstated or fabricated as zero | Summed overlapping captures; empty reduction | Latest explicitly captured allocation or unavailable; unit regression. |
| Browser acceptance depended on old Goa trip/output | Hardcoded retained evidence assumptions | Fresh trip/destination/output settings; historical evidence preserved. |
| Persisted database cannot restart | Reproducible FalkorDB GRAPH.EFFECT replay SIGSEGV on fixture graph keys; exact engine defect not proven | Preserve original/backup; approved fixture-only repair starts/restarts; separate activation and hosted/drill checks passed. Underlying engine durability remains unresolved. |
| Relay stop leaves dashboard labeled live | Proxy can hold SSE open without a browser error event | Ten-second heartbeat watchdog marks data stale/reopens stream; controlled regression and real relay stop/reconnect passed. |
| Fresh website launcher cannot open SQLite | Default data directory existed only from earlier local setup | Create parent before seed; actual fresh-checkout startup and default/override SQLite regressions pass. |

Ruff's indirect Pydantic annotation diagnostic did not prove a runtime NameError;
the annotation was made explicit. Initial browser selector and test-fixture
schema mistakes were harness errors, not claimed as application defects.
No blanket lint/dependency cleanup was attempted.

## Security actions required from owner

1. Revoke/rotate any still-active NVIDIA key exposed by the imported guide in
   commit `b905b56a08d2153d9009df92652bb8e496fc082d`. The currently configured key
   differs; exposed-key validity was deliberately not probed. Do not post keys.
2. Rotate any deployed session-signing secret that used the old launcher literal
   from the same commit, and invalidate affected sessions. The local launcher now
   generates a private secret; no remote secret was changed.
3. Decide whether to approve history rewriting. Proposed procedure: revoke first,
   agree affected refs/forks, make a private backup, use a focused git-filter-repo
   replacement on the two affected paths without exposing values, rescan every
   rewritten ref, coordinate fresh collaborator clones, then explicitly authorize
   force-push/cache remediation. **No rewrite or force-push has occurred.**
4. Retain the original and pristine recovery volumes. Live cutover was separately
   approved and verified. Use the explicit recovery override consistently; any
   further data-discarding repair or rollback requires a new decision.
5. Decide deployment domains/publication scope, hosting credentials and storage.
   No deployment or purchase has been made.

`secret-scan.json` scans tracked + nonignored untracked files and all reachable
Git blobs across local refs. Current tree: zero findings. History: two secret
blobs, paths/commits only, no values. This equivalent pattern scanner is not a
guarantee against encoded/unknown formats; ignored runtime secrets were not
copied. `ignore-proof.json` covers active private file patterns. Tracked historical
Markdown exceptions are explicitly documented, not falsely declared untracked.

## Deployment preparation and unverified items

Relay Dockerfile, Railway path/PORT/healthcheck, restrictive build context and
Vercel dist build agree; the relay image built locally. Website serves its Vite
build locally. Its complete Railway/Vercel deployment remains unverified.
Use HTTPS, exact `DASHBOARD_CORS_ORIGINS`, public `VITE_DASHBOARD_API_URL`, private
source URL/grant and `DASHBOARD_VIEWER_TOKEN`. Source grant selects an intentionally
published demo account/trip. It is separate from viewer access and never belongs
in a frontend build. Cross-site HttpOnly cookies can be privacy-blocked; prefer
same-site domains or a same-origin proxy and test streaming/expiry/reconnect.

Keep one memory owner/worker per embedded runtime, durable SQL/journal/vector
storage and authenticated reachable FalkorDB. The relay remains read-only and
has no embedded-store access. Coordinated backups, restart recovery and restore
drills remain release requirements: the activation passed a controlled restart,
but the engine defect has not been proven fixed. Preflight against the actual
recovered service passes every check (`preflight-final.json`). Earlier
`preflight-current.json` describes the outage, including the correct 6379 failure;
passing PING against disposable port 6389 never constituted production recovery.

Malformed provider tools and exhausted execution are rejected by existing agent
guards/tests; unavailable owner/relay paths have API/SSE coverage. Falkor outage
visibility and real relay stop/stale/reconnect passed in the browser. A fresh
browser exercise of each provider protocol failure/turn-budget exhaustion remains
unverified. GPU execution on deployment hardware, representative hosted
reliability, performance after finalisation, supplier verification, payment,
multi-replica use, fresh Python installation and cloud cookie/SSE behavior are
also unverified. No GPU utilization, no-memory baseline, cost/token savings or
unsupported byte quota was invented. Legacy standalone booking helpers with
explicit confirmation remain referenced outside the hosted connected tool loop;
the hosted specialists have no booking/payment tool and website requests stay
`requested`.

## Supported claim

The implementation has demonstrated authenticated seven-specialist hosted travel
planning with current scoped memory, saved drafts, PDF export, synthetic booking
requests and real read-only memory inspection, with stronger viewer/developer
boundaries and regression coverage for stale proofs, conflicts, isolation and
forgetting. An approved repaired volume now supports a fresh local demonstration
and a controlled database restart plus relay reconnect. The original persistence
failure is preserved; this is not proof of an engine durability fix. It cannot claim
production/cloud readiness, live supplier inventory, confirmed bookings,
representative agent reliability, unlimited scale or measured memory savings.
