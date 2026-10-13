from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, engine
from .routers import auth, bookings, catalog


@asynccontextmanager
async def lifespan(_):
    Base.metadata.create_all(engine)  # swap for Alembic migrations before first deploy
    yield


app = FastAPI(title="Travel API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api")
app.include_router(bookings.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")  # last: generic /{kind} routes


@app.get("/health")
def health():
    return {"status": "ok"}
