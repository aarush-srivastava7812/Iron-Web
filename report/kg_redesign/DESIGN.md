# Proposed claim, evidence, and change graph

This is an isolated design prototype, not a change to the application's memory schema. Its entities and interpretations were hand encoded from three fictional demonstration sentences. No model performed extraction. The Kùzu prototype was closed, reopened, and queried before its viewer export was generated. The belief-score proposal remains postponed.

## What the earlier graph lost

The earlier demonstration repeated each whole sentence once per entity, gave relationships no source-memory ownership, and stored `USES PostgreSQL` together with `AVOIDS PostgreSQL`. The last label was an overinterpretation: changing to SQLite does not assert dislike, avoidance, or a ban. Generic graph traversal could not explain which claim changed, what evidence justified the change, or which unrelated claims remained.

The objective is faithful representation and evidence selection, not a larger number of edges. Restructuring the same sentences does not create new source information. It makes the information addressable and enables traceable compositions of premises.

## The three source records

| Source | Text |
|---|---|
| S1 | Maya maintains Project Atlas. |
| S2 | Project Atlas uses Python and PostgreSQL. |
| S3 | Project Atlas now uses SQLite instead of PostgreSQL. |

Keep each source verbatim, once. Retain origin, user/project namespace, recorded time when known, source identity, and event time separately. Sequence 1/2/3 in this demonstration means order of submitted sentences, not a calendar date.

## Canonical claims

| Claim | Subject | Predicate | Object | Polarity | Evidence | Interpretation after S3 |
|---|---|---|---|---|---|---|
| C1 | Maya | maintains | Project Atlas | Positive | S1 | Last-known maintenance; not freshly confirmed |
| C2 | Project Atlas | uses | Python | Positive | S2 | Last-known usage; unaffected by the stated database change |
| C3 | Project Atlas | uses | PostgreSQL | Positive | S2 | Historical report, replaced in the described use |
| C4 | Project Atlas | uses | SQLite | Positive | S3 | Latest reported replacement |
| C5 | Project Atlas | uses | PostgreSQL | Negative | S3, `instead of PostgreSQL` | Cessation in the described use; not a global ban |

C5 is a normalized interpretation of the explicit replacement, not a separate new source. All claims have context `Atlas, described use; environment unspecified`. Real validity dates remain null because the examples supply none. Negative polarity attaches to the same predicate; it is not encoded as the stronger predicate `AVOIDS`.

The type classification of Python as a programming language and SQLite/PostgreSQL as database technologies is supplied ontology knowledge. It is recorded as an external modeling input, not evidence extracted from S1/S2/S3. No global constraint says a project can use only one database.

Each Claim node links to a SUBJECT Entity, OBJECT Entity, and its supporting Source. The support edge records the exact quote and character offsets. Polarity, qualifiers, modality, temporal scope, extraction method, and uncertainty belong to the claim. Repeated mentions can supply additional support edges without copying full source records.

## An explicit replacement event

X1 records a TechnologyReplacement concerning Atlas:

- Previous use claim: C3.
- Replacement use claim: C4.
- Cessation claim: C5.
- Evidence: S3.
- Real effective date: unknown.
- Reason: unknown.

C4 has a `SUPERSEDES` link to C3. C5 has an `ENDS_CURRENT_APPLICABILITY` link to C3. C3 is retained. C1 and C2 are not superseded.

This is a change of state, not an unresolved same-time contradiction. If two incompatible claims concern overlapping event times, the same entity, the same constrained property, and the same context, create a dispute relationship instead. Multiple databases, multiple environments, and different historical periods are not automatically contradictions.

`SUPERSEDES` in this prototype points new-to-old. The current application stores old-to-new under that name. Integration must adapt that convention explicitly and test both endpoints rather than silently reverse existing records.

## Useful, bounded inference

The prototype evaluates answers from exported database records, using named, small rules:

1. `maintains(Maya, Atlas)` plus latest reported `uses(Atlas, SQLite)` establishes that Maya maintains a project whose latest reported database in this context is SQLite.
2. The replacement event establishes PostgreSQL-to-SQLite change without retracting Python usage.
3. Source selection for the composed maintenance/database answer is S1 + S3, not every nearby observation. Explaining what changed adds S2 as prior evidence.
4. Python remains last known from S2; it is not independently re-confirmed by S3.
5. Maintenance does not entail personal expertise. Usage does not entail critical operational dependency. A switch does not entail a reason, speed improvement, or calendar date.

Derived answers carry premise claim IDs, source IDs, the rule used, scope, and unresolved fields. If derived results are later persisted, store them separately with `DERIVED_FROM` and a rule version; invalidate/recompute them when a premise changes. Do not turn an agent's repeated answer into independent evidence for its own premises.

## Explainability and information gain

A relationship should explain who/what it concerns, exactly what is asserted, polarity, context, source phrase, extraction origin, known/unknown times, why it is current or historical, and the claims it replaces. Rich metadata is preferable to a proliferation of vague relationship labels.

For this prototype, improvement is demonstrated by answerable questions and blocked unsupported conclusions, not an invented numeric information-gain score. Verified questions include current reported database, previous database, maintainer, scoped change, and composed project context. Motive, exact date, and personal expertise remain unknown.

For future retrieval, actual information gain is query-relative uncertainty reduction. `IG = H(answer before evidence) - H(answer after evidence)` only becomes measurable once an answer distribution and evaluation protocol are defined. As a practical selection heuristic, use newly covered query slots, independent evidence, explicit change resolution, and redundancy penalties. Label that heuristic as coverage/novelty, not calibrated entropy. A third copy of the same sentence supplies no new independent evidence.

## Applying this to the application

1. **Add a structured claim model.** Extend ingestion validation with subject/predicate/object, polarity, context, modality, source spans, nullable effective times, and explicit replacement references. Support multiple claims per source. Add a small predicate/type registry; cardinality and compatibility rules are context-specific. Keep source reliability, extraction certainty, and importance separate.
2. **Change extraction output.** Have the extractor return atomic claims and explicit changes, along with evidence spans. Validation checks that every quoted span is real and each relationship endpoint exists. A model's confidence is not a calibrated probability. Compare replacement/contradiction candidates using shared entity and context, then relation semantics; embedding similarity only proposes candidates.
3. **Add Claim/Source/Change tables to Kùzu.** Keep existing entities. Store claim-level support and evolution links. Preserve aliases with namespace-aware identity resolution; type+name alone can conflate different people or projects. No evidence should be discarded during migration. Use coordinated writes for claims and changes rather than a successful save followed by an independently failing detector pass.
4. **Link Qdrant records to claims.** Keep original source vectors and add atomic claim vectors if retrieval measurements justify them. Store `claim_id`, `source_memory_id`, `record_kind`, namespace, polarity, context, and lifecycle metadata. Qdrant proposes relevant evidence; Kùzu determines its scope and relationships. Group claim hits by source for document-level metrics so repeated claims are not counted as independent evidence.
5. **Make retrieval question-aware.** Identify requested slots and temporal/context scope, retrieve candidate claims, follow predicate-compatible paths, include the evidence needed to explain changes, and build an evidence bundle. Relevance should include path semantics and evidence utility, not a uniform bonus for all graph neighbors. Return the answer-supporting claims, rule, sources, history, and unknowns alongside the score.
6. **Use readable graph projections.** Default to entities and understandable claim-backed relationships. Expand individual claims to reveal their source and evolution; offer complete storage records separately. Support before/after views, history, disputes, and query-highlighted premise paths. Display unknown fields rather than inferred precision.
7. **Migrate and verify on copies.** Start with sources and namespace mappings. Convert duplicated observations into source-linked claims only when the original text justifies the interpretation; do not mechanically convert `AVOIDS` into cessation. Produce a reconciliation report and preserve legacy IDs. Keep the existing read path while the v2 path is verified.

Main implementation touchpoints are `memory/ingestion/extractor.py`, `memory/ingestion/nim_extractor.py`, `memory/graph/kuzu_store.py`, `memory/engine.py`, `memory/retrieval/hybrid.py`, `memory/ranking/scorer.py`, and the public result models. These application files were not modified by this prototype.

## Required behavior checks

- Replacement affects C3 only; C1 and C2 remain available.
- Query before the replacement still returns PostgreSQL; latest reported query returns SQLite.
- Unknown effective dates are not replaced with the ingestion timestamp.
- A test-environment database does not supersede production use.
- A project can use two databases unless a source explicitly narrows the slot.
- Same-time unresolved disagreements retain both claims and report uncertainty.
- Evidence spans round-trip exactly; every derived answer exposes its premises.
- Repeated or paraphrased source copies do not manufacture independent support.
- Retracted premises invalidate dependent inferred answers.
- Migration and failed cross-store writes preserve original sources and historical records.

The existing isolated prototype verifies persisted node/edge counts, source spans, stage-dependent database answers, preservation of unrelated claims, blocked skill inference, and unknown date/reason. It does not validate model extraction, production integration, or quantitative retrieval gains.

## References

The claim-as-a-node pattern follows the general idea of making statements describable, discussed in [W3C RDF 1.2 Concepts](https://www.w3.org/TR/rdf12-concepts/). Evidence and derived-answer chains follow ideas in [W3C PROV-O](https://www.w3.org/TR/prov-o/). These are modeling references; this prototype uses Kùzu property graphs and does not claim RDF or PROV conformance.
