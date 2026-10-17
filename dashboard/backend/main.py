"""Separate read-only dashboard backend. No agents, website UI, or store writers."""

import asyncio
from collections import OrderedDict
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import time
from urllib.parse import urlparse
from uuid import UUID

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

    async def read(self, resource="snapshot", params=None):
        if not self.source or len(self.token) < 32:
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
        if resource not in {"snapshot", "graph", "vectors", "shared-memory"}:
            raise HTTPException(404, "Unknown memory inspection resource")
        key = (resource, tuple(sorted((params or {}).items())))
        async with self.lock:
            cached = self.cache.get(key)
            if cached is not None and time.monotonic() < cached[0]:
                return cached[1]
            try:
                response = await self.client.get(
                    self.source + "/api/dashboard/" + resource,
                    params=params,
                    headers={"Authorization": "Bearer " + self.token},
                )
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
    denied = gate(request) if request.url.path.startswith("/api/dashboard/") and request.method != "OPTIONS" else None
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


@app.get("/api/dashboard/snapshot")
async def snapshot():
    return await relay.read()


@app.get("/api/dashboard/overview")
async def overview():
    data = await relay.read()
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
async def agents():
    return (await relay.read())["agents"]


@app.get("/api/dashboard/tiers")
async def tiers():
    return (await relay.read())["tiers"]


@app.get("/api/dashboard/credentials")
async def credentials():
    return (await relay.read())["credentials"]


@app.get("/api/dashboard/events")
async def events(
    after: int = Query(default=0, ge=0),
    boot: str | None = Query(default=None, max_length=64),
):
    data = await relay.read()
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
    offset: int = Query(default=0, ge=0, le=1000000),
    limit: int = Query(default=120, ge=1, le=120),
):
    return await relay.read("graph", dict(offset=offset, limit=limit))


@app.get("/api/dashboard/shared-memory")
async def shared_memory(
    offset: int = Query(default=0, ge=0, le=1000000),
    limit: int = Query(default=120, ge=1, le=120),
):
    return await relay.read("shared-memory", dict(offset=offset, limit=limit))


@app.get("/api/dashboard/vectors")
async def vectors(
    after: UUID | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    include_values: bool = False,
):
    params = dict(limit=limit, include_values=str(include_values).lower())
    if after:
        params["after"] = str(after)
    return await relay.read("vectors", params)


async def snapshot_events(request):
    while not await request.is_disconnected():
        if gate(request) is not None:
            yield 'event: feed_error\ndata: {"message":"Viewer session expired. Sign in again."}\n\n'
            return
        try:
            payload = await relay.read()
            yield (
                "event: snapshot\ndata: "
                + json.dumps(payload, allow_nan=False)
                + "\n\n"
            )
        except HTTPException as error:
            yield (
                "event: feed_error\ndata: "
                + json.dumps(dict(message=error.detail))
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
