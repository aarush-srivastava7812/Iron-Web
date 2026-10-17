"""One authenticated HTTP smoke through isolated stores, plan, PDF, booking and relay."""
import asyncio
import json

import httpx

from tests.test_application_integration import connected_app, plan, requirements, trip, user  # noqa: F401
from tests.test_memory_dashboard import publish


def test_offline_trip_to_pdf_requested_booking_and_dashboard(connected_app, monkeypatch):  # noqa: F811
    from agents.config import settings
    from app.main import app as website
    import dashboard.backend.main as dashboard
    monkeypatch.setattr(settings, "agent_mode", "offline")
    monkeypatch.delenv("DASHBOARD_VIEWER_TOKEN", raising=False)
    client, runtime = connected_app
    headers = user(client, "isolated_offline_smoke")
    path = trip(client, headers)
    requirements(client, headers, path, destination="Kerala", end_date="2026-12-03", budget=200000)
    result = plan(client, headers, path)["orchestration"]
    assert result["status"] == "ok"
    assert len(result["agent_results"]) == 7
    assert all(row["execution"]["mode"] == "offline" for row in result["agent_results"])
    assert client.get(path + "/plan", headers=headers).json()["stale"] is False
    created = client.post(path + "/travel-books", headers=headers)
    assert created.status_code == 201
    pdf = client.get(created.json()["download_url"], headers=headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    catalog = client.get("/api/website/catalog").json()
    package = next(p for p in catalog["destinations"] if p["name"] == "Kashmir")
    import datetime as dt
    start = dt.date(2026, 12, 1)
    booking = client.post("/api/bookings", headers=headers, json={"items":[{
        "item_type":"package", "item_id":package["id"], "quantity":2,
        "start_date":start.isoformat(), "end_date":(start+dt.timedelta(days=package["nights"])).isoformat()}]})
    assert booking.status_code == 201 and booking.json()["status"] == "requested"
    grant = publish(monkeypatch, client, headers, path)
    relay = dashboard.MemoryRelay()
    relay.source, relay.token = "http://website", grant["Authorization"][7:]
    monkeypatch.setattr(dashboard, "relay", relay)
    async def inspect():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=website)) as source:
            relay.client = source
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=dashboard.app), base_url="http://localhost") as monitor:
                response = await monitor.get("/api/dashboard/snapshot")
                assert response.status_code == 200
                data = response.json()
                assert data["agents"]["observed"] == 8
                assert len(data["tiers"]["layers"]) == 3 and data["vectors"]["points"]
                assert "context_token" not in json.dumps(data)
    asyncio.run(inspect())
