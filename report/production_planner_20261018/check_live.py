"""Exercise the deployed planner through Vercel; never persist session secrets."""
import json
from pathlib import Path
import time

import requests

ROOT = Path(__file__).resolve().parent
ORIGIN = "https://voyara-travel-taupe.vercel.app"
session = requests.Session()
session.headers.update({"Origin": ORIGIN})
report = {"origin": ORIGIN, "checks": []}


def call(label, method, path, body=None, timeout=240):
    started = time.monotonic()
    response = session.request(method, ORIGIN + "/api" + path,
                               json=body, timeout=timeout)
    try:
        data = response.json()
    except ValueError:
        data = response.text[:1200]
    check = {"label": label, "method": method, "path": path,
             "http_status": response.status_code,
             "seconds": round(time.monotonic() - started, 3)}
    report["checks"].append(check)
    print(json.dumps(check), flush=True)
    if response.status_code >= 400:
        check["error"] = data
    (ROOT / "api_result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    response.raise_for_status()
    return data


try:
    session.headers["X-Voyara-Judge"] = "1"
    call("Judge demo sign-in", "POST", "/auth/judge")
    session.headers.pop("X-Voyara-Judge")
    session.headers["X-CSRF-Token"] = session.cookies.get("voyara_csrf")
    call("Session persists", "GET", "/auth/me")
    destinations = call("Catalog through Vercel", "GET", "/destinations")
    report["catalog_destinations"] = [d["name"] for d in destinations]
    destination = next((d["name"] for d in destinations if d["name"] == "Jaipur"), destinations[0]["name"])
    conversation = call("Create isolated test trip", "POST", "/assistant/conversations",
                        {"title": "Production planner verification 2026-10-18"})
    path = "/assistant/conversations/" + conversation["id"]
    report["conversation_id"] = conversation["id"]
    requirements = {"destination": destination, "start_date": "2026-11-12",
                    "end_date": "2026-11-15", "budget": 30000,
                    "currency": "INR", "traveller_count": 2,
                    "pace": "moderate", "interests": ["Culture", "Food"]}
    report["requirements"] = requirements
    call("Commit confirmed requirements", "PUT", path + "/requirements", requirements)
    report["confirmed_context"] = call("Read confirmed trip memory", "GET", path + "/requirements")
    result = call("Generate trip with travel agents", "POST", path + "/messages",
                  {"content": "Plan my trip", "page": "plan"})
    report["planner_response"] = result
    orchestration = result.get("orchestration", {})
    summary = {"connection_status": result.get("connection_status"),
               "status": orchestration.get("status"),
               "agents": [{"agent_id": a["agent_id"], "status": a["status"],
                           "latency_ms": a.get("latency_ms"), "execution": a.get("execution")}
                          for a in orchestration.get("agent_results", [])],
               "response": result.get("reply", {}).get("content")}
    report["summary"] = summary
    print(json.dumps(summary, ensure_ascii=True), flush=True)
    report["saved_plan"] = call("Read persisted generated draft", "GET", path + "/plan")
except Exception as error:
    report["exception"] = {"type": type(error).__name__, "message": str(error)}
    print(json.dumps(report["exception"]), flush=True)
finally:
    (ROOT / "api_result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Report: " + str(ROOT / "api_result.json"), flush=True)
