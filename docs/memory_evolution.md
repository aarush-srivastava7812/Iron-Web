# Memory evolution and graph recall

The existing architecture remains FalkorDB for the graph and Qdrant for vector search. The new layer adds individually changeable claims, source messages, scopes, change history, and dependencies. Existing text memories keep their existing behavior; they are not silently converted or marked protected.

## What now works

- Ordinary claim scores range from zero to 0.99 and weaken with age. They use graded freshness, source quality, corroboration and agreement rules. Each score includes its contributing inputs and fired rules.
- Explicit user-confirmed instructions and rules are protected at 1 while applicable. Time alone does not weaken them. An accepted direct correction or replacement can transfer protection, leaving the former claim stored with its previous score and reason. A declared expiration still ends applicability.
- A conflicting assertion creates a visible dispute. It does not automatically replace an accepted claim. Disputed memories are not a basis for completing work.
- Confirmations affect only the specified value, subject and scope. Repetition by the same author is not independent corroboration; agent echoes do not refresh or strengthen an accepted user fact.
- Current retrieval replaces an outdated typed paragraph with current claim evidence. Original source text remains available through `get`, and explicit history queries retain earlier assertions. Corrected beliefs are labelled as earlier assertions rather than established past truth.
- Field-aware recall distinguishes supported, missing, disputed, unconfirmed and unresolved questions. A phone-number question is not answered with an unrelated profile note.
- Accepted identities and explicit references support short multi-step evidence paths. The core does not guess that similar project or organization names are the same.
- Work records identify the exact claim versions used. Changes or disputes flag only dependent work, including downstream prerequisites. Completed work retains its completion record even when a later change requires review.

The fuzzy parameters are transparent defaults, not calibrated truth probabilities. The default ordinary half-life is 90 days; each claim can specify another value. A score does not grant access, prove a fact, or determine who owns work.

## Supplying memories

The application supplies the meaning it has identified in a message. The core checks and stores that interpretation. Plain messages sent with source information are saved as episodes; the core does not invent semantic facts from those messages. Automatic free-text extraction into the new claim contract is not added by this change.

```python
from memory.engine import MemoryEngine

engine = MemoryEngine()
old_id = engine.add(
    "The user approved a maximum budget of 1000.",
    memory_id="budget-original",
    claims=[{"subject": "Traveller", "predicate": "budget", "value": 1000,
             "kind": "rule", "scope": {"trip_id": "A"}}],
    source_info={"origin": "user", "actor_id": "user-1", "user_confirmed": True},
)

old_claim = engine.get(old_id).metadata["memory_claim_ids"][0]
engine.record_work("plan-v1", [old_claim], agent_id="planner")

engine.add(
    "The user lowered the approved budget to 600.",
    memory_id="budget-replacement",
    claims=[{"subject": "Traveller", "predicate": "budget", "value": 600,
             "kind": "rule", "scope": {"trip_id": "A"}, "action": "supersede",
             "reason": "Explicit user budget change"}],
    source_info={"origin": "user", "actor_id": "user-1", "user_confirmed": True},
)

answer = engine.recall("What is the budget?", "Traveller", scope={"trip_id": "A"})
handoff = engine.handoff(["plan-v1"])
# answer: supported 600; handoff: old plan requires review, with both versions.
```

`source_info` is supplied by the trusted application. Its confirmation flag describes verified user intent; it is not authentication. The local HTTP service retains its existing access boundary. Tenant authentication and routing remain separate work. The agent tool adapter binds agent provenance and refuses attempts to impersonate user confirmation or authorize deletion.

An agent can send a proposed claim through `MemoryToolAdapter(engine, agent_id="planner")`. Such a claim remains attributed to that agent. The trusted application records confirmed user changes directly; an agent cannot promote its own suggestion by labelling itself a user or a verified tool.

## Claim and change rules

A claim declares its subject, predicate and value. `scope` contains applicable qualifiers, such as the trip, document type or condition. Single-valued fields can conflict; declare `cardinality="multiple"` for independent skills/interests/items. An episode is always distinct, rather than a competing value of a single fact.

Use `action="confirm"` for the same existing value. Use `supersede` for an accepted change over time and `correct` for an earlier assertion that was mistaken. Accepted changes require a confirmed user source and a reason. Optional `targets` identify exact claim versions; cross-field or cross-scope targets are rejected. Old nodes and original sources are retained.

Use `action="retract"`, `value=None`, a reason and the relevant field/scope to withdraw an applied statement without inventing a replacement. The retained withdrawal instruction links to the earlier claim through `RETRACTS`; the requested fact is missing until a new value is approved. Related work requires review. Retraction preserves history; explicit evidence deletion is a separate operation.

Only confirmed user instructions/rules can receive protection. Eligible claims are protected by default unless `protected=False` is supplied. When a protected claim is replaced through an accepted change, its eligible replacement inherits protection. Importance and query relevance remain separate from this protection.

Use `action="alias"` with a confirmed user source for an accepted graph-wide identity, with the canonical subject name as the value. Alias cycles and conflicting canonical identities are rejected. Scoped identities should use distinct subject identifiers; a local nickname must not silently merge global entities.

`references` identifies explicit subject links, such as an employer organization. `recall_path(question, subject, ["employer", "location"])` follows those links and includes each step's claim/source evidence plus accepted identity evidence. No reference link means no inferred next step.

Question `aliases` supply trusted field labels/paraphrases. Agent assertions cannot rewrite that vocabulary. Passing `predicate` explicitly is the reliable interface for an agent that already knows what field the user requested. Broad questions with no identifiable field return `unresolved_question`; this release does not claim general natural-language question understanding.

## Reading, time and history

`search` remains candidate discovery. Versioned results carry `memory_evidence`, state warnings and source paths; disputed results are labelled. Use `recall` for deciding whether a particular requested field can be answered. It requires an explicit subject and either a requested predicate or a recognized field label.

Scores are computed from stored evidence at read time. There is no need to rewrite every node hourly. Claim nodes retain their creation score, protection setting, half-life, original value and change history; `inspect_claim` returns the current score and explanation. The raw database creation score is not a constantly updated current score.

`query_time` selects the memory state/effective period to inspect. `known_at` limits the evidence and changes that were known by that time. `source_info.recorded_at` supports explicit historical replay; actual service receipt time is also retained. Unspecified effective dates remain unspecified, and retention of an earlier statement does not establish that statement was historically true.

Typed source events are immutable. A repeated event ID with the same content is idempotent; different content under the same event ID is rejected. Use a new event for a correction. Text deduplication skips versioned records, and automatic deletion of their retained evidence is refused. Explicit user-confirmed deletion is available through the engine and invalidates affected work.

## Application and agent interfaces

The existing `/api/add` endpoint accepts `claims` and `source_info`. The additional local JSON endpoints are:

| Endpoint | Purpose |
| --- | --- |
| `/api/recall` | Requested field, supporting evidence and answer status |
| `/api/recall-path` | A bounded explicit chain of field relationships |
| `/api/claim` | Current claim score, history and explanation |
| `/api/work` | Record exact memory versions used by work |
| `/api/complete-work` | Mark owned work completed after checking current evidence |
| `/api/handoff` | Used/current versions, completion state and review requirements |

The in-process tool adapter exposes the corresponding operations. It remains an in-process adapter, not a new MCP transport. HTTP clients must be trusted local application callers; this release does not implement tenant authorization by trusting a field in the request.

The above describes the original engine/dashboard interface. The additive [shared service](shared_memory_service.md) now provides authenticated `/v1` interfaces with private user spaces, durable receipts, ordered workers, unclear-change safeguards, history, notifications and fenced task ownership. The original local dashboard is not converted into an authenticated multi-user endpoint.

All updates use the existing graph staging/publication and vector compensation mechanism. This preserves caught-failure recovery; it does not add a crash-atomic transaction across the two databases. Reads/writes use the existing shared locks. Limits are explicit: 32 claims per event, 64 referenced subjects, bounded field/identity history, up to four steps in an evidence path, and bounded dependency invalidation. A limit failure is visible and does not silently publish a partially invalidated change.

## Inspect the implemented demo

The [final demo evidence](../report/lifecycle_implementation_20261014_final/README.md) contains actual stored graph data and real BGE embeddings. It shows an accepted protected change, an unresolved agent proposal, partial confirmation, a missing answer, an accepted identity, a two-step query, and a handoff with only affected work requiring review.

Run another isolated demo with a fresh output path:

```powershell
& '.\.venv\Scripts\python.exe' scripts/demo_memory_lifecycle.py --report report/lifecycle_demo_fresh
```

The script preserves its isolated named graph for inspection and records the name in `results.json`. Its data is an explicit demonstration fixture. It is not an automatic extraction benchmark or a production-readiness claim. The larger unseen-input evaluation and representative scaling/load studies remain later work.
