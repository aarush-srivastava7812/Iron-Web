# Agra chat fix — 19 October 2026

The screenshot showed the separate conversational intake panel waiting on NVIDIA, even though research agents had been switched to TinyFish. That panel still made two hosted interpretation/reply calls. Its request had no frontend deadline, and Agra was absent from the demo destination catalog.

## Changes

- TinyFish mode collects a conservative, unconfirmed trip draft locally. It does not send chat history, trip details, or memory to NVIDIA/TinyFish during intake. Research starts only after review and confirmation.
- The exact message `i want to go for a trip to agra can you plan it` recognizes Agra and asks for departure date/duration, traveler count, and total budget. Explicit ISO dates, day counts, party counts and INR amounts can be added in a follow-up.
- Invalid/ambiguous updates preserve the previous draft. Mandatory requirements remain visible and block unverified confirmation. Draft messages do not become confirmed memory automatically.
- TinyFish planning can retain a confirmed destination without a matching catalog ID. Agra does not acquire fabricated catalog listings or another city's itinerary. The trip editor preserves the external destination option.
- Chat loading text and footer no longer incorrectly claim NVIDIA use. A stalled chat request aborts after 20 seconds, retains its input and restores controls; it warns that the user should reopen the chat to check whether the message was saved before retrying.
- The existing NVIDIA-mode provider failure contract remains intact: failed extraction does not modify the draft.

## Verification

**51 targeted regression tests passed** across local chat intake, existing conversational/Travel Book behavior, TinyFish adapter and authenticated memory integration. Agra confirmation used simulated provider responses with real isolated graph/vector memory and declared test embedding fixtures; no real Agra research run was purchased for this fix.

Real local browser acceptance passed:

1. Exact screenshot message received HTTP 200 and a useful missing-details reply in **0.266 seconds**.
2. Loading indicator cleared and controls became available.
3. A follow-up with `2026-12-01 for three days, two adults, INR 30000 total` preserved Agra and calculated the return date as `2026-12-03`, awaiting confirmation.
4. A deliberately held request timed out and restored controls while preserving input.
5. No uncaught browser errors.

Frontend build, focused Ruff and whitespace checks passed. The local application was restarted at http://127.0.0.1:8094/ . Existing open tabs need one refresh to load the new JavaScript bundle. No GitHub push or deployment was performed.

Evidence: `browser.json`, `agra_reply.png`. Browser harness: `scripts/check_tinyfish_chat_local.py`.
