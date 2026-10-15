"""Isolated real-model memory check; no hosted generation or production writes.

Run with --report FRESH_DIR --tokenizer LOCAL_FILE [--gpu]. The tokenizer
identifies a declared plain-text consumer contract; no response model is run.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import numpy as np

from memory.cache.cards import CardRouter
from memory.context.contracts import AgentProfile
from memory.context.runtime import ContextRuntime
from memory.context.tokens import TokenBudget
from memory.embeddings.embedder import Embedder
from memory.engine import MemoryEngine
from memory.shared.service import PendingMemory, SharedMemoryService


def write(path, value):
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--tokenizer-id", required=True)
    parser.add_argument(
        "--model-cache",
        type=Path,
        default=Path(tempfile.gettempdir()) / "fastembed_cache",
    )
    parser.add_argument("--gpu", action="store_true")
    args = parser.parse_args()
    if args.report.exists() or not args.tokenizer.is_file():
        raise ValueError(
            "Use a fresh report directory and an existing local tokenizer."
        )
    args.report.mkdir(parents=True)
    run_id = uuid.uuid4().hex[:12]
    runtime_path = ROOT / "data/three_tier_checks" / run_id
    model = Embedder(use_gpu=False, cache_dir=str(args.model_cache))
    counter = TokenBudget.from_file(args.tokenizer, args.tokenizer_id)
    context_runtime = ContextRuntime(
        profiles=[
            AgentProfile(
                actor_id="planner",
                version="1",
                instructions="Plan practical trips using supported requirements.",
            ),
            AgentProfile(
                actor_id="reviewer",
                version="1",
                instructions="Review plans against current requirements.",
            ),
        ],
        tokens=counter,
        ranker=CardRouter(use_gpu=False),
    )
    keys, credentials = {}, []
    for tenant, actor, role in [
        ("A", "user", "user"),
        ("A", "planner", "agent"),
        ("A", "reviewer", "agent"),
        ("B", "user", "user"),
        ("B", "planner", "agent"),
    ]:
        token = secrets.token_hex(24)
        keys[tenant, actor] = token
        credentials.append(
            dict(
                tenant=tenant,
                actor=actor,
                role=role,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
            )
        )

    def factory(path, name):
        return MemoryEngine(
            config={"extraction_policy": "none"},
            qdrant_path=str(path),
            graph_name=name,
            embedder=model,
            use_gpu=False,
        )

    namespace = "test_tiers_" + run_id
    service = SharedMemoryService(
        runtime_path,
        credentials,
        namespace=namespace,
        engine_factory=factory,
        context_runtime=context_runtime,
        autostart=False,
    )
    request = dict(
        subject="Traveller",
        scope={"trip_id": "summer"},
        task_type="itinerary",
        query="A restful trip with beaches and vegetarian meals",
    )

    def principal(actor="planner", tenant="A"):
        return service.authenticate(keys[tenant, actor])

    def submit(eid, claims):
        service.submit(
            principal("user"),
            dict(
                event_id=eid,
                subject="Traveller",
                scope=request["scope"],
                text="Explicit demonstration fixture: " + eid,
                confirmed=True,
                claims=[
                    dict(subject="Traveller", scope=request["scope"], **c)
                    for c in claims
                ],
            ),
        )

    def drain():
        while service.process_one():
            pass

    report = dict(
        run_id=run_id,
        fixture=True,
        real_embeddings=True,
        generation_measured=False,
        tokenizer=counter.identity,
        runtime=str(runtime_path),
        namespace=namespace,
        checks={},
        timings={},
    )
    try:
        submit(
            "trip-original",
            [
                dict(predicate=p, value=v, kind="rule" if p == "budget" else "fact")
                for p, v in dict(
                    destination="Goa",
                    dates="2026-12-01 to 2026-12-05",
                    budget=100000,
                    currency="INR",
                    dietary="vegetarian",
                    pace="restful",
                    interests=["beaches", "local food"],
                    activity_preferences="Few activities with breaks",
                ).items()
            ],
        )
        drain()
        first = service.context(principal(), **request)
        assert first["status"] == "ready" and "100000" in first["traveller_text"]
        baseline_prompt, baseline_claims = first["prompt"], first["claim_ids"]
        for mode in ["uncached_equivalent", "ram_cpu"] + (
            ["ram_gpu"] if args.gpu else []
        ):
            context_runtime.ranker = CardRouter(use_gpu=mode == "ram_gpu")
            context_runtime.cache.invalidate()
            cold_start = time.perf_counter()
            cold = service.context(principal(), **request)
            cold_ms = (time.perf_counter() - cold_start) * 1000
            if mode == "ram_gpu":
                assert cold["residency"]["device"] == "cuda", cold["residency"]
            rows = []
            for _ in range(15):
                if mode == "uncached_equivalent":
                    context_runtime.cache.invalidate()
                    context_runtime.ranker.clear()
                start = time.perf_counter()
                packet = service.context(principal(), **request)
                elapsed = (time.perf_counter() - start) * 1000
                assert (
                    packet["prompt"] == baseline_prompt
                    and packet["claim_ids"] == baseline_claims
                )
                rows.append(
                    dict(
                        ms=elapsed,
                        cache_hit=packet["cache_hit"],
                        prompt_tokens=packet["tokens"]["prompt"],
                        residency=packet["residency"],
                    )
                )
            report["timings"][mode] = dict(
                cold_ms=cold_ms,
                p50_ms=float(np.percentile([r["ms"] for r in rows], 50)),
                p95_ms=float(np.percentile([r["ms"] for r in rows], 95)),
                samples=rows,
            )
        report["checks"]["same_prompt_and_evidence_all_modes"] = True
        submit(
            "budget-change",
            [
                dict(
                    predicate="budget",
                    value=60000,
                    kind="rule",
                    action="supersede",
                    reason="User lowered approved cap",
                )
            ],
        )
        try:
            service.context(principal(), **request)
            raise AssertionError("Pending change bypassed cache gate")
        except PendingMemory:
            report["checks"]["pending_change_blocks_warm_cache"] = True
        drain()
        changed = service.context(principal(), **request)
        assert (
            "60000" in changed["traveller_text"] and "100000" not in changed["prompt"]
        )
        assert not service.validate_context(principal(), first["context_token"])[
            "valid"
        ]
        report["checks"]["accepted_change_rebuilds_and_rejects_old_snapshot"] = True
        other = service.context(principal(tenant="B"), **request)
        assert other["status"] == "needs_information" and "60000" not in other["prompt"]
        report["checks"]["private_user_isolation"] = True
        service.record_work(principal(), "revised-plan", changed["claim_ids"])
        handoff = service.handoff(principal("reviewer"), ["revised-plan"])
        report["checks"]["context_dependencies_reach_handoff"] = handoff["can_continue"]
        service.forget(principal("user"), "budget-change")
        drain()
        redacted = service.context(principal(), **request)
        assert redacted["required_issues"]["budget"] == "missing"
        assert "60000" not in redacted["prompt"] and "100000" not in redacted["prompt"]
        report["checks"]["redaction_does_not_resurrect_old_budget"] = True
        for label, packet in [
            ("original", first),
            ("changed", changed),
            ("redacted", redacted),
        ]:
            # Only synthetic fixture text is exported. Never credentials or execution leases.
            write(
                args.report / (label + ".json"),
                {k: v for k, v in packet.items() if k != "context_token"},
            )
            (args.report / (label + ".md")).write_text(
                packet["prompt"], encoding="utf-8"
            )
        report["graphs"] = {
            tenant: engine.graph_name for tenant, engine in service.engines.items()
        }
        report["checks"]["all_declared_checks_pass"] = all(report["checks"].values())
        report["versions"] = {}
        for package in [
            "onnxruntime-gpu",
            "qdrant-client",
            "falkordb",
            "tokenizers",
            "fastembed-gpu",
            "fastembed",
        ]:
            try:
                report["versions"][package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                report["versions"][package] = None
        import onnxruntime as ort

        report["loaded_onnxruntime"] = dict(
            version=ort.__version__,
            module_path=ort.__file__,
            providers=ort.get_available_providers(),
        )
        report["source_sha256"] = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in [
                ROOT / "memory/context",
                ROOT / "memory/cache",
                ROOT / "memory/shared",
            ]
            for p in folder.glob("*.py")
        }
        report["limits"] = [
            "Synthetic travel fixture; no held-out study or generated-answer evaluation.",
            "15 same-query samples per mode; timings describe this local run, not general latency guarantees.",
            "Uncached equivalent uses the same assembler and card information; this is not an old-system final-answer benchmark.",
            "GPU path checks CPU scores for parity and tie handling; no claim of purely GPU execution or speedup.",
            "GPU tensor/arena accounting excludes CUDA context, library workspace and other processes.",
        ]
        write(args.report / "results.json", report)
        print(
            json.dumps(
                dict(
                    report=str(args.report.resolve()),
                    checks=report["checks"],
                    timings={
                        k: {n: v[n] for n in ["p50_ms", "p95_ms"]}
                        for k, v in report["timings"].items()
                    },
                ),
                indent=2,
            )
        )
    finally:
        service.close()


if __name__ == "__main__":
    main()
