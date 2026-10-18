# Main integration and repository cleanup — October 18, 2026

All existing local and origin branch tips are intended to be contained in the resulting main merge. Branch comparison found four unmerged commits on `codex/deploy-voyara`; every other branch tip was already an ancestor of main. The deployment branch merged without conflicts. Existing uncommitted dashboard, documentation and demonstration work was retained. No branches were deleted and no published history was rewritten.

## Cleanup

Removed 344 obsolete/generated or duplicate files from the working tree, totaling 269,212,383 bytes. This includes 26 byte-identical copies and 15 previously tracked files. The remainder was untracked local render/recording material that had never been published. Recoverable copies, SHA-256 checksums and the working-tree patch are preserved locally under ignored `.scratch/merge-cleanup-20261018/`.

- Keep one final video: `youtube-upload/ironweb-voyara-2m58-final.mp4`, exactly 178 seconds, with the retained voice and captions transcribed from its actual audio.
- Keep matching SRT/ASS captions, the actual voiceover transcript, the final verification record and upload text.
- Keep screenshots in `docs/screenshots/demo-2026-10-18/`; remove identical copies from the blog and recording directories.
- Consolidate identical historical failure screenshots and the raw duplicate of the shared-memory walkthrough. Historical result documents remain; screenshot references use canonical copies. [Asset aliases and hashes](asset-aliases.json) record the removed duplicate paths.
- Remove superseded video exports, earlier summary captions/transcripts, one-off rendering helpers, preview frames, raw browser recordings and segment/audio intermediates.
- Keep the local distribution ZIP ignored, together with existing private runtimes, databases, dependencies and caches.

Referenced application interfaces, legacy test fixtures, research adapters, dated results, source snapshots and mirrored website catalog assets were retained. Equal bytes alone do not make a fixture, versioned experiment input or separately served catalog redundant.

README, blog publishing instructions and demonstration links now use the final video, voice-derived captions and canonical screenshots. A relative Markdown-link scan found no links to removed assets.

## Validation

- Backend, agents and website: **458 passed, 2 skipped, 6 deselected**. Offline execution used a separate disposable FalkorDB instance on local port 6391, rather than the running application's database.
- Dashboard unit tests: **13 passed**.
- Actual-feed browser regressions: **3 passed**. The first run exposed a five-second initial-load timeout in the stalled-stream test. Its bootstrap allowance is now 30 seconds; the 18-second stale/reconnect assertions are unchanged. The complete browser suite then passed.
- Dashboard production build: passed.
- Website production build: passed.
- Production dependency audits: zero reported vulnerabilities for either frontend.
- Current tracked/nonignored tree credential-pattern scan: zero findings. This is a pattern-based check, not a guarantee against every credential format.
- Reachable history scan: two old credential-bearing blobs, both already present on `origin/main` before this task. Current copies are clean. The existing owner-side credential revocation/rotation and separately approved history-cleanup action remain outstanding; this merge does not resolve them or print their values.
- Merge conflict and whitespace checks: passed.

The deployment code/configuration and isolated judge authentication tests are integrated. No cloud deployment, provider call, application-data migration or live-database cleanup was performed by this merge task. The recorded public endpoint availability was not reverified; the deployment guide retains its original verification scope and ephemeral-storage limits.
