# TinyFish × Iron Web 2: external-memory lifecycle

Implemented on `codex/tinyfish-memory-refresh`. This branch is not merged or
deployed. Existing local work was carried forward when the branch was created.

## What runs

Before the travel workflow starts its specialist agents, the catalog adapter
recalls destination evidence for opening hours, permits and accessibility. This
is separate from confirmed traveler preferences. Missing, expired or differing
source observations trigger a bounded background TinyFish Search/Fetch job.
Recall returns immediately with the usable evidence and pending/review status.

Completed jobs preserve exact quotations found in fetched page text, source
URLs, retrieval and expiry timestamps, prior version IDs and verification
status. SQL is the durable replayable ledger. The optional public-page NIM
reader proposes quotes; exact substring validation is enforced locally. If no
supported quotation is extracted, the topic remains missing.

Source-only observations are indexed in the owner's native FalkorDB vector
store, without creating any Traveller claim. Graph relationships connect them
to destination/topic entities, cited URLs and available previous source nodes.
Graph outages leave SQL history intact and indexing retries on recall. Native
vector ranking is optional; exact SQL evidence remains available during outages.

Every specialist gateway receives the same eligible external evidence snapshot.
Hosted agent prompts explicitly label quotations as untrusted data. Changed
high-impact evidence flags relevant owned trip workspaces for review and marks
saved plan versions stale; it does not automatically alter schedules or prices.

## What the system does not infer

- Freshness is not verification, credibility or trip-date applicability.
- Different quotations may be complementary: a conflict candidate requires
  review and is excluded from current external evidence.
- No web observation can overwrite a user preference, confirm a protected rule,
  fabricate supplier availability or execute a reservation.
- The external-memory ledger is owner-scoped; public research is reused across
  that owner's agents, not silently across different users.
- Retention/decay scores remain separate from external-fact expiry.

## Controls and endpoints

- Existing `TINYFISH_API_KEY` enables Search/Fetch; private identity, budgets,
  trip dates and preferences never enter research queries.
- Existing research executor limits work to two workers and eight active jobs.
- Failed, empty or disputed recent results have a five-minute automatic retry
  cooldown. Running jobs are reused. Startup marks interrupted jobs failed
  rather than replaying chargeable work.
- `POST /api/travel/destinations/{id}/memory/recall` accepts `topics` and
  `auto_refresh` (default true). It is authenticated and returns evidence,
  missing/stale/conflict topics and any refresh job ID.
- `GET /api/travel/destinations/{id}/memory` returns up to 100 owned versions.
- Existing destination-research endpoints still support explicit research.
- Authenticated/published dashboard snapshots include a `tinyfish` section;
  `/tinyfish` in the dashboard presents stored counts, citations, version
  history, job metrics and lifecycle events. Rendering never starts research.

## Evidence and reproduction

- `python scripts/benchmark_tinyfish_memory.py`: controlled transport ablation
  measuring repeat-call reduction and seeded lifecycle guard cases.
- `python scripts/check_tinyfish_memory_live.py`: one real, generic public
  Search/Fetch connectivity check, with extraction disabled.
- `python scripts/update_tinyfish_guides.py`: embeds both records into the
  offline system guides, labeling controlled vs live measurements separately.
- `python -m pytest tests/test_external_memory.py tests/test_agent_presentation.py -q`
- In `dashboard/frontend`: `npm test`, `npm run build`, and
  `npx playwright test tests/tinyfish-memory.spec.js`.

Measured artifacts and scope are in `report/tinyfish_memory/`. No financial,
live-latency or recommendation-quality improvement is claimed from mock runs.
