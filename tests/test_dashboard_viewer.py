"""HTTP and SSE use the same fail-closed viewer boundary."""
import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from dashboard.backend import main, viewer

SECRET = "unit-test-viewer-" + "v" * 40


@pytest.fixture
def feed(monkeypatch):
    monkeypatch.delenv("DASHBOARD_VIEWER_TOKEN", raising=False)
    async def read(*args, **kwargs):
        return {"schema": "iron_web_dashboard_v1", "status": "online"}
    monkeypatch.setattr(main.relay, "read", read)


def client(host="localhost", peer="127.0.0.1", scheme="http"):
    return TestClient(main.app, base_url=f"{scheme}://{host}", client=(peer, 12345))


def test_loopback_only_default_and_forwarded_requests_fail_closed(feed):
    with client() as c:
        assert c.get("/api/dashboard/snapshot").status_code == 200
        assert c.get("/api/dashboard/stream", headers={"Forwarded": "for=remote"}).status_code == 503
    for host, peer in [("dashboard.example", "127.0.0.1"), ("localhost", "203.0.113.4")]:
        with client(host, peer) as c:
            assert c.get("/api/dashboard/snapshot").status_code == 503
            assert c.get("/api/dashboard/stream").status_code == 503
            assert c.get("/health").status_code == 200


def test_configured_gate_covers_http_sse_and_cookie_login(feed, monkeypatch):
    monkeypatch.setenv("DASHBOARD_VIEWER_TOKEN", SECRET)
    with client() as c:
        for resource in ["snapshot", "graph", "vectors", "shared-memory", "credentials", "stream"]:
            assert c.get("/api/dashboard/" + resource).status_code == 401
        denied = c.get("/api/dashboard/snapshot", headers={"Origin": "http://localhost:5174"})
        assert denied.headers["access-control-allow-origin"] == "http://localhost:5174"
        assert denied.headers["access-control-allow-credentials"] == "true"
        assert c.get("/api/dashboard/snapshot", headers={"Authorization": "Bearer " + SECRET}).status_code == 200
        assert c.post("/viewer/session", json={"secret": SECRET}).status_code == 403
        headers = {"Origin": "http://localhost"}
        assert c.post("/viewer/session", headers=headers, json={"secret": "incorrect"}).status_code == 401
        assert c.post("/viewer/session", headers=headers, json={"secret": "\u2603"}).status_code == 401
        signed = c.post("/viewer/session", headers=headers, json={"secret": SECRET})
        assert signed.status_code == 200 and SECRET not in signed.text
        assert "HttpOnly" in signed.headers["set-cookie"]
        assert c.get("/api/dashboard/snapshot").status_code == 200
        monkeypatch.setenv("DASHBOARD_VIEWER_TOKEN", SECRET + "rotated")
        assert c.get("/api/dashboard/snapshot").status_code == 401


def test_https_cookie_and_bad_config(feed, monkeypatch):
    monkeypatch.setenv("DASHBOARD_VIEWER_TOKEN", "short")
    with client() as c:
        assert c.get("/api/dashboard/snapshot").status_code == 503
    monkeypatch.setenv("DASHBOARD_VIEWER_TOKEN", SECRET)
    with client("dashboard.example", "203.0.113.4", "https") as c:
        result = c.post("/viewer/session", headers={"Origin": "https://dashboard.example"}, json={"secret": SECRET})
        assert result.status_code == 200
        assert "Secure" in result.headers["set-cookie"] and "SameSite=none" in result.headers["set-cookie"]
        assert c.get("/api/dashboard/snapshot").status_code == 200


def test_active_stream_expires_and_never_emits_memory_after_expiry(feed, monkeypatch):
    monkeypatch.setenv("DASHBOARD_VIEWER_TOKEN", SECRET)
    old = str(int(time.time()) - viewer.TTL - 1)
    cookie = old + "." + viewer.signature(SECRET, old)
    class Connected(Request):
        async def is_disconnected(self):
            return False
    request = Connected({"type": "http", "scheme": "http", "path": "/api/dashboard/stream",
                         "client": ("127.0.0.1", 1), "headers": [(b"host", b"localhost"), (b"cookie", (viewer.COOKIE + "=" + cookie).encode())]})
    async def check():
        stream = main.snapshot_events(request)
        assert "expired" in await anext(stream)
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
    asyncio.run(check())
