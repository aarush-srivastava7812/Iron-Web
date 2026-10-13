from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..deps import current_user
from ..models import AIConversation, AIMemory, AIMessage, User
from ..schemas import ConversationIn, MemoryIn, MessageIn

router = APIRouter(prefix="/assistant", tags=["assistant"])


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
    db.commit()
    return {
        "message": message,
        "connection_status": "not_configured",
        "detail": "Your message is saved. Connect your AI memory backend to generate a response.",
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
