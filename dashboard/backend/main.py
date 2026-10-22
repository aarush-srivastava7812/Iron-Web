"""Separate read-only dashboard backend. No agents, website UI, or store writers."""

import hashlib
import asyncio
from collections import OrderedDict
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import time
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from .viewer import gate, sign_in


class MemoryRelay:
    def __init__(self):
        self.client = None
        self.lock = asyncio.Lock()
        self.cache = OrderedDict()
        self.source = os.getenv("DASHBOARD_SOURCE_URL", "").rstrip("/")
        self.token = os.getenv("DASHBOARD_SOURCE_TOKEN", "")

    async def read(
        self, resource="snapshot", params=None, *, session=None, fresh=False
    ):
        if session == "":
            raise HTTPException(
                401,
                "Sign in to the travel website in this browser, then click Follow live.",
            )
        if not self.source or (session is None and len(self.token) < 32):
            raise HTTPException(
                503,
                "Set DASHBOARD_SOURCE_URL and DASHBOARD_SOURCE_TOKEN on the dashboard backend.",
            )
        parsed = urlparse(self.source)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise HTTPException(503, "Invalid source URL configuration")
        if resource not in {
            "snapshot",
            "graph",
            "vectors",
            "shared-memory",
            "session",
            "history",
        }:
            raise HTTPException(404, "Unknown memory inspection resource")
        identity = (
            hashlib.sha256(session.encode()).hexdigest()
            if session is not None
            else "published"
        )
        key = (identity, resource, tuple(sorted((params or {}).items())))
        async with self.lock:
            cached = self.cache.get(key)
            if not fresh and cached is not None and time.monotonic() < cached[0]:
                return cached[1]
            try:
                response = await self.client.get(
                    self.source
                    + "/api/dashboard/"
                    + ("live/" if session is not None else "")
                    + resource,
                    params=params,
                    headers={"Cookie": "voyara_session=" + session}
                    if session is not None
                    else {"Authorization": "Bearer " + self.token},
                )
                if session is not None and response.status_code == 401:
                    self.cache.pop(key, None)
                    raise HTTPException(
                        401,
                        "Sign in to the travel website in this browser, then click Follow live.",
                    )
                if resource == "history" and response.status_code == 404:
                    self.cache.pop(key, None)
                    raise HTTPException(404, "Agent run not found in this account.")
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or (
                    resource == "snapshot"
                    and payload.get("schema") != "iron_web_dashboard_v1"
                ):
                    raise ValueError("Invalid source snapshot")
            except (httpx.HTTPError, ValueError) as error:
                self.cache.clear()
                raise HTTPException(
                    503,
                    "Memory feed unavailable. Check the website's source URL, publication grant, selected memory scope, and database health.",
                ) from error
            self.cache.pop(key, None)
            while len(self.cache) >= 64:
                self.cache.popitem(last=False)
            if session is not None:
                payload["website_url"] = self.source
            self.cache[key] = (time.monotonic() + 1.5, payload)
            return payload


relay = MemoryRelay()


@asynccontextmanager
async def lifespan(_):
    async with httpx.AsyncClient(
        timeout=12, follow_redirects=False, trust_env=False
    ) as client:
        relay.client = client
        yield
    relay.client = None
    relay.cache.clear()


app = FastAPI(title="Iron Web Memory Dashboard", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def headers(request, call_next):
    # Preflights contain no memory; the same gate protects HTTP pages and SSE.
    denied = (
        gate(request)
        if request.url.path.startswith("/api/dashboard/")
        and request.method != "OPTIONS"
        else None
    )
    response = denied if denied is not None else await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.post("/viewer/session", include_in_schema=False)
async def viewer_session(request: Request):
    return await sign_in(request)


# CORS wraps gate errors too, so the configured frontend can display sign-in.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        v.strip()
        for v in os.getenv(
            "DASHBOARD_CORS_ORIGINS", "http://127.0.0.1:5174,http://localhost:5174"
        ).split(",")
        if v.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Accept", "Last-Event-ID", "Content-Type", "Authorization"],
)


@app.get("/health")
def health():
    return dict(
        status="ok",
        service="iron-web-memory-dashboard",
        source_configured=bool(relay.source and len(relay.token) >= 32),
    )


def source_mode():
    return os.getenv("DASHBOARD_SOURCE_MODE", "website")


async def read_current(request, resource="snapshot", params=None, *, fresh=False):
    session = (
        request.cookies.get("voyara_session", "")
        if source_mode() == "website"
        else None
    )
    return await relay.read(resource, params, session=session, fresh=fresh)


@app.get("/api/dashboard/connection")
def connection_info():
    return dict(mode=source_mode(), website_url=relay.source)


@app.get("/api/dashboard/session")
async def website_session(request: Request):
    return await read_current(request, "session", fresh=True)


@app.get("/api/dashboard/history")
async def run_history(
    request: Request,
    run_id: str | None = Query(
        default=None, max_length=96, pattern=r"^[A-Za-z0-9:_-]+$"
    ),
    before: int | None = Query(default=None, ge=1),
    limit: int = Query(default=30, ge=1, le=100),
    agent_id: str | None = Query(default=None, max_length=80),
):
    params = dict(limit=limit)
    if run_id:
        params["run_id"] = run_id
    if before is not None:
        params["before"] = before
    if agent_id:
        params["agent_id"] = agent_id
    return await read_current(request, "history", params, fresh=True)


@app.get("/api/dashboard/snapshot")
async def snapshot(request: Request, fresh: bool = False):
    return await read_current(request, fresh=fresh)


@app.get("/api/dashboard/overview")
async def overview(request: Request):
    data = await read_current(request)
    return {
        k: data[k]
        for k in (
            "schema",
            "status",
            "timestamp",
            "scope",
            "trip_id",
            "storage",
            "databases",
            "models",
            "cache",
            "notes",
        )
    }


@app.get("/api/dashboard/agents")
async def agents(request: Request):
    return (await read_current(request))["agents"]


@app.get("/api/dashboard/tiers")
async def tiers(request: Request):
    return (await read_current(request))["tiers"]


@app.get("/api/dashboard/credentials")
async def credentials(request: Request):
    return (await read_current(request))["credentials"]


@app.get("/api/dashboard/events")
async def events(
    request: Request,
    after: int = Query(default=0, ge=0),
    boot: str | None = Query(default=None, max_length=64),
):
    data = await read_current(request)
    observations = data["observations"]
    reset = boot is not None and boot != observations["boot"]
    rows = observations["events"]
    return dict(
        boot=observations["boot"],
        reset=reset,
        next_cursor=observations["sequence"],
        oldest_cursor=rows[0]["id"] if rows else None,
        gap=bool(
            not reset
            and after > 0
            and after
            < observations.get("retained_from", rows[0]["id"] if rows else 1) - 1
        ),
        events=[e for e in rows if reset or e["id"] > after],
        receipts=data["receipts"],
    )


@app.get("/api/dashboard/graph")
async def graph(
    request: Request,
    offset: int = Query(default=0, ge=0, le=1000000),
    limit: int = Query(default=120, ge=1, le=120),
):
    return await read_current(request, "graph", dict(offset=offset, limit=limit))


@app.get("/api/dashboard/shared-memory")
async def shared_memory(
    request: Request,
    offset: int = Query(default=0, ge=0, le=1000000),
    limit: int = Query(default=120, ge=1, le=120),
):
    return await read_current(
        request, "shared-memory", dict(offset=offset, limit=limit)
    )


@app.get("/api/dashboard/vectors")
async def vectors(
    request: Request,
    after: str | None = Query(
        default=None,
        max_length=200,
        pattern=r"^(?:source_[a-f0-9]{64}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12})$",
    ),
    limit: int = Query(default=25, ge=1, le=100),
    include_values: bool = False,
):
    params = dict(limit=limit, include_values=str(include_values).lower())
    if after:
        params["after"] = str(after)
    return await read_current(request, "vectors", params)


async def snapshot_events(request):
    while not await request.is_disconnected():
        if gate(request) is not None:
            yield 'event: feed_error\ndata: {"message":"Viewer session expired. Sign in again."}\n\n'
            return
        try:
            payload = await read_current(request)
            yield (
                "event: snapshot\ndata: "
                + json.dumps(payload, allow_nan=False)
                + "\n\n"
            )
        except HTTPException as error:
            yield (
                "event: feed_error\ndata: "
                + json.dumps(dict(message=error.detail, status=error.status_code))
                + "\n\n"
            )
        await asyncio.sleep(2)


@app.get("/api/dashboard/stream")
async def stream(request: Request):
    return StreamingResponse(
        snapshot_events(request),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache, no-store"},
    )


FRONTEND = Path(__file__).resolve().parents[1] / "inspection"


@app.get("/", include_in_schema=False)
def inspection_ui():
    return FileResponse(FRONTEND / "index.html")


@app.get("/app.js", include_in_schema=False)
def inspection_script():
    return FileResponse(FRONTEND / "app.js", media_type="text/javascript")


@app.get("/config.js", include_in_schema=False)
def inspection_config():
    from fastapi.responses import Response

    return Response("window.DASHBOARD_API_URL = '';", media_type="text/javascript")
