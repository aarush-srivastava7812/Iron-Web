# Current architecture decisions

| Decision | Implemented effect |
|---|---|
| Storage boundary | Qdrant remains embedded; FalkorDB supplies the named graph service. A pinned Compose service provides local persistence. |
| One ingestion facade | The pipeline and benchmark evaluator use `MemoryEngine`; pre-extracted input does not bypass storage safety. |
| Coordinated writes | A staging graph is published atomically while a recovery graph and exact vector snapshots compensate caught failures, including a lost publication response. This is not a durable transaction spanning both stores. |
| Shared graph access | Reentrant thread locks and renewed Redis leases serialize cooperating clients. Native unique/mandatory ID constraints retain identifier integrity, and revision-aware entity and conflict caches refresh across clients. Seed entities are read in bounded batches. |
| Explicit ownership | Observations and newly extracted relationships carry their source memory ID. Exact legacy matching supports older observations. |
| Stable identities | Extracted entity IDs use normalized name/type hashes. Document IDs remain intact through ingestion and retrieval. |
| Explicit extraction | `none` is the default. Hosted extraction requires a selected policy and credentials. Failures produce errors instead of placeholder facts. |
| Conservative maintenance | Similarity alone does not delete a record. Distinct contexts and episodes remain separate; original metadata is retained in merge provenance. |
| Gather before ranking | Graph evidence joins the candidate pool before conflicts, reranking and scoring. CPU/GPU paths keep the same bounded pool. |
| Explicit time controls | Request modes define validity filtering. Supersession uses direction and effective time. Shared entities do not imply mutually exclusive facts. |
| Effective settings | Unknown settings fail validation. Local server-only index controls, unused score terms and inactive orchestration flags were removed. |
| Lazy optional components | Imports and status queries do not initialize models. GPU runtime preparation and hosted calls occur only when selected. |
| Shared evaluation contract | Core and optional SDK adapters use the same local metric functions and runner. Resume binds results to source, data and configuration. |
| Complete-context slices | Question subsets retain their full histories. Existing versions and historical outputs remain unchanged. |
| Research boundary | Mechanism baselines and genuine SDK adapters are separate from the user application and carry distinct names. |
| Historical evidence | Earlier designs, scripts and outputs remain recoverable. Current behavior is documented from the implemented code and verification records. |
| Versioned claim layer | Optional structured claims retain sources, exact scopes, confirmations, disputes and accepted changes inside FalkorDB. Ordinary fuzzy scores and explicit protection are separate from importance. |
| Authoritative evidence | Versioned vector/graph hits are reconciled with eligible field-level graph evidence. Field recall reports missing/disputed information and source paths. |
| Work dependencies | Exact used claim versions and prerequisites drive bounded invalidation and evidence-carrying handoffs; completion history survives later review requirements. |

The earlier design decisions and phase examples are retained under `archive/2026-10-12/design-history/`. The pre-cleanup repository state is Git commit `724c551`.
The FalkorDB replacement is documented in [the migration decision record](architecture/adr-001-falkordb.md). Earlier benchmark measurements at `6d10601` used Kùzu and do not measure the new backend.

The vector-placement experiment retains Qdrant: [measured comparison](../report/vector_placement_20261013_p5_paired/REPORT.md). The [memory evolution guide](memory_evolution.md) describes the implemented claim, fuzzy-score and evidence interfaces, including their limits and trusted-caller boundary.

The optional [three-tier context layer](three_tier_memory_usage.md), implemented on 2026-10-15, adds equal agent/traveller text budgets, evidence-backed task/mood cards, bounded host caching and actual CUDA card-vector matching with CPU fallback. It discovers scoped saved fields and makes rules/instructions mandatory, preserving their exact dependency IDs. Authenticated context snapshots hash relevant claim/source state, identity links and durable journal rows, with runtime identity and time expiry. Cache hits retain trip-aware pending/failed/unclear gates; global changes remain conservative blockers, and consumers revalidate after generation. Permanent claims and work coordination remain in the existing stores. The context layer requires explicit local consumer-tokenizer/profile configuration and does not itself provide a generative model or site integration.
