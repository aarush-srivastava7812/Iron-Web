"""Additive claim graph; Qdrant discovers, FalkorDB decides current eligibility.

All mutations run inside the engine's existing coordinated-write boundary.
Graph reads are bounded, field/scope indexed, and never treat semantic similarity
as an accepted change. Caller-supplied source provenance is a trusted local API
contract, not a replacement for future tenant authentication.
"""

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import re
import time

import numpy as np

from memory.lifecycle.fuzzy import score_memory
from memory.lifecycle.models import ClaimInput, SourceInput, canonical_json


def identifier(prefix, value):
    return prefix + hashlib.sha256(canonical_json(value).encode()).hexdigest()[:32]


def subject_id(name):
    return identifier("subject_", name.strip().casefold())


class MemoryLifecycle:
    def __init__(self, graph_store, vector_store, settings):
        self.graph = graph_store
        self.vectors = vector_store
        self.settings = settings
        self.limit = settings["max_related_claims"]

    def _rows(self, query, **params):
        return self.graph.execute(query, params).rows

    def _bounded(self, rows):
        if len(rows) > self.limit:
            raise ValueError(
                "Related-memory limit reached; narrow subject, field or scope."
            )
        return rows

    def ensure_schema(self):
        existing = {
            (r[0], p)
            for r in self._rows(
                "CALL db.indexes() YIELD label,properties RETURN label,properties"
            )
            for p in r[1]
        }
        for label, field in [
            ("MemoryClaim", "id"),
            ("MemoryClaim", "memory_id"),
            ("MemoryClaim", "group_key"),
            ("MemoryClaim", "predicate"),
            ("MemoryClaim", "subject_id"),
            ("MemorySource", "id"),
            ("MemorySource", "memory_id"),
            ("MemoryContext", "id"),
            ("MemoryField", "id"),
            ("MemoryWork", "id"),
        ]:
            if (label, field) not in existing:
                self._rows(f"CREATE INDEX FOR (n:{label}) ON (n.{field})")
        labels = {
            "MemoryClaim",
            "MemorySource",
            "MemoryContext",
            "MemoryField",
            "MemoryWork",
        }
        constraints = {
            (r[0], r[1], tuple(r[2]), r[3]) for r in self._rows("CALL db.constraints()")
        }
        for label in labels:
            for kind in ("UNIQUE", "MANDATORY"):
                if (kind, label, ("id",), "NODE") not in constraints:
                    create = (
                        self.graph.graph.create_node_unique_constraint
                        if kind == "UNIQUE"
                        else self.graph.graph.create_node_mandatory_constraint
                    )
                    create(label, "id")
        deadline = time.monotonic() + self.graph.socket_timeout
        while True:
            required = [
                r
                for r in self._rows("CALL db.constraints()")
                if r[1] in labels and r[2] == ["id"] and r[0] in {"UNIQUE", "MANDATORY"}
            ]
            if len(required) == 2 * len(labels) and all(
                r[4] == "OPERATIONAL" for r in required
            ):
                break
            if any(r[4] == "FAILED" for r in required) or time.monotonic() >= deadline:
                raise RuntimeError(
                    "Lifecycle identifier constraints could not be verified."
                )
            time.sleep(0.01)

    def prepare(
        self,
        content,
        claims,
        source_info,
        memory_id,
        timestamp,
        valid_from,
        valid_until,
        metadata,
    ):
        if not claims:
            raise ValueError("Typed ingestion needs at least one claim.")
        if len(claims) > 32:
            raise ValueError("One event may contain at most 32 claims.")
        source = (
            source_info
            if isinstance(source_info, SourceInput)
            else SourceInput.model_validate(source_info or {})
        )
        parsed = [
            c if isinstance(c, ClaimInput) else ClaimInput.model_validate(c)
            for c in claims
        ]
        for c in parsed:
            if c.aliases and source.origin == "agent":
                raise ValueError(
                    "Agents cannot redefine the trusted question-field vocabulary."
                )
            if c.protected and not source.user_confirmed:
                raise ValueError("Protection requires explicit user confirmation.")
            if (
                c.action in {"correct", "supersede", "alias", "retract"}
                and not source.user_confirmed
            ):
                raise ValueError(
                    "Accepted changes and identities require a confirmed user source."
                )
            if c.action in {"correct", "supersede", "retract"} and not c.reason.strip():
                raise ValueError("An accepted change requires a reason.")
        event = source.event_id or memory_id
        sid = identifier("source_", [source.origin, source.actor_id, event])
        digest = identifier(
            "receipt_",
            dict(
                content=content,
                claims=[c.model_dump() for c in parsed],
                source=source.model_dump(),
                timestamp=timestamp,
                valid_from=valid_from,
                valid_until=valid_until,
                metadata=metadata,
            ),
        )
        previous = self._rows(
            "MATCH(s:MemorySource {id:$id}) RETURN s.memory_id,s.digest", id=sid
        )
        if previous:
            if previous[0][1] != digest:
                raise ValueError(
                    "An event ID already identifies different immutable source content."
                )
            return dict(existing_memory_id=previous[0][0])
        existing_id = self._rows(
            "MATCH(s:MemorySource {memory_id:$mid}) RETURN s.id", mid=memory_id
        )
        if existing_id:
            raise ValueError(
                "Versioned source memories are immutable; add a new event for a change."
            )
        recorded = (
            int(time.time()) if source.recorded_at is None else source.recorded_at
        )
        entities = {}
        for c in parsed:
            for name in [c.subject] + c.references:
                # Subjects are identifiers/names, not automatically merged synonyms.
                entities[subject_id(name)] = dict(
                    id=subject_id(name), name=name, type="MemorySubject"
                )
            if c.action == "alias":
                entities[subject_id(c.value)] = dict(
                    id=subject_id(c.value), name=c.value, type="MemorySubject"
                )
        if len(entities) > 64:
            raise ValueError("An event may refer to at most 64 subjects.")
        return dict(
            source=source,
            claims=parsed,
            source_id=sid,
            digest=digest,
            recorded_at=recorded,
            original_metadata=deepcopy(metadata),
            received_at=int(time.time()),
            entities=list(entities.values()),
            claim_ids=[identifier("claim_", [sid, i]) for i in range(len(parsed))],
        )

    def _canonical_subject(self, sid, known_at=None):
        known_at = int(time.time()) if known_at is None else known_at
        seen = set()
        for _ in range(16):
            if sid in seen:
                raise ValueError("Identity alias cycle.")
            seen.add(sid)
            rows = self._rows(
                "MATCH(a:Entity {id:$id})-[r:CANONICAL_ALIAS]->(b:Entity) WHERE coalesce(r.recorded_at,0) <= $known RETURN DISTINCT b.id",
                id=sid,
                known=known_at,
            )
            if not rows:
                return sid
            if len(rows) != 1:
                raise ValueError("Identity has multiple accepted canonical subjects.")
            sid = rows[0][0]
        raise ValueError("Identity chain exceeds the supported depth.")

    def equivalent_subjects(self, sid, known_at=None):
        known_at = int(time.time()) if known_at is None else known_at
        canonical = self._canonical_subject(sid, known_at)
        seen, frontier = {canonical}, [canonical]
        while frontier:
            rows = self._bounded(
                self._rows(
                    "MATCH(a:Entity)-[r:CANONICAL_ALIAS]->(b:Entity) WHERE b.id IN $ids AND coalesce(r.recorded_at,0) <= $known RETURN DISTINCT a.id LIMIT $limit",
                    ids=frontier,
                    known=known_at,
                    limit=self.limit + 1,
                )
            )
            frontier = [r[0] for r in rows if r[0] not in seen]
            seen.update(frontier)
            if len(seen) > self.limit:
                raise ValueError("Identity group exceeds the supported limit.")
        return sorted(seen)

    def group(self, claim, at=None, historical=False, known_at=None):
        if claim.get("kind") == "episode":
            return [claim]
        at = int(time.time()) if at is None else at
        known_at = int(time.time()) if known_at is None else known_at
        subjects = self.equivalent_subjects(claim["subject_id"], known_at)
        keys = [
            identifier(
                "field_", [sid, claim["predicate"], json.loads(claim["scope_json"])]
            )
            for sid in subjects
        ]
        rows = self._bounded(
            self._rows(
                "MATCH(c:MemoryClaim) WHERE c.group_key IN $keys AND c.recorded_at <= $known "
                + (
                    "AND ((c.ended_at <= $at AND coalesce(c.ended_known_at,c.ended_at) <= $known) OR c.valid_until < $at) "
                    if historical
                    else "AND c.accepted_at <= $at AND c.valid_from <= $at AND c.valid_until >= $at AND (c.ended_at IS NULL OR c.ended_at > $at OR coalesce(c.ended_known_at,c.ended_at) > $known) "
                )
                + "RETURN properties(c) LIMIT $limit",
                keys=keys,
                at=at,
                known=known_at,
                limit=self.limit + 1,
            )
        )
        return [dict(r[0]) for r in rows]

    @staticmethod
    def active(claim, at, known_at=None):
        known_at = int(time.time()) if known_at is None else known_at
        return (
            claim["valid_from"] <= at <= claim["valid_until"]
            and claim["accepted_at"] <= at
            and claim["recorded_at"] <= known_at
            and (
                claim.get("ended_at") is None
                or at < claim["ended_at"]
                or claim.get("ended_known_at", claim["ended_at"]) > known_at
            )
        )

    @staticmethod
    def overlaps(a, b):
        return max(a["valid_from"], b["valid_from"]) <= min(
            a["valid_until"], b["valid_until"]
        )

    def ingest(self, plan, memory_id, content):
        self.ensure_schema()
        source = plan["source"]
        sid = plan["source_id"]
        recorded = plan["recorded_at"]
        props = dict(
            id=sid,
            memory_id=memory_id,
            event_id=source.event_id or memory_id,
            text=content,
            origin=source.origin,
            actor_id=source.actor_id,
            user_confirmed=source.user_confirmed,
            quality=source.quality,
            evidence_group=source.support_group(),
            recorded_at=recorded,
            received_at=plan["received_at"],
            digest=plan["digest"],
        )
        props["metadata_json"] = canonical_json(plan["original_metadata"])
        self._rows("CREATE(s:MemorySource {id:$props.id}) SET s += $props", props=props)
        for index, item in enumerate(plan["claims"]):
            protected = (
                (source.user_confirmed and item.kind in {"instruction", "rule"})
                if item.protected is None
                else item.protected
            )
            effective = recorded if item.effective_at is None else item.effective_at
            props = dict(
                id=plan["claim_ids"][index],
                memory_id=memory_id,
                source_id=sid,
                subject_id=subject_id(item.subject),
                subject_name=item.subject,
                predicate=item.predicate,
                value_json=canonical_json(item.value),
                kind=item.kind,
                scope_json=canonical_json(item.scope),
                scope_key=identifier("context_", item.scope),
                valid_from=item.valid_from,
                valid_until=item.valid_until,
                accepted_at=effective,
                recorded_at=recorded,
                accepted=source.user_confirmed
                or source.origin == "tool"
                or item.kind == "episode",
                protected=protected,
                cardinality=item.cardinality,
                half_life_days=item.half_life_days or self.settings["half_life_days"],
                reason=item.reason,
                group_key=identifier(
                    "field_", [subject_id(item.subject), item.predicate, item.scope]
                ),
            )
            props["references_json"] = canonical_json(item.references)
            props["action"] = item.action
            props["score_at_creation"] = (
                1.0
                if props["protected"]
                else score_memory(
                    age_seconds=0,
                    half_life_days=props["half_life_days"],
                    source_quality=source.quality,
                    independent_groups=1,
                )["score"]
            )
            priors = [] if item.kind == "episode" else self.group(props, effective)
            overlapping = [
                c
                for c in priors
                if self.overlaps(c, props)
                and (c.get("ended_at") is None or effective < c["ended_at"])
            ]
            same = [c for c in overlapping if c["value_json"] == props["value_json"]]
            different = [
                c
                for c in overlapping
                if c["value_json"] != props["value_json"]
                and c["cardinality"] == "single"
                and item.cardinality == "single"
            ]
            if item.action == "confirm" and not same:
                raise ValueError(
                    "Confirmation requires an existing matching value in the same field and scope."
                )
            replacements = []
            if item.action in {"correct", "supersede", "retract"}:
                eligible = [c for c in overlapping if self.active(c, effective)]
                if item.targets is not None:
                    replacements = [c for c in eligible if c["id"] in item.targets]
                    if set(item.targets) != {c["id"] for c in replacements}:
                        raise ValueError(
                            "Change targets must be active claims in the same subject, field and scope."
                        )
                else:
                    if item.cardinality == "multiple":
                        raise ValueError(
                            "A multi-valued field needs explicit change targets."
                        )
                    replacements = eligible
                if not replacements:
                    raise ValueError("Accepted change has no active matching target.")
                if item.action != "retract" and any(
                    c["protected"] for c in replacements
                ):
                    if item.kind not in {"instruction", "rule"}:
                        raise ValueError(
                            "A protected instruction/rule needs an eligible replacement."
                        )
                    props["protected"] = True
                    props["score_at_creation"] = 1.0
                props["accepted"] = True
            previous_scores = {
                c["id"]: self.view(c, effective, peers=priors)["fuzzy_score"]
                for c in replacements
            }
            if item.action == "retract":
                props.update(
                    kind="instruction",
                    predicate="__retracted__." + item.predicate,
                    value_json=canonical_json(
                        dict(
                            retracted_field=item.predicate,
                            targets=[c["id"] for c in replacements],
                            reason=item.reason,
                        )
                    ),
                    protected=source.user_confirmed
                    if item.protected is None
                    else item.protected,
                )
                props["group_key"] = identifier(
                    "field_", [props["subject_id"], props["predicate"], item.scope]
                )
                props["score_at_creation"] = (
                    1.0 if props["protected"] else props["score_at_creation"]
                )
            self._rows(
                "CREATE(c:MemoryClaim {id:$props.id}) SET c += $props", props=props
            )
            self._rows(
                "MATCH(c:MemoryClaim {id:$id}),(s:MemorySource {id:$source}),(e:Entity {id:$subject}) "
                "CREATE(c)-[:SUPPORTED_BY]->(s) CREATE(c)-[:ABOUT]->(e) "
                "MERGE(x:MemoryContext {id:$scope}) SET x.qualifiers=$qualifiers "
                "CREATE(c)-[:IN_CONTEXT]->(x) "
                "MERGE(f:MemoryField {id:$predicate}) CREATE(c)-[:"
                + ("RETRACTS_FIELD" if item.action == "retract" else "ASSERTS_FIELD")
                + "]->(f)",
                id=props["id"],
                source=sid,
                subject=props["subject_id"],
                scope=props["scope_key"],
                qualifiers=props["scope_json"],
                predicate=item.predicate,
            )
            for reference in item.references:
                self._rows(
                    "MATCH(c:MemoryClaim {id:$id}),(e:Entity {id:$ref}) CREATE(c)-[:REFERS_TO {role:$role}]->(e)",
                    id=props["id"],
                    ref=subject_id(reference),
                    role=item.predicate,
                )
            # A field label is an explicit aid to question parsing, not an NLP claim.
            old = self._rows(
                "MATCH(f:MemoryField {id:$id}) RETURN f.aliases", id=item.predicate
            )
            aliases = list(
                dict.fromkeys(
                    (json.loads(old[0][0]) if old and old[0][0] else [])
                    + item.aliases
                    + [item.predicate.replace("_", " ").replace(".", " ")]
                )
            )
            self._rows(
                "MATCH(f:MemoryField {id:$id}) SET f.aliases=$aliases",
                id=item.predicate,
                aliases=canonical_json(aliases[:32]),
            )
            for prior in same:
                self.link(
                    props["id"],
                    prior["id"],
                    "CONFIRMS",
                    recorded,
                    item.reason or "Matching field and scope",
                )
            for prior in different:
                if item.action in {"supersede", "retract"} and prior["id"] in {
                    claim["id"] for claim in replacements
                }:
                    # An accepted change over time is not a simultaneous contradiction.
                    continue
                self.link(
                    props["id"],
                    prior["id"],
                    "CONTRADICTS",
                    recorded,
                    item.reason
                    or "Different single-valued assertions in an overlapping scope",
                )
            for prior in replacements:
                self._rows(
                    "MATCH(c:MemoryClaim {id:$id}) SET c.ended_at=$at,c.ended_known_at=$known,c.ended_by=$replacement,c.end_reason=$reason,c.previous_score=$score",
                    id=prior["id"],
                    at=effective,
                    known=recorded,
                    replacement=props["id"],
                    reason="corrected"
                    if item.action == "correct"
                    else "retracted"
                    if item.action == "retract"
                    else "superseded",
                    score=previous_scores[prior["id"]],
                )
                self.link(
                    props["id"],
                    prior["id"],
                    "RETRACTS" if item.action == "retract" else "SUPERSEDES",
                    effective,
                    item.reason,
                )
            if replacements:
                self.invalidate_work(
                    [c["id"] for c in replacements], props["id"], item.reason
                )
            elif different:
                self.invalidate_work(
                    [c["id"] for c in different],
                    props["id"],
                    "Unresolved contradiction: " + item.reason,
                )
            if item.action == "alias":
                target = subject_id(item.value)
                if (
                    target == props["subject_id"]
                    or self._canonical_subject(target, 2**63 - 1) == props["subject_id"]
                ):
                    raise ValueError("Identity alias would create a cycle.")
                existing = self._rows(
                    "MATCH(a:Entity {id:$id})-[:CANONICAL_ALIAS]->(b) RETURN b.id",
                    id=props["subject_id"],
                )
                if existing and self._canonical_subject(
                    props["subject_id"]
                ) != self._canonical_subject(target):
                    raise ValueError(
                        "Identity already has a different canonical subject."
                    )
                self._rows(
                    "MATCH(a:Entity {id:$a}),(b:Entity {id:$b}),(c:MemoryClaim {id:$claim}) "
                    "MERGE(a)-[r:CANONICAL_ALIAS {evidence_claim_id:$claim}]->(b) SET r.recorded_at=$recorded "
                    "CREATE(c)-[:IDENTIFIES]->(b)",
                    a=props["subject_id"],
                    b=target,
                    claim=props["id"],
                    recorded=recorded,
                )

    def link(self, new, old, relation, at, reason):
        if relation not in {"CONTRADICTS", "SUPERSEDES", "CONFIRMS", "RETRACTS"}:
            raise ValueError("Unknown lifecycle relation.")
        self._rows(
            f"MATCH(a:MemoryClaim {{id:$new}}),(b:MemoryClaim {{id:$old}}) "
            f"MERGE(a)-[r:{relation}]->(b) SET r.at=$at,r.reason=$reason",
            new=new,
            old=old,
            at=at,
            reason=reason,
        )

    def claim(self, claim_id):
        rows = self._rows(
            "MATCH(c:MemoryClaim {id:$id}) RETURN properties(c)", id=claim_id
        )
        return dict(rows[0][0]) if rows else None

    def views(self, claims, at, known_at=None):
        """Read bounded evidence once for this request, not once per candidate.

        Nothing survives the request, so a subsequent read always observes new
        confirmations, accepted identities and invalidations from the graph.
        """
        if not claims:
            return []
        known_at = int(time.time()) if known_at is None else known_at
        equivalents = {
            sid: self.equivalent_subjects(sid, known_at)
            for sid in {c["subject_id"] for c in claims}
        }
        field_keys = {
            c["id"]: [
                identifier("field_", [sid, c["predicate"], json.loads(c["scope_json"])])
                for sid in equivalents[c["subject_id"]]
            ]
            for c in claims
            if c["kind"] != "episode"
        }
        keys = sorted({key for group in field_keys.values() for key in group})
        rows = (
            self._bounded(
                self._rows(
                    "MATCH(c:MemoryClaim) WHERE c.group_key IN $keys AND c.recorded_at <= $known "
                    "AND c.accepted_at <= $at AND c.valid_from <= $at AND c.valid_until >= $at "
                    "AND (c.ended_at IS NULL OR c.ended_at > $at OR coalesce(c.ended_known_at,c.ended_at) > $known) "
                    "RETURN properties(c) LIMIT $limit",
                    keys=keys,
                    known=known_at,
                    at=at,
                    limit=self.limit + 1,
                )
            )
            if keys
            else []
        )
        by_key = defaultdict(list)
        for row in rows:
            peer = dict(row[0])
            by_key[peer["group_key"]].append(peer)
        source_ids = sorted(
            {c["source_id"] for c in claims} | {r[0]["source_id"] for r in rows}
        )
        sources = [
            dict(r[0])
            for r in self._rows(
                "MATCH(s:MemorySource) WHERE s.id IN $ids RETURN properties(s)",
                ids=source_ids,
            )
        ]
        subjects = sorted({sid for group in equivalents.values() for sid in group})
        identity = (
            [
                dict(
                    alias_subject_id=r[0],
                    canonical_subject_id=r[1],
                    evidence_claim_id=r[2],
                )
                for r in self._bounded(
                    self._rows(
                        "MATCH(a:Entity)-[r:CANONICAL_ALIAS]->(b:Entity) WHERE a.id IN $ids AND b.id IN $ids "
                        "AND coalesce(r.recorded_at,0) <= $known RETURN a.id,b.id,r.evidence_claim_id LIMIT $limit",
                        ids=subjects,
                        known=known_at,
                        limit=self.limit + 1,
                    )
                )
            ]
            if any(len(s) > 1 for s in equivalents.values())
            else []
        )
        return [
            self.view(
                c,
                at,
                known_at,
                peers=[c]
                if c["kind"] == "episode"
                else [p for key in field_keys[c["id"]] for p in by_key[key]],
                source_evidence=sources,
                subject_evidence=equivalents[c["subject_id"]],
                identity_evidence=identity,
            )
            for c in claims
        ]

    def view(
        self,
        claim,
        at,
        known_at=None,
        peers=None,
        source_evidence=None,
        subject_evidence=None,
        identity_evidence=None,
    ):
        known_at = int(time.time()) if known_at is None else known_at
        peers = self.group(claim, at, known_at=known_at) if peers is None else peers
        peers = [c for c in peers if c["recorded_at"] <= known_at]
        current = self.active(claim, at, known_at)
        supportive = [
            c
            for c in peers
            if c["value_json"] == claim["value_json"] and self.active(c, at, known_at)
        ]
        contrary = [
            c
            for c in peers
            if c["value_json"] != claim["value_json"]
            and self.active(c, at, known_at)
            and c["cardinality"] == "single"
            and claim["cardinality"] == "single"
        ]
        source_ids = list(dict.fromkeys(c["source_id"] for c in supportive)) or [
            claim["source_id"]
        ]
        contrary_source_ids = {c["source_id"] for c in contrary}
        all_source_ids = sorted(set(source_ids) | contrary_source_ids)
        sources = (
            [s for s in source_evidence if s["id"] in all_source_ids]
            if source_evidence is not None
            else [
                dict(r[0])
                for r in self._rows(
                    "MATCH(s:MemorySource) WHERE s.id IN $ids RETURN properties(s)",
                    ids=all_source_ids,
                )
            ]
        )
        contrary_groups = {
            s["evidence_group"] for s in sources if s["id"] in contrary_source_ids
        }
        sources = [s for s in sources if s["id"] in source_ids]
        accepted_sources = {c["source_id"] for c in supportive if c["accepted"]}
        contributors = [
            s for s in sources if s["id"] in accepted_sources and s["origin"] != "agent"
        ] or sources
        groups = {
            s["evidence_group"] for s in contributors if s["origin"] != "agent"
        } or ({"agent_assertions"} if contributors else set())
        latest = max(
            (s["recorded_at"] for s in contributors), default=claim["recorded_at"]
        )
        protected = claim["protected"] and current
        if not current:
            explanation = dict(score=0.0, hard_rule="not_current", fired_rules=[])
        elif protected:
            explanation = dict(
                score=1.0, hard_rule="user_confirmed_protection", fired_rules=[]
            )
        elif not self.settings.get("fuzzy_enabled", True):
            explanation = dict(
                score=0.5, hard_rule="fuzzy_disabled_control", fired_rules=[]
            )
        else:
            explanation = score_memory(
                age_seconds=max(0, at - latest),
                half_life_days=claim["half_life_days"],
                source_quality=max((s["quality"] for s in contributors), default=0.5),
                independent_groups=len(groups),
                conflicts=len(contrary_groups),
            )
        status = (
            claim.get("end_reason", "expired")
            if not current
            else "disputed"
            if contrary
            else "accepted"
            if claim["accepted"]
            else "proposed"
        )
        end_known = (
            claim.get("ended_at") is not None
            and claim.get("ended_known_at", claim["ended_at"]) <= known_at
        )
        correction_known = end_known and claim.get("end_reason") == "corrected"
        change = (
            self.claim(claim["ended_by"])
            if end_known and claim.get("ended_by")
            else None
        )
        equivalent = (
            self.equivalent_subjects(claim["subject_id"], known_at)
            if subject_evidence is None
            else subject_evidence
        )
        identity = (
            [
                i
                for i in identity_evidence
                if i["alias_subject_id"] in equivalent
                and i["canonical_subject_id"] in equivalent
            ]
            if identity_evidence is not None
            else [
                dict(
                    alias_subject_id=r[0],
                    canonical_subject_id=r[1],
                    evidence_claim_id=r[2],
                )
                for r in self._rows(
                    "MATCH(a:Entity)-[r:CANONICAL_ALIAS]->(b:Entity) WHERE a.id IN $ids "
                    "AND b.id IN $ids AND coalesce(r.recorded_at,0) <= $known RETURN a.id,b.id,r.evidence_claim_id LIMIT $limit",
                    ids=equivalent,
                    known=known_at,
                    limit=self.limit + 1,
                )
            ]
            if len(equivalent) > 1
            else []
        )
        return dict(
            claim_id=claim["id"],
            memory_id=claim["memory_id"],
            subject=claim["subject_name"],
            subject_id=claim["subject_id"],
            predicate=claim["predicate"],
            value=json.loads(claim["value_json"]),
            kind=claim["kind"],
            scope=json.loads(claim["scope_json"]),
            status=status,
            accepted=bool(claim["accepted"]),
            current_eligible=current,
            protected=protected,
            accepted_for_current_use=bool(
                claim["accepted"] and current and not contrary and not correction_known
            ),
            correction_known=correction_known,
            protected_at_creation=claim["protected"],
            fuzzy_score=explanation["score"],
            fuzzy_explanation=explanation,
            previous_score=claim.get("previous_score") if end_known else None,
            changed_by=claim.get("ended_by") if end_known else None,
            change_reason=change.get("reason") if change else None,
            conflicting_claim_ids=[c["id"] for c in contrary],
            sources=sources,
            valid_from=claim["valid_from"],
            valid_until=claim["valid_until"],
            accepted_at=claim["accepted_at"],
            ended_at=claim.get("ended_at") if end_known else None,
            reason=claim["reason"],
            historical_meaning="earlier assertion; correction does not establish historical truth"
            if correction_known
            else "source assertion; effective dates unspecified"
            if claim["valid_from"] == 0 and claim["valid_until"] == 2**63 - 1
            else "source assertion with declared validity",
            references=json.loads(claim.get("references_json", "[]")),
            identity_evidence=identity,
            evidence_path=[claim["id"], "SUPPORTED_BY", claim["source_id"]],
        )

    def selected(self, claims, at, mode, known_at=None):
        known_at = int(time.time()) if known_at is None else known_at
        result = []
        for c in claims:
            if c["recorded_at"] > known_at:
                continue
            current = self.active(c, at, known_at)
            ended = (
                c.get("ended_at") is not None
                and c["ended_at"] <= at
                and c.get("ended_known_at", c["ended_at"]) <= known_at
            ) or c["valid_until"] < at
            if (mode == "historical" and ended) or (mode != "historical" and current):
                result.append(c)
        return result

    def infer_predicate(self, query):
        words = re.sub(r"[^\w]+", " ", query.casefold()).strip()
        builtins = {
            "phone number": "phone_number",
            "phone": "phone_number",
            "mobile number": "phone_number",
            "budget": "budget",
            "preferred name": "preferred_name",
        }
        matches = []
        for label, predicate in builtins.items():
            if re.search(r"(?<!\w)" + re.escape(label) + r"(?!\w)", words):
                matches.append((len(label), predicate))
        for predicate, raw in self._rows(
            "MATCH(f:MemoryField) RETURN f.id,f.aliases LIMIT $limit",
            limit=self.limit + 1,
        ):
            for label in json.loads(raw or "[]"):
                label = re.sub(r"[^\w]+", " ", label.casefold()).strip()
                if label and re.search(
                    r"(?<!\w)" + re.escape(label) + r"(?!\w)", words
                ):
                    matches.append((len(label), predicate))
        if not matches:
            return None
        longest = max(n for n, p in matches)
        choices = {p for n, p in matches if n == longest}
        return next(iter(choices)) if len(choices) == 1 else None

    def fetch_field(self, subject, predicate, scope, at, mode, known_at=None):
        known_at = int(time.time()) if known_at is None else known_at
        subjects = self.equivalent_subjects(subject_id(subject), known_at)
        keys = [identifier("field_", [sid, predicate, scope]) for sid in subjects]
        rows = self._bounded(
            self._rows(
                "MATCH(c:MemoryClaim) WHERE c.group_key IN $keys AND c.recorded_at <= $known "
                + (
                    "AND ((c.ended_at <= $at AND coalesce(c.ended_known_at,c.ended_at) <= $known) OR c.valid_until < $at) "
                    if mode == "historical"
                    else "AND c.accepted_at <= $at AND c.valid_from <= $at AND c.valid_until >= $at AND (c.ended_at IS NULL OR c.ended_at > $at OR coalesce(c.ended_known_at,c.ended_at) > $known) "
                )
                + "RETURN properties(c) LIMIT $limit",
                keys=keys,
                at=at,
                known=known_at,
                limit=self.limit + 1,
            )
        )
        return self.selected([dict(r[0]) for r in rows], at, mode, known_at)

    def recall(
        self,
        query,
        subject,
        predicate=None,
        scope=None,
        query_time=None,
        temporal_mode="now",
        known_at=None,
    ):
        if (
            not isinstance(query, str)
            or not query.strip()
            or not isinstance(subject, str)
            or not subject.strip()
        ):
            raise ValueError("Recall needs a question and an explicit subject.")
        if temporal_mode not in {"now", "historical", "auto"}:
            raise ValueError("Invalid recall time mode.")
        at = int(time.time()) if query_time is None else query_time
        if not isinstance(at, int) or isinstance(at, bool) or not 0 <= at <= 2**63 - 1:
            raise ValueError("Query time must be a nonnegative INT64 integer.")
        if known_at is not None and (
            not isinstance(known_at, int)
            or isinstance(known_at, bool)
            or not 0 <= known_at <= 2**63 - 1
        ):
            raise ValueError("Known-at time must be a nonnegative INT64 integer.")
        if predicate is not None and (
            not isinstance(predicate, str) or not predicate.strip()
        ):
            raise ValueError("Requested field must be nonempty text.")
        scope = {} if scope is None else scope
        if not isinstance(scope, dict):
            raise ValueError("Scope must be an object.")
        canonical_json(scope)
        predicate = predicate or self.infer_predicate(query)
        if predicate is None:
            return dict(
                answer_status="unresolved_question",
                requested_predicate=None,
                evidence=[],
                warnings=[
                    "Specify the field; related text alone cannot establish an answer."
                ],
            )
        claims = self.fetch_field(
            subject, predicate, scope, at, temporal_mode, known_at
        )
        views = self.views(claims, at, known_at)
        # Keep source multiplicity in evidence, but one answer per equivalent value.
        unique = {}
        for v in sorted(
            views,
            key=lambda v: (
                v["accepted"],
                v["protected"],
                v["fuzzy_score"],
                v["claim_id"],
            ),
        ):
            unique[
                v["claim_id"]
                if v["kind"] == "episode"
                else canonical_json([v["value"], v["scope"]])
            ] = v
        views = list(unique.values())
        status = (
            "missing"
            if not views
            else "disputed"
            if any(v["status"] == "disputed" for v in views)
            else "unconfirmed"
            if any(not v["accepted"] for v in views)
            else "supported"
        )
        if any(v["correction_known"] for v in views):
            status = "historical_assertion"
        return dict(
            answer_status=status,
            subject=subject,
            requested_predicate=predicate,
            scope=scope,
            temporal_mode=temporal_mode,
            evidence=views,
            warnings=["Resolve conflicting claims before acting."]
            if status == "disputed"
            else [],
        )

    def recall_path(self, query, subject, predicates, scope=None, query_time=None):
        if (
            not isinstance(predicates, list)
            or not 1 <= len(predicates) <= 4
            or any(not isinstance(p, str) or not p.strip() for p in predicates)
        ):
            raise ValueError("An evidence path needs one to four explicit field names.")
        frontier = [subject]
        steps = []
        for index, predicate in enumerate(predicates):
            next_subjects = []
            evidence = []
            for name in frontier:
                packet = self.recall(query, name, predicate, scope, query_time)
                steps.append(
                    dict(
                        subject=name,
                        predicate=predicate,
                        answer_status=packet["answer_status"],
                        evidence=packet["evidence"],
                    )
                )
                if packet["answer_status"] != "supported":
                    return dict(
                        answer_status=packet["answer_status"],
                        steps=steps,
                        evidence=[],
                        warnings=packet["warnings"],
                    )
                evidence.extend(packet["evidence"])
                for view in packet["evidence"]:
                    next_subjects.extend(view["references"])
            if index == len(predicates) - 1:
                return dict(
                    answer_status="supported",
                    steps=steps,
                    evidence=evidence,
                    warnings=[],
                )
            frontier = list(dict.fromkeys(next_subjects))
            if not frontier:
                return dict(
                    answer_status="missing",
                    steps=steps,
                    evidence=[],
                    warnings=[
                        "The stored evidence contains no explicit next subject link."
                    ],
                )
            if len(frontier) > 16:
                raise ValueError(
                    "Evidence path branching exceeds the supported budget."
                )

    def reconcile(
        self, candidates, query, at, mode, document_ids=None, query_embedding=None
    ):
        """Replace raw versioned paragraphs with eligible field-level evidence.

        A vector hit on an old version can lead to its current version through the
        indexed field group. Explicit document scopes are never widened by this.
        """
        typed = [c for c in candidates if c.get("payload", {}).get("memory_claim_ids")]
        if not typed:
            return candidates
        # An explicitly named graph subject is an identity constraint, rather
        # than a weak similarity hint. Preserve explicitly linked companions.
        named = [
            sid
            for sid, name in self.graph.get_entity_name_index()
            if sid.startswith("subject_")
            and name
            and re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", query, re.I)
        ]
        allowed_subjects = set()
        if named:
            for sid in named:
                allowed_subjects.update(self.equivalent_subjects(sid))
            frontier = list(allowed_subjects)
            for _ in range(2):
                linked = self._bounded(
                    self._rows(
                        "MATCH(c:MemoryClaim)-[:REFERS_TO]->(e:Entity) WHERE c.subject_id IN $ids AND c.accepted=true "
                        "AND c.recorded_at <= $known AND c.accepted_at <= $at "
                        "AND ($history OR (c.valid_from <= $at AND c.valid_until >= $at AND (c.ended_at IS NULL OR c.ended_at > $at))) "
                        "RETURN DISTINCT e.id LIMIT $limit",
                        ids=frontier,
                        limit=self.limit + 1,
                        known=int(time.time()),
                        at=at,
                        history=mode == "historical",
                    )
                )
                following = set()
                for (sid,) in linked:
                    following.update(self.equivalent_subjects(sid))
                frontier = list(following - allowed_subjects)
                allowed_subjects.update(following)
                if len(allowed_subjects) > self.limit:
                    raise ValueError(
                        "Named subject expansion exceeded the declared budget."
                    )
                if not frontier:
                    break
        legacy = [
            c for c in candidates if not c.get("payload", {}).get("memory_claim_ids")
        ]
        seed_ids = list(
            dict.fromkeys(
                cid for c in typed for cid in c["payload"]["memory_claim_ids"]
            )
        )
        rows = self._bounded(
            self._rows(
                "MATCH(c:MemoryClaim) WHERE c.id IN $ids RETURN properties(c) LIMIT $limit",
                ids=seed_ids,
                limit=self.limit + 1,
            )
        )
        matched = {}
        expanded = set()
        discovery_relevance = {}
        seed_scores = {c["memory_id"]: c.get("score", 0) for c in typed}
        for row in rows:
            seed = dict(row[0])
            if allowed_subjects and seed["subject_id"] not in allowed_subjects:
                continue
            group_key = seed["id"] if seed["kind"] == "episode" else seed["group_key"]
            if group_key not in expanded:
                expanded.add(group_key)
                group_claims = self.group(seed, at, historical=mode == "historical")
            else:
                group_claims = [
                    c for c in matched.values() if c["group_key"] == seed["group_key"]
                ]
            for claim in group_claims:
                if document_ids is None or claim["memory_id"] in document_ids:
                    matched[claim["id"]] = claim
                    discovery_relevance[claim["id"]] = max(
                        discovery_relevance.get(claim["id"], 0),
                        seed_scores.get(seed["memory_id"], 0),
                    )
                if len(matched) > self.limit:
                    raise ValueError("Evidence expansion exceeded the declared limit.")
        selected = self.selected(list(matched.values()), at, mode)
        by_value = {}
        for claim, view in zip(selected, self.views(selected, at)):
            identity_subjects = {claim["subject_id"]}
            for link in view["identity_evidence"]:
                identity_subjects.update(
                    (link["alias_subject_id"], link["canonical_subject_id"])
                )
            key = canonical_json(
                [
                    sorted(identity_subjects),
                    claim["predicate"],
                    claim["scope_json"],
                    claim["value_json"],
                ]
            )
            if claim["kind"] == "episode":
                key = claim["id"]
            rank = (
                view["accepted"],
                view["protected"],
                view["fuzzy_score"],
                claim["recorded_at"],
                claim["id"],
            )
            if key not in by_value or rank > by_value[key][0]:
                by_value[key] = (rank, view)
        by_memory = defaultdict(list)
        for rank, view in by_value.values():
            by_memory[view["memory_id"]].append(view)
        seeds = {c["memory_id"]: c for c in typed}
        output = list(legacy)
        for mid, views in by_memory.items():
            point = self.vectors.get_memory(mid)
            if point is None:
                continue  # Never manufacture content from an orphaned discovery hit.
            payload = deepcopy(point["payload"])
            score = seeds.get(mid, {}).get("score", 0)
            if query_embedding is not None:
                vector = np.asarray(point["vector"], dtype=np.float32)
                denominator = float(
                    np.linalg.norm(vector) * np.linalg.norm(query_embedding)
                )
                score = (
                    float(np.dot(vector, query_embedding) / denominator)
                    if denominator
                    else 0
                )
            # A discovery hit on an old statement still identifies the same
            # field after an accepted change. Carry its relevance across that
            # explicit field link; never carry its obsolete value into output.
            score = max(
                score, max(discovery_relevance.get(v["claim_id"], 0) for v in views)
            )
            content = "\n".join(
                f"{v['subject']}: {v['predicate'].replace('_',' ').replace('.',' ')} = {v['value']}"
                + (f" (context: {canonical_json(v['scope'])})" if v["scope"] else "")
                + (f" [{v['status']}]" if v["status"] not in {"accepted"} else "")
                for v in views
            )
            payload["memory_evidence"] = views
            payload["answer_status"] = (
                "disputed"
                if any(v["status"] == "disputed" for v in views)
                else "unconfirmed"
                if any(not v["accepted"] for v in views)
                else "evidence"
            )
            boost = self.settings["reliability_weight"] * max(
                v["fuzzy_score"] for v in views
            )
            output.append(
                dict(
                    memory_id=mid,
                    text=content,
                    payload=payload,
                    score=score,
                    reliability_boost=boost,
                    graph_relevance=seeds.get(mid, {}).get("graph_relevance", 1.0),
                    retrieval_method=seeds.get(mid, {}).get(
                        "retrieval_method", "graph_revision"
                    ),
                    lifecycle_trace=dict(
                        claim_ids=[v["claim_id"] for v in views],
                        source_paths=[v["evidence_path"] for v in views],
                        discovery_memory_ids=[c["memory_id"] for c in typed],
                    ),
                    contradiction_penalty=1.0
                    if payload["answer_status"] == "disputed"
                    else 0,
                )
            )
        return output

    def graph_candidates(self, seeds, at, mode, document_ids, query_embedding, limit):
        subjects = [sid for sid in seeds if sid.startswith("subject_")]
        if not subjects:
            return []
        rows = self._rows(
            "MATCH(c:MemoryClaim) WHERE c.subject_id IN $subjects "
            "AND ($scoped=false OR c.memory_id IN $ids) RETURN DISTINCT c.memory_id LIMIT $limit",
            subjects=subjects,
            scoped=document_ids is not None,
            ids=document_ids or [],
            limit=limit,
        )
        candidates = []
        for (mid,) in rows:
            point = self.vectors.get_memory(mid)
            if point is None:
                continue
            score = 0.0
            if query_embedding is not None:
                vector = np.asarray(point["vector"], dtype=np.float32)
                denominator = float(
                    np.linalg.norm(vector) * np.linalg.norm(query_embedding)
                )
                score = (
                    float(np.dot(vector, query_embedding) / denominator)
                    if denominator
                    else 0
                )
            candidates.append(
                dict(
                    memory_id=mid,
                    text=point["payload"]["text"],
                    payload=point["payload"],
                    score=score,
                    graph_relevance=1.0,
                    retrieval_method="graph",
                )
            )
        return candidates

    def _work_watches(self, claims, requirement_context=None):
        watches = {
            canonical_json(
                dict(subject_id=c["subject_id"], scope=json.loads(c["scope_json"]))
            )
            for c in claims
        }
        if requirement_context is not None:
            watches.add(canonical_json(requirement_context))
        return [json.loads(w) for w in sorted(watches)]

    def _work_requirements(self, watches, at):
        """Discover new mandatory fields within the work's subjects and scopes.

        Group keys watch additions; exact USES edges still determine whether a
        change to an existing field affects this task. Unrelated trips do not
        enter the query. Future rules are discovered once they become active.
        """
        expanded = []
        for watch in watches:
            scope = watch["scope"]
            scopes = {canonical_json({}), canonical_json(scope)}
            if "session_id" in scope:
                scopes.add(
                    canonical_json(
                        {k: v for k, v in scope.items() if k != "session_id"}
                    )
                )
            expanded.append(
                dict(
                    subjects=self.equivalent_subjects(watch["subject_id"], at),
                    scopes=sorted(scopes),
                )
            )
        rows = self._bounded(
            self._rows(
                "UNWIND $watches AS watch MATCH(c:MemoryClaim) "
                "WHERE c.subject_id IN watch.subjects AND c.scope_json IN watch.scopes "
                "AND (c.kind IN ['rule','instruction'] OR c.protected=true) "
                "RETURN DISTINCT c.id,properties(c) LIMIT $limit",
                watches=expanded,
                limit=self.limit + 1,
            )
        )
        return [
            c
            for c in self.selected([dict(r[1]) for r in rows], at, "now", at)
            if not c["predicate"].startswith("__retracted__.")
        ]

    def register_work(
        self,
        work_id,
        claim_ids,
        depends_on=None,
        description="",
        agent_id="",
        requirement_context=None,
    ):
        if not isinstance(work_id, str) or not work_id.strip():
            raise ValueError("Work ID must be nonempty.")
        if (
            not isinstance(claim_ids, list)
            or not claim_ids
            or len(claim_ids) > 64
            or any(not isinstance(c, str) for c in claim_ids)
        ):
            raise ValueError("Work must name between one and 64 exact claim versions.")
        depends_on = [] if depends_on is None else depends_on
        if (
            not isinstance(depends_on, list)
            or len(depends_on) > 64
            or work_id in depends_on
        ):
            raise ValueError("Invalid work dependencies.")
        fingerprint_data = [
            sorted(set(claim_ids)),
            sorted(set(depends_on)),
            description,
            agent_id,
        ]
        if requirement_context is not None:
            fingerprint_data.append(requirement_context)
        fingerprint = identifier("work_", fingerprint_data)
        old = self._rows(
            "MATCH(w:MemoryWork {id:$id}) RETURN w.fingerprint", id=work_id
        )
        if old:
            if old[0][0] != fingerprint:
                raise ValueError("Work versions are immutable; use a new work ID.")
            return self.work(work_id)
        at = int(time.time())
        claims = []
        for cid in claim_ids:
            c = self.claim(cid)
            if c is None:
                raise ValueError("Work references an unknown claim.")
            v = self.view(c, at)
            if (
                not v["current_eligible"]
                or not v["accepted"]
                or v["status"] == "disputed"
            ):
                raise ValueError(
                    "Work cannot rely on inactive, disputed or unconfirmed claims."
                )
            claims.append(c)
        for wid in depends_on:
            w = self.work(wid)
            if (
                w is None
                or w["status"] == "stale"
                or w.get("validation_state") == "stale"
            ):
                raise ValueError("Work prerequisite is missing or stale.")
            if self.handoff([wid])["work"][0]["needs_review"]:
                raise ValueError("Work prerequisite evidence requires review.")
        watches = self._work_watches(claims, requirement_context)
        requirements = self._work_requirements(watches, at)
        self.ensure_schema()
        props = dict(
            id=work_id,
            description=description,
            agent_id=agent_id,
            status="ready",
            created_at=at,
            validation_state="current",
            fingerprint=fingerprint,
            used_claim_ids=canonical_json(list(dict.fromkeys(claim_ids))),
            dependency_ids=canonical_json(list(dict.fromkeys(depends_on))),
            requirement_watches_json=canonical_json(watches),
            known_requirement_fields_json=canonical_json(
                sorted({c["group_key"] for c in requirements})
            ),
        )
        self._rows("CREATE(w:MemoryWork {id:$props.id}) SET w += $props", props=props)
        self._rows(
            "MATCH(w:MemoryWork {id:$id}) UNWIND $claims AS cid MATCH(c:MemoryClaim {id:cid}) CREATE(w)-[:USES]->(c)",
            id=work_id,
            claims=list(dict.fromkeys(claim_ids)),
        )
        self._rows(
            "MATCH(w:MemoryWork {id:$id}) UNWIND $deps AS wid MATCH(p:MemoryWork {id:wid}) CREATE(w)-[:DEPENDS_ON]->(p)",
            id=work_id,
            deps=list(dict.fromkeys(depends_on)),
        )
        return self.work(work_id)

    def work(self, work_id):
        rows = self._rows(
            "MATCH(w:MemoryWork {id:$id}) RETURN properties(w)", id=work_id
        )
        return dict(rows[0][0]) if rows else None

    def complete_work(self, work_id, agent_id):
        work = self.work(work_id)
        if work is None:
            raise ValueError("Unknown work ID.")
        if work["agent_id"] and work["agent_id"] != agent_id:
            raise ValueError("Only the recorded owner can complete this work.")
        if not self.handoff([work_id])["can_continue"]:
            raise ValueError(
                "Work must be reviewed against current evidence before completion."
            )
        if work["status"] == "completed":
            return work
        self._rows(
            "MATCH(w:MemoryWork {id:$id}) SET w.status='completed',w.completed_at=$at",
            id=work_id,
            at=int(time.time()),
        )
        return self.work(work_id)

    def invalidate_work(self, claim_ids, replacement_id, reason):
        cap = self.settings["max_affected_work"]
        rows = self._rows(
            "MATCH(w:MemoryWork)-[:USES]->(c:MemoryClaim) WHERE c.id IN $ids RETURN DISTINCT w.id LIMIT $limit",
            ids=claim_ids,
            limit=cap + 1,
        )
        seen = {r[0] for r in rows}
        frontier = list(seen)
        while frontier:
            rows = self._rows(
                "MATCH(w:MemoryWork)-[:DEPENDS_ON]->(p:MemoryWork) WHERE p.id IN $ids RETURN DISTINCT w.id LIMIT $limit",
                ids=frontier,
                limit=cap + 1,
            )
            frontier = [r[0] for r in rows if r[0] not in seen]
            seen.update(frontier)
            if len(seen) > cap:
                raise ValueError(
                    "Change affects too much work for one commit; no partial invalidation is permitted."
                )
        if len(seen) > cap:
            raise ValueError("Affected-work limit reached.")
        if seen:
            self._rows(
                "MATCH(w:MemoryWork) WHERE w.id IN $ids SET w.validation_state='stale', "
                "w.status=CASE WHEN w.status='completed' THEN 'completed' ELSE 'stale' END,w.invalidated_by=$replacement,w.review_reason=$reason",
                ids=sorted(seen),
                replacement=replacement_id,
                reason=reason,
            )

    def handoff(self, work_ids):
        if (
            not isinstance(work_ids, list)
            or not 1 <= len(work_ids) <= 64
            or any(not isinstance(w, str) for w in work_ids)
        ):
            raise ValueError("Handoff needs one to 64 work IDs.")
        at = int(time.time())
        evaluated, visiting = {}, set()

        def evaluate(wid):
            if wid in evaluated:
                return evaluated[wid]
            if wid in visiting:
                raise ValueError("Cyclic work prerequisites require review.")
            if len(evaluated) + len(visiting) >= 64:
                raise ValueError("Work prerequisite review exceeds the 64-task bound.")
            visiting.add(wid)
            work = self.work(wid)
            if work is None:
                raise ValueError("Unknown work ID.")
            used = []
            current = {}
            warnings = []
            if "requirement_watches_json" not in work:
                warnings.append(
                    "Legacy work has no requirement snapshot; create a reviewed work version."
                )
            else:
                requirements = self._work_requirements(
                    json.loads(work["requirement_watches_json"]), at
                )
                known = set(json.loads(work["known_requirement_fields_json"]))
                added = [c for c in requirements if c["group_key"] not in known]
                if added:
                    warnings.append(
                        "New mandatory requirements were added; review a fresh context."
                    )
                    for c in added:
                        current[c["id"]] = self.view(c, at)
            for cid in json.loads(work["used_claim_ids"]):
                c = self.claim(cid)
                if c is None:
                    warnings.append("A used source was deleted; review required.")
                    continue
                used.append(self.view(c, at))
                for peer in self.selected(self.group(c, at), at, "now"):
                    current[peer["id"]] = self.view(peer, at)
            needs_review = (
                work["status"] == "stale"
                or work.get("validation_state") == "stale"
                or bool(warnings)
                or any(not v["current_eligible"] for v in used)
                or any(v["status"] == "disputed" for v in current.values())
            )
            prerequisites = [self.work(d) for d in json.loads(work["dependency_ids"])]
            prerequisite_reviews = {
                d["id"]: evaluate(d["id"])["needs_review"]
                for d in prerequisites
                if d is not None
            }
            needs_review = (
                needs_review
                or any(
                    d is None
                    or d["status"] == "stale"
                    or d.get("validation_state") == "stale"
                    for d in prerequisites
                )
                or any(prerequisite_reviews.values())
            )
            packet = dict(
                work=work,
                used_versions=used,
                current_evidence=list(current.values()),
                prerequisites=prerequisites,
                awaiting_prerequisites=[
                    d["id"]
                    for d in prerequisites
                    if d is not None and d["status"] != "completed"
                ],
                needs_review=needs_review,
                warnings=warnings,
                prerequisite_reviews=prerequisite_reviews,
            )
            visiting.remove(wid)
            evaluated[wid] = packet
            return packet

        packets = [evaluate(wid) for wid in work_ids]
        return dict(
            as_of=at,
            can_continue=not any(
                p["needs_review"] or p["awaiting_prerequisites"] for p in packets
            ),
            work=packets,
        )

    def remove_source(self, memory_id):
        rows = self._rows(
            "MATCH(c:MemoryClaim {memory_id:$mid}) RETURN c.id", mid=memory_id
        )
        ids = [r[0] for r in rows]
        if ids:
            self.invalidate_work(
                ids, "deleted:" + memory_id, "Used memory was explicitly deleted"
            )
        self._rows(
            "MATCH(a:Entity)-[r:CANONICAL_ALIAS]->(b:Entity) WHERE r.evidence_claim_id IN $ids DELETE r",
            ids=ids,
        )
        self._rows(
            "MATCH(c:MemoryClaim {memory_id:$mid}) DETACH DELETE c", mid=memory_id
        )
        self._rows(
            "MATCH(s:MemorySource {memory_id:$mid}) DETACH DELETE s", mid=memory_id
        )

    def counts(self):
        return {
            label: self._rows(f"MATCH(n:{label}) RETURN count(n)")[0][0]
            for label in [
                "MemorySource",
                "MemoryClaim",
                "MemoryContext",
                "MemoryField",
                "MemoryWork",
            ]
        }
