from fastapi import APIRouter, Depends, HTTPException
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..deps import current_user
from ..models import AIConversation, AIMemory, AIMessage, Destination, FoodPlace, Guide, Stay, TransportRoute, User
from ..schemas import ConversationIn, MemoryIn, MessageIn

router = APIRouter(prefix="/assistant", tags=["assistant"])

CATALOG_HINTS = {
    "stay": Stay, "food": FoodPlace, "transport": TransportRoute, "guide": Guide,
}


def _suggest(query: str, db: Session) -> str:
    """Rules-based reply: match the message against the live catalog so the
    travel desk can suggest real listings without an external AI provider."""
    words = [w for w in query.lower().replace("?", " ").split() if len(w) > 2]
    if not words:
        return "Tell me a place, a mood or a food you love, and I'll suggest something real from our catalog."
    found: list[tuple[str, str]] = []
    for kind, model in CATALOG_HINTS.items():
        for word in words:
            for column in ("name", "description", "kind", "cuisine", "mode", "specialties", "languages"):
                if not hasattr(model, column):
                    continue
                stmt = select(model).where(sa.cast(getattr(model, column), sa.String).ilike(f"%{word}%")).limit(2)
                for obj in db.scalars(stmt):
                    label = obj.name if hasattr(obj, "name") else getattr(obj, "operator", "")
                    found.append((kind, f"{label}"))
            if len(found) >= 4:
                break
        if len(found) >= 4:
            break
    if not found:
        places = db.scalars(select(Destination).limit(3)).all()
        names = ", ".join(place.name for place in places)
        return f"I couldn't match that to a specific listing yet, but you could start with {names} — or browse the Explore page and add favourites to your trip plan."
    unique = list(dict.fromkeys(found))[:4]
    summary = "; ".join(f"{kind.title()}: {label}" for kind, label in unique)
    return f"Here are some ideas from our catalog that match your message — {summary}. Add any of them to your trip plan and pick dates when you're ready."


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
    reply_text = _suggest(body.content, db)
    reply = AIMessage(conversation_id=conversation.id, role="assistant", content=reply_text)
    db.add(reply)
    conversation.updated_at = conversation.updated_at
    db.commit()
    return {
        "message": message,
        "reply": reply,
        "connection_status": "local_rules_based",
        "detail": "Suggested from our live catalog. Deeper AI advice arrives when the memory backend is connected.",
    }


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    conversation = db.scalar(
        select(AIConversation).where(
            AIConversation.id == conversation_id, AIConversation.user_id == user.id
        )
    )
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    db.delete(conversation)
    db.commit()


@router.get("/memory")
def list_memory(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(AIMemory).where(AIMemory.user_id == user.id).order_by(AIMemory.updated_at.desc())
    ).all()


@router.post("/memory", status_code=201)
def save_memory(
    body: MemoryIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
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
    db.commit()
    return snapshot


@router.delete("/memory/{memory_id}", status_code=204)
def delete_memory(
    memory_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    snapshot = db.scalar(
        select(AIMemory).where(AIMemory.id == memory_id, AIMemory.user_id == user.id)
    )
    if snapshot is None:
        raise HTTPException(404, "Memory snapshot not found")
    db.delete(snapshot)
    db.commit()
