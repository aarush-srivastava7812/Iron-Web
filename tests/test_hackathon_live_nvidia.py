"""Opt-in hosted inference; memory embeddings use the declared offline fixture."""
import json
import os
from pathlib import Path

import pytest

from tests.test_application_integration import connected_app, user, trip, requirements, plan  # noqa: F401


@pytest.mark.skipif(os.getenv("VOYARA_LIVE_CHECK") != "1", reason="Opt-in NVIDIA network check")
def test_live_connected_specialists_execute_distinct_tools(connected_app, monkeypatch):  # noqa: F811
    from agents.config import settings
    monkeypatch.setattr(settings, "agent_mode", "nvidia")
    client, _ = connected_app
    headers = user(client, "live_nvidia")
    path = trip(client, headers)
    requirements(client, headers, path, end_date="2026-12-03")
    response = plan(client, headers, path)
    result = response["orchestration"]
    report = Path("report/hackathon_travel_20261017")
    report.mkdir(parents=True, exist_ok=True)
    # No request credentials, memory proofs or user data are retained.
    evidence = dict(scope="Live NVIDIA decisions, synthetic catalog, offline embedding fixture, real temporary memory stores",
                    status=result["status"], agents=result.get("agent_results", []),
                    itinerary=result.get("itinerary"), budget=result.get("budget"))
    (report / "live_nvidia.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    assert result["status"] == "ok", result.get("response")
    agents = result["agent_results"]
    assert len(agents) == 7
    assert all(r["execution"]["completed"] and r["execution"]["mode"] == "nvidia" for r in agents)
    assert len({r["execution"]["tool_calls"][0] for r in agents}) == len(agents)
    assert all(r["execution"]["temperature"] > 0 for r in agents)
    assert any("review_schedule" in r["execution"]["tool_calls"] for r in agents)
    assert client.get(path + "/plan", headers=headers).json()["version"] == 1
