from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import create_schema
from .routers import assistant, auth, bookings, catalog, itineraries, profile


@asynccontextmanager
async def lifespan(_):
    create_schema()
    yield


app = FastAPI(title="Travel API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api")
app.include_router(bookings.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(itineraries.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")  # last: generic /{kind} routes
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def homepage():
    built_index = frontend_dist / "index.html"
    if built_index.is_file():
        return FileResponse(built_index)
    raise HTTPException(503, "Frontend build not found. Run npm run build in travel-app/frontend.")


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
    raise HTTPException(503, "Frontend build not found. Run npm run build in travel-app/frontend.")
