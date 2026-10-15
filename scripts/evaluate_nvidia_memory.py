"""Live two-agent evaluation; all source messages enter one authenticated API.

Run with NVIDIA_API_KEY in the process environment, --tokenizer LOCAL_FILE,
--report FRESH_DIR and optional --gpu. No credential is saved or printed.
"""

# ruff: noqa: E402 -- set local module/DLL paths before importing model runtimes.

import argparse
from collections import defaultdict
import hashlib
from http.server import ThreadingHTTPServer
import importlib.metadata
import json
import os
from pathlib import Path
import secrets
import statistics
import subprocess
import sys
from threading import Thread
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
DLL_HANDLES = []
for directory in (ROOT / "data/evaluation_runtime").glob("*/nvidia/*/bin"):
    if os.name == "nt":
        DLL_HANDLES.append(os.add_dll_directory(str(directory.resolve())))
    os.environ["PATH"] = str(directory.resolve()) + os.pathsep + os.environ["PATH"]

import numpy as np
import psutil

from examples.nvidia_memory_agents import (
    NvidiaModel,
    TravelAgent,
    TravelIntake,
    check_plan,
)
from memory.cache.cards import CardRouter
from memory.context.contracts import AgentProfile, ContextPolicy
from memory.context.runtime import ContextRuntime
from memory.context.tokens import TokenBudget
from memory.embeddings.embedder import Embedder
from memory.engine import MemoryEngine
from memory.lifecycle.fuzzy import score_memory
from memory.lifecycle.models import canonical_json
from memory.shared.client import SharedMemoryClient, SharedRequestError
from memory.shared.service import SharedMemoryService
from shared_server import handler_for


def clean(value):
    if isinstance(value, dict):
        return {
            k: "<redacted>"
            if k in {"context_token", "lease_token", "token_hash", "api_key"}
            else clean(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(clean(value), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def distribution(samples):
    return (
        dict(
            n=len(samples),
            min_ms=min(samples),
            p50_ms=float(np.percentile(samples, 50)),
            p95_ms=float(np.percentile(samples, 95)),
            max_ms=max(samples),
            mean_ms=statistics.mean(samples),
        )
        if samples
        else dict(n=0)
    )


class TimedClient(SharedMemoryClient):
    def __init__(self, *args, records, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.records, self.actor = records, actor

    def call(self, path, **body):
        start = time.perf_counter()
        row = dict(path=path, actor=self.actor, request=clean(body))
        try:
            result = super().call(path, **body)
            row.update(
                http_status=202 if path == "/v1/events" else 200, response=clean(result)
            )
            return result
        except SharedRequestError as error:
            row.update(http_status=error.status, response=clean(error.body))
            raise
        finally:
            row["elapsed_ms"] = (time.perf_counter() - start) * 1000
            self.records.append(row)


def disk_bytes(path):
    return sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file())


def snapshot(service, runtime, tenant):
    engine = service.engine(tenant)
    with engine.graph_store.write_lock, engine._operation_lock, runtime.cache.lock:
        rows = list(runtime.cache.items.values())
        compiled = [row[0]["compiled"] for row in rows]
        cards = {c["version"]: c for item in compiled for c in item["cards"]}
        graph = engine.graph_store
        nodes = [
            dict(labels=r[0], properties=dict(r[1]))
            for r in graph.execute("MATCH(n) RETURN labels(n),properties(n)").rows
        ]
        edges = [
            dict(type=r[0], properties=dict(r[1]))
            for r in graph.execute("MATCH()-[r]->() RETURN type(r),properties(r)").rows
        ]
        points, _ = engine.vector_store.client.scroll(
            engine.vector_store.collection_name,
            limit=1000,
            with_vectors=True,
            with_payload=True,
        )
        try:
            native_bytes = graph.redis.memory_usage(graph.graph_name)
        except Exception:
            native_bytes = None
        index = runtime.ranker.index
        info = psutil.Process().memory_info()
        journal = service.root / "events.sqlite3"
        return dict(
            tier1=dict(
                cache_entries=len(compiled),
                accounted_ram_payload_bytes=runtime.cache.bytes,
                agent_text_utf8_bytes=sum(
                    len(c["agent_text"].encode()) for c in compiled
                ),
                traveller_text_utf8_bytes=sum(
                    len(c["traveller_text"].encode()) for c in compiled
                ),
                agent_tokens=sum(
                    runtime.tokens.count(c["agent_text"]) for c in compiled
                ),
                traveller_tokens=sum(
                    runtime.tokens.count(c["traveller_text"]) for c in compiled
                ),
            ),
            tier2=dict(
                unique_cached_cards=len(cards),
                cached_card_text_utf8_bytes=sum(
                    len(c["text"].encode()) for c in cards.values()
                ),
                active_catalog_cards=len(index.ids),
                cpu_matrix_bytes=index.matrix.nbytes if index.matrix is not None else 0,
                residency=index.status(),
            ),
            tier3=dict(
                graph=graph.graph_name,
                node_counts=graph.get_node_counts(),
                edge_counts=graph.get_edge_counts(),
                node_total=len(nodes),
                edge_total=len(edges),
                graph_serialized_logical_bytes=len(
                    canonical_json([nodes, edges]).encode()
                ),
                redis_reported_graph_bytes=native_bytes,
                vector_count=len(points),
                raw_vector_float32_bytes=sum(
                    np.asarray(p.vector, dtype=np.float32).nbytes for p in points
                ),
                vector_payload_json_bytes=sum(
                    len(canonical_json(p.payload).encode()) for p in points
                ),
                qdrant_directory_bytes=disk_bytes(engine.vector_store.path),
                journal_files_bytes={
                    p.name: p.stat().st_size
                    for p in journal.parent.glob("events.sqlite3*")
                },
                event_count=service.journal.db.execute(
                    "SELECT count(*) FROM events"
                ).fetchone()[0],
            ),
            process_rss_bytes=info.rss,
            process_peak_working_set_bytes=getattr(info, "peak_wset", None),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--gpu", action="store_true")
    args = parser.parse_args()
    if args.report.exists():
        raise ValueError("Use a fresh report directory.")
    key = os.environ.pop(
        "NVIDIA_API_KEY"
    )  # Keep the credential out of child environments.
    args.report.mkdir(parents=True)
    out, wall_start, http_rows = args.report.resolve(), time.perf_counter(), []
    checks, storage, ingestion, decisions, benches = {}, {}, [], {}, {}

    def model_record(row):
        save(out / "model_calls" / (row["label"] + ".json"), row)
        print(
            json.dumps(
                dict(
                    model_call=row["label"],
                    ms=round(row["elapsed_ms"], 1),
                    finish=row.get("finish_reason"),
                    error=row.get("error_type"),
                )
            ),
            flush=True,
        )

    model = NvidiaModel(key, on_record=model_record)
    del key
    tokenizer = TokenBudget.from_file(
        args.tokenizer, "NVIDIA-Nemotron-3.5-Lightning-30B-A3B"
    )
    start = time.perf_counter()
    embedder = Embedder(
        use_gpu=False, cache_dir=str(Path(os.environ["TEMP"]) / "fastembed_cache")
    )
    runtime = ContextRuntime(
        profiles=[
            AgentProfile(
                actor_id="planner",
                version="live-eval-v1",
                instructions="You are the travel planner. Respect current protected requirements; profile interests are optional. Explain choices and stop if offers cannot comply.",
            ),
            AgentProfile(
                actor_id="reviewer",
                version="live-eval-v1",
                instructions="You are the travel reviewer. Independently verify cost and every current requirement. Reject stale or unsuitable plans; preserve completed history.",
            ),
        ],
        tokens=tokenizer,
        policy=ContextPolicy(context_limit=16384, output_tokens=2200),
        ranker=CardRouter(use_gpu=args.gpu),
    )
    run_id = uuid.uuid4().hex[:10]
    private = ROOT / "data/nvidia_memory_runs" / run_id
    records, keys = [], {}
    for tenant, actor, role in [
        ("riya", "user", "user"),
        ("riya", "planner", "agent"),
        ("riya", "reviewer", "agent"),
        ("other", "planner", "agent"),
    ]:
        token = secrets.token_hex(24)
        keys[tenant, actor] = token
        records.append(
            dict(
                tenant=tenant,
                actor=actor,
                role=role,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
            )
        )
    service = SharedMemoryService(
        private,
        records,
        namespace="test_nv_" + run_id,
        interpreter=TravelIntake(model),
        autostart=True,
        context_runtime=runtime,
        engine_factory=lambda path, name: MemoryEngine(
            config={"extraction_policy": "none"},
            qdrant_path=str(path),
            graph_name=name,
            embedder=embedder,
            use_gpu=False,
        ),
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(service))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    clients = {
        actor: TimedClient(
            "http://127.0.0.1:" + str(server.server_port),
            keys["riya", actor],
            timeout=90,
            records=http_rows,
            actor=actor,
        )
        for actor in ("user", "planner", "reviewer")
    }
    other = TimedClient(
        "http://127.0.0.1:" + str(server.server_port),
        keys["other", "planner"],
        timeout=90,
        records=http_rows,
        actor="other/planner",
    )
    initialization_ms = (time.perf_counter() - start) * 1000
    fixture = json.loads((ROOT / "examples/fixtures/travel_catalog.json").read_text())
    save(out / "travel_fixture.json", fixture)
    request = dict(
        subject="Riya",
        scope={"trip_id": "goa-family"},
        task_type="itinerary",
        session_id="call-1",
        query="Prepare a compliant relaxed Goa family trip.",
    )
    agents = {
        role: TravelAgent(role, clients[role], model)
        for role in ("planner", "reviewer")
    }
    failure = None

    def ingest(eid, text, scope, actor="user", confirmed=True, pending_check=False):
        started = time.perf_counter()
        receipt = clients[actor].add_event(
            event_id=eid, text=text, subject="Riya", scope=scope, confirmed=confirmed
        )
        saved_ms = (time.perf_counter() - started) * 1000
        blocked = None
        if pending_check:
            try:
                clients["planner"].context(**request)
                blocked = False
            except SharedRequestError as error:
                blocked = error.status == 409
        clients[actor].wait_ready(eid, timeout=90)
        row = service.journal.get("riya", eid)
        prepared = json.loads(row["prepared"])
        data = dict(
            event_id=eid,
            text=text,
            subject="Riya",
            scope=scope,
            actor=actor,
            confirmed=confirmed,
            source_utf8_bytes=len(text.encode()),
            receipt_status=receipt["status"],
            receipt_ms=saved_ms,
            ready_ms=(time.perf_counter() - started) * 1000,
            interpreted_claims=prepared["claims"],
            pending_blocked=blocked,
        )
        ingestion.append(data)
        save(out / "ingestion.json", ingestion)
        save(out / "intake-normalizations.json", service.interpreter.normalizations)
        print(
            json.dumps(
                dict(
                    event=eid,
                    ready_ms=round(data["ready_ms"], 1),
                    claims=len(prepared["claims"]),
                    pending_blocked=blocked,
                )
            ),
            flush=True,
        )
        return data

    def context(label, role="planner", **override):
        packet = clients[role].context(**dict(request, **override))
        save(out / "contexts" / (label + ".json"), packet)
        (out / "contexts" / (label + ".md")).write_text(
            packet["prompt"], encoding="utf-8"
        )
        return packet

    def respond(label, role, budget, walking, draft=None):
        result = agents[role].respond(label, request, fixture, draft)
        save(out / "agents" / (label + ".json"), result)
        decisions[label] = result["output"]
        checks[label + "_context_current"] = result["status"] == "ready"
        if result["output"]:
            checks[label + "_reads_current_limits"] = (
                result["output"].get("budget_inr") == budget
                and result["output"].get("max_walk_metres") == walking
            )
            cited = result["output"].get(
                "evidence_claim_ids" if role == "planner" else "checked_claim_ids", []
            )
            checks[label + "_cites_real_evidence"] = bool(cited) and set(cited) <= set(
                result["context"]["claim_ids"]
            )
        if role == "planner" and result["output"]:
            oracle = check_plan(
                result["output"], fixture, budget=budget, walking=walking
            )
            save(out / "agents" / (label + "-oracle.json"), oracle)
            checks[label + "_all_constraints"] = all(oracle.values())
        save(
            out / "agents" / (label + "-model-checks.json"),
            result.get("model_checks", {}),
        )
        return result

    try:
        storage["empty"] = snapshot(service, runtime, "riya")
        ingest(
            "usual-preferences",
            "Usually I prefer vegetarian food, an active pace, an aisle seat, and interests in hiking, boat rides and local food.",
            {},
        )
        ingest(
            "goa-intake",
            "Plan Goa from 2026-12-10 to 2026-12-14 for two adults, departing Delhi. My total budget is INR 90000. Vegetarian food and morning flights are required. A step-free hotel is mandatory. Maximum walking is 500 metres. No boats. At most one activity per day. For this trip I want a relaxed pace, calm beaches and local food. Prefer a comfortable resort when the budget permits.",
            {"trip_id": "goa-family"},
            pending_check=True,
        )
        ingest(
            "trip-mood",
            "My current mood for this trip is relaxed.",
            {"trip_id": "goa-family"},
        )
        initial = context("initial")
        checks["initial_context_ready"] = initial["status"] == "ready"
        if initial["status"] != "ready":
            raise RuntimeError(
                "Automatic intake did not satisfy the context field contract."
            )
        checks["trip_mood_inherited"] = any(
            c["card_id"] == "relaxed" for c in initial["cards"]
        )
        checks["actual_cuda_residency"] = (
            initial["residency"]["device"] == "cuda" if args.gpu else True
        )
        for mode in ("ram_gpu" if args.gpu else "ram_cpu", "uncached_cpu", "ram_cpu"):
            runtime.ranker = CardRouter(use_gpu=(mode == "ram_gpu"))
            runtime.cache.invalidate()
            samples = []
            for index in range(13):
                if mode == "uncached_cpu":
                    runtime.cache.invalidate()
                    runtime.ranker.clear()
                tick = time.perf_counter()
                packet = clients["planner"].context(**request)
                samples.append((time.perf_counter() - tick) * 1000)
                checks["same_evidence_" + mode] = (
                    checks.get("same_evidence_" + mode, True)
                    and packet["prompt"] == initial["prompt"]
                    and packet["claim_ids"] == initial["claim_ids"]
                )
            benches[mode] = dict(
                first_ms=samples[0], warm=distribution(samples[1:]), samples_ms=samples
            )
            runtime.ranker.clear()
        runtime.ranker = CardRouter(use_gpu=args.gpu)
        runtime.cache.invalidate()
        initial = context("initial-for-agents")
        context("flight", task_type="flight")
        context("hotel", role="reviewer", task_type="hotel")
        context("initial-restored")
        storage["after_intake_and_cache_warm"] = snapshot(service, runtime, "riya")
        plan = respond("planner-initial", "planner", 90000, 500)
        review = respond("reviewer-initial", "reviewer", 90000, 500, plan["output"])
        checks["initial_reviewer_agrees_with_oracle"] = review["output"][
            "decision"
        ] == ("approve" if checks["planner-initial_all_constraints"] else "reject")
        accepted = agents["planner"].complete_reviewed(
            plan, agents["reviewer"], review, fixture, "initial-plan"
        )
        checks["only_checked_reviewed_initial_work_completed"] = (
            accepted["status"] == "completed"
        )
        budget_event = ingest(
            "lower-budget",
            "Change my total trip budget to INR 65000.",
            {"trip_id": "goa-family"},
            pending_check=True,
        )
        checks["pending_budget_blocks"] = budget_event["pending_blocked"]
        checks["old_context_proof_rejected"] = not clients["planner"].validate_context(
            plan["context"]["context_token"]
        )["valid"]
        handoff = clients["reviewer"].handoff(["initial-plan"])
        save(out / "budget-handoff.json", handoff)
        checks["completed_plan_requires_review_after_budget"] = (
            not handoff["can_continue"]
            and handoff["work"][0]["work"]["status"] == "completed"
        )
        revised = respond("planner-revised", "planner", 65000, 500)
        recheck = respond("reviewer-revised", "reviewer", 65000, 500, revised["output"])
        checks["revised_reviewer_agrees_with_oracle"] = recheck["output"][
            "decision"
        ] == ("approve" if checks["planner-revised_all_constraints"] else "reject")
        accepted = agents["planner"].complete_reviewed(
            revised, agents["reviewer"], recheck, fixture, "revised-plan"
        )
        checks["only_checked_reviewed_revised_work_completed"] = (
            accepted["status"] == "completed"
        )
        canary = dict(
            revised["output"],
            flight_id="F-LATE",
            hotel_id="H-STAIRS",
            activity_ids=["A-CRUISE"],
            budget_inr=90000,
            total_inr=50000,
        )
        canary_review = respond(
            "reviewer-negative-control", "reviewer", 65000, 500, canary
        )
        checks["reviewer_rejects_injected_bad_plan"] = (
            canary_review["output"]["decision"] == "reject"
        )
        save(
            out / "negative-control.json",
            dict(
                candidate=canary,
                origin="Deliberately corrupted by harness, not a planner model error",
            ),
        )
        walking_event = ingest(
            "walking-change",
            "Change my maximum walking distance to 50 metres.",
            {"trip_id": "goa-family"},
            pending_check=True,
        )
        checks["pending_walking_blocks"] = walking_event["pending_blocked"]
        walking_handoff = clients["reviewer"].handoff(["revised-plan"])
        save(out / "walking-handoff.json", walking_handoff)
        checks["brief_only_work_detects_walking_change"] = not walking_handoff[
            "can_continue"
        ]
        pause = respond("planner-no-suitable-hotel", "planner", 65000, 50)
        final_review = respond(
            "reviewer-no-suitable-hotel", "reviewer", 65000, 50, pause["output"]
        )
        checks["both_agents_stop_when_no_hotel_fits"] = (
            pause["output"]["decision"] == "pause"
            and final_review["output"]["decision"] == "pause"
        )
        stable = context("before-other-trip")
        ingest(
            "other-trip",
            "My Bengaluru trip is from 2027-01-10 to 2027-01-12. Its total budget is INR 18000.",
            {"trip_id": "bengaluru"},
        )
        checks["unrelated_trip_keeps_cache_warm"] = clients["planner"].context(
            **request
        )["cache_hit"]
        checks["unrelated_trip_preserves_proof"] = clients["planner"].validate_context(
            stable["context_token"]
        )["valid"]
        isolated = other.context(**request)
        checks["other_user_sees_no_trip_data"] = (
            isolated["status"] == "needs_information"
            and "65000" not in isolated["prompt"]
        )
        engine = service.engine("riya")
        preference = clients["planner"].recall(
            "seat preference", "Riya", "seat_preference", {}
        )["evidence"][0]
        before_score = preference["fuzzy_score"]
        for role in ("planner", "reviewer"):
            ingest(
                "repeated-seat-" + role,
                "I prefer an aisle seat.",
                {},
                actor=role,
                confirmed=False,
            )
        after = clients["planner"].recall(
            "seat preference", "Riya", "seat_preference", {}
        )["evidence"][0]
        checks["agent_repetitions_do_not_inflate_confidence"] = (
            abs(after["fuzzy_score"] - before_score) < 0.001
            and after["fuzzy_explanation"]["inputs"]["support"] == 1 / 3
        )
        claim = engine.lifecycle.claim(preference["claim_id"])
        at = int(time.time())
        decay = [
            dict(
                days=days,
                **engine.inspect_claim(claim["id"], query_time=at + days * 86400),
            )
            for days in (0, 30, 90, 365)
        ]
        protected = clients["planner"].recall(
            "budget", "Riya", "budget", request["scope"]
        )["evidence"][0]
        old_claims = engine.graph_store.execute(
            "MATCH(c:MemoryClaim {predicate:'budget'}) WHERE c.scope_json=$scope RETURN c.id",
            {"scope": canonical_json(request["scope"])},
        ).rows
        old_views = [
            engine.inspect_claim(row[0])
            for row in old_claims
            if row[0] != protected["claim_id"]
        ]
        controls = {
            name: score_memory(
                age_seconds=age,
                half_life_days=90,
                source_quality=quality,
                independent_groups=groups,
                conflicts=conflicts,
            )
            for name, age, quality, groups, conflicts in [
                ("fresh_one_source", 0, 0.9, 1, 0),
                ("three_independent_sources", 0, 0.9, 3, 0),
                ("conflicting_source", 0, 0.9, 1, 1),
                ("older_90_days", 90 * 86400, 0.9, 1, 0),
                ("lower_quality", 0, 0.4, 1, 0),
            ]
        }
        checks["ordinary_preference_decays"] = all(
            a["fuzzy_score"] > b["fuzzy_score"] for a, b in zip(decay, decay[1:])
        )
        checks["protected_budget_stays_one"] = (
            engine.inspect_claim(protected["claim_id"], query_time=at + 365 * 86400)[
                "fuzzy_score"
            ]
            == 1
        )
        checks["superseded_budget_score_zero"] = bool(old_views) and all(
            v["fuzzy_score"] == 0 for v in old_views
        )
        base = controls["fresh_one_source"]["score"]
        checks["fuzzy_sensitivity_directions"] = (
            controls["three_independent_sources"]["score"]
            > base
            > controls["conflicting_source"]["score"]
            and base > controls["lower_quality"]["score"]
            and base > controls["older_90_days"]["score"]
        )
        save(
            out / "fuzzy-results.json",
            dict(
                actual_before=preference,
                actual_after_agent_repetition=after,
                actual_time_controls=decay,
                current_protected_budget=protected,
                old_budget_views=old_views,
                mathematical_controls=controls,
            ),
        )
        tick = time.perf_counter()
        hits = clients["planner"].call(
            "/v1/search",
            query="Goa vegetarian relaxed family walking boats budget",
            k=5,
            retrieval_mode="hybrid",
            temporal_mode="now",
        )
        benches["hybrid_search_single_ms"] = (time.perf_counter() - tick) * 1000
        save(out / "hybrid-search.json", hits)
        checks["durable_hybrid_returns_evidence"] = bool(hits)
        final_context = context("final-memory")
        storage["after_full_scenario"] = snapshot(service, runtime, "riya")
        source = dict(
            engine.graph_store.execute(
                "MATCH(s:MemorySource) RETURN properties(s) LIMIT 1"
            ).rows[0][0]
        )
        point = engine.vector_store.get_memory(source["memory_id"])
        save(
            out / "metadata-sample.json",
            dict(
                source=source,
                claim=engine.lifecycle.claim(protected["claim_id"]),
                vector_payload=point["payload"],
                context=final_context,
                work=engine.lifecycle.work("revised-plan"),
                journal_receipt=service.journal.public(
                    service.journal.get("riya", "goa-intake")
                ),
            ),
        )
        # Cold restart verifies tier 1/2 are derivatives and tier 3 is durable.
        service.close()
        checks["volatile_tiers_cleared_on_close"] = (
            runtime.cache.bytes == 0 and runtime.ranker.index.device_matrix is None
        )
        reopened = SharedMemoryService(
            private,
            records,
            namespace=service.namespace,
            interpreter=service.interpreter,
            autostart=False,
            context_runtime=runtime,
            engine_factory=lambda path, name: MemoryEngine(
                config={"extraction_policy": "none"},
                qdrant_path=str(path),
                graph_name=name,
                embedder=embedder,
                use_gpu=False,
            ),
        )
        service.__dict__ = reopened.__dict__
        storage["after_restart_before_context"] = snapshot(service, runtime, "riya")
        rebuilt = context("after-restart")
        checks["restart_rebuilds_from_durable_memory"] = (
            not rebuilt["cache_hit"]
            and rebuilt["status"] == "ready"
            and "65000" in rebuilt["prompt"]
            and "[50]" in rebuilt["prompt"]
        )
        storage["after_restart_rebuilt"] = snapshot(service, runtime, "riya")
    except Exception as error:
        failure = dict(
            type=type(error).__name__,
            message=str(error)
            if not hasattr(error, "response")
            else "Provider request failed; see safe call metrics",
        )
        print(json.dumps(dict(run_error=failure)), flush=True)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        service.close()
        save(out / "storage.json", storage)
        save(out / "http-transcript.json", http_rows)
        save(out / "model-latency.json", model.records)
        save(out / "decisions.json", decisions)
        save(out / "ingestion.json", ingestion)
        elapsed_ms = (time.perf_counter() - wall_start) * 1000
        latency = defaultdict(list)
        for row in http_rows:
            latency[row["path"]].append(row["elapsed_ms"])
        calls = [r["elapsed_ms"] for r in model.records]
        claims_count = sum(len(row["interpreted_claims"]) for row in ingestion)
        results = dict(
            model=model.model,
            run_id=run_id,
            failure=failure,
            checks=checks,
            counts=dict(
                passed=sum(v is True for v in checks.values()),
                failed=sum(v is not True for v in checks.values()),
            ),
            elapsed_ms=elapsed_ms,
            initialization_ms=initialization_ms,
            model_calls=len(model.records),
            model_latency=distribution(calls),
            sum_model_call_ms=sum(calls),
            memory_benchmarks=benches,
            local_http_latency={
                path: distribution(values) for path, values in latency.items()
            },
            ingestion_events=len(ingestion),
            interpreted_claims=claims_count,
            ingested_source_utf8_bytes=sum(
                row["source_utf8_bytes"] for row in ingestion
            ),
            storage_final=storage.get("after_full_scenario"),
            gpu_requested=args.gpu,
            consumer_tokenizer=tokenizer.identity,
            versions={
                name: importlib.metadata.version(name)
                for name in ["openai", "tokenizers", "qdrant-client", "falkordb"]
            },
            api_base="https://integrate.api.nvidia.com/v1",
            source_commit=subprocess.check_output(
                ["git", "-c", "safe.directory=" + ROOT.as_posix(), "rev-parse", "HEAD"],
                cwd=ROOT,
                text=True,
            ).strip(),
            source_dirty=bool(
                subprocess.check_output(
                    [
                        "git",
                        "-c",
                        "safe.directory=" + ROOT.as_posix(),
                        "diff",
                        "--name-only",
                    ],
                    cwd=ROOT,
                    text=True,
                ).strip()
            ),
            agent_decision_sources={
                p.stem: json.loads(p.read_text(encoding="utf-8")).get("decision_source")
                for p in (out / "agents").glob("*.json")
                if "-oracle" not in p.stem and "-model-checks" not in p.stem
            },
            physical_disk_after_close_bytes=disk_bytes(private),
            api_usage=[
                dict(label=r["label"], usage=r.get("usage")) for r in model.records
            ],
            limits=[
                "One synthetic travel task; one run, no statistical answer-quality claim.",
                "Same hosted model serves distinct planner/reviewer contexts; correlated errors remain possible.",
                "Schema-guided intake and role/card definitions are application configuration; no autonomous persona invention.",
                "Tier 1 and 2 are overlapping derivatives of tier 3, not disjoint source partitions.",
                "Tier 2 CUDA stores card vectors; card text remains in host memory and is sent to the hosted model.",
                "RAM bytes are cache-accounted payload, not all Python/model memory; GPU provider/context overhead is separate.",
                "Local token counts cover the memory prompt; provider usage includes complete chat formatting and the fixture catalog.",
            ],
        )
        save(out / "results.json", results)
        save(
            out / "source-hashes.json",
            {
                str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for directory in (ROOT / "memory",)
                for p in directory.rglob("*.py")
            },
        )
        print(
            json.dumps(
                dict(
                    report=str(out),
                    checks=results["counts"],
                    elapsed_ms=elapsed_ms,
                    failure=failure,
                )
            ),
            flush=True,
        )
    return int(failure is not None or any(v is not True for v in checks.values()))


if __name__ == "__main__":
    raise SystemExit(main())
