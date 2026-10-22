"""Website adapter: read grants for the separate memory dashboard backend."""

import logging
import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..agent_runtime import get_agent_runtime
from ..db import get_db
from ..deps import current_user, _scope_user
from ..models import AIConversation, AIMessage, Booking, Itinerary, User
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
        user_id = (
            db.scalar(
                select(User.id).where(
                    User.username == os.environ["DASHBOARD_USER_USERNAME"]
                )
            )
            or ""
        )
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
def published_snapshot(target=Depends(published_target), db: Session = Depends(get_db)):
    from ..external_memory import snapshot
    data = inspect(target)
    data["tinyfish"] = snapshot(db, target[0].user_id, target[1])
    return data


@router.get("/dashboard/graph")
def graph(
    offset: int = Query(default=0, ge=0, le=1000000),
    limit: int = Query(default=120, ge=1, le=120),
    target=Depends(published_target),
):
    return inspect(target, "graph", offset=offset, limit=limit)


@router.get("/dashboard/vectors")
def vectors(
    after: str | None = Query(
        default=None,
        max_length=200,
        pattern=r"^(?:source_[a-f0-9]{64}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12})$",
    ),
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


@router.get("/dashboard/live/{section}")
def live_dashboard(
    section: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    runtime=Depends(get_agent_runtime),
    trip_id: str | None = Query(default=None, max_length=36),
    run_id: str | None = Query(
        default=None, max_length=96, pattern=r"^[A-Za-z0-9:_-]+$"
    ),
    before: int | None = Query(default=None, ge=1),
    agent_id: str | None = Query(default=None, max_length=80),
    offset: int = Query(default=0, ge=0, le=1000000),
    limit: int = Query(default=30, ge=1, le=120),
    after: str | None = Query(
        default=None,
        max_length=200,
        pattern=r"^(?:source_[a-f0-9]{64}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12})$",
    ),
    include_values: bool = False,
):
    """The website session selects its owner; the dashboard cannot choose a tenant."""
    if section not in {
        "session",
        "snapshot",
        "history",
        "graph",
        "vectors",
        "shared-memory",
    }:
        raise HTTPException(404, "Unknown dashboard resource")
    if section == "vectors" and limit > 100:
        raise HTTPException(422, "Vector page limit must be at most 100")
    connection = dict(mode="website", user_id=user.id, username=user.username)
    if section == "session":
        return dict(connection=connection)
    target = owned_target(db, runtime, user.id, trip_id)
    if section == "history":
        if run_id:
            row = target[0].run_history.detail(run_id)
            if row is None or (trip_id and row["trip_id"] != trip_id):
                raise HTTPException(404, "Agent run not found")
            return row
        return target[0].run_history.page(
            trip_id=trip_id,
            agent_id=agent_id,
            before=before,
            limit=limit,
            include_details=False,
        )
    options = (
        dict(after=after, limit=limit, include_values=include_values)
        if section == "vectors"
        else dict(offset=offset, limit=min(limit, 120))
    )
    data = inspect(target, section, **({} if section == "snapshot" else options))
    if section == "snapshot":
        from ..external_memory import snapshot
        data["tinyfish"] = snapshot(db, user.id, trip_id)
        data["connection"] = connection
        data["travel"] = dict(
            conversations=db.scalar(
                select(func.count())
                .select_from(AIConversation)
                .where(AIConversation.user_id == user.id)
            ),
            messages=db.scalar(
                select(func.count())
                .select_from(AIMessage)
                .join(AIConversation)
                .where(AIConversation.user_id == user.id)
            ),
            bookings=db.scalar(
                select(func.count())
                .select_from(Booking)
                .where(Booking.user_id == user.id)
            ),
            itineraries=db.scalar(
                select(func.count())
                .select_from(Itinerary)
                .where(Itinerary.user_id == user.id)
            ),
            recent_trips=[
                dict(id=row.id, title=row.title, updated_at=row.updated_at.isoformat())
                for row in db.scalars(
                    select(AIConversation)
                    .where(AIConversation.user_id == user.id)
                    .order_by(AIConversation.updated_at.desc(), AIConversation.id)
                    .limit(10)
                )
            ],
        )
    return data


@router.get("/dashboard/history")
def published_history(
    target=Depends(published_target),
    run_id: str | None = Query(
        default=None, max_length=96, pattern=r"^[A-Za-z0-9:_-]+$"
    ),
    before: int | None = Query(default=None, ge=1),
    limit: int = Query(default=30, ge=1, le=100),
    agent_id: str | None = Query(default=None, max_length=80),
):
    if run_id:
        row = target[0].run_history.detail(run_id)
        if row is None or (target[1] and row["trip_id"] != target[1]):
            raise HTTPException(404, "Agent run not found")
        return row
    return target[0].run_history.page(
        trip_id=target[1],
        agent_id=agent_id,
        before=before,
        limit=limit,
        include_details=False,
    )
