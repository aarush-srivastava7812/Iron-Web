# Current architecture decisions

| Decision | Implemented effect |
|---|---|
| Embedded storage | Qdrant and Kùzu operate locally. The application exposes no alternative Neo4j or remote Qdrant backend. |
| One ingestion facade | The pipeline and benchmark evaluator use `MemoryEngine`; pre-extracted input does not bypass storage safety. |
| Coordinated writes | Graph transactions and exact vector snapshots compensate caught failures. This is not a durable transaction spanning both stores. |
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

The earlier design decisions and phase examples are retained under `archive/2026-10-12/design-history/`. The pre-cleanup repository state is Git commit `724c551`.
