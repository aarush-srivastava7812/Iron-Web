"""Authenticated, coherent context snapshots over the existing service boundary."""

import base64
import hashlib
import hmac
import json
import secrets
import time

from memory.context.contracts import ContextRequest, FieldRule
from memory.lifecycle.models import canonical_json
from memory.lifecycle.service import subject_id


class ContextAccess:
    def __init__(self, service, runtime):
        self.service, self.runtime = service, runtime
        self.secret, self.boot = secrets.token_bytes(32), secrets.token_hex(16)
        self.clock = time.time
        self.resident_scopes = {}

    def purge(self, tenant, payload=None):
        def matches(scope):
            return payload is None or self.service.journal.affects_scope(payload, scope)

        self.runtime.cache.invalidate(
            lambda key: key[0] == tenant and matches(json.loads(key[4]))
        )
        if self.runtime.ranker and matches(self.resident_scopes.get(tenant)):
            self.runtime.ranker.invalidate(self.boot + ":" + tenant)

    def _allowed(self, principal):
        if principal.role != "agent" or principal.actor not in self.runtime.profiles:
            raise PermissionError(
                "Context requires an authenticated, configured agent."
            )

    @staticmethod
    def source_rows(engine, request, now):
        lifecycle = engine.lifecycle
        subjects = lifecycle.equivalent_subjects(subject_id(request.subject), int(now))
        scopes = [canonical_json({}), canonical_json(request.scope)]
        if request.session_id:
            scopes.append(
                canonical_json(dict(request.scope, session_id=request.session_id))
            )
        rows = lifecycle._bounded(
            lifecycle._rows(
                "MATCH(c:MemoryClaim)-[:SUPPORTED_BY]->(s:MemorySource) "
                "WHERE c.subject_id IN $subjects AND c.scope_json IN $scopes "
                "RETURN properties(c),properties(s) ORDER BY c.id LIMIT $limit",
                subjects=subjects,
                scopes=scopes,
                limit=lifecycle.limit + 1,
            )
        )
        return subjects, [[dict(c), dict(s)] for c, s in rows]

    def _stamp(self, principal, engine, request, now):
        subjects, rows = self.source_rows(engine, request, now)
        aliases = engine.lifecycle._bounded(
            engine.lifecycle._rows(
                "MATCH(a:Entity)-[r:CANONICAL_ALIAS]->(b:Entity) WHERE a.id IN $subjects OR b.id IN $subjects "
                "RETURN a.id,b.id,properties(r) ORDER BY a.id,b.id LIMIT $limit",
                subjects=subjects,
                limit=engine.lifecycle.limit + 1,
            )
        )
        return dict(
            graph=hashlib.sha256(
                canonical_json([subjects, rows, aliases]).encode()
            ).hexdigest(),
            events=self.service.journal.scope_fingerprint(
                principal.tenant, request.scope
            ),
            runtime=self.runtime.fingerprint,
            boot=self.boot,
        )

    @staticmethod
    def trip_rules(engine, request, now):
        """Discover scoped atomic fields, rather than a travel-name whitelist.

        Every active rule/instruction is mandatory for every trip task. Other
        saved facts remain source data. Episodes are never promoted to rules.
        Current eligibility and disputes are still decided by exact recall.
        """
        lifecycle = engine.lifecycle
        subjects = lifecycle.equivalent_subjects(subject_id(request.subject), int(now))
        scopes = [canonical_json({}), canonical_json(request.scope)]
        if request.session_id:
            scopes.append(
                canonical_json(dict(request.scope, session_id=request.session_id))
            )
        rows = lifecycle._bounded(
            lifecycle._rows(
                "MATCH(c:MemoryClaim) WHERE c.subject_id IN $subjects AND c.scope_json IN $scopes "
                "AND c.kind <> 'episode' RETURN properties(c) LIMIT $limit",
                subjects=subjects,
                scopes=scopes,
                limit=lifecycle.limit + 1,
            )
        )
        fields = {}
        for claim in lifecycle.selected(
            [dict(r[0]) for r in rows], int(now), "now", int(now)
        ):
            predicate = claim["predicate"]
            if predicate.startswith("__retracted__."):
                continue
            location = (
                "session" if "session_id" in json.loads(claim["scope_json"]) else "trip"
            )
            if claim["scope_json"] == "{}":
                location = "profile"
            if predicate == "mood":
                continue  # Mood has its own explicit inheritance/expiry policy.
            required = claim["protected"] or claim["kind"] in {"rule", "instruction"}
            if location == "profile" and not required:
                continue  # Only explicitly allowed ordinary preferences inherit.
            key = (predicate, location)
            previous = fields.get(key)
            fields[key] = FieldRule(
                predicate=predicate,
                required=required or bool(previous and previous.required),
                location=location,
                hot=bool(required),
            )
        return [fields[p] for p in sorted(fields)]

    @staticmethod
    def next_boundary(engine, now):
        # Include future claims/changes not present in a current recall answer.
        rows = engine.graph_store.execute(
            "MATCH(c:MemoryClaim) UNWIND [c.valid_from,c.accepted_at,c.ended_at,c.recorded_at,c.ended_known_at] AS boundary "
            "WITH boundary WHERE boundary > $at RETURN min(boundary)",
            {"at": now},
        ).rows
        expiry = engine.graph_store.execute(
            "MATCH(c:MemoryClaim) WHERE c.valid_until >= $at AND c.valid_until < $maximum RETURN min(c.valid_until)",
            {"at": now, "maximum": 2**63 - 1},
        ).rows
        bounds = [rows[0][0]] if rows and rows[0][0] is not None else []
        if expiry and expiry[0][0] is not None:
            bounds.append(expiry[0][0] + 1)
        return min(bounds, default=float("inf"))

    def _encode(self, payload):
        raw = canonical_json(payload).encode()
        return (
            base64.urlsafe_b64encode(raw).decode()
            + "."
            + hmac.new(self.secret, raw, hashlib.sha256).hexdigest()
        )

    def _decode(self, token, principal):
        if not isinstance(token, str) or len(token) > 16000:
            raise PermissionError("Invalid context proof.")
        try:
            encoded, signature = token.split(".")
            raw = base64.b64decode(encoded, altchars=b"-_", validate=True)
            if not hmac.compare_digest(
                signature, hmac.new(self.secret, raw, hashlib.sha256).hexdigest()
            ):
                raise ValueError("Invalid signature")
            payload = json.loads(raw)
        except (ValueError, UnicodeError) as error:
            raise PermissionError("Invalid context proof.") from error
        if payload["tenant"] != principal.tenant or payload["actor"] != principal.actor:
            raise PermissionError("Context proof belongs to another principal.")
        return payload

    def context(self, principal, **body):
        self._allowed(principal)
        request = ContextRequest.model_validate(body)
        service, runtime = self.service, self.runtime
        with service._gate(principal):
            service._ready(principal, request.scope)
            engine = service.engine(principal.tenant)
            with engine.graph_store.write_lock, engine._operation_lock:
                # Initialize the optional facade before taking the source stamp.
                _ = engine.lifecycle
                now = self.clock()
                stamp = self._stamp(principal, engine, request, now)
                key = (
                    principal.tenant,
                    principal.actor,
                    self.boot,
                    request.subject,
                    canonical_json(request.scope),
                    request.session_id,
                    request.task_type,
                    runtime.fingerprint,
                )
                cached = runtime.cache.get(key, now)
                hit = bool(cached and cached["stamp"] == stamp)
                if cached and not hit:
                    self.purge(principal.tenant, dict(scope=request.scope))
                if hit:
                    compiled = cached["compiled"]
                else:

                    def read(predicate, scope):
                        answer = engine.recall(
                            predicate,
                            request.subject,
                            predicate=predicate,
                            scope=scope,
                            query_time=int(now),
                            known_at=int(now),
                        )
                        if predicate == "mood" and "session_id" in scope:
                            subjects = engine.lifecycle.equivalent_subjects(
                                subject_id(request.subject), int(now)
                            )
                            answer["scope_has_history"] = bool(
                                engine.lifecycle._rows(
                                    "MATCH(c:MemoryClaim) WHERE c.subject_id IN $subjects AND c.scope_json=$scope "
                                    "AND c.predicate IN ['mood','__retracted__.mood'] AND c.recorded_at <= $at RETURN c.id LIMIT 1",
                                    subjects=subjects,
                                    scope=canonical_json(scope),
                                    at=int(now),
                                )
                            )
                        return answer

                    compiled = runtime.compile(
                        principal.actor,
                        request,
                        read,
                        now,
                        self.trip_rules(engine, request, now),
                    )
                    compiled["expires"] = min(
                        compiled["expires"], self.next_boundary(engine, int(now))
                    )
                    # No derived card is ingested as independent source evidence.
                    stamp = self._stamp(principal, engine, request, now)
                    runtime.cache.put(
                        key, dict(stamp=stamp, compiled=compiled), compiled["expires"]
                    )
                self.resident_scopes[principal.tenant] = request.scope
                result = runtime.assemble(
                    compiled,
                    request,
                    owner=self.boot + ":" + principal.tenant,
                    embedder=engine.embedder
                    if runtime.ranker and compiled["cards"]
                    else None,
                )
                service._ready(principal, request.scope)
                if (
                    self._stamp(principal, engine, request, now) != stamp
                    or self.clock() >= compiled["expires"]
                ):
                    self.purge(principal.tenant, dict(scope=request.scope))
                    raise RuntimeError("Context changed while it was assembled; retry.")
                expires = compiled["expires"]
                result.update(
                    cache_hit=hit,
                    expires_at=expires,
                    subject=request.subject,
                    scope=request.scope,
                    task_type=request.task_type,
                    context_token=self._encode(
                        dict(
                            tenant=principal.tenant,
                            actor=principal.actor,
                            stamp=stamp,
                            expires=expires,
                            status=result["status"],
                            claim_ids=result["claim_ids"],
                            request=dict(
                                subject=request.subject,
                                scope=request.scope,
                                task_type=request.task_type,
                                session_id=request.session_id,
                            ),
                        )
                    ),
                    cache_payload_bytes=runtime.cache.bytes,
                )
                for card in result["cards"]:
                    card.update(
                        subject=request.subject,
                        scope=request.scope,
                        generated_at=now,
                        expires_at=expires,
                        token_count=runtime.tokens.count(card["text"]),
                    )
                return result

    def validate(self, principal, context_token):
        self._allowed(principal)
        payload = self._decode(context_token, principal)
        request = ContextRequest.model_validate(payload["request"])
        service = self.service
        with service._gate(principal):
            service._ready(principal, request.scope)
            engine = service.engine(principal.tenant)
            with engine.graph_store.write_lock, engine._operation_lock:
                now = self.clock()
                valid = (
                    now < payload["expires"]
                    and self._stamp(principal, engine, request, now) == payload["stamp"]
                )
                if not valid:
                    self.purge(principal.tenant, dict(scope=request.scope))
                return dict(
                    valid=valid, status="current" if valid else "context_changed"
                )
