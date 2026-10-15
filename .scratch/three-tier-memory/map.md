# Three-Tier Agent Memory Before Travel Site Integration

Labels: wayfinder:map
Status: resolved
Tracker: local Markdown

## Destination

Resolve the architecture and implementation gates for a two-part hot cache, task/persona cards with a GPU residency path, and the existing durable hybrid memory. The travel agency site must wait until the core acceptance gates pass.

## Notes

- User instruction, 2026-10-14: use Wayfinder, answer the questions autonomously, show the problems, and handle this before combining the travel agency site.
- Execution authorized on 2026-10-15: build the design and test each component while building. The [implementation log](implementation.md) and [usage guide](../../docs/three_tier_memory_usage.md) supersede the planning-only status below; site integration remains separate.
- This resumes cache architecture work previously deferred in the older graph-memory map.
- Planning scope: settle decisions and identify verification work. Do not claim the new tiers are implemented or merge the site in this session.
- The user's autonomous-answer instruction overrides Wayfinder's live grilling and one-ticket/session pacing. Decision tickets use AFK task investigations rather than pretending a human interview took place.
- Use [Wayfinder](C:/Users/User/.codex/skills/wayfinder/SKILL.md), [domain modeling](C:/Users/User/.codex/skills/domain-modeling/SKILL.md), [research](C:/Users/User/.codex/skills/research/SKILL.md), and [local tracker operations](C:/Users/User/.codex/skills/setup-matt-pocock-skills/issue-tracker-local.md). Grilling was read; its live questions are replaced by documented agent decisions under the user's instruction.
- Preserve the existing uncommitted implementation and data. Keep research in a local linked evidence file; do not publish branches or change storage/model providers as part of this map.
- Assignee is Codex. Claim each ticket before investigating; append its answer on resolution. Questions and detailed decisions live in tickets; the map is an index.

## Decisions so far

- [Existing Memory Core and the Missing Tiers](issues/01-existing-core.md): retain the durable core and its authenticated checks; hot profiles, cards and context assembly are new work.
- [How GPU-Resident Persona Cards Reach the Model](issues/02-gpu-card-feasibility.md): a bounded GPU card embedding matrix selects evidence-backed text; actual residency needs implementation proof.
- [Tier Boundaries, the Equal Cache Split and Persona Scope](issues/03-tier-contracts.md): equal agent/traveller token caps, exact trip scope, explicit temporary mood and evidence-backed derived cards.
- [Prevent Stale Cards, Lost Changes and Cross-User Memory](issues/04-freshness-and-authority.md): readiness and generation checks apply to every hit; invalidate on changes, expiry and deletion and recheck before response/work.
- [Context Assembly, Card Routing and Bounded Resource Use](issues/05-routing-and-budgets.md): filter scope before ranking, serialize bounded selected text, account GPU residency and preserve equivalent CPU selection.
- [Problems to Demonstrate and Gates Before Site Integration](issues/06-before-site-gates.md): implement/verify the core and real GPU path first, then connect the site; architecture completion does not imply implementation completion.

## Not yet specified

- No unresolved decisions remain for this first context contract. Actual residency, consumer-runtime binding and workload measurements are explicit execution gates in [Problems to Demonstrate and Gates Before Site Integration](issues/06-before-site-gates.md).

## Out of scope

- Travel site integration, deployment, external bookings/payments, replacing Qdrant/FalkorDB, and training a new model.
- Claiming a performance improvement, paper novelty, or production readiness without measurements.
