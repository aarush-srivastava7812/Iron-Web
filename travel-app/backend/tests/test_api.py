import os
import tempfile

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
    assert len(c.get("/api/destinations").json()) == 5
    cheap = c.get("/api/stays", params={"max_price": 1000}).json()
    assert cheap and all(s["price_inr"] <= 1000 for s in cheap)
    assert c.get("/api/nope").status_code == 404


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
    assert c.post(f"/api/bookings/{bid}/cancel", headers=h).json()["status"] == "cancelled"
    assert c.get("/api/transport/1").json()["seats_available"] == route["seats_available"] + 2
    assert c.post("/api/bookings", json={"items": [{"item_type": "stay", "item_id": 1}]}, headers=h).status_code == 422
