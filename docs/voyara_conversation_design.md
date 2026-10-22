# Voyara conversation behavior

This change improves the local dialogue manager used in TinyFish mode. It is a
bounded travel assistant, not an unrestricted language model. Draft intake makes
no hosted inference calls. Existing NVIDIA-mode interpretation remains available.

## Design basis

- [Google: Questions](https://developers.google.com/assistant/conversation-design/questions)
  recommends focused follow-up questions, support for the answers requested, and
  narrower repair prompts when an answer is ambiguous. Voyara accepts several
  details together but asks only for the next missing essential.
- [Google: Confirmations](https://developers.google.com/assistant/conversation-design/confirmations)
  describes acknowledging interpreted details so people can correct them. Voyara
  shows exactly which draft values changed and requires review before research.
- [Microsoft: Guidelines for Human-AI Interaction](https://www.microsoft.com/en-us/research/articles/guidelines-for-human-ai-interaction-eighteen-best-practices-for-human-centered-ai-design/)
  emphasizes supporting corrections and communicating limitations. Voyara accepts
  direct corrections, distinguishes budget from cost, and names failed research.

These are interaction-design references; no retired Google Assistant runtime or
new chatbot framework is introduced.

## Conversation policy

The application keeps owner-scoped working state alongside the existing draft:
the last question asked, contextual suggestions, unresolved per-person budget,
and a confirmation tied to the exact mandatory conditions proposed for removal.
It does not copy one conversation's state into another or automatically import
saved preferences. The traveler can explicitly ask to use saved preferences.

1. Recognize the intent before extracting values. Summaries, destination
   information, catalog previews, help, privacy and research-status questions are
   read-only. An ordinary mention of another city in an information request does
   not change the trip.
2. Interpret explicit values and context-bound short answers. For example,
   `two` means party size only after that question was asked. Adults and children
   are counted together. `three nights` means four calendar days. Relative dates
   use Asia/Kolkata; interpreted dates and unstated years are shown explicitly.
3. Validate a proposed edit before changing the draft. Invalid dates, conflicting
   dates/day counts, ambiguous choices, unsupported currencies and hypothetical
   changes get a clarification. Existing facts remain intact.
4. Acknowledge changes and ask one next question. The essentials are destination,
   departure, return/duration, traveler count and total INR budget. Reply buttons
   follow that question. Repeated unsupported replies offer the manual editor.
5. Keep important distinctions visible. A budget is a spending limit; calculated
   costs require a saved plan. Catalog options are examples, not live availability.
   Destination information is a guide, not a verified quote. Agra's short factual
   overview links to the [district's official tourism guide](https://agra.nic.in/tourist-places/).
6. Preserve user control. Saying `yes`, asking for status, or chatting about a
   destination cannot trigger paid research, booking, payment or confirmed-memory
   writes. The review/confirmation controls start research. Removing mandatory
   conditions requires a separate explicit confirmation that becomes stale if
   those conditions change in another tab.

Per-person amounts are shown with their arithmetic, such as INR 15,000 × 2 = INR
30,000 total. Without a party count, the amount stays provisional and the bot asks
for that count. The basis survives informational detours and scales when party
size changes; an explicit new group-total amount replaces that basis.

Explicit removal of a trip dietary preference remains an unconfirmed draft edit.
The corresponding scoped memory retraction happens only on trip confirmation.
Saved profile data and other travelers' memories are not deleted by that edit.

## Research and recovery

Owner-scoped job metadata supplies queued, running, successful and failed states.
Chat status checks do not wait for a long research lock or start duplicate jobs.
Failed specialists are named, the saved draft remains available, and retry costs
are explained. The UI shows elapsed time without inventing a completion percentage,
allows minimizing the panel, refreshes persisted conversation history when reopened,
and avoids adding the same final reply twice.

Network timeouts restore the input controls and retain unsent text. Read-only
hotel previews for a different destination cannot be chosen for the current trip.
Mandatory requirements remain visible and block plans the system cannot verify.

This conversation change does not establish that arbitrary TinyFish web research
will complete. The production restaurant timeout reported before this change is
a separate provider/research problem; no paid research was retried for this work.

## Verification

- `tests/test_conversation_intake.py`: contextual values, relative dates, money,
  corrections, information intents and ambiguity, with an explicit test date.
- `tests/test_chat_dialogue.py`: real authenticated multi-turn HTTP conversations,
  private state, saved memory boundaries, corrections and research-lock recovery.
- Existing chat, memory, planning-job and application integration regressions.
- `scripts/check_chat_dialogue_local.py`: real local browser conversation,
  page reload mid-conversation, contextual buttons, read-only previews, corrections,
  a clearly labeled simulated research-failure UI case and network-timeout recovery.

The browser test creates an isolated local account, never confirms a trip, never
starts paid research, and records no credentials or browser storage. Evidence is
saved locally under `report/chat_dialogue_20261019/`.
