"""Run the real two-agent/two-user travel flow, restart and mixed HTTP load."""

# ruff: noqa: E402
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import statistics
import sys
from threading import Thread
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
from memory.embeddings.embedder import Embedder
from memory.engine import MemoryEngine
from memory.shared.service import SharedMemoryService
from memory.shared.interpreter import TravelInterpreter
from shared_server import handler_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    out = args.report.resolve()
    if out.exists() or not out.is_relative_to(ROOT):
        parser.error("Choose a fresh report directory inside the workspace.")
    out.mkdir(parents=True)
    (out / ".gitignore").write_text("runtime/\n", encoding="utf-8")
    runtime = out / "runtime"
    runtime.mkdir()
    tokens, credentials = {}, []
    for tenant, actor, role in [
        ("A", "traveller", "user"),
        ("A", "planner", "agent"),
        ("A", "reviewer", "agent"),
        ("B", "traveller", "user"),
    ]:
        token = secrets.token_urlsafe(32)
        tokens[tenant, actor] = token
        credentials.append(
            dict(
                tenant=tenant,
                actor=actor,
                role=role,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
            )
        )
    namespace = "shared_demo_" + uuid.uuid4().hex[:10]
    (runtime / "service.json").write_text(
        json.dumps(
            dict(
                runtime=str(runtime),
                namespace=namespace,
                principals=credentials,
                travel_interpreter=True,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    (runtime / "credentials.json").write_text(
        json.dumps(
            [dict(tenant=t, actor=a, token=k) for (t, a), k in tokens.items()], indent=2
        ),
        encoding="utf-8",
    )
    model = Embedder(
        use_gpu=False, cache_dir="C:/Users/User/AppData/Local/Temp/fastembed_cache"
    )

    def factory(path, name):
        return MemoryEngine(
            config={"extraction_policy": "none"},
            qdrant_path=str(path),
            graph_name=name,
            embedder=model,
        )

    service = SharedMemoryService(
        runtime,
        credentials,
        namespace=namespace,
        engine_factory=factory,
        interpreter=TravelInterpreter(),
    )

    def start(current, port=0):
        server = ThreadingHTTPServer(
            ("127.0.0.1", port), handler_for(current, ROOT / "web/shared")
        )
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    server, thread = start(service)
    base = f"http://127.0.0.1:{server.server_port}"
    exchanges = []
    scope = {"trip_id": "demo-trip"}

    def call(path, body, actor="traveller", tenant="A", record=True):
        request = Request(
            base + path,
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + tokens[tenant, actor],
            },
        )
        started = time.perf_counter()
        try:
            response = urlopen(request, timeout=30)
        except HTTPError as error:
            response = error
        result = json.loads(response.read())
        status = response.code
        if record:
            exchanges.append(
                dict(
                    endpoint=path,
                    actor=actor,
                    tenant=tenant,
                    request=body,
                    status=status,
                    result=result,
                )
            )
        return status, result, (time.perf_counter() - started) * 1000

    def event(eid, text, **kw):
        tenant = kw.pop("tenant", "A")
        actor = kw.pop("actor", "traveller")
        code, result, elapsed = call(
            "/v1/events",
            dict(
                event_id=eid,
                text=text,
                subject="Traveller",
                scope=scope,
                session_id="session-" + eid,
                confirmed=actor == "traveller",
                **kw,
            ),
            actor,
            tenant,
        )
        assert code == 202, (code, result)
        return result, elapsed

    def wait(eid, tenant="A"):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            _, result, _ = call(
                "/v1/events/status", dict(eid=eid), tenant=tenant, record=False
            )
            if result["status"] in {"ready", "failed"}:
                assert result["status"] == "ready", result
                return result
            time.sleep(0.02)
        raise RuntimeError("Event did not become ready")

    def recall(predicate, tenant="A"):
        code, result, _ = call(
            "/v1/recall",
            dict(
                query="What is the " + predicate + "?",
                subject="Traveller",
                predicate=predicate,
                scope=scope,
            ),
            tenant=tenant,
        )
        assert code == 200, (code, result)
        return result

    checks = {}
    try:
        event("budget-1", "My maximum travel budget is 1000.")
        wait("budget-1")
        event("seat-1", "I prefer an aisle seat.")
        wait("seat-1")
        event(
            "procedure-1",
            "Review requirements before drafting a travel plan.",
            claims=[
                dict(
                    subject="Traveller",
                    predicate="planning_procedure",
                    kind="procedure",
                    scope=scope,
                    value={
                        "steps": [
                            "Read current requirements",
                            "Check unresolved disputes",
                            "Draft within approved constraints",
                            "Verify current evidence before handoff",
                        ]
                    },
                )
            ],
        )
        wait("procedure-1")
        budget = recall("budget")["evidence"][0]["claim_id"]
        seat = recall("seat_preference")["evidence"][0]["claim_id"]
        procedure = recall("planning_procedure")["evidence"][0]["claim_id"]
        for wid, cid in [("plan-v1", budget), ("seat-note", seat)]:
            assert (
                call(
                    "/v1/work",
                    dict(
                        work_id=wid,
                        claim_ids=[cid, procedure] if wid == "plan-v1" else [cid],
                        description="Demonstration planning work",
                    ),
                    "planner",
                )[0]
                == 200
            )
        call("/v1/work/claim", dict(work_id="plan-v1"), "planner")
        checks["one_task_owner"] = (
            call("/v1/work/claim", dict(work_id="plan-v1"), "reviewer")[0] == 409
        )
        seat_owned = call("/v1/work/claim", dict(work_id="seat-note"), "planner")[1][
            "work"
        ]
        call(
            "/v1/work/complete",
            dict(work_id="seat-note", lease_token=seat_owned["lease_token"]),
            "planner",
            record=False,
        )
        # Keep execution credentials out of published exchanges.
        for exchange in exchanges:
            if isinstance(exchange.get("result"), dict) and isinstance(
                exchange["result"].get("work"), dict
            ):
                exchange["result"]["work"].pop("lease_token", None)
        event("budget-2", "Change my travel budget to 600.")
        wait("budget-2")
        handoff = call(
            "/v1/handoff", dict(work_ids=["plan-v1", "seat-note"]), "reviewer"
        )[1]
        checks["affected_work_review"] = (
            not handoff["can_continue"] and handoff["work"][0]["needs_review"]
        )
        checks["completed_unrelated_work_retained"] = (
            handoff["work"][1]["work"]["status"] == "completed"
            and not handoff["work"][1]["needs_review"]
        )
        new = recall("budget")["evidence"][0]
        checks["accepted_change_and_protection"] = (
            new["value"] == 600 and new["fuzzy_score"] == 1
        )
        checks["procedural_memory_used"] = procedure in json.loads(
            handoff["work"][0]["work"]["used_claim_ids"]
        )
        call(
            "/v1/work",
            dict(
                work_id="plan-v2",
                claim_ids=[new["claim_id"], procedure],
                depends_on=["seat-note"],
            ),
            "reviewer",
        )
        revised = call(
            "/v1/work/claim", dict(work_id="plan-v2"), "reviewer", record=False
        )[1]["work"]
        completed = call(
            "/v1/work/complete",
            dict(work_id="plan-v2", lease_token=revised["lease_token"]),
            "reviewer",
            record=False,
        )[1]
        checks["second_agent_completes_revised_work"] = (
            completed["status"] == "completed"
        )
        checks["missing_answer"] = recall("phone_number")["answer_status"] == "missing"
        event("budget-1", "My travel budget is 300.", tenant="B")
        wait("budget-1", "B")
        checks["private_user_spaces"] = (
            recall("budget", "B")["evidence"][0]["value"] == 300
            and recall("budget")["evidence"][0]["value"] == 600
        )
        load_start = time.perf_counter()

        def submit_load(i):
            saved, latency = event(
                "load-" + str(i), "Planner checkpoint " + str(i), actor="planner"
            )
            return saved["id"], latency

        with ThreadPoolExecutor(max_workers=8) as pool:
            submissions = list(pool.map(submit_load, range(24)))
            status_reads = list(
                pool.map(
                    lambda i: call(
                        "/v1/events/status",
                        dict(eid="load-" + str(i % 24)),
                        "planner",
                        record=False,
                    )[0],
                    range(48),
                )
            )
        ready = [wait(eid) for eid, _ in submissions]
        elapsed = time.perf_counter() - load_start
        samples = sorted(latency for _, latency in submissions)
        load = dict(
            concurrent_clients=8,
            writes=24,
            status_reads=48,
            status_read_errors=sum(code != 200 for code in status_reads),
            receipt_median_ms=statistics.median(samples),
            receipt_p95_ms=samples[int(0.95 * len(samples))],
            completed_events_per_second=24 / elapsed,
            total_seconds=elapsed,
            semantic_ready_p95_ms=sorted(
                (r["ready"] - r["submitted"]) * 1000 for r in ready
            )[int(0.95 * len(ready))],
        )
        checks["mixed_http_no_lost_events"] = not load["status_read_errors"] and all(
            r["status"] == "ready" for r in ready
        )
        server.shutdown()
        server.server_close()
        thread.join()
        service.close()
        service = SharedMemoryService(
            runtime,
            credentials,
            namespace=namespace,
            engine_factory=factory,
            interpreter=TravelInterpreter(),
        )
        server, thread = start(service)
        base = f"http://127.0.0.1:{server.server_port}"
        checks["restart_preserves_memory"] = (
            recall("budget")["evidence"][0]["value"] == 600
        )
        checks["restart_preserves_completed_work"] = (
            call("/v1/handoff", dict(work_ids=["plan-v2"]), "reviewer")[1]["work"][0][
                "work"
            ]["status"]
            == "completed"
        )
        event("proposal", "My budget is 900.", actor="planner")
        wait("proposal")
        checks["agent_proposal_does_not_take_authority"] = (
            recall("budget")["answer_status"] == "disputed"
        )
        assert all(checks.values()), checks
        evidence = dict(
            checks=checks,
            load=load,
            api_url=base,
            graphs={t: service.engine(t).graph_name for t in ["A", "B"]},
            model=model.model_name,
            exchanges=exchanges,
            receipts=[service.journal.public(r) for r in service.journal.export("A")],
            scope="Explicit local demonstration. Raw travel messages use the named limited grammar. This is not a general language-model agent, actual booking, large-scale benchmark or public deployment.",
        )

        # Ensure no bearer or task-execution secrets reach the public evidence.
        def public(value):
            if isinstance(value, dict):
                return {k: public(v) for k, v in value.items() if k != "lease_token"}
            if isinstance(value, list):
                return [public(v) for v in value]
            return value

        encoded = json.dumps(public(evidence), indent=2)
        for token in tokens.values():
            assert token not in encoded
        (out / "results.json").write_text(encoded, encoding="utf-8")
        engine = service.engine("A")
        nodes = []
        for label in [
            "Entity",
            "Observation",
            "MemoryClaim",
            "MemorySource",
            "MemoryContext",
            "MemoryField",
            "MemoryWork",
        ]:
            for row in engine.graph_store.execute(
                f"MATCH(n:{label}) RETURN properties(n)"
            ).rows:
                props = dict(row[0])
                props.pop("lease_token", None)
                node = dict(id=props["id"], type=label, properties=props)
                if label == "MemoryClaim":
                    node["state"] = engine.inspect_claim(props["id"])
                nodes.append(node)
        links = [
            dict(source=r[0], target=r[1], type=r[2], properties=dict(r[3]))
            for r in engine.graph_store.execute(
                "MATCH(a)-[r]->(b) RETURN a.id,b.id,type(r),properties(r)"
            ).rows
        ]
        (out / "graph.json").write_text(
            json.dumps(
                dict(graph_name=engine.graph_name, nodes=nodes, links=links), indent=2
            ),
            encoding="utf-8",
        )
        shutil.copyfile(
            ROOT / "report/lifecycle_implementation_20261014_final/index.html",
            out / "index.html",
        )
        print(
            json.dumps(
                dict(
                    report=str(out),
                    api_url=base,
                    checks=checks,
                    load=load,
                    graphs=evidence["graphs"],
                )
            ),
            flush=True,
        )
        if args.serve:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        service.close()


if __name__ == "__main__":
    main()
