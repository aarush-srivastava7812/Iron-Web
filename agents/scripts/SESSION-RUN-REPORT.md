# Full Website Run — 10 Sessions (with NVIDIA NIM LLM enabled)

Date: 16 Oct 2026, ~00:30 IST
Services: travel backend :8000 (live catalog) · agents :8100 · FalkorDB (compose) · NIM `openai/gpt-oss-20b`
Script: `agents/scripts/run_sessions.py` · raw data: `agents/scripts/session_results.json`

| # | Session | User | Page | Status | Agents run | Clarify? | Itinerary | Budget | Mem writes | Validation issues | Latency (ms) |
|---|---------|------|------|--------|-----------|----------|-----------|--------|------------|-------------------|--------------|
| 1 | s1 | Aarav | home | needs_clarification | trip consultant | yes | - | - | 0 | 0 | 10,565 |
| 2 | s2 | Aarav | explore | ok | explore, trip consultant | no | - | - | 2 | 0 | 4,861 |
| 3 | s3 | Diya | stays | ok | budget booking, stay, trip consultant | no | - | ₹5,973 (estimate) | 2 | 2 (over-budget warnings) | 5,845 |
| 4 | s4 | Diya | food_guide | ok | food guide, trip consultant | no | - | - | 2 | 0 | 23,572 |
| 5 | s5 | Kabir | tour_guide | ok | tour guide, trip consultant | no | - | - | 1 | 0 | 9,298 |
| 6 | s6 | Kabir | plan | ok | all 7 (full pipeline) | no | 4 days | ₹14,905 (estimate) | 2 | 1 | 11,936 |
| 7 | s7 | Meera | plan | ok | all 7 (full pipeline) | no | 3 days | ₹12,540 (estimate) | 1 | 1 | 11,581 |
| 8 | s8 | Meera | support | ok | travel support, trip consultant | no | - | - | 1 | 0 | 11,327 |
| 9 | s9 | Rohan | support | ok | travel support, trip consultant | no | - | - | 1 | 0 | 4,691 |
| 10 | s10 | Sana | explore | ok | explore, trip consultant | no | - | - | 1 | 0 | 5,176 |
| M | s1+2 | Aarav | memory | ok | memory gateway (introspection) | - | - | - | - | 0 | 138 |

## Result summary

- **10/10 sessions succeeded** (s1 correctly answered with a clarifying question — vague input).
- **0 agent failures**, 0 retries needed, no invented data (all budgets labeled `estimate`).
- **13 durable memories written** across sessions (preferences, dietary needs, trip decisions) — all via the gateway's duplicate-safe controlled writes.
- **Returning-user memory works**: Aarav's s1/s2 sessions produced 3 retrievable memories (checked in row M, 138 ms).
- **Page→agent mapping behaved exactly per architecture**: food page ran only food guide; plan page ran all 7 with parallel research; support ran only support.
- **LLM engaged**: Trip Consultant used NIM for structured extraction (e.g. "me and my wife" → party=2, "around 25000" → budget 25,000, "sunset views" → interests), with deterministic fallback always available.
- Average latency ≈ 9.9 s (LLM-bound); s4 was a slow NIM call (23.6 s) but completed. Non-LLM memory introspection: 138 ms.

## Notes / fixes made during this run

1. `meta/llama-3.3-70b-instruct` (and all meta llama chat models) reached end-of-life on NVIDIA NIM (HTTP 410). Default switched to **`openai/gpt-oss-20b`** (verified 200 OK); override via `NIM_MODEL` in `agents/.env`.
2. gpt-oss is a reasoning model — small `max_tokens` budgets get consumed by reasoning and return empty `content`. `NimClient.chat()` now retries once with a 3× token cap; `NIM_TIMEOUT_S` default raised to 45 s.
3. All 39 agent tests re-passed with the LLM enabled.
