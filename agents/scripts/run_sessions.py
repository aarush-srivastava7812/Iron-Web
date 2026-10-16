"""Full multi-session run across all pages. Produces a results table.

Usage: .venv-cpu/Scripts/python.exe agents/scripts/run_sessions.py
"""
from __future__ import annotations

import json
import time
import urllib.request

AGENTS = "http://127.0.0.1:8100"
TRAVEL = "http://127.0.0.1:8000"

SCENARIOS = [
    ("s1", "Aarav",   "home",       "I want a holiday somewhere peaceful"),
    ("s2", "Aarav",   "explore",    "Suggest beach destinations in India for a relaxed week"),
    ("s3", "Diya",    "stays",      "Find a homestay in Munnar for 3 nights, budget 4000 per night"),
    ("s4", "Diya",    "food_guide", "vegetarian food places in Jaipur"),
    ("s5", "Kabir",   "tour_guide", "What should I see in Varanasi? I love heritage and culture"),
    ("s6", "Kabir",   "plan",       "Plan a 4 day trip to Goa for 2 people with a budget of 60k, relaxed pace"),
    ("s7", "Meera",   "plan",       "Plan a 3 day trip to Manali for 4 friends, adventure and trekking, budget 80k"),
    ("s8", "Meera",   "support",    "What should I pack for a 4 day trip to Manali in March?"),
    ("s9", "Rohan",   "support",    "Our train to Kochi got delayed, need to change day 2 of our plan"),
    ("s10","Sana",    "explore",    "I visited Goa last year and loved it. Where else could I go?"),
]


def post(url: str, body: dict, timeout: float = 180) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main() -> None:
    rows = []
    for i, (session, user, page, request) in enumerate(SCENARIOS, 1):
        started = time.perf_counter()
        try:
            data = post(f"{AGENTS}/agents/query", {
                "request": request, "user_id": user.lower(),
                "session_id": f"run-{session}", "page": page,
            })
            wall = int((time.perf_counter() - started) * 1000)
            agents_ran = ", ".join(sorted({r["agent_id"].replace("_agent", "").replace("_", " ")
                                           for r in data["agent_results"] if r["status"] != "skipped"}))
            failed = [r["agent_id"] for r in data["agent_results"] if r["status"] == "failed"]
            itinerary_days = len(data["itinerary"]["days"]) if data.get("itinerary") else "-"
            budget = (f"₹{data['budget']['total_inr']:,} ({data['budget']['status']})"
                      if data.get("budget") and data["budget"].get("total_inr") else "-")
            llm = any("llm" in (e.get("source") or "") or False
                      for r in data["agent_results"] for e in r.get("evidence", []))
            rows.append({
                "#": i, "session": session, "user": user, "page": page,
                "request": request[:52] + ("…" if len(request) > 52 else ""),
                "status": data["status"], "agents": agents_ran,
                "clarify": "yes" if data["status"] == "needs_clarification" else "no",
                "itinerary": itinerary_days, "budget": budget,
                "writes": len(data["memory_write_proposals"]),
                "issues": len(data["validation_issues"]),
                "failed": ", ".join(failed) or "-",
                "latency_ms": wall,
            })
        except Exception as error:
            rows.append({"#": i, "session": session, "user": user, "page": page,
                         "request": request[:52], "status": f"ERROR: {error}"})
        time.sleep(0.5)

    # Returning-user memory check: Aarav planned something in s1/s2; now ask again.
    try:
        started = time.perf_counter()
        mem = json.loads(urllib.request.urlopen(
            f"{AGENTS}/agents/memory/aarav", timeout=30).read().decode())
        rows.append({"#": "M", "session": "s1+2", "user": "Aarav", "page": "memory",
                     "request": f"{len(mem['items'])} durable memories retrieved",
                     "status": "ok" if mem["items"] else "empty",
                     "agents": "memory_gateway", "clarify": "-",
                     "itinerary": "-", "budget": "-", "writes": "-",
                     "issues": int(mem.get("truncated", False)),
                     "failed": "-", "latency_ms": int((time.perf_counter() - started) * 1000)})
    except Exception as error:
        rows.append({"#": "M", "session": "s1+2", "user": "Aarav", "page": "memory",
                     "request": "memory check", "status": f"ERROR: {error}"})

    print(json.dumps(rows, indent=2))
    with open("agents/scripts/session_results.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


if __name__ == "__main__":
    main()
