from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import create_schema, SessionLocal
from .routers import dashboard
from .routers import journey
from .routers import trips
from .routers import assistant, auth, bookings, catalog, favorites, itineraries, leads, offers, profile, google_auth, website


@asynccontextmanager
async def lifespan(_):
    create_schema()
    from .planning_jobs import recover
    with SessionLocal() as db:
        recover(db)
        from .destination_research import recover as recover_research
        recover_research(db)
    yield
    from .agent_runtime import runtime
    runtime.close()


app = FastAPI(title="Travel API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def browser_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    response.headers["Referrer-Policy"] = (
        "no-referrer-when-downgrade" if request.url.hostname in {"localhost", "127.0.0.1"}
        else "strict-origin-when-cross-origin")
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api")
app.include_router(google_auth.router, prefix="/api")
app.include_router(website.router, prefix="/api")
app.include_router(bookings.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(itineraries.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(journey.router, prefix="/api")
app.include_router(trips.router, prefix="/api")
app.include_router(offers.router, prefix="/api")
app.include_router(favorites.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")  # last: generic /{kind} routes
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")
travel_assets=frontend_dist/"travel"
if not travel_assets.exists():
    travel_assets=frontend_dist.parent/"public"/"travel"
if travel_assets.exists():
    app.mount("/travel",StaticFiles(directory=travel_assets),name="travel-images")
catalog_dir = Path(__file__).resolve().parents[2] / "catalog"
if catalog_dir.exists():
    app.mount("/catalog", StaticFiles(directory=catalog_dir, html=True), name="catalog-pages")


@app.get("/", include_in_schema=False)
def homepage():
    built_index = frontend_dist / "index.html"
    if built_index.is_file():
        return FileResponse(built_index)
    raise HTTPException(503, "Frontend build not found. Run npm run build in frontend.")


@app.get("/transitions.js", include_in_schema=False)
def transition_script():
    script = Path(__file__).resolve().parents[2] / "transitions" / "transition.js"
    return FileResponse(script, media_type="text/javascript")


@app.get("/transitions.css", include_in_schema=False)
def transition_styles():
    stylesheet = Path(__file__).resolve().parents[2] / "transitions" / "transition.css"
    return FileResponse(stylesheet, media_type="text/css")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/{spa_path:path}", include_in_schema=False)
def spa_fallback(spa_path: str):
    if spa_path.startswith("api/"):
        raise HTTPException(404, "Not Found")
    built_index = frontend_dist / "index.html"
    if built_index.is_file():
        return FileResponse(built_index)
    raise HTTPException(503, "Frontend build not found. Run npm run build in frontend.")
