"""Read-only views over the live owner's stores and disposable agent observations."""

import hashlib
import os
import time

from qdrant_client.models import FieldCondition, Filter, MatchAny

from memory.lifecycle.models import canonical_json
from memory.observability import public_value

GRAPH_FIELDS = {
    "id",
    "predicate",
    "value_json",
    "kind",
    "scope_json",
    "qualifiers",
    "subject_name",
    "name",
    "accepted",
    "protected",
    "action",
    "valid_from",
    "valid_until",
    "accepted_at",
    "recorded_at",
    "ended_at",
    "ended_by",
    "end_reason",
    "reason",
    "memory_id",
    "origin",
    "user_confirmed",
    "confidence",
    "status",
    "validation_state",
    "agent_id",
    "content",
    "text",
    "description",
    "timestamp",
    "importance",
    "entity_id",
    "source_memory_id",
    "created_at",
    "completed_at",
    "invalidated_by",
}


def credential_status():
    from agents.config import settings as agent_settings
    from agents.resource_manager.model_registry import inference_usage
    key = agent_settings.nvidia_api_key
    usage = inference_usage()
    configured_mode = agent_settings.agent_mode
    enabled = configured_mode == "nvidia" or (configured_mode == "auto" and bool(key))
    active = usage["requests"] > 0
    return dict(
        runtime="nvidia_tool_agents" if enabled else "offline_python",
        provider="NVIDIA NIM" if enabled else "local Python agents",
        active_credential="NVIDIA_API_KEY" if active else None,
        hosted_calls=usage["requests"], hosted_calls_scope=usage["scope"], usage=usage,
        explanation="Provider calls are observed process-wide; configuration alone does not prove a call. Context packet accounting is separate from hosted token usage.",
        configured=[dict(provider="NVIDIA NIM", variable="NVIDIA_API_KEY", configured=bool(key),
            masked=("nvapi-****" + key[-4:]) if len(key) >= 12 else ("configured (hidden)" if key else None),
            fingerprint=hashlib.sha256(key.encode()).hexdigest()[:12] if key else None,
            model=agent_settings.nim_agent_model, active=active, enabled=enabled,
            source="process environment" if os.environ.get("NVIDIA_API_KEY") else "agents/.env or root .env" if key else "not configured")],
    )


def scopes_for(trip_id):
    return [
        canonical_json({}),
        canonical_json({"trip_id": trip_id}),
        canonical_json({"trip_id": trip_id, "session_id": trip_id}),
    ]


def claim_status(claim, now):
    if not claim.get("accepted"):
        return "unaccepted"
    if claim.get("ended_at") is not None and claim["ended_at"] <= now:
        return claim.get("end_reason", "ended")
    if claim.get("valid_from", 0) > now or claim.get("accepted_at", 0) > now:
        return "future"
    if claim.get("valid_until", 2**63 - 1) < now:
        return "expired"
    if claim.get("action") == "retract":
        return "retraction"
    return "eligible_candidate"


def graph_snapshot(engine, trip_id=None, *, offset=0, limit=120, claims_only=False):
    graph = engine.graph_store
    if trip_id is None and not claims_only:
        rows = graph.execute(
            "MATCH(n) RETURN labels(n),properties(n) ORDER BY n.id SKIP $offset LIMIT $limit",
            dict(offset=offset, limit=limit + 1),
        ).rows
        nodes = []
        for labels, properties in rows[:limit]:
            props = dict(properties)
            node = dict(
                id=props["id"],
                labels=labels,
                properties={k: v for k, v in props.items() if k in GRAPH_FIELDS},
            )
            if "MemoryClaim" in labels:
                node["lifecycle_status"] = claim_status(props, int(time.time()))
            nodes.append(node)
        ids = [n["id"] for n in nodes]
        edges = (
            graph.execute(
                "MATCH(a)-[r]->(b) WHERE a.id IN $ids AND b.id IN $ids "
                "RETURN a.id,type(r),b.id ORDER BY a.id,type(r),b.id LIMIT 601",
                {"ids": ids},
            ).rows
            if ids
            else []
        )
        return dict(
            nodes=nodes,
            edges=[dict(source=a, relation=r, target=b) for a, r, b in edges[:600]],
            truncated=len(rows) > limit,
            next_offset=offset + limit if len(rows) > limit else None,
            offset=offset,
            limit=limit,
            edge_limit=600,
            edges_truncated=len(edges) > 600,
            scope="selected traveler's whole knowledge graph",
            eligibility_note="Claims include lifecycle history and candidates; agent context fields report resolved eligibility.",
            edge_scope="Relationships whose endpoints are both on this node page",
        )
    where = " WHERE c.scope_json IN $scopes" if trip_id else ""
    params = dict(scopes=scopes_for(trip_id), offset=offset, limit=limit + 1)
    claims = [
        dict(row[0])
        for row in graph.execute(
            "MATCH(c:MemoryClaim)"
            + where
            + " RETURN properties(c) ORDER BY c.recorded_at DESC,c.id SKIP $offset LIMIT $limit",
            params,
        ).rows
    ]
    truncated, claims = len(claims) > limit, claims[:limit]
    ids, now = [c["id"] for c in claims], int(time.time())
    nodes = {
        c["id"]: dict(
            id=c["id"],
            labels=["MemoryClaim"],
            properties={k: v for k, v in c.items() if k in GRAPH_FIELDS},
            lifecycle_status=claim_status(c, now),
        )
        for c in claims
    }
    edges, edge_truncated = [], False
    if ids:
        rows = graph.execute(
            "MATCH(c:MemoryClaim)-[r]->(n) WHERE c.id IN $ids "
            "AND (NOT n:MemoryClaim OR n.id IN $ids) "
            "RETURN c.id,type(r),labels(n),properties(n) ORDER BY c.id,type(r),n.id LIMIT 601",
            {"ids": ids},
        ).rows
        edge_truncated = len(rows) > 600
        for source, relation, labels, properties in rows[:600]:
            props = dict(properties)
            target = props.get("id")
            if target is None:
                continue
            nodes.setdefault(
                target,
                dict(
                    id=target,
                    labels=labels,
                    properties={k: v for k, v in props.items() if k in GRAPH_FIELDS},
                ),
            )
            edges.append(dict(source=source, target=target, relation=relation))
    return dict(
        nodes=list(nodes.values()),
        edges=edges,
        truncated=truncated,
        next_offset=offset + limit if truncated else None,
        offset=offset,
        limit=limit,
        edge_limit=600,
        edges_truncated=edge_truncated,
        scope="selected trip and inherited profile"
        if trip_id
        else "selected traveler's whole shared store",
        eligibility_note="Eligible candidates may still be disputed. Agent context fields report resolved support/conflict decisions.",
    )


def shared_memory_snapshot(engine, trip_id=None, *, offset=0, limit=120):
    graph = graph_snapshot(
        engine, trip_id, offset=offset, limit=limit, claims_only=True
    )
    return dict(
        scope=graph["scope"],
        note=graph["eligibility_note"],
        claims=[n for n in graph["nodes"] if "MemoryClaim" in n["labels"]],
        offset=offset,
        next_offset=graph["next_offset"],
        limit=limit,
    )


def vector_snapshot(
    engine, trip_id=None, *, after=None, limit=25, include_values=False
):
    store = engine.vector_store
    conditions = None
    if trip_id:
        # Profile sources have an empty session ID; no other trip's text is exposed.
        conditions = Filter(
            must=[FieldCondition(key="session_id", match=MatchAny(any=[trip_id, ""]))]
        )
    records, cursor = store.client.scroll(
        collection_name=store.collection_name,
        scroll_filter=conditions,
        limit=limit,
        offset=after,
        with_payload=True,
        with_vectors=include_values,
    )
    points = []
    for record in records:
        item = dict(id=str(record.id), payload=record.payload)
        if include_values:
            item["vector"] = record.vector
        points.append(item)
    return dict(
        collection=store.collection_name,
        mode="embedded",
        dimensions=store.dimension,
        distance=str(store.distance),
        points=points,
        next_cursor=str(cursor) if cursor is not None else None,
        values_included=include_values,
        limit=limit,
        scope="selected trip and profile sources"
        if trip_id
        else "selected traveler's whole vector store",
    )


def agent_summary(observations, context_runtime):
    events, now = observations["events"], time.time()
    rows = []
    for profile in context_runtime.profiles.values():
        used = [e for e in events if e["agent_id"] == profile.actor_id]
        reads = [e for e in used if e["kind"] == "context_assembled"]
        latest = used[-1] if used else None
        reading = bool(
            latest
            and latest["kind"] == "context_requested"
            and now - latest["timestamp"] < 60
        )
        rows.append(
            dict(
                agent_id=profile.actor_id,
                version=profile.version,
                instructions=profile.instructions,
                observed=bool(used),
                last_seen=latest["timestamp"] if latest else None,
                reading_memory=reading,
                reads_in_window=len(reads),
                cache_hits_in_window=sum(
                    bool(e["detail"].get("cache_hit")) for e in reads
                ),
            )
        )
    return dict(
        registered=len(rows),
        observed=sum(r["observed"] for r in rows),
        reading_memory=sum(r["reading_memory"] for r in rows),
        active_last_60s=sum(
            r["last_seen"] is not None and now - r["last_seen"] < 60 for r in rows
        ),
        rows=rows,
        count_scope="bounded observation window since process start, selected memory scope",
    )


def tier_snapshot(context_runtime, observations):
    policy = context_runtime.policy.model_dump()
    contexts = observations["contexts"]
    return dict(
        policy=policy,
        accounting="Exact UTF-8 bytes for the deterministic consumer"
        if context_runtime.tokens.identity == "voyara-deterministic-utf8-v1"
        else "Configured consumer tokenizer",
        tokenizer=context_runtime.tokens.identity,
        layers=[
            dict(
                tier=1,
                name="Hot context",
                storage="RAM",
                authority=False,
                description="Equal bounded halves: agent instructions and current traveler essentials.",
                per_half_budget=policy["half_tokens"],
            ),
            dict(
                tier=2,
                name="Task and mood cards",
                storage="CPU RAM / optional CUDA",
                authority=False,
                description="Source-derived task cards, selected within the card and device budgets.",
                per_card_budget=policy["card_tokens"],
                max_cards=policy["max_cards"],
            ),
            dict(
                tier=3,
                name="Durable shared memory",
                storage="FalkorDB + embedded Qdrant + receipt journal",
                authority=True,
                description="FalkorDB decides claim eligibility and lifecycle. Qdrant supports discovery; SQLite tracks receipts.",
            ),
        ],
        captured_contexts=contexts,
        templates=[t.model_dump(mode="json") for t in context_runtime.templates],
        note="Contexts come from actual agent reads; dashboard inspection does not compile or warm them.",
    )


def resource_snapshot(engine):
    # Device inspection is lazy and never initializes a model.
    from agents.resource_manager.resource_monitor import _process_rss_mb
    status = engine.get_device_status().model_dump()
    rss = _process_rss_mb()
    return dict(source="measured", scope="website process / device snapshot", ram_bytes=int(rss * 1048576) if rss is not None else None,
        vram_bytes=int(status["vram_used_mb"] * 1048576) if status.get("vram_used_mb") is not None else None,
        gpu_util=None, device=status)

def build_snapshot(traveler, trip_id=None):
    started = time.perf_counter()
    engine = traveler.service.engine(traveler.user_id)
    # Match the engine's lock order. Never take the long-running workflow lock.
    with engine.graph_store.write_lock, engine._operation_lock:
        graph = graph_snapshot(engine, trip_id)
        claims_page = shared_memory_snapshot(engine, trip_id)
        vectors = vector_snapshot(engine, trip_id)
        storage = engine.storage_status()
        with traveler.service.journal.lock:
            rows = traveler.service.journal.db.execute(
                "SELECT id,status,submitted,ready,attempts,memory_id FROM events "
                "WHERE tenant=? AND (? IS NULL OR json_extract(payload,'$.session_id')=?) "
                "ORDER BY sequence DESC LIMIT 60",
                (traveler.user_id, trip_id, trip_id),
            ).fetchall()
            receipts = [dict(row) for row in rows]
        observations = traveler.observations.snapshot(trip_id)
    context_runtime = traveler.service.context_access.runtime
    cache = context_runtime.cache
    with cache.lock:
        cache_status = dict(
            entries=len(cache.items),
            payload_bytes=cache.bytes,
            max_entries=cache.max_entries,
            max_payload_bytes=cache.max_bytes,
            scope="whole application context runtime; payload quota, not process RAM",
        )
    config = engine.config_data
    return public_value(
        dict(
            schema="iron_web_dashboard_v1",
            status="online",
            timestamp=time.time(),
            trip_id=trip_id,
            scope="trip_and_profile" if trip_id else "traveler_shared_memory",
            observations=observations,
            graph=graph,
            shared_memory=claims_page,
            vectors=vectors,
            receipts=receipts,
            storage=dict(**storage, scope="selected traveler's whole store"),
            databases=dict(
                falkordb=dict(
                    status="online",
                    graph=engine.graph_store.graph_name,
                    role="authoritative claim graph",
                    tls=config["falkordb"]["tls"],
                ),
                qdrant=dict(
                    status="online",
                    mode="embedded",
                    collection=engine.vector_store.collection_name,
                    dimensions=engine.vector_store.dimension,
                    role="vector discovery",
                ),
                journal=dict(
                    status="online", type="SQLite WAL", role="durable event receipts"
                ),
            ),
            models=dict(
                embedding=config["embeddings"]["model"],
                reranker=config["reranker"]["model"],
                reranker_enabled=config["retrieval"]["reranker_enabled"],
                extraction_policy=config["extraction_policy"],
                gpu_requested=engine.use_gpu,
            ),
            cache=cache_status,
            tiers=tier_snapshot(context_runtime, observations),
            credentials=credential_status(),
            agents=agent_summary(observations, context_runtime),
            resources=resource_snapshot(engine),
            inspection_ms=round((time.perf_counter() - started) * 1000, 2),
            notes=[
                "Observations are bounded to 500 events and contexts to 256 entries; both reset on process restart.",
                "Database counts cover the selected traveler's store; graph/vector pages may have a narrower trip scope.",
                "Lifecycle graph contents are candidates, including history. Agent field support determines current usability.",
            ],
        )
    )
