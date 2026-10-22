# Voyara chatbot improvements â€” 19 October 2026

Status: local browser acceptance passed. No paid research, booking or payment was started. This change is local and uncommitted; GitHub, Vercel and Render were not updated in this round.

## Implemented

- Persistent owner-scoped conversation state; one follow-up question at a time; short answers remain meaningful after reload.
- Direct corrections, origin/destination separation, adult/child counts, relative dates in Asia/Kolkata, return-date edits, duration changes, total/per-person budget arithmetic and budget-basis preservation.
- Read-only summaries, sourced destination descriptions and comparisons, catalog previews, capabilities, privacy and research status. A budget is distinguished from a saved estimate; availability is not invented.
- Atomic validation and ambiguity repair; required conditions remain visible. Clearing mandatory conditions requires an explicit confirmation bound to the unchanged condition list.
- Explicit preference removal stays unconfirmed until review, then retracts the corresponding trip-scoped memory fact. Other travelers and saved profile data are not deleted.
- Responsive status messages while research holds a memory lock; no duplicate paid runs on status questions. Named failed specialists, saved-draft recovery, context-specific reply buttons and visible background progress.
- Browser reload restores the conversation. Duplicate final research replies are suppressed. Other-city hotel previews cannot be selected for the current destination. Network timeout restores controls and preserves input.

## Validation

- Initial broader conversation/application/planning-job regression suite: 79 passed.
- Final focused parser/chat/planning-job regression run: 68 passed.
- Five multi-turn integration scenarios rerun after the final state-preservation and stale-confirmation changes: all passed.
- Frontend production build, Ruff checks and git whitespace checks passed.
- Real local browser: passed; 11 actual chat turns, six acceptance checks, zero uncaught page errors. Slowest measured send-to-enabled-input round trip: 0.234 seconds. Screenshots: conversation.png and simulated_failure_recovery.png.

The provider-failure UI case is explicitly simulated; it does not demonstrate a successful TinyFish research run. The earlier hosted restaurant-research timeout remains a separate problem. This chatbot is a bounded local travel dialogue manager, not an unrestricted LLM.

Design references and behavior details: docs/voyara_conversation_design.md. Browser details: browser.json. Reproduce with scripts/check_chat_dialogue_local.py against the local TinyFish-mode app on port 8094.

Final screenshot review also corrected an empty-interest acknowledgment and ensured automatic scrolling reaches the latest reply. The focused context test and full browser acceptance passed again afterward.
