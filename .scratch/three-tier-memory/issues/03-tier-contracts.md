# Tier Boundaries, the Equal Cache Split and Persona Scope

Labels: wayfinder:task
Type: task
Mode: AFK
Status: resolved
Assignee: Codex
Parent: ../map.md
Blocked by: 01, 02

## Question

What does each tier contain, how is the first cache split into equal halves, and how do stable preferences, trip constraints, moods and agent characteristics remain distinct?

## Answer

Use three logical tiers, with tiers 1/2 derived from durable evidence and versioned application profiles. Do not reinterpret the first tier as a physical split of CPU hardware cache or GPU VRAM.

| Tier | Contents | Placement and ownership |
| --- | --- | --- |
| 1A: agent half | Assigned role, specialties, style, task responsibility and policy references | Hot process RAM; immutable versioned application profile bound to authenticated agent |
| 1B: traveller/trip half | Stated enduring preferences plus the current trip's key requirements/goals, keeping their scopes visible | Hot process RAM; evidence-backed summary keyed by private user space, subject and exact trip/session scope |
| 2: task/mood cards | Richer task-specific constraints, preferences, conditional procedures, explicit temporary mood and cited examples | Durable structured definitions/Markdown renderings; host active catalog; bounded GPU matching representations |
| 3: durable memory | Current/history claims, vector discovery, graph relations and dependencies, source episodes, receipt journal and recoverable card/profile artifacts | Existing FalkorDB/Qdrant/SQLite plus service-owned derived artifacts; no backend replacement |

The equal split means two **equal maximum serialized token budgets**, initially **1024 tokens each**. Count with the target generator's tokenizer. The initial tier-1 maximum is 2048 tokens per assembled context. Agent profiles can share physical RAM across requests; neither half must be padded. Do not silently borrow the traveller half for agent prose or vice versa. Move optional detail to cards; if mandatory requirements cannot fit, return a capacity error or narrow the task instead of truncating them. Metadata bytes are bounded/accounted separately.

Distinguish four concepts, recorded in the [glossary](../../../GLOSSARY.md): agent profile, traveller profile, trip brief and mood state. A broad inferred psychological persona is not needed. Agent role/style must not grant tool privileges; permissions remain enforced by the service/tools.

Read trip fields under exact `trip_id` scope. Read enduring profile fields separately under the application's explicit profile scope. The existing lifecycle `fetch_field` hashes the exact scope; it provides no automatic scope inheritance. The new assembler must implement a visible, allowlisted fallback only for optional preferences. A missing trip budget/date is not filled by another trip's value. A disputed trip field remains disputed; profile fallback must not hide it.

Current explicit trip requirements govern task feasibility. Stable preferences guide choices where compatible. An explicitly stated mood guides pace/tone and optional selections; it never overrides a confirmed cap or other hard requirement. Use explicit session/trip scope and stated expiration where available; otherwise use a proposed **30-minute idle expiry** for a mood derivative and do not refresh it merely because it is read. This is a design default, not an inference that the person's real mood changed.

Compile a card as a structured object first, then render a `persona.md`-style view. Minimum fields: `card_id`, `card_version`, authenticated-space binding, subject, exact scope, `task_type`, optional explicit mood tag, source event IDs, exact supporting claim IDs, profile/template versions, generated time, expiry/validity boundaries, answer statuses, canonical content hash and token count. Invariants: missing/disputed requirements remain visible; each factual sentence maps to eligible evidence; template guidance is labelled separately from user claims; no source text can modify agent permissions.

Persist recoverable card definitions and derived snapshots under service-owned private space, with a compiler-versioned manifest. They are **derived artifacts**, never new independent evidence. Warm rebuilding must not submit every card as a new source event or graph claim; that would fabricate corroboration and amplify graph-copy writes. An LLM rewrite is optional and cannot add facts or silently remove mandatory fields.
