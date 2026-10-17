import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent_runtime import get_agent_runtime
from ..db import get_db
from ..deps import current_user
from ..models import AIMessage, TravelBook, User
from ..schemas import MessageIn
from .. import journey, travel_book
from .assistant import _owned_conversation

router=APIRouter(prefix="/assistant/conversations",tags=["travel journey"])


@router.get("/{conversation_id}/workspace")
def get_workspace(conversation_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    _owned_conversation(db,user,conversation_id)
    row=journey.workspace(db,conversation_id)
    db.commit()
    return journey.present(db,row,user.id)


@router.put("/{conversation_id}/workspace")
def update_workspace(conversation_id:str,body:journey.DraftUpdate,user:User=Depends(current_user),db:Session=Depends(get_db),runtime=Depends(get_agent_runtime)):
    _owned_conversation(db,user,conversation_id)
    with runtime.for_user(user.id).lock:
        row=journey.workspace(db,conversation_id)
        journey.update_draft(db,row,body.draft.model_dump(mode="json",exclude_none=True),body.expected_revision)
        db.commit()
        return journey.present(db,row,user.id)


@router.post("/{conversation_id}/chat")
def chat(conversation_id:str,body:MessageIn,user:User=Depends(current_user),db:Session=Depends(get_db),runtime=Depends(get_agent_runtime)):
    conversation=_owned_conversation(db,user,conversation_id)
    # Save the original before attempting hosted inference.
    original=AIMessage(conversation_id=conversation_id,role="user",content=body.content.strip())
    if not original.content:
        raise HTTPException(422,"Message must not be blank.")
    db.add(original); db.commit()
    with runtime.for_user(user.id).lock:
        row=journey.workspace(db,conversation_id)
        try:
            answer=journey.chat_turn(db,row,user,original.content)
        except Exception:
            db.rollback()
            row=journey.workspace(db,conversation_id)
            answer=dict(status="unavailable",reply="Your message is saved. The travel assistant could not finish this turn. Please retry.",cards=[])
        reply=AIMessage(conversation_id=conversation_id,role="assistant",content=answer["reply"])
        db.add(reply)
        conversation.updated_at=dt.datetime.now(dt.timezone.utc)
        if conversation.title=="New travel chat" and row.data.get("draft",{}).get("destination"):
            conversation.title=row.data["draft"]["destination"]+" · your journey"
        db.commit()
        return dict(**answer,message=original,assistant_message=reply,workspace=journey.present(db,row,user.id),mode="nvidia")


@router.post("/{conversation_id}/selections")
def select_choice(conversation_id:str,body:journey.SelectionIn,user:User=Depends(current_user),db:Session=Depends(get_db),runtime=Depends(get_agent_runtime)):
    _owned_conversation(db,user,conversation_id)
    with runtime.for_user(user.id).lock:
        row=journey.workspace(db,conversation_id)
        journey.select_item(db,row,body)
        db.commit()
        return journey.present(db,row,user.id)


@router.post("/{conversation_id}/confirm")
def confirm_trip(conversation_id:str,body:journey.ConfirmIn,user:User=Depends(current_user),db:Session=Depends(get_db),runtime=Depends(get_agent_runtime)):
    _owned_conversation(db,user,conversation_id)
    row=journey.workspace(db,conversation_id)
    try:
        result=journey.confirm(db,row,user,runtime,body)
    except HTTPException:
        raise
    except Exception as error:
        db.rollback()
        raise HTTPException(503,"Trip details could not be confirmed through memory. Your draft is saved; retry when the memory service is ready.") from error
    reply=AIMessage(conversation_id=conversation_id,role="assistant",content=result["response"])
    db.add(reply); db.commit()
    return dict(orchestration=result,reply=result["response"],workspace=journey.present(db,row,user.id))


@router.get("/{conversation_id}/travel-book")
def book_preview(conversation_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    _owned_conversation(db,user,conversation_id)
    return travel_book.snapshot(db,conversation_id,user)


@router.post("/{conversation_id}/travel-books",status_code=201)
def create_book(conversation_id:str,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db),runtime=Depends(get_agent_runtime)):
    _owned_conversation(db,user,conversation_id)
    with runtime.for_user(user.id).lock:
        data=travel_book.snapshot(db,conversation_id,user)
        digest=journey.fingerprint(data)
        row=db.scalar(select(TravelBook).where(TravelBook.conversation_id==conversation_id,TravelBook.fingerprint==digest))
        if row is None:
            row=TravelBook(conversation_id=conversation_id,fingerprint=digest,snapshot=data,
                           pdf=travel_book.render_pdf(data,str(request.base_url)))
            db.add(row); db.commit()
        return dict(id=row.id,version=data["version"],download_url=f"/api/assistant/conversations/{conversation_id}/travel-books/{row.id}.pdf")


@router.get("/{conversation_id}/travel-books/{book_id}.pdf")
def download_book(conversation_id:str,book_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    _owned_conversation(db,user,conversation_id)
    book=db.scalar(select(TravelBook).where(TravelBook.id==book_id,TravelBook.conversation_id==conversation_id))
    if book is None:
        raise HTTPException(404,"Travel Book not found.")
    return Response(content=book.pdf,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="Voyara-Travel-Book-v{book.snapshot["version"]}.pdf"'})
