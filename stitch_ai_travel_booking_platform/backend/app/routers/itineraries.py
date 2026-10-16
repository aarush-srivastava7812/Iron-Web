from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Booking, Destination, Itinerary, User
from ..schemas import ItineraryIn, ItineraryOut

router = APIRouter(prefix="/itineraries", tags=["itineraries"])


def _validate_refs(body: ItineraryIn, user: User, db: Session) -> None:
    if body.end_date and body.start_date and body.end_date < body.start_date:
        raise HTTPException(422, "end_date must be on or after start_date")
    if body.destination_id is not None and db.get(Destination, body.destination_id) is None:
        raise HTTPException(404, "Destination not found")
    if body.booking_ids:
        owned = set(
            db.scalars(
                select(Booking.id).where(
                    Booking.user_id == user.id, Booking.id.in_(body.booking_ids)
                )
            )
        )
        if owned != set(body.booking_ids):
            raise HTTPException(404, "One or more bookings were not found")


@router.get("", response_model=list[ItineraryOut])
def list_itineraries(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Itinerary).where(Itinerary.user_id == user.id).order_by(Itinerary.created_at.desc())
    ).all()


@router.post("", response_model=ItineraryOut, status_code=201)
def create_itinerary(
    body: ItineraryIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _validate_refs(body, user, db)
    itinerary = Itinerary(user_id=user.id, **body.model_dump())
    db.add(itinerary)
    db.commit()
    return itinerary


@router.patch("/{itinerary_id}", response_model=ItineraryOut)
def update_itinerary(
    itinerary_id: int,
    body: ItineraryIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    itinerary = db.scalar(
        select(Itinerary).where(Itinerary.id == itinerary_id, Itinerary.user_id == user.id)
    )
    if itinerary is None:
        raise HTTPException(404, "Itinerary not found")
    _validate_refs(body, user, db)
    for key, value in body.model_dump().items():
        setattr(itinerary, key, value)
    db.commit()
    return itinerary


@router.delete("/{itinerary_id}", status_code=204)
def delete_itinerary(
    itinerary_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    itinerary = db.scalar(
        select(Itinerary).where(Itinerary.id == itinerary_id, Itinerary.user_id == user.id)
    )
    if itinerary is None:
        raise HTTPException(404, "Itinerary not found")
    db.delete(itinerary)
    db.commit()
