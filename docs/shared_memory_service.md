# Shared memory: application and agent connection

The shared service is now implemented. It keeps the existing FalkorDB graph and Qdrant vectors, adding a small SQLite journal for durable event receipts and notifications. That journal is a processing queue; accepted memories and work dependencies remain in the graph. The existing local dashboard remains separate.

## What an application can rely on

Sending a message returns a saved receipt quickly. Its state changes from queued to interpreting to ready, or to failed. Saved does not mean interpreted. Clients can read receipt status and original conversation history while processing continues. Scoped recall, context and evidence-linked tasks stop on relevant pending, failed or unclear events. Another explicitly scoped trip can proceed independently. Global/unscoped changes and discovery search retain the conservative per-user gate.

Two workers can process different users independently. Messages for one user are processed in receipt order. Authenticated credentials select the user space and actor; request bodies cannot choose another user, pretend to be the user, or take another agent's identity. Each space has its own named graph, vector directory and request gate. One local service process owns a runtime; opening a second owner is rejected.

An unrecognized confirmed requirement is stored as an episode and marked `needs_review`. That state blocks use of old requirements; an inability to interpret a requested change never means the old rule was reapproved. Clarify it through a new interpreted event and explicitly withdraw the unclear requirement, or withdraw it if it was not meant as a requirement. Ordinary unconfirmed conversation events can be ready without producing semantic claims. Receipt fields report claim kinds and the semantic claim count.

Work records identify exact memory versions. Agents must acquire ownership before completing work. A competing agent cannot acquire an active task, and an old completion proof stops working after ownership expires and another agent acquires it. Completed work is retained rather than executed again. Handoff readers receive current requirements and review reasons without another agent's execution credential.

Notifications stay available across restarts until each agent acknowledges them. A failed receipt remains visible and blocks work until retried or explicitly withdrawn. An authenticated user can request deletion of an event's retained evidence; processing removes its graph/vector memory and scrubs its original text from the journal. Replaying that event ID does not recreate deleted evidence. Existing private backup copies need a separate operator retention/deletion policy.

## Local setup

Use the existing workspace environment and running FalkorDB service. Setup creates credentials for two separate users and a planner/reviewer for each. Credentials are private files, ignored by Git, and are never printed by the script.

```powershell
& '.\.venv\Scripts\python.exe' scripts/setup_shared_service.py --runtime data/shared_service
& '.\.venv\Scripts\python.exe' shared_server.py --config data/shared_service/service.json --port 3351
```

Open `http://127.0.0.1:3351/`. Paste the appropriate credential from your local `data/shared_service/credentials.json` into the connection field. The example UI sends real events and reads actual shared memory. The local server binds to localhost. Public deployment needs a trusted HTTPS gateway and private database/filesystem access; this change does not provision that deployment.

The default interpreter is a conservative travel grammar. Version 2 supports the evaluated multi-clause travel intake in addition to simple budget, seat and destination statements. Every clause must be recognized: it preserves an unrecognized, conditional or conflicting message as an episode rather than silently accepting only the easy parts. The full source message remains available. This is a limited application adapter, not general language understanding. Your application can send structured `claims` directly for language outside this adapter.

An optional hosted interpreter accepts an OpenAI-compatible client. Configure `hosted_interpreter` in the private service configuration with `base_url`, `model`, and `api_key_env` (default `NVIDIA_API_KEY`). The server reads the credential from the environment. Missing credentials cause setup to fail visibly, rather than silently claiming extraction. No hosted provider was configured or tested in this implementation run.

## The teammate's connection contract

Every request uses `Authorization: Bearer <private credential>` and JSON. Tenant and actor identifiers come from the credential. The application UI uses its user's credential for confirmed changes; each agent has a separate agent credential. An agent's suggestions remain attributed proposals.

| Endpoint | What it does |
| --- | --- |
| `/v1/events` | Save a source event; returns a receipt, not semantic completion |
| `/v1/events/status` | Read a receipt using `eid` |
| `/v1/events/retry` | Retry a failed receipt |
| `/v1/events/withdraw` | User declines a queued/failed event, retaining its source |
| `/v1/identity` | Read the authenticated actor/role and private user space |
| `/v1/events/forget` | User requests retained evidence deletion and text redaction |
| `/v1/history` | Original messages and states; accepts `limit`, `after`, `session_id` |
| `/v1/recall`, `/v1/recall-path` | Field answer status, supporting evidence and paths |
| `/v1/search` | Reconciled discovery candidates, not a guaranteed final answer |
| `/v1/work` | Register work and the exact claim versions it uses |
| `/v1/work/list` | View saved work without execution credentials |
| `/v1/work/claim` | Acquire a task with an execution lease |
| `/v1/work/complete` | Complete owned work using its current `lease_token` |
| `/v1/handoff` | Used/current evidence, completed work and review requirements |
| `/v1/notifications`, `/v1/notifications/ack` | Per-agent notification delivery and acknowledgment |

Use `memory.shared.client.SharedMemoryClient` from a Python application. It exposes the same API and preserves pending/failed status as errors. [The two-agent integration example](../examples/shared_memory_integration.py) shows the complete confirmed requirement → accepted change → handoff → revised work flow. It is independent of the teammate's UI/framework.

Status 409 means pending memory or a task/state conflict; the client must check receipts/handoff instead of asserting completion. Status 401/403 means missing or insufficient credentials. Only `ready` establishes that the event's interpretation was committed.

## Recovery and private snapshots

Killed-process checks cover acknowledgment before interpretation, termination after vector insertion, and termination after graph publication. Restart replays the same immutable event and repairs only service-owned partial writes. These checks establish application-process recovery on the tested server, not universal power-loss durability or exactly-once external bookings.

Stop the service before taking a cold snapshot. Its runtime lock prevents a backup process from copying active embedded vector files. Snapshot data includes original messages, private configuration/credentials, and graph records, and must be kept private.

```powershell
& '.\.venv\Scripts\python.exe' scripts/shared_memory_snapshot.py backup --config data/shared_service/service.json --destination data/shared_backup_1
& '.\.venv\Scripts\python.exe' scripts/shared_memory_snapshot.py restore --snapshot data/shared_backup_1 --runtime data/shared_restored_1
```

Restore requires a fresh directory and fresh graph names. It preserves original memories and completed work; active execution proofs are cleared. Existing targets are refused. The implementation uses validated graph records, not native Redis RESTORE: a native restore experiment failed on the tested FalkorDB release and that path was removed.

## Practical limits

The current engine serializes cooperating operations within one graph and copies a graph for safe publication. That limits throughput as graphs grow. This service measures concurrent submission and independent user progress; it does not claim unlimited simultaneous writes. The additive [three-tier context layer](three_tier_memory_usage.md), implemented on 2026-10-15, supplies scoped profiles/cards, a bounded cache and optional CUDA matching while preserving these gates. It does not remove graph-copy ingestion costs.

The core handles memory/state checks. A real booking/payment system must separately implement conditional external actions and recovery; a task lease alone cannot guarantee that an interrupted external action never happened. Real customer workloads, hosted-language interpretation, public deployment and the teammate's actual app integration remain separate acceptance work.
