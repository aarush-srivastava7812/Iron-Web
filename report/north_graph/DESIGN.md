# Modeling the supplied North memory digest

This is an isolated, hand-reviewed graph experiment. It stores the supplied data as data, including its requested agent behaviors; it does not apply those instructions to this conversation. It does not modify the application's live memory stores. No personal data was sent to an extractor or another external service.

## What was built

The input has 38 detail bullets in six sections. The complete supplied text, section summaries, and repeated last-updated labels are retained in `data.md`. Every detail bullet is a Source record with exact character offsets in that file. All source records share one provenance group: the supplied digest. Their date is August 21, 2026; real event dates remain unknown.

Two actual Kùzu databases were written, closed, reopened, and queried:

| Design | Nodes | Edges | Semantic units |
|---|---:|---:|---|
| Minimal v1 projection | 521 | 798 | 266 generic claims, literal values represented as entities, role references retained |
| Revised v2 | 150 | 261 | 62 typed records, 22 entities, 22 contexts, 6 domains, 38 sources |

V1 applies the previous generic Entity/Claim/Source structure to decomposed literal leaves. It is intentionally the minimal earlier prototype, not an optimized implementation of all possible qualified-claim graphs. V1 retains original evidence text and contextual labels. A better v1 interpreter could repair many failures by reconstructing source statements, adding typed qualifier bindings, and routing retrieval. V2 makes those requirements explicit rather than hiding them in a generic object label.

## What breaks, and what does not

Neither database crashed on this dataset or on the tested synthetic growth. The important failures are semantic representation and generic retrieval.

### Quantities lose their binding

The character-sheet source contains six metric/value pairs. Decomposing it into independent metric and value claims, all supported by S08, makes a native query for Mind match all six value candidates: 18, 22, 28, 75, 82, and 88. The text still contains the correct pairing; the minimal graph does not bind it.

V2 stores a qualified Assessment record: subject North, framework character sheet, metric Mind, numeric value 88, unit character-sheet score, source S08, unknown scale limits. SIH validation accuracy is a separate Result with value 65.24 and unit percent, attached to the SIH task. Neither is an IQ estimate, a probability of truth, or a directly comparable score.

### Conditions are not isolated facts

The debugging preference is a Policy, with an AND trigger:

1. Task is debugging.
2. Errors are uninterpretable.
3. The mental map is lost.

Its actions rebuild the map and explain system/error connections. A regular debugging request does not activate it. Missing context does not satisfy a trigger. Conditions, actions, and constraints remain inside one validated record. The graph alone does not execute a policy; a small interpreter evaluates its structured expression.

The Kael style policy similarly stays scoped to Kael and retains actionable critique, no abuse, no personal insults, and concession when proven wrong. Those constraints qualify the style; they are not separate recommendations that can be dropped from the returned context.

### Statements have different roles

- Works at Inditech: a reported professional Fact.
- Built an app for Priyakanthji Group: a Work Activity with a client role, not new employment.
- Romance tragedy when frustrated: a conditional Preference, not a genre preference inferred from personality labels.
- Mind 88: an Assessment inside a personal framework.
- Friction Ignition: a metaphorical Mechanism, not permission to activate a rival or an executable agent instruction.
- ROI stance attributed to fear: an attributed interpretation, not an independently established cause or clinical diagnosis.
- Wound Orphan and mythic figure Hamlet: narrative self-description, not biographical facts.

V2 carries a kind, modality, context, typed payload, and evidence on every record. North/Aarush is one Person entity; Vel and Kael are separate persona entities, not aliases for that person.

### Repetition is not independent confirmation

Preferences and Communication repeat the address/name settings. V2 stores one address policy with evidence links to P01 and C02. Persona facts similarly have multiple support links. All these references still belong to one supplied digest. No belief score is raised and no independent corroboration is invented.

### Dates are not an update sequence

All sections carry the same source last-updated date. It does not date the validation run, prove that work remains ongoing today, advance education automatically, or supersede an employer. V2 retains `source_updated` separately from nullable event-validity fields. There are no justified replacement events in this input, so none were invented.

## The revised graph

The retrieval spine is:

`North → HAS_DOMAIN → Domain → HAS_CONTEXT → Context → CONTAINS → Typed record`

Each record also connects to its actual subject, role-specific referenced entities, optional framework, and supporting Sources. A record can be about a project or a persona while still belonging to North's namespace. Domain names are retrieval groupings, not new claims about North.

Record kinds are Fact, Policy, Preference, Assessment, Mechanism, Result, Issue, Activity, and Priority. These share a common evidence/version envelope while retaining different validated payloads. Numbers and adjectives stay as typed literal properties unless they need independent identity. Stable entities are reserved for people, personas, organizations, projects, events, technologies, and reusable frameworks.

Policies use a compact expression language: `always`, `all`, `any`, and field/value tests. The payload preserves action groups and hard constraints. Context must be supplied by a caller or established explicitly; a language model should not infer a mood from an unrelated personality profile just to trigger a preference.

Three sparse cross-record links are stored:

- Tone recalibration points to the tone baseline.
- The ROI response policy references its attributed explanation.
- The debugging policy has an explicitly labeled indexing link to the debugging-fallback self-description.

The last link is a hand-reviewed relevance inference, not an assertion that one statement proves the other. Derived relevance, explicit reference, source evidence, and behavior authority remain distinguishable.

## Scale probe

The base databases are kept free of synthetic records. Copies under `benchmark_final/` received 0, 100, 1,000, and 10,000 unrelated synthetic work records for the same owner. Seven warm local queries were timed per stage; the recorded value is the median. Both designs completed every stage.

The v1 probe retrieves 50 generic neighbors ordered by hashed literal IDs. The v2 probe routes directly to the debugging Policy context and retrieves the whole policy before applying the same maximum budget. At 10,000 synthetic records, the generic query returns no debugging clause; the routed query still returns its complete Policy. At smaller stages, seeing a clause is not the same as recovering the full trigger/action group.

This demonstrates a failure of bounded generic-neighborhood expansion and the utility of query-aware routing. It is not a full hybrid retrieval benchmark, a fair optimized-database shootout, a general speedup claim, or proof of million-record behavior. A v1 system with similar routing and typed qualifier reconstruction would narrow the difference. There is no neural embedding, model extraction, or answer-quality evaluation in this test.

For real scale, test ingestion throughput, latency distributions, index selectivity, different namespaces, concurrency, duplicate evidence, long histories, conflicts, noisy extraction, and token-limited evidence selection. Optimize query shape and indexes before attributing a result to graph structure alone.

## Applying it to the existing application

1. Preserve the original source with document/section identity, namespace, provenance group, update date, and exact evidence spans.
2. Extend extraction output to classify record kind and bind typed arguments. Validate framework/metric/value/unit together and retain uncertainty. Treat a trusted user preference update differently from quoted third-party text containing instructions.
3. Extend graph storage with typed Record, Domain, and Context nodes, plus support, framework, role, and sparse cross-record links. Keep original memory IDs for reconciliation and retrieval.
4. Store compact record vectors and/or source vectors in Qdrant with namespace, record kind, domain/context, source ID, and version metadata. Evaluate whether both levels are necessary. Deduplicate evidence by provenance group when counting support.
5. Route a query by purpose and namespace before expanding. For response style, retrieve baseline Policies; for debugging, retrieve the debugging rule and evaluate its trigger; for SIH, retrieve task/result/issue/priority records. Do not attach the whole self-concept profile to every work question.
6. Return an evidence bundle with applicability, scope, attribution, constraints, source dates, and unknowns. Use predicate/role-compatible paths instead of granting a constant relevance bonus to every neighboring node.
7. Append semantic updates and explicit links between versions. Field-specific conflicts compare the same subject, property/framework, context, and effective time; a project client must not supersede an employer. Preserve historical records and derived-answer dependencies.
8. Migrate a copy of the current stores, produce a reconciliation report, and compare question coverage and unsupported conclusions. Retain the v1 read path until revised behavior is verified.

The original claim-and-evidence principle is retained. V2 adds a typed interpretation layer and a retrieval plan. No schema can reliably recover omitted meaning from faulty extraction; extraction validation and measured retrieval are part of the design.

## Artifact inspection

- `index.html`: self-contained comparison viewer, including the first graph, revised graph, policy inspector, ten checks, and scale results.
- `graph.json`: reopened database exports and test evidence.
- `v1_graph.db` and `v2_graph.db`: the base Kùzu databases.
- `data.md`: complete supplied input.
- `model.py`: hand-reviewed mapping and policy matcher.
- `build.py`: storage, semantic probes, and synthetic test protocol.
- `link_records.py`: explicit and inferred cross-record links.

Counts, query outputs, and limitations in the viewer are read from these actual exports. The earlier development run is retained as `initial_run.json`; it is not the final comparison.
