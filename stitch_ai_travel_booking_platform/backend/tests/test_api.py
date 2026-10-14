import os
import tempfile
from unittest.mock import AsyncMock

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/t.db"

from fastapi.testclient import TestClient  # noqa: E402

import seed  # noqa: E402
from app.main import app  # noqa: E402

seed.run()
c = TestClient(app)
U = {"email": "a@b.com", "username": "vansh", "password": "supersecret1"}


def auth():
    r = c.post("/api/auth/login", json={"identifier": "vansh", "password": U["password"]})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_auth_flow():
    assert c.post("/api/auth/register", json=U).status_code == 201
    assert c.post("/api/auth/register", json=U).status_code == 409
    assert c.post("/api/auth/login", json={"identifier": "vansh", "password": "wrongpass"}).status_code == 401
    assert c.get("/api/auth/me").status_code == 401
    assert c.get("/api/auth/me", headers=auth()).json()["email"] == "a@b.com"


def test_catalog_filters():
    assert len(c.get("/api/destinations").json()) >= 9
    cheap = c.get("/api/stays", params={"max_price": 1000}).json()
    assert cheap and all(s["price_inr"] <= 1000 for s in cheap)
    assert c.get("/api/destinations", params={"tag": "island"}).json()[0]["slug"] == "andaman"
    assert c.get("/api/food", params={"diet": "veg"}).json()
    assert c.get("/api/stays", params={"amenity": "breakfast"}).json()
    assert c.get("/api/guides", params={"specialty": "history"}).json()
    assert c.get("/api/nope").status_code == 404


def test_voyara_homepage():
    response = c.get("/")
    assert response.status_code == 200
    assert "Voyara — Find your somewhere" in response.text


def test_voyara_transition_assets():
    script = c.get("/transitions.js")
    stylesheet = c.get("/transitions.css")
    assert script.status_code == 200
    assert "export const travelFX" in script.text
    assert stylesheet.status_code == 200
    assert ".wipe-airplane-curtain" in stylesheet.text


def test_voyara_image_catalog():
    response = c.get("/api/images.json")
    assert response.status_code == 200
    images = response.json()
    assert len(images["destinations"]) >= 5
    assert all(image["image"].startswith("https://images.unsplash.com/") for image in images["destinations"])
    assert all("thumb" in image for image in images["stays"] + images["food"])


def test_memory_preferences_rerank_catalog_for_authenticated_user(monkeypatch):
    from app.routers.catalog import memory_bridge

    monkeypatch.setattr(
        memory_bridge,
        "get_user_long_term_preferences",
        AsyncMock(return_value={
            "budget_tier": "low",
            "dietary_choices": ["vegetarian", "local_cafes"],
            "preferred_transport": ["train"],
            "travel_style": "slow travel",
            "favorite_environments": ["mountains"],
        }),
    )
    user = {"email": "memory@example.com", "username": "memory_user", "password": "supersecret1"}
    registered = c.post("/api/auth/register", json=user)
    assert registered.status_code == 201
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    anonymous_food = c.get("/api/food")
    personalized_food = c.get("/api/food", headers=headers)
    personalized_transport = c.get("/api/transport", headers=headers)

    assert anonymous_food.status_code == 200
    assert "ai_match_score" not in anonymous_food.json()[0]
    assert personalized_food.json()[0]["kind"] == "cafe"
    assert personalized_food.json()[0]["ai_match_score"] > personalized_food.json()[-1]["ai_match_score"]
    assert personalized_transport.json()[0]["mode"] == "train"


def test_memory_service_failure_keeps_catalog_available(monkeypatch):
    from app.routers.catalog import memory_bridge
    from memory_adapter import MemoryServiceError

    monkeypatch.setattr(
        memory_bridge,
        "get_user_long_term_preferences",
        AsyncMock(side_effect=MemoryServiceError("preference service unavailable")),
    )
    user = {"email": "fallback@example.com", "username": "fallback_user", "password": "supersecret1"}
    registered = c.post("/api/auth/register", json=user)
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    response = c.get("/api/stays", headers=headers)

    assert response.status_code == 200
    assert response.headers["x-memory-status"] == "unavailable"
    assert response.json()
    assert "ai_match_score" not in response.json()[0]


def test_memory_bridge_fetches_external_preferences(monkeypatch):
    import asyncio

    import memory_adapter

    requested = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"preferences": {"travel_style": "slow_travel", "preferred_transport": ["scenic_bus"]}}

    class AsyncClient:
        def __init__(self, timeout):
            assert timeout == 5.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def get(self, url, headers):
            requested.update(url=url, headers=headers)
            return Response()

    monkeypatch.setattr(memory_adapter.httpx, "AsyncClient", AsyncClient)
    bridge = memory_adapter.CustomMemoryBridge("https://memory.example/api", "test-token")

    preferences = asyncio.run(bridge.get_user_long_term_preferences("user-123"))
    ranked = asyncio.run(bridge.filter_inventory_by_memory("user-123", [
        {"catalogKind": "transport", "mode": "flight", "description": "flight route"},
        {"catalogKind": "transport", "mode": "bus", "description": "slow travel route"},
    ]))

    assert requested["url"] == "https://memory.example/api/users/user-123/preferences"
    assert requested["headers"]["Authorization"] == "Bearer test-token"
    assert preferences == {"travel_style": "slow_travel", "preferred_transport": ["scenic_bus"]}
    assert ranked[0]["mode"] == "bus"
    assert ranked[0]["ai_match_score"] > ranked[1]["ai_match_score"]


def test_booking_and_cancel():
    h = auth()
    body = {"items": [
        {"item_type": "stay", "item_id": 1, "start_date": "2026-12-01", "end_date": "2026-12-04"},
        {"item_type": "transport", "item_id": 1, "quantity": 2},
    ]}
    r = c.post("/api/bookings", json=body, headers=h)
    assert r.status_code == 201
    stay = c.get("/api/stays/1").json()["price_inr"]
    route = c.get("/api/transport/1").json()
    assert r.json()["total_inr"] == stay * 3 + route["price_inr"] * 2
    assert c.get("/api/transport/1").json()["seats_available"] == route["seats_available"]
    bid = r.json()["id"]
    assert r.json()["status"] == "requested"
    assert c.post(f"/api/bookings/{bid}/cancel", headers=h).json()["status"] == "cancelled"
    assert c.get("/api/transport/1").json()["seats_available"] == route["seats_available"] + 2
    assert c.post("/api/bookings", json={"items": [{"item_type": "stay", "item_id": 1}]}, headers=h).status_code == 422


def test_profile_memory_and_recommendation_preferences():
    registered = c.post("/api/auth/register", json={
        "email": "profile@example.com", "username": "profile_user", "password": "supersecret1",
    })
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    defaults = c.get("/api/profile", headers=headers)
    assert defaults.status_code == 200
    assert defaults.json()["preferred_transport"] == []

    updated = c.patch("/api/profile", headers=headers, json={
        "budget_range": "Under ₹5,000",
        "travel_style": "Slow travel",
        "dietary_restrictions": ["Vegetarian"],
        "preferred_transport": ["Train"],
        "favorite_destinations": ["manali"],
    })
    assert updated.status_code == 200
    assert updated.json()["travel_style"] == "Slow travel"
    assert c.get("/api/assistant/memory", headers=headers).json()[0]["category"] == "travel_preferences"

    food = c.get("/api/food", headers=headers).json()
    routes = c.get("/api/transport", headers=headers).json()
    assert food[0]["diet"] in {"veg", "both"}
    assert routes[0]["mode"] == "train"


def test_itineraries_and_assistant_data_are_user_scoped():
    owner = c.post("/api/auth/register", json={
        "email": "trip-owner@example.com", "username": "trip_owner", "password": "supersecret1",
    }).json()
    stranger = c.post("/api/auth/register", json={
        "email": "trip-stranger@example.com", "username": "trip_stranger", "password": "supersecret1",
    }).json()
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    stranger_headers = {"Authorization": f"Bearer {stranger['access_token']}"}

    created = c.post("/api/itineraries", headers=owner_headers, json={
        "title": "A slow weekend", "destination_id": 1, "notes": "Leave room for a long lunch.",
        "booking_ids": [],
    })
    assert created.status_code == 201
    itinerary_id = created.json()["id"]
    assert c.get("/api/itineraries", headers=owner_headers).json()[0]["title"] == "A slow weekend"
    assert c.get("/api/itineraries", headers=stranger_headers).json() == []
    assert c.delete(f"/api/itineraries/{itinerary_id}", headers=stranger_headers).status_code == 404

    conversation = c.post("/api/assistant/conversations", headers=owner_headers, json={}).json()
    saved = c.post(
        f"/api/assistant/conversations/{conversation['id']}/messages",
        headers=owner_headers,
        json={"content": "I like scenic train journeys."},
    )
    assert saved.status_code == 200
    assert saved.json()["connection_status"] == "not_configured"
    assert c.get(
        f"/api/assistant/conversations/{conversation['id']}", headers=owner_headers
    ).json()["messages"][0]["content"] == "I like scenic train journeys."
    assert c.get(
        f"/api/assistant/conversations/{conversation['id']}", headers=stranger_headers
    ).status_code == 404

    snapshot = c.post("/api/assistant/memory", headers=owner_headers, json={
        "category": "favorite_route", "value": {"mode": "train"},
        "source_conversation_id": conversation["id"],
    })
    assert snapshot.status_code == 201
    assert c.get("/api/assistant/memory", headers=stranger_headers).json() == []
