# Memory Changes, Evidence and Authority

Labels: wayfinder:grilling
Type: grilling
Status: resolved
Assignee: Codex
Parent: [Shared Agent Memory: Hackathon, Research and Reuse](../map.md)
Blocked by: 07

## Question

What precisely makes a candidate memory accepted, current, disputed, superseded or retracted, and who has authority to change it?

Define the minimum episode/fact/procedure distinctions, field versus complete-record updates, scope and event-time uncertainty, and direct user correction versus agent guess. Preserve old nodes without confusing former beliefs with historically true facts. Decide which constraints and dependent decisions must be checked before an agent continues work.

The first paused idea is now an explicit **planned addition to the existing KG**, after the vector comparison and placement decision. Plan a fuzzy value from 0 to 1, ordinary memories capped at 0.99, and explicit protection at 1. Protection prevents automatic decay; an accepted direct contradiction/correction or replacement can end the old memory's current acceptance and transfer protection to the new one. Preserve both nodes, their sources, prior scores and change reasons. A new conflicting statement alone does not silently win.

Represent `CONTRADICTS` and accepted `SUPERSEDES` as distinct explainable links. Separate direct contradiction, later change, different scope, partial confirmation and unresolved identity. Determine authority and acceptance before changing eligibility; a high fuzzy value never decides access, task ownership, or which assertion is authoritative.

Set the smallest usable decay/reinforcement/conflict rules, protections, effective-time behavior and rule explanations with the user. The earlier prototype's hand-set weights and half-lives remain experimental. This planning update authorizes inclusion in the route, not code changes or a settled policy for every case.

## Comments

### Existing evidence

The previous fixture shows that a repeated discipline does not reconfirm study year, completed internship does not establish job termination, and the same organization name needs explicit identity evidence. These examples test proposed behavior; they do not define a complete production contract.

### Planned checks after the placement decision

An ordinary belief can weaken with time or unresolved conflicting evidence; a protected accepted rule stays at 1 under time alone. An accepted replacement preserves the old node as non-current, transfers protection where appropriate and flags work that depended on the old version. An unaccepted contradiction remains visible as a dispute, including when the old memory is protected. A scoped exception or partial update changes only the relevant part. Retried input does not manufacture independent support.

### 2026-10-14 — Authorized implementation evidence

The later “start applying the plan” and “ok implement” instructions authorize the first implementation, superseding the earlier planning-only restriction. The [implementation guide](../../../docs/memory_evolution.md) and [actual final graph demo](../../../report/lifecycle_implementation_20261014_final/README.md) describe that implemented contract.

Confirmed user instructions/rules receive protection at 1; ordinary evidence uses explainable fuzzy rules capped at 0.99. Accepted changes preserve versions and invalidate dependent work. A later change creates `SUPERSEDES`; a correction also creates `CONTRADICTS`; an unaccepted conflicting proposal stays disputed. Scope, field-level confirmation, accepted aliases, event retries, attribution, temporal history and explicit deletion are checked in `tests/test_memory_lifecycle.py`.

The user accepted the recommended protection boundary. Decay periods and membership/rule weights are configurable initial defaults, not research-calibrated truth probabilities. Keep this broader ticket open for calibration and difficult real-input policy cases; its open status does not mean the authorized first implementation is waiting for permission.


## Answer

The first contract is implemented: source-attributed immutable claims, scoped field updates, protected confirmed rules/instructions, genuine fuzzy explanations, distinct contradiction/change/retraction links, retained versions and reasons, identity evidence, explicit privacy deletion and independent support/disagreement groups. Unclear confirmed requirements require review and block stale actions. Defaults are configurable and not calibrated truth probabilities.

[Implementation/evaluation contract](../../../docs/memory_evolution.md). [Actual shared-service evidence](../../../report/shared_memory_20261014_final/results.json).

### Decision source

The user's 2026-10-14 instruction, “all the steps in the wayfinder plan complete, if remaining then complete it”, delegates completion of remaining engineering work under the existing destination and accepted architecture/protection boundary. The documented first-contract defaults implement that authorization; they are engineering choices, not fabricated answers about customer identity, teammate commitments, scientific findings or production readiness.
