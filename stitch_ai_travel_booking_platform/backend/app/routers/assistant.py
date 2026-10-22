from fastapi import APIRouter, Depends, HTTPException
import datetime as dt
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..deps import current_user
from ..models import AIConversation, AIMemory, AIMessage, User
from ..schemas import ConversationIn, MemoryIn, MessageIn, TripRequirementsIn
from ..agent_runtime import CatalogSnapshot, get_agent_runtime
from memory.shared.service import PendingMemory
from .. import plan_drafts
from .. import planning_jobs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/conversations/{conversation_id}/message-jobs", status_code=202)
def start_message_job(conversation_id: str, body: MessageIn, user: User = Depends(current_user),
                      db: Session = Depends(get_db), runtime=Depends(get_agent_runtime)):
    _owned_conversation(db, user, conversation_id)
    if not body.content.strip():
        raise HTTPException(422, "Message must not be blank")
    return planning_jobs.start(db, user.id, conversation_id, "message", body, runtime)


@router.get("/conversations/{conversation_id}/planning-jobs/{job_id}")
def get_planning_job(conversation_id: str, job_id: str, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    _owned_conversation(db, user, conversation_id)
    job = db.scalar(select(planning_jobs.PlanningJob).where(
        planning_jobs.PlanningJob.id == job_id, planning_jobs.PlanningJob.user_id == user.id,
        planning_jobs.PlanningJob.conversation_id == conversation_id))
    if job is None:
        raise HTTPException(404, "Planning job not found")
    return planning_jobs.present(job)

@router.get("/conversations")
def list_conversations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(AIConversation)
        .where(AIConversation.user_id == user.id)
        .order_by(AIConversation.updated_at.desc())
    ).all()


@router.post("/conversations", status_code=201)
def create_conversation(
    body: ConversationIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    conversation = AIConversation(user_id=user.id, title=body.title)
    db.add(conversation)
    db.commit()
    return conversation


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    conversation = db.scalar(
        select(AIConversation)
        .options(selectinload(AIConversation.messages))
        .where(AIConversation.id == conversation_id, AIConversation.user_id == user.id)
    )
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    return conversation


@router.post("/conversations/{conversation_id}/messages")
def save_message(
    conversation_id: str,
    body: MessageIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    runtime = Depends(get_agent_runtime),
):
    conversation = db.scalar(
        select(AIConversation).where(
            AIConversation.id == conversation_id, AIConversation.user_id == user.id
        )
    )
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    message = AIMessage(conversation_id=conversation.id, role="user", content=body.content.strip())
    db.add(message)
    if conversation.title == "New travel chat":
        conversation.title = body.content.strip()[:137] + ("..." if len(body.content.strip()) > 137 else "")
    if not body.content.strip():
        raise HTTPException(422, "Message must not be blank")
    # Persist the user's original message even if a model/store is unavailable.
    from agents.orchestration.routing import plan_tasks
    from agents.schemas import OrchestrationRequest
    from memory.shared.interpreter import TravelInterpreter
    tasks = plan_tasks(OrchestrationRequest(request=body.content.strip(), user_id=user.id,
                       session_id=conversation_id, page=body.page))
    changes = TravelInterpreter()(body.content.strip(), dict(subject="Traveller", scope={"trip_id": conversation_id}))
    if "itinerary_planner" in tasks or changes:
        plan_drafts.invalidate(db, conversation_id)
    db.commit()
    try:
        traveler = runtime.for_user(user.id)
        with traveler.lock:
            traveler.observations.emit(conversation.id, "workflow_started")
            traveler.sync_profile(db)
            def refresh_profile():
                db.expire_all()
                traveler.sync_profile(db)
            result = traveler.reply(conversation.id, body.content.strip(), body.page, CatalogSnapshot(db),
                                    before_validate=refresh_profile)
            plan_drafts.save_generated(db, conversation.id, result)
            db.commit()
        traveler.observations.emit(conversation.id, "workflow_finished",
            status=result["status"], agents=[r["agent_id"] for r in result.get("agent_results", [])])
        status = "agents_connected"
        detail = "Uses your confirmed trip requirements and saved preferences. Prices and availability need provider confirmation."
        if result["status"] == "failed":
            status, detail = "agent_incomplete", "A specialist could not complete its work. No complete plan was saved."
    except PendingMemory:
        if "traveler" in locals():
            traveler.observations.emit(conversation.id, "workflow_paused", status="pending_memory")
        result = dict(status="pending_memory", response="A memory update needs review before planning can continue. Confirm your Trip details or retry once the memory service is ready.", memory=[], agent_results=[])
        status, detail = "memory_pending", "Your message was saved; a current plan could not be returned."
    except Exception:
        db.rollback()
        if "traveler" in locals():
            traveler.observations.emit(conversation.id, "workflow_failed", status="unavailable")
        logger.exception("Connected travel assistant unavailable")
        result = dict(status="unavailable", response="Your message is saved. The memory and agent service is unavailable; please retry. You can still browse the catalog.", memory=[], agent_results=[])
        status, detail = "unavailable", "No plan was generated."
    reply_text = result["response"]
    reply = AIMessage(conversation_id=conversation.id, role="assistant", content=reply_text)
    db.add(reply)
    conversation.updated_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    return {
        "message": message,
        "reply": reply,
        "connection_status": status,
        "detail": detail,
        "orchestration": result,
    }


@router.get("/conversations/{conversation_id}/plan")
def get_plan(conversation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _owned_conversation(db, user, conversation_id)
    rows = plan_drafts.versions(db, conversation_id)
    return plan_drafts.view(rows[0], rows) if rows else None


@router.post("/conversations/{conversation_id}/plan/edits")
def edit_plan(conversation_id: str, body: plan_drafts.PlanEdit,
              user: User = Depends(current_user), db: Session = Depends(get_db),
              runtime = Depends(get_agent_runtime)):
    _owned_conversation(db, user, conversation_id)
    with runtime.for_user(user.id).lock:
        return plan_drafts.edit(db, conversation_id, body)


def _owned_conversation(db, user, conversation_id):
    conversation = db.scalar(select(AIConversation).where(
        AIConversation.id == conversation_id, AIConversation.user_id == user.id))
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    return conversation


@router.put("/conversations/{conversation_id}/requirements")
def save_requirements(conversation_id: str, body: TripRequirementsIn,
                      user: User = Depends(current_user), db: Session = Depends(get_db),
                      runtime = Depends(get_agent_runtime)):
    _owned_conversation(db, user, conversation_id)
    try:
        traveler = runtime.for_user(user.id)
        with traveler.lock:
            plan_drafts.invalidate(db, conversation_id)
            db.commit()
            receipt = traveler.save_requirements(conversation_id, body)
        return {"status": "ready", "event_id": receipt["id"], "trip_id": conversation_id}
    except PendingMemory as error:
        raise HTTPException(409, "Trip details were received but memory is not ready. Retry or inspect memory events.") from error
    except Exception as error:
        logger.exception("Trip requirements could not be committed")
        raise HTTPException(503, "Memory service is unavailable. Trip details were not confirmed.") from error


@router.get("/conversations/{conversation_id}/requirements")
def get_requirements(conversation_id: str, user: User = Depends(current_user),
                     db: Session = Depends(get_db), runtime = Depends(get_agent_runtime)):
    _owned_conversation(db, user, conversation_id)
    try:
        traveler = runtime.for_user(user.id)
        with traveler.lock:
            traveler.sync_profile(db)
            packet = traveler.service.context(traveler.principals["travel_orchestrator"],
                subject="Traveller", scope={"trip_id": conversation_id},
                session_id=conversation_id, task_type="itinerary")
            return {key: packet[key] for key in ("status", "required_issues", "fields", "cards", "cache_hit", "residency")}
    except PendingMemory as error:
        raise HTTPException(409, "Memory has a pending update; resolve it before planning.") from error
    except Exception as error:
        raise HTTPException(503, "Memory service is unavailable.") from error


@router.delete("/conversations/{conversation_id}/requirements/{predicate}", status_code=204)
def delete_requirement(conversation_id: str, predicate: str, user: User = Depends(current_user),
                       db: Session = Depends(get_db), runtime = Depends(get_agent_runtime)):
    _owned_conversation(db, user, conversation_id)
    try:
        traveler = runtime.for_user(user.id)
        with traveler.lock:
            plan_drafts.invalidate(db, conversation_id)
            db.commit()
            traveler.delete_field(conversation_id, predicate)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except Exception as error:
        raise HTTPException(503, "Memory deletion could not be confirmed.") from error


@router.get("/conversations/{conversation_id}/memory-events")
def memory_events(conversation_id: str, after: int = 0, user: User = Depends(current_user),
                  db: Session = Depends(get_db), runtime = Depends(get_agent_runtime)):
    _owned_conversation(db, user, conversation_id)
    traveler = runtime.for_user(user.id)
    with traveler.lock:
        return traveler.events(conversation_id, after)


@router.delete("/conversations/{conversation_id}/memory-events/{event_id}", status_code=204)
def forget_event(conversation_id: str, event_id: str, user: User = Depends(current_user),
                 db: Session = Depends(get_db), runtime = Depends(get_agent_runtime)):
    _owned_conversation(db, user, conversation_id)
    try:
        traveler = runtime.for_user(user.id)
        with traveler.lock:
            plan_drafts.invalidate(db, conversation_id)
            db.commit()
            traveler.forget_event(conversation_id, event_id)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    except Exception as error:
        raise HTTPException(503, "Memory deletion could not be confirmed.") from error


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db),
    runtime = Depends(get_agent_runtime),
):
    conversation = db.scalar(
        select(AIConversation).where(
            AIConversation.id == conversation_id, AIConversation.user_id == user.id
        )
    )
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    try:
        traveler = runtime.for_user(user.id)
        with traveler.lock:
            traveler.forget_trip(conversation_id)
    except Exception as error:
        raise HTTPException(503, "Trip memory deletion could not be confirmed; the conversation is retained for retry.") from error
    db.delete(conversation)
    db.commit()


@router.get("/memory")
def list_memory(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(AIMemory).where(AIMemory.user_id == user.id).order_by(AIMemory.updated_at.desc())
    ).all()


@router.post("/memory", status_code=201)
def save_memory(
    body: MemoryIn, user: User = Depends(current_user), db: Session = Depends(get_db),
    runtime = Depends(get_agent_runtime),
):
    with runtime.for_user(user.id).lock:
        return _save_memory(body, user, db)


def _save_memory(body, user, db):
    if body.source_conversation_id:
        exists = db.scalar(
            select(AIConversation.id).where(
                AIConversation.id == body.source_conversation_id,
                AIConversation.user_id == user.id,
            )
        )
        if exists is None:
            raise HTTPException(404, "Conversation not found")
    snapshot = AIMemory(
        user_id=user.id,
        category=body.category,
        value=body.value,
        source_conversation_id=body.source_conversation_id,
    )
    db.add(snapshot)
    for trip_id in db.scalars(select(AIConversation.id).where(AIConversation.user_id == user.id)):
        plan_drafts.invalidate(db, trip_id)
    db.commit()
    return snapshot


@router.delete("/memory/{memory_id}", status_code=204)
def delete_memory(
    memory_id: int, user: User = Depends(current_user), db: Session = Depends(get_db),
    runtime = Depends(get_agent_runtime),
):
    with runtime.for_user(user.id).lock:
        return _delete_memory(memory_id, user, db)


def _delete_memory(memory_id, user, db):
    snapshot = db.scalar(
        select(AIMemory).where(AIMemory.id == memory_id, AIMemory.user_id == user.id)
    )
    if snapshot is None:
        raise HTTPException(404, "Memory snapshot not found")
    db.delete(snapshot)
    for trip_id in db.scalars(select(AIConversation.id).where(AIConversation.user_id == user.id)):
        plan_drafts.invalidate(db, trip_id)
    db.commit()
