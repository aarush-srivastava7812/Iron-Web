"""Bounded single-process planning jobs with durable, owner-scoped results.

The deployment already requires a single API worker for embedded stores. Jobs
survive browser refresh; interrupted jobs fail explicitly after process restart
and are never replayed automatically (research can incur provider charges).
"""
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import logging
import time
from threading import RLock
import uuid

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import JSON, DateTime, ForeignKey, String, select, update
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from .db import Base

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="trip-planner")
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
                result=job.result if job.status == "completed" else None, error=job.error,
                progress=(job.result or {}).get("progress", []), target_seconds=60)


def latest(db, user_id, conversation_id):
    from agents.presentation import research_failure
    job = db.scalar(select(PlanningJob).where(PlanningJob.user_id == user_id,
                    PlanningJob.conversation_id == conversation_id).order_by(PlanningJob.created_at.desc()).limit(1))
    if job is None:
        return None
    value = {key: item for key, item in present(job).items() if key != "result"}
    value["created_at"] = job.created_at.isoformat()
    result = job.result or {}
    value["reply_id"] = result.get("assistant_message_id") or (result["reply"].get("id") if isinstance(result.get("reply"), dict) else None)
    orchestration = result.get("orchestration", {})
    if job.status == "completed":
        value["status"] = "ready" if orchestration.get("status") == "ok" else "failed"
    labels = {"explore_agent": "Destination research", "stay_agent": "Hotel research",
              "food_guide_agent": "Restaurant research", "tour_guide_agent": "Attraction research"}
    value["failed_specialists"] = [dict(name=labels.get(agent["agent_id"], "A planning specialist"),
        reason=research_failure(" ".join(agent.get("errors", []))))
        for agent in orchestration.get("agent_results", []) if agent.get("status") == "failed"]
    return value


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
        if len(db.scalars(select(PlanningJob.id).where(PlanningJob.status.in_(ACTIVE))).all()) >= 2:
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
        stages = {}
        stage_lock = RLock()
        def progress(agent_id, status):
            with stage_lock:
                if agent_id == "trip_consultant":
                    stages["trip_memory"] = dict(agent_id="trip_memory", status="completed",
                        updated_at=dt.datetime.now(dt.timezone.utc).isoformat())
                stages[agent_id] = dict(agent_id=agent_id, status=status,
                    updated_at=dt.datetime.now(dt.timezone.utc).isoformat())
                try:
                    with sessions() as progress_db:
                        progress_db.execute(update(PlanningJob).where(PlanningJob.id == job_id,
                            PlanningJob.status.in_(ACTIVE)).values(result={"progress": list(stages.values())}))
                        progress_db.commit()
                except Exception:
                    logger.warning("Could not persist planning progress", exc_info=True)
        traveler = None
        try:
            progress("trip_memory", "running")
            created = job.created_at.replace(tzinfo=dt.timezone.utc) if job.created_at.tzinfo is None else job.created_at
            if (dt.datetime.now(dt.timezone.utc) - created).total_seconds() > 45:
                raise HTTPException(503, "Planning could not start promptly. No research was launched; please try again.")
            traveler = runtime.for_user(job.user_id)
            traveler.on_progress = progress
            traveler.research_deadline = time.monotonic() + max(0, 45 - (dt.datetime.now(dt.timezone.utc) - created).total_seconds())
            user = db.get(User, job.user_id)
            if user is None or not user.is_active:
                raise HTTPException(401, "Sign in again before planning.")
            if job.kind == "confirm":
                result = confirm_trip(job.conversation_id, ConfirmIn(**job.payload), user, db, runtime)
            else:
                result = save_message(job.conversation_id, MessageIn(**job.payload), user, db, runtime)
            progress("trip_memory", "completed")
            job.result = {**jsonable_encoder(result), "progress": list(stages.values())}
            job.status = "completed"
        except Exception as error:
            db.rollback()
            job = db.get(PlanningJob, job_id)
            if job is None:
                return
            job.status = "failed"
            job.error = str(error.detail)[:500] if isinstance(error, HTTPException) else "Planning could not finish. Your trip details are saved; review them before retrying."
            logger.exception("Planning job failed")
        finally:
            if traveler is not None:
                traveler.on_progress = None
                traveler.research_deadline = None
        db.commit()
