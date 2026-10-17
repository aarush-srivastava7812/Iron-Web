# Field-aware memory evolution: an isolated, executable prototype

The supplied content is random test data. This demonstration extends a copy of the earlier graph; it does not ingest profile facts into the application or modify the application's memory system. The user instructed that the undated second batch be treated as newly received information. The user separately confirmed that the two Inditech names denote the same organization.

## What is actually stored

`evolution.db` is a real Kuzu database containing all 62 earlier Records and 38 earlier Sources, plus 29 new Records, six exact paragraph Sources, and one clarification Source. It contains 143 independently scoreable Facets and retains the earlier domain/context/entity/evidence structure. Current totals are Entity 41, Domain 10, Context 35, Record 91, Source 45, Facet 143.

The new relations are nine CONFIRMS edges targeting six distinct earlier fields, one accepted SAME_AS edge, and two unresolved POSSIBLE_RELATION edges. Actual supplied data produces zero CONTRADICTS and zero SUPERSEDES edges. Absence of a fact in a later summary is not negation. Nine confirmation edges are not nine independent corroborating sources.

`counterfactuals.db` is separate: six TestClaim nodes and four change edges demonstrate three explicitly synthetic cases. The positive controls are not represented as supplied facts in `evolution.db`.

`graph.json` includes the model, reopened database counts, stored scores and fuzzy traces, source text, provenance, checks, and separately labelled controls. The interactive viewer projects selected relationships from this model. Its education lens groups the two new study mentions visually; the record browser and export preserve each distinct record and source. The viewer is not a screenshot of every edge in a single force-directed graph.

## Why the previous model needed another layer

A useful record preserves a complete policy or episode, but a record is not always the smallest independently updateable proposition. “Third-year BTech student in AI & Data Science” contains three updateable fields. The new statement repeats only the discipline. Refreshing the entire earlier record would wrongly refresh the year and degree.

This version uses Record -> HAS_FACET -> Facet -> FACET_EVIDENCE -> Source. CONFIRMS, CONTRADICTS and SUPERSEDES target Facets. Entity identity remains a different operation. Compound policy triggers stay together as structured policy payloads so their AND/OR conditions are not broken apart. The registry is hand-reviewed; it is not a universal automatic atomizer.

The identity example is staged. Before the clarification, string similarity nominates an unresolved Inditech identity candidate. It does not establish identity. After the user confirmation, `inditech_systems -[SAME_AS {source_id: C_ORG, status: accepted}]-> inditech` is persisted. Original names remain. A completed internship and reported employment still have different properties, scopes and episodes. SAME_AS cannot itself imply job termination or a new current employer.

GDPE versus the new platform, and SIH versus PrefIQ, remain unresolved possible relationships. The user's reminder that these are random data does not resolve those within-fixture project identities.

## Relationship decision gates

1. Resolve only accepted entity aliases; nominate uncertain matches as candidates.
2. Compare typed subject, property and scope. Different properties/scopes add knowledge rather than replace it.
3. Compare values and cardinality. Same value confirms; a multi-valued stack permits both SQLite and PostgreSQL.
4. For different exclusive values, check event context and explicit change/correction evidence. An overlapping-context clash can be CONTRADICTS. “From now on” can SUPERSEDE a prior current state. An explicit correction of the earlier assertion can do both.
5. Acceptance is a separate decision. A new report alone does not automatically resolve a clash or gain protection.

The comparison function consumes already normalized fields and explicit flags. It does not infer these flags from arbitrary natural language. In a production system, extraction and candidate classification need validation before this state transition runs.

## Fuzzy logic and protection

Every ordinary Facet has a current acceptance degree between 0 and 0.99. The inputs are source quality, freshness, support, and conflict. These are configurable demonstration values, not calibrated truth probabilities. The default source quality is 0.85, not a measured reliability estimate. Same-author re-mentions receive bounded support 0.35; repeated paragraphs are not treated as independent verification.

For x in [0,1], the membership sets overlap:

- low: 1 up to 0.2, then linearly falls to 0 at 0.5;
- medium: triangular membership with vertices 0.2, 0.5, 0.8;
- high: rises linearly from 0 at 0.5 to 1 at 0.8, then stays 1.

Freshness is `2 ** (-age_days / half_life_days)`. Completed historical episodes use freshness 1. Rule conjunction uses minimum membership; each rule has a singleton consequent. Examples: reliable source AND weak conflict -> 0.96; fresh AND reliable AND weak conflict -> 0.98; aging AND weak conflict -> 0.78; strong unresolved conflict -> 0.18. The trace stores all memberships, firing strengths and consequents.

`weighted_consequent = sum(firing_i * consequent_i) / sum(firing_i)`

`acceptance = min(0.99, 0.99 * weighted_consequent * freshness)`

This is a Sugeno-style fuzzy rule controller followed by an explicit temporal attenuation factor. It is not merely an exponential decay labelled fuzzy logic. Rules and half-lives are demonstration choices requiring evaluation. The rule model does not prove a proposition true and is not a query-ranking score.

Protection is an explicit state flag. It is not obtained by rounding 0.99 to 1. A protected active/disputed claim stays at score 1 despite time or an unaccepted competing report. An accepted direct replacement/correction transfers that protection to the new node. The old node remains stored with current eligibility score 0 and a separately retained prior acceptance of 1. For a correction, this prior value is an audit of a former belief, not a claim that the corrected fact was historically true.

The three controls demonstrate:

| Case | Relation | Earlier node | New node |
| --- | --- | --- | --- |
| Explicit change from North to Aarush as preferred address | SUPERSEDES | retained, superseded, current 0, prior 1 | active, protected 1 |
| Explicit correction of the earlier year from 3 to 4 | CONTRADICTS and SUPERSEDES | retained, retracted, current 0, prior 1 | active, protected 1 |
| Unaccepted competing year 4 in the same asserted context | CONTRADICTS, unresolved | retained, disputed, protected 1 | retained, disputed, about 0.178 |

Protection does not eliminate conflict. Retrieval must inspect status and conflict links even when a claim scores 1. The disputed case should produce an uncertainty statement or resolution request, not a confident answer selected only by score.

## Time and scope

The second batch's event dates and original source update dates remain unknown. Receipt order is 2; the clarification is order 3. The first source snapshot was updated 2026-08-21, 53 days before the client date 2026-10-13. Source freshness is being modelled, not an invented effective date for employment, projects, courses, or study years. A confirmed field resets its source-freshness age; unrelated fields do not.

The default year-3 score is approximately 0.783 (180-day half-life); BTech is approximately 0.868 (365-day half-life); the re-mentioned discipline is approximately 0.962. Those numbers reflect configured freshness and rules, not factual contradictions. Completed historical results do not lose credibility purely through age, though future corrections can still challenge them. Current relevance should be computed separately.

Other preserved constraints: “synthetic” applies only in selected appropriate documents; India is study location, not inferred nationality; production readiness is a goal rather than an achieved state; Day 32 is course progress rather than completion of all 100 days; model/tool exposure is not an expertise assertion. Hardware quantities retain their units; the supplied CPU name is preserved without external verification. The empty Dive Deeper heading creates no fact.

## Application path and remaining limits

Keep raw sources immutable. Produce validated typed records/fields with stable subject/property/scope identities and evidence spans. Retrieve comparison candidates by those identities and semantic similarity rather than all-pairs comparison. Preserve extraction uncertainty and do not let agent-generated paraphrases become independent evidence. Run identity and temporal/cardinality gates before classifying updates. Commit source, fields, links, status and audit event together; publish vector-index updates through a retryable outbox after commit.

For retrieval: obtain entity/field/context candidates through lexical/vector indexes, expand their evidence and change links, apply current-versus-history intent, and combine relevance with acceptance. Return both sides of unresolved contradictions with provenance. Historical requests can select superseded states; corrections must distinguish former assertions from historically valid facts. A vector hit for an old claim must still be reconciled against its current KG status.

The prototype currently stores scores/traces as a snapshot. A production implementation would calculate freshness at query time or in a scheduled materialization, version the rule parameters, record observation/validity time separately, and log accepted transitions append-only. Source deletion/privacy controls require their own lifecycle. Protection-transfer policy should have a clear authority requirement; explicit user correction is sufficient for these synthetic controls, an arbitrary agent assertion is not.

Still incomplete: automatic extraction and paraphrase equivalence; robust scoped negation and event-time inference; validated identity resolution without user confirmation; calibrated source authority; conflict-resolution adjudication; incremental changes across graph/vector stores; measured retrieval/information gain at real scale. The earlier unrelated-record growth experiment does not establish scalability for this new evolution model. This prototype proves preservation and update behavior for these fixtures, not universal correctness or production throughput.

## Inspect and reproduce

Run `viewer.py` after changing model exports. Run `serve.py` to create a local viewer URL in `server.json`. `verify_view.py` checks the interactive controls and parity with persisted scores. `build.py` refuses to overwrite either database, so use a fresh output copy for a clean reconstruction. `queries.cypher` contains examples for directly inspecting the actual stored KG and separate controls.
