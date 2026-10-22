# TinyFish production verification — 19 October 2026

Initial release: d43e2ac199b983b7ec8790841a011594c70b8b15.
Vercel: dpl_DuDPgoErGLvz2NQFfTpYr1QLxxgT, production READY.
Render: dep-dbb4nqbl550s73cc6kc0, live on existing free plan.

The first live Agra attempt failed after 517 seconds. Chat intake passed in 0.59 and 0.25 seconds; owner-scoped HTTP 202 jobs and polling worked beyond the previous proxy timeout. Destination and food research completed, while the stay and attraction automations remained in the provider queue until timeout. No complete plan was saved. See first_attempt_failed.json and provider_progress.json. This failure prompted bounded provider submission and a direct public encyclopedia starting page for destination overview research.

A separate judge saved and read confirmed trip memory during research (3.05 seconds). A manual Jaipur itinerary, persisted version, browser reload and Travel Book PDF all passed (23.7 seconds). These manual checks do not establish TinyFish research success. See concurrent_memory.json and manual_result.json. Render events showed no new OOM restart; sampled peak memory at that point was 413.88 MiB under the 512 MiB limit. Sampling is not a stress-test guarantee.

The key is private on Render, excluded from GitHub and frontend builds. No paid hosting tier, disk, booking, payment or wallet top-up was created. Render free-tier filesystem is ephemeral; service replacement can discard saved trips and public research caches.

Corrective deployment and final live outcome will be recorded below.

## Final outcome: full TinyFish auto planning failed

Corrective commit: bc5addad03e872f5a78b601f3d37ea076dbbfb46, pushed to main and codex/azinhack-2026-tinyfish. Vercel production deployment dpl_3NEAxaqEpLTFUzJRvguyJWtrvqFd is READY. Render deployment dep-dbb4udk9v7es73a7ihg0 is live. Backend final health: HTTP 200.

Bounded submission fixed the queued stay/attraction timeout: destination, stay and attraction research each validated successfully. Restaurant research navigated several menus, could not finish within its 480-second limit and was cancelled. The run returned a visible failure after 510.5 seconds (500.08 seconds from job acceptance); no complete plan was saved. See live_browser.json and failure.png. The test did not reach the automated Travel Book/PDF checks because no complete research plan existed. Earlier manual Travel Book/PDF checks passed; they are explicitly recorded as manual.

Final Agra chat took 0.50 and 0.28 seconds. No uncaught browser errors were recorded. Sampled peak memory on the corrective deployment was 424.42 MiB. No new server-failure/OOM event appeared in the final event snapshot. The two deployments and GitHub push succeeded, but the four-specialist TinyFish planner is not yet reliably passing end to end. No further paid research retries were started after this failure.
