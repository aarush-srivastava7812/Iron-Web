"""Bounded single-process planning jobs with durable, owner-scoped results.

The deployment already requires a single API worker for embedded stores. Jobs
survive browser refresh; interrupted jobs fail explicitly after process restart
and are never replayed automatically (research can incur provider charges).
"""
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import logging
from threading import RLock
import uuid

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import JSON, DateTime, ForeignKey, String, select, update
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from .db import Base

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="trip-planner")
_lock = RLock()
ACTIVE = ("queued", "running")


class PlanningJob(Base):
    __tablename__ = "planning_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    payload: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))


def present(job):
    return dict(job_id=job.id, status=job.status,
                status_url=f"/assistant/conversations/{job.conversation_id}/planning-jobs/{job.id}",
                result=job.result if job.status == "completed" else None, error=job.error)


def recover(db):
    db.execute(update(PlanningJob).where(PlanningJob.status.in_(ACTIVE)).values(
        status="failed", error="The server restarted during planning. Review your saved trip before starting a new run."))
    db.commit()


def start(db, user_id, conversation_id, kind, body, runtime):
    payload = body.model_dump(mode="json")
    with _lock:
        active = db.scalar(select(PlanningJob).where(PlanningJob.user_id == user_id, PlanningJob.status.in_(ACTIVE)))
        if active:
            if active.conversation_id == conversation_id and active.kind == kind and active.payload == payload:
                return present(active)
            raise HTTPException(409, "Your travel team is already planning a trip. Wait for that run to finish.")
        if len(db.scalars(select(PlanningJob.id).where(PlanningJob.status.in_(ACTIVE))).all()) >= 8:
            raise HTTPException(503, "The travel team is busy. Please try again shortly.")
        job = PlanningJob(id=str(uuid.uuid4()), user_id=user_id, conversation_id=conversation_id,
                          kind=kind, payload=payload, status="queued")
        db.add(job)
        db.commit()
        sessions = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
        _executor.submit(_run, sessions, job.id, runtime)
        return present(job)


def _run(sessions, job_id, runtime):
    from .models import User
    from .schemas import MessageIn
    from .journey import ConfirmIn
    from .routers.assistant import save_message
    from .routers.journey import confirm_trip

    with sessions() as db:
        job = db.get(PlanningJob, job_id)
        if job is None:
            return
        job.status = "running"
        db.commit()
        try:
            user = db.get(User, job.user_id)
            if user is None or not user.is_active:
                raise HTTPException(401, "Sign in again before planning.")
            if job.kind == "confirm":
                result = confirm_trip(job.conversation_id, ConfirmIn(**job.payload), user, db, runtime)
            else:
                result = save_message(job.conversation_id, MessageIn(**job.payload), user, db, runtime)
            job.result = jsonable_encoder(result)
            job.status = "completed"
        except Exception as error:
            db.rollback()
            job = db.get(PlanningJob, job_id)
            if job is None:
                return
            job.status = "failed"
            job.error = str(error.detail)[:500] if isinstance(error, HTTPException) else "Planning could not finish. Your trip details are saved; review them before retrying."
            logger.exception("Planning job failed")
        db.commit()
