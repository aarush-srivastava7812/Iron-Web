import pytest
from fastapi.testclient import TestClient

from test_website import site
from app.config import settings
from app.main import app
from app.models import User

ORIGIN = "https://voyara-travel-taupe.vercel.app"
HEADERS = {"Origin": ORIGIN, "X-Voyara-Judge": "1"}


@pytest.fixture
def judge(site, monkeypatch):
    monkeypatch.setattr(settings, "judge_demo_enabled", True)
    monkeypatch.setattr(settings, "judge_demo_origins", [ORIGIN])
    monkeypatch.setattr(settings, "cookie_secure", True)
    monkeypatch.setattr(settings, "secret_key", "test-only-judge-session-secret-at-least-32")
    return TestClient(app, base_url=ORIGIN), site[-1]


def test_judges_have_separate_normal_accounts_and_secure_sessions(judge):
    client, sessions = judge
    assert client.get("/api/auth/judge/config").json() == {"enabled": True}
    first = client.post("/api/auth/judge", headers=HEADERS)
    assert first.status_code == 200, first.text
    assert first.json()["full_name"] == "Voyara Judge"
    assert all("Secure" in cookie for cookie in first.headers.get_list("set-cookie"))
    assert "HttpOnly" in first.headers.get_list("set-cookie")[0]
    assert client.get("/api/auth/me").json()["id"] == first.json()["id"]
    favorite = {"item_type": "package", "item_id": 1}
    assert client.post("/api/favorites", json=favorite).status_code == 403
    csrf = {"X-CSRF-Token": client.cookies.get("voyara_csrf")}
    assert client.post("/api/favorites", headers=csrf, json=favorite).status_code == 201
    assert len(client.get("/api/favorites").json()) == 1
    assert client.post("/api/auth/logout", headers=csrf).status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    second = client.post("/api/auth/judge", headers=HEADERS)
    assert second.status_code == 200
    assert second.json()["id"] != first.json()["id"]
    assert client.get("/api/favorites").json() == []
    with sessions() as db:
        for identity in [first.json()["id"], second.json()["id"]]:
            user = db.get(User, identity)
            assert user.role == "user"
            assert user.password_hash == "!judge-demo-session-only!"
    # Hosted demo access does not unlock the local developer account.
    assert client.get("/api/auth/developer/config").json() == {"enabled": False}
    assert client.post("/api/auth/developer", headers=HEADERS).status_code == 404


@pytest.mark.parametrize("headers", [{}, {"Origin": ORIGIN},
    {"Origin": "https://evil.example", "X-Voyara-Judge": "1"},
    {"Origin": "https://voyara-travel-taupe.vercel.app.evil.example", "X-Voyara-Judge": "1"}])
def test_judge_requires_exact_origin_and_explicit_header(judge, headers):
    client, _ = judge
    assert client.post("/api/auth/judge", headers=headers).status_code == 403


@pytest.mark.parametrize("setting,value", [("judge_demo_enabled", False),
    ("cookie_secure", False), ("judge_demo_origins", []),
    ("judge_demo_origins", ["http://example.com"]), ("secret_key", "weak")])
def test_judge_demo_fails_closed_without_hosted_configuration(judge, monkeypatch, setting, value):
    client, _ = judge
    monkeypatch.setattr(settings, setting, value)
    assert client.get("/api/auth/judge/config").json() == {"enabled": False}
    assert client.post("/api/auth/judge", headers=HEADERS).status_code == 404
