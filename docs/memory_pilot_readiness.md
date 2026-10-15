# Company pilot and reusable core

The core now has a reusable authenticated API, a Python client, application-independent typed claims, retained versions, explicit change/retraction rules, private user spaces, bounded task coordination and cold backup/fresh-target restoration. The travel interpreter is an optional adapter, not the core's data model. A second application can send its own subject/predicate/value/scope claims without changing the graph engine.

This is a supported starting point for a pilot discussion. It is not a validated commercial product, pricing result or evidence that a company will buy it. The real partner/use case remains unspecified; the random profile data supplied earlier is not evidence of an actual employer or pilot authorization.

## Pilot acceptance worksheet

The partner supplies the concrete problem, authorized data, users/agents, expected volume, latency needs, deployment/access boundary, retention/deletion requirements, support owner and operating budget. Agree the success cases and failure costs before importing real data. Keep the first pilot to one workflow that benefits from accepted changes and handoffs.

Demonstrate that a second application uses the same API unchanged; authenticated users cannot reach another user's data; agent proposals cannot impersonate user approval; unsupported requirements cause review; accepted changes invalidate only related work; completed work is retained; and operators can export a private snapshot, restore it into a fresh target, and delete a source event without resurrecting it on retry.

Measure the actual workload rather than extrapolating from the 24-event local burst. Test growth, contention, queue delay, memory cost and the effect of whole-graph publication copies. Decide worker count, backlog limits, monitoring/alerting and backup cadence from those results. Check database access and filesystem permissions separately from the API's token boundary. Within a company tenant, finer per-user/per-agent restrictions may be needed beyond the demonstrated one-private-space-per-user model.

## Operating instructions

Use the [service guide](shared_memory_service.md) for local setup, credential generation, event/receipt states, history, notifications, review and deletion. Stop the service before cold backup; restore only into a fresh directory and graph names. Protect snapshots, which contain private data and credentials. Invalidate active execution leases on restoration, and manage old backup copies under the partner's retention/deletion policy.

The native binary restore experiment failed on the tested FalkorDB release. The shipped path uses explicit validated graph records and closed vector files, and its fresh-target restore check passes. This is a reason to test the selected server release and actual operating procedure rather than treating database documentation as a completed recovery proof.

For external bookings, payments or physical maintenance actions, agree conditional tool execution, retry receipts and reconciliation. A memory task lease alone does not prove exactly-once behavior outside the memory service. The current demonstration creates planning records and makes no such external actions.

## Release gate

Pilot readiness requires the partner's agreed acceptance results, a representative load test, access review, recovery drill, operator handoff and support budget. Broad enterprise packaging, pricing, billing and sales claims follow evidence from the pilot. They are not completed by a working graph visualization or a research outline.
