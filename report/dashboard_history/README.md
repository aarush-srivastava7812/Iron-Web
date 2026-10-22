# Dashboard history-first mode

The dashboard opens a saved project replay by default. `Follow live` explicitly
replaces it with the authenticated account snapshot and opens its SSE stream.
`Saved history` closes that stream and restores the replay. Source mode is kept
in the page URL, including through navigation and reload. Live failures never
substitute replay values. Late callbacks from closed streams cannot overwrite
history mode.

## Replay data

`dashboard/frontend/public/history-snapshot.json` is deliberately public sample
data, not an export of a user's private memory or account. It is built from the
existing seeded 17 October `events.json` sequence and recorded 22 October
TinyFish test receipts. It contains 40 example events, 20 memory records,
3 reconstructed agent contexts and 11 example saved reads. Nine core roles are
listed; only the three observed in the source example have recorded reads.

The graph and context cards are reconstructed example views. Displayed context
sizes are computed UTF-8 bytes of these example strings, not hosted-model token
usage. Uncaptured elapsed times, hardware allocation, numeric vectors, provider
tokens and billing remain unavailable. Controlled TinyFish counts are explicitly
labelled mock-transport challenge results, distinct from live account totals.
One separately recorded public connectivity check retains its original scope.

The default view is labelled `Saved project replay · not live` on every page.
Replay History and numeric-vector inspection use only bundled data. No live
dashboard API call, cookie probe or SSE connection starts until live is selected.
The authentic account run history is still available on the History page while
in live mode; it is never mixed with the public replay.

Rebuild data: `node scripts/build_dashboard_history.mjs`.

## Validation

- 15 JavaScript unit tests passed, including default mode, URL persistence and
  rejection of cross-mode payloads.
- 4 history-mode browser tests passed: every page without live requests, full
  source replacement, stream cleanup and late callbacks, failed live auth,
  explicit return to history, and controls/layout at 1440, 1024, 390 and 320 px.
- 4 TinyFish/presentation browser regressions passed. The live-only fixture
  checks now explicitly select `?mode=live`.
- 3 real authenticated live-feed browser checks passed, including graph and
  inspector interactions, mobile/reduced-motion behavior, and stalled-SSE
  recovery. They submit no paid research.
- Dashboard production build passed. The live site smoke script now explicitly
  opts into live mode when testing actual dashboard data.

All work remains on the unmerged feature branch. Backend account data and
provider execution are unchanged by this dashboard replay feature.
