"""Website adapter: read grants for the separate memory dashboard backend."""

import logging
import os
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent_runtime import get_agent_runtime
from ..db import get_db
from ..deps import current_user, _scope_user
from ..models import AIConversation, User
from memory.dashboard import (
    build_snapshot,
    graph_snapshot,
    vector_snapshot,
    shared_memory_snapshot,
)
from memory.observability import public_value

logger = logging.getLogger(__name__)
router = APIRouter(tags=["memory-dashboard-source"])


def owned_target(db, runtime, user_id, trip_id=None):
    _scope_user(db, user_id)
    if (
        trip_id
        and db.scalar(
            select(AIConversation.id).where(
                AIConversation.id == trip_id, AIConversation.user_id == user_id
            )
        )
        is None
    ):
        raise HTTPException(404, "Monitored trip not found")
    return runtime.for_user(user_id), trip_id


def published_target(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
    runtime=Depends(get_agent_runtime),
):
    expected = os.getenv("DASHBOARD_PUBLISH_TOKEN", "")
    if len(expected) < 32 or not secrets.compare_digest(
        authorization, "Bearer " + expected
    ):
        raise HTTPException(401, "Dashboard publication grant required")
    user_id = os.getenv("DASHBOARD_USER_ID", "")
    trip_id = os.getenv("DASHBOARD_TRIP_ID", "") or None
    if not user_id and os.getenv("DASHBOARD_USER_USERNAME"):
        user_id = db.scalar(select(User.id).where(User.username == os.environ["DASHBOARD_USER_USERNAME"])) or ""
    if not user_id:
        raise HTTPException(
            503,
            "Set DASHBOARD_USER_ID on the website backend; optionally narrow with DASHBOARD_TRIP_ID.",
        )
    _scope_user(db, user_id)
    owner = db.get(User, user_id)
    if not owner or not owner.is_active:
        raise HTTPException(404, "Monitored traveler not found")
    return owned_target(db, runtime, user_id, trip_id)


def inspect(target, section="snapshot", **options):
    traveler, trip_id = target
    try:
        if section == "snapshot":
            return build_snapshot(traveler, trip_id)
        engine = traveler.service.engine(traveler.user_id)
        with engine.graph_store.write_lock, engine._operation_lock:
            if section == "graph":
                return public_value(graph_snapshot(engine, trip_id, **options))
            if section == "shared-memory":
                return public_value(shared_memory_snapshot(engine, trip_id, **options))
            return public_value(vector_snapshot(engine, trip_id, **options))
    except Exception as error:
        logger.exception("Memory dashboard inspection unavailable")
        raise HTTPException(
            503,
            "Memory inspection unavailable. Check the website backend and FalkorDB.",
        ) from error


@router.get("/dashboard/snapshot")
def published_snapshot(target=Depends(published_target)):
    return inspect(target)


@router.get("/dashboard/graph")
def graph(
    offset: int = Query(default=0, ge=0, le=1000000),
    limit: int = Query(default=120, ge=1, le=120),
    target=Depends(published_target),
):
    return inspect(target, "graph", offset=offset, limit=limit)


@router.get("/dashboard/vectors")
def vectors(
    after: UUID | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    include_values: bool = False,
    target=Depends(published_target),
):
    return inspect(
        target,
        "vectors",
        after=str(after) if after else None,
        limit=limit,
        include_values=include_values,
    )


@router.get("/assistant/conversations/{conversation_id}/dashboard")
def owner_snapshot(
    conversation_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    runtime=Depends(get_agent_runtime),
):
    return inspect(owned_target(db, runtime, user.id, conversation_id))


@router.get("/dashboard/shared-memory")
def shared_memory(
    offset: int = Query(default=0, ge=0, le=1000000),
    limit: int = Query(default=120, ge=1, le=120),
    target=Depends(published_target),
):
    return inspect(target, "shared-memory", offset=offset, limit=limit)
