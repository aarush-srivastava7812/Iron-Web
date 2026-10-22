"""Application-owned persona and bounded, evidence-backed agent context.

This compiles data, not assistant answers. A persona cannot grant database
permissions. Memory/source text is untrusted data, never system instructions.
"""

from copy import deepcopy
import json
import math
import time
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .graph.models import canonical


class RequiredField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    subject: str = Field(min_length=1, max_length=200)
    predicate: str = Field(min_length=1, max_length=128)

    @field_validator("subject", "predicate")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Required field identifiers cannot be blank.")
        return value.strip()


class ContextProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    agent_id: str = Field(default="assistant", min_length=1, max_length=200)
    persona: str = Field(default="", max_length=16000)
    fixed_cache: tuple[str, ...] = Field(default=(), max_length=32)
    required_fields: tuple[RequiredField, ...] = Field(default=(), max_length=32)
    max_context_tokens: int = Field(default=8192, ge=256, le=65536, strict=True)
    # Model-specific query floor and near-best window, NOT truth probabilities.
    # Absolute per-item zero cutoffs discard valid negative-logit paraphrases.
    min_rerank_score: float | None = Field(default=None, allow_inf_nan=False)
    min_query_score: float = Field(default=-5.0, allow_inf_nan=False)
    score_window: float = Field(default=2.5, gt=0, allow_inf_nan=False)

    @field_validator("fixed_cache")
    @classmethod
    def bounded_rules(cls, values):
        if any(not text.strip() or len(text) > 4000 for text in values):
            raise ValueError(
                "Fixed rules must be nonblank and at most 4000 characters each."
            )
        return tuple(dict.fromkeys(text.strip() for text in values))

    @model_validator(mode="after")
    def unique_fields(self):
        keys = [(f.subject, f.predicate) for f in self.required_fields]
        if len(keys) != len(set(keys)):
            raise ValueError("Required fields must be unique.")
        if not self.agent_id.strip():
            raise ValueError("Agent ID cannot be blank.")
        return self


class ContextCapacity(ValueError):
    pass


def build_context(memory, query, scope=None, limit=None, *, request_id=None, used=True):
    """Fixed application rules + current requirements + relevant ranked data.

    Fixed rules and persona are constructor-bound. Required fields use exact
    scoped recall and cannot be replaced by a semantically similar observation.
    Only emitted memories are reinforced; duplicate source IDs occur once.
    """
    from .graph.store import ConcurrentChange
    from .vector.store import checked_text

    if not isinstance(query, str) or len(query) > 32000 or "\x00" in query:
        raise ValueError(
            "Query must be a string of at most 32000 characters without null bytes."
        )
    memory._limits(
        memory.candidate_limit, memory.result_limit if limit is None else limit
    )
    scope = json.loads(memory._scope(scope))
    if type(used) is not bool:
        raise ValueError("Used must be a boolean.")
    if request_id is not None:
        request_id = checked_text(request_id)
    started, revision = time.perf_counter(), memory.revision()
    profile, encoder = memory.profile, memory.vectors._encoder()
    packet = dict(
        fixed_cache=[
            dict(text=text, kind="application_rule", trusted=True)
            for text in profile.fixed_cache
        ],
        hot_cache=[],
        persona=profile.persona,
        similar_memory=[],
        status="ready",
        issues=[],
        metadata={},
    )
    fixed_keys = set()
    for field in profile.required_fields:
        answer = memory.recall(field.subject, field.predicate, scope, used=False)
        if answer["status"] != "supported":
            packet["issues"].append(
                dict(
                    code="required_field_" + answer["status"],
                    subject=field.subject,
                    predicate=field.predicate,
                )
            )
            continue
        evidence = [e for e in answer["evidence"] if e["accepted"]]
        ids = sorted({e["source_id"] for e in evidence})
        fixed_keys.add((field.subject, field.predicate))
        packet["fixed_cache"].append(
            dict(
                kind="required_fact",
                trusted=False,
                subject=field.subject,
                predicate=field.predicate,
                values=answer["values"],
                claim_ids=sorted(e["claim_id"] for e in evidence),
                source_ids=ids,
                text=canonical(
                    dict(
                        subject=field.subject,
                        predicate=field.predicate,
                        values=answer["values"],
                    )
                ),
            )
        )

    def token_count():
        body = {
            key: packet[key]
            for key in ("fixed_cache", "hot_cache", "persona", "similar_memory")
        }
        return len(encoder.tokenizer.encode(canonical(body)).ids) + len(
            encoder.tokenizer.encode(query).ids
        )

    tokens = token_count()
    if tokens > profile.max_context_tokens:
        raise ContextCapacity(
            "Persona, fixed requirements and query exceed the context budget; narrow the request or increase the configured budget."
        )
    rows, search_stats = [], {}
    if not query.strip():
        packet["issues"].append(dict(code="empty_query"))
    else:
        query = checked_text(query)
        if len(encoder.tokenizer.encode(query).ids) > 450:
            packet["issues"].append(dict(code="query_too_long"))
        else:
            rows = memory.search(
                query,
                scope,
                limit,
                used=False,
                validate_pins=True,
                min_score=profile.min_rerank_score,
                min_query_score=profile.min_query_score,
                score_window=profile.score_window,
            )
            search_stats = deepcopy(memory.last_search)
    accepted_rows, omitted, dropped_status, emitted_sources = [], 0, set(), set()
    represented_in_fixed = False
    for row in rows:
        sid = row["source_id"]
        if sid in emitted_sources:
            continue
        if not memory._usable(row):
            dropped_status.add(row["source_status"])
            for field in row["current_fields"]:
                if field["status"] in {"conflict", "unconfirmed"}:
                    packet["issues"].append(
                        dict(
                            code="field_" + field["status"],
                            subject=field["subject"],
                            predicate=field["predicate"],
                        )
                    )
            continue
        fields = [
            f
            for f in row["current_fields"]
            if f["status"] == "supported"
            and (f["subject"], f["predicate"]) not in fixed_keys
            and any(e["source_id"] == sid and e["accepted"] for e in f["evidence"])
        ]
        if row["current_fields"] and not fields:
            represented_in_fixed = True
            continue
        # Never repeat obsolete raw prose from a mixed current/historical source.
        text = (
            canonical(
                [
                    dict(
                        subject=f["subject"],
                        predicate=f["predicate"],
                        values=f["values"],
                    )
                    for f in fields
                ]
            )
            if fields
            else row["source_text"]
        )
        hot = bool(row["cache_eligible"])
        score = row["rerank_score"]
        if score is None or not math.isfinite(score):
            raise RuntimeError("Context requires validated finite relevance scores.")
        item = dict(
            source_id=sid,
            text=text,
            kind="current_fact" if fields else "episode",
            trusted=False,
            source_status=row["source_status"],
            fuzzy_score=1.0
            if hot
            else min(0.99, row["retention"].get("fuzzy_score", 0)),
            semantic_score=1.0 - row["distance"],
            rerank_score=score,
            score_type="cross_encoder_logit",
            fields=[
                dict(subject=f["subject"], predicate=f["predicate"], values=f["values"])
                for f in fields
            ],
            claim_ids=sorted(
                {
                    e["claim_id"]
                    for f in fields
                    for e in f["evidence"]
                    if e["source_id"] == sid and e["accepted"]
                }
            ),
        )
        key = "hot_cache" if hot else "similar_memory"
        packet[key].append(item)
        actual = token_count()
        if actual > profile.max_context_tokens:
            packet[key].pop()
            if hot:
                raise ContextCapacity(
                    "Relevant pinned memories exceed the context budget; narrow the scope or increase the configured budget."
                )
            omitted += 1
            continue
        tokens = actual
        emitted_sources.add(sid)
        accepted_rows.append(row)
    if not rows and query.strip() and not packet["issues"]:
        packet["issues"].append(dict(code="no_relevant_memory"))
    if rows and not accepted_rows and not represented_in_fixed:
        packet["issues"].append(dict(code="no_usable_memory"))
    if omitted and not accepted_rows:
        packet["issues"].append(dict(code="context_budget_exhausted"))
    packet["issues"] = [
        dict(v) for v in {canonical(i): i for i in packet["issues"]}.values()
    ]
    packet["status"] = "needs_information" if packet["issues"] else "ready"
    if used and accepted_rows and packet["status"] == "ready":
        memory._touch_results(accepted_rows, revision, request_id or uuid4().hex)
    if memory.revision() != revision:
        raise ConcurrentChange(
            "Memory changed while assembling context; retry the same request ID."
        )
    packet["metadata"] = dict(
        agent_id=profile.agent_id,
        revision=revision,
        context_tokens=tokens,
        max_context_tokens=profile.max_context_tokens,
        omitted_for_budget=omitted,
        excluded_statuses=sorted(dropped_status),
        candidate_limit=memory.candidate_limit,
        result_limit=memory.result_limit if limit is None else limit,
        search=search_stats,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
    )
    return packet
