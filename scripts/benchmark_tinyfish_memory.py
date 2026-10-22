"""Reproducible controlled ablation; no live provider calls or private data.

Compares an uncached Search/Fetch loop with recall reuse, and exercises evidence
guards against seeded stale, changed and unsupported quotations. This measures
local lifecycle behavior, not TinyFish quality, live latency or production ROI.
"""
# ruff: noqa: E402 -- Standalone script binds the repository's backend import root.

import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
from uuid import uuid4

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "stitch_ai_travel_booking_platform/backend")]
from agents.config import settings
from app import destination_research, external_memory as external
from app.db import Base
from app.models import (
    AIConversation,
    Destination,
    DestinationResearch,
    ExternalKnowledgeVersion,
    TripWorkspace,
    User,
)


def run():
    counters = {"search": 0, "fetch": 0}
    quote = "Museum opens at 09:00 every day."
    url = "https://tourism.example.org/jaipur"

    def transport(request):
        if request.url.host == "api.search.tinyfish.ai":
            counters["search"] += 1
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"url": url, "title": "Fixture museum", "snippet": quote}
                    ]
                },
            )
        counters["fetch"] += 1
        return httpx.Response(200, json={"results": [{"url": url, "text": quote}]})

    old_key = settings.tinyfish_api_key
    settings.tinyfish_api_key = "controlled-fixture-not-a-real-key"
    try:
        with tempfile.TemporaryDirectory(
            prefix="tinyfish-memory-ablation-"
        ) as folder, httpx.Client(transport=httpx.MockTransport(transport)) as client:
            engine = create_engine(
                "sqlite:///" + str(Path(folder) / "benchmark.sqlite")
            )
            Base.metadata.create_all(engine)
            with sessionmaker(engine, expire_on_commit=False)() as db:
                db.add(
                    User(
                        id="benchmark",
                        email="benchmark@example.test",
                        username="benchmark",
                        password_hash="unused",
                    )
                )
                db.add(
                    Destination(
                        id=1,
                        name="Jaipur",
                        slug="jaipur",
                        state="Rajasthan",
                        description="Seeded benchmark",
                        lat=26.9,
                        lng=75.8,
                    )
                )
                db.commit()
                # Baseline: repeat public source lookup for every identical request.
                for _ in range(10):
                    destination_research.retrieve(
                        "Jaipur", ["hours"], client=client, extract=False
                    )
                baseline_requests = sum(counters.values())
                counters.update(search=0, fetch=0)
                payload = destination_research.retrieve(
                    "Jaipur", ["hours"], client=client, extract=False
                )
                payload["findings"] = {
                    "hours": {
                        "statements": [
                            dict(quote=quote, source_url=url, entity_name="Museum")
                        ]
                    }
                }
                job = DestinationResearch(
                    id=str(uuid4()),
                    requested_by="benchmark",
                    destination_id=1,
                    status="completed",
                    topics=["hours"],
                    payload=payload,
                )
                db.add(job)
                db.flush()
                external.ingest(db, job)
                db.commit()
                reused = 0
                for _ in range(9):
                    recalled = external.recall(
                        db, "benchmark", 1, ["hours"], auto_refresh=False
                    )
                    reused += bool(recalled["evidence"])
                reuse_requests = sum(counters.values())
                stale_excluded = changed_flagged = unsupported_rejected = 0
                trip = AIConversation(
                    id=str(uuid4()), user_id="benchmark", title="Seeded plan"
                )
                db.add(trip)
                db.flush()
                work = TripWorkspace(
                    conversation_id=trip.id,
                    revision=1,
                    data={"draft": {"destination": "Jaipur"}, "travel": {"plan": {}}},
                )
                db.add(work)
                db.commit()
                for index in range(20):
                    value = f"Museum opens at {index:02}:30 in this seeded case."
                    item = json.loads(json.dumps(payload))
                    item["fetched_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
                    item["pages"][0]["text"] = value
                    item["findings"]["hours"]["statements"][0]["quote"] = value
                    item["expires_at"] = (
                        dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
                    ).isoformat()
                    job = DestinationResearch(
                        id=str(uuid4()),
                        requested_by="benchmark",
                        destination_id=1,
                        status="completed",
                        topics=["hours"],
                        payload=item,
                    )
                    db.add(job)
                    db.flush()
                    external.ingest(db, job)
                    db.commit()
                    stale_excluded += not bool(
                        external.recall(
                            db, "benchmark", 1, ["hours"], auto_refresh=False
                        )["evidence"]
                    )
                    if index < 10:
                        db.refresh(work)
                        changed_flagged += bool(
                            work.data["travel"].get("evidence_review_required")
                        )
                        work.data = {
                            "draft": {"destination": "Jaipur"},
                            "travel": {"plan": {}},
                        }
                        db.commit()
                for _ in range(10):
                    item = json.loads(json.dumps(payload))
                    item["fetched_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
                    item["findings"]["hours"]["statements"][0]["quote"] = (
                        "Unsupported quotation absent from the fetched fixture page."
                    )
                    job = DestinationResearch(
                        id=str(uuid4()),
                        requested_by="benchmark",
                        destination_id=1,
                        status="completed",
                        topics=["hours"],
                        payload=item,
                    )
                    db.add(job)
                    db.flush()
                    row = external.ingest(db, job)[0]
                    db.commit()
                    unsupported_rejected += not bool(row.payload["statements"])
                versions = len(list(db.scalars(select(ExternalKnowledgeVersion))))
            engine.dispose()
        report = dict(
            schema="tinyfish-memory-ablation-v1",
            generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            scope="Controlled local ablation using mock Search/Fetch transport and seeded exact source statements. No live TinyFish calls. Not a production latency, quality or cost claim.",
            baseline="Uncached Search/Fetch loop; evidence guards measured as separate seeded challenge cases, not as a claim about the previous release.",
            repeated_requests=dict(
                requests=10,
                baseline_http_requests=baseline_requests,
                memory_http_requests=reuse_requests,
                memory_reuses=reused,
                reduction_percent=round(
                    100 * (baseline_requests - reuse_requests) / baseline_requests
                ),
            ),
            stale_exclusion=dict(passed=stale_excluded, cases=20),
            changed_plan_detection=dict(passed=changed_flagged, cases=10),
            unsupported_quote_rejection=dict(passed=unsupported_rejected, cases=10),
            durable_versions=versions,
            reproduction=".venv/Scripts/python.exe scripts/benchmark_tinyfish_memory.py",
        )
        output = ROOT / "report/tinyfish_memory/benchmark.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
        print(json.dumps(report, indent=2))
        if (stale_excluded, changed_flagged, unsupported_rejected, reused) != (
            20,
            10,
            10,
            9,
        ):
            raise SystemExit("Evidence benchmark failed")
        return report
    finally:
        settings.tinyfish_api_key = old_key


if __name__ == "__main__":
    run()
