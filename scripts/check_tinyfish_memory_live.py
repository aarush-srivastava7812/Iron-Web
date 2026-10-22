"""One public Search/Fetch smoke check. Never sends private traveler data."""

# ruff: noqa: E402
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "stitch_ai_travel_booking_platform/backend")]
from app.destination_research import retrieve

started = time.perf_counter()
payload = retrieve("Jaipur", ["hours", "permits"], extract=False)
report = dict(
    provider=payload["provider"],
    mode="live public Search + Fetch; extraction disabled",
    destination="Jaipur",
    fetched_at=payload["fetched_at"],
    elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
    search_requests=1,
    fetch_requests=1,
    sources=len(payload["sources"]),
    fetched_pages=len(payload["pages"]),
    source_urls=[page["url"] for page in payload["pages"]],
    scope="Single live provider connectivity check. No memory quality, latency improvement, verified opening hours or reservation claim.",
)
output = ROOT / "report/tinyfish_memory/live-research.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8", newline="\n")
print(json.dumps(report, indent=2))
