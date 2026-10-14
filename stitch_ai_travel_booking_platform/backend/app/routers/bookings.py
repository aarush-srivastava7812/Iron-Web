from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Booking, BookingItem, FoodPlace, Guide, Stay, TransportRoute, User
from ..schemas import BookingIn, BookingOut

router = APIRouter(prefix="/bookings", tags=["bookings"])
MODELS = {"stay": Stay, "food": FoodPlace, "transport": TransportRoute, "guide": Guide}


def _price(item, obj) -> int:
    """Server-side pricing; client-supplied prices are never trusted."""
    if item.item_type == "transport":
        if obj.seats_available < item.quantity:
            raise HTTPException(409, f"Only {obj.seats_available} seats left on route {obj.id}")
        obj.seats_available -= item.quantity
        return obj.price_inr * item.quantity
    if item.item_type == "food":
        return obj.price_inr * item.quantity
    if not (item.start_date and item.end_date) or item.end_date < item.start_date:
        raise HTTPException(422, "Valid start_date and end_date required")
    span = (item.end_date - item.start_date).days
    if item.item_type == "stay":
        if span < 1:
            raise HTTPException(422, "Stay needs at least one night")
        return obj.price_inr * span * item.quantity
    return obj.price_inr * (span + 1) * item.quantity  # guide: inclusive days


@router.post("", response_model=BookingOut, status_code=201)
def create(body: BookingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    booking, total = Booking(user_id=user.id, total_inr=0, status="requested"), 0
    for it in body.items:
        obj = db.get(MODELS[it.item_type], it.item_id, with_for_update=True)
        if not obj:
            raise HTTPException(404, f"{it.item_type} {it.item_id} not found")
        cost = _price(it, obj)
        total += cost
        unit = cost // it.quantity if it.item_type != "transport" else obj.price_inr
        booking.items.append(BookingItem(item_type=it.item_type, item_id=it.item_id, quantity=it.quantity,
                                         unit_price_inr=unit, start_date=it.start_date, end_date=it.end_date))
    booking.total_inr = total
    db.add(booking)
    db.commit()
    return booking


@router.get("", response_model=list[BookingOut])
def mine(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Booking).where(Booking.user_id == user.id).order_by(Booking.id.desc())).all()


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel(booking_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    b = db.get(Booking, booking_id)
    if not b or b.user_id != user.id:
        raise HTTPException(404, "Booking not found")
    if b.status == "cancelled":
        raise HTTPException(409, "Already cancelled")
    for it in b.items:
        if it.item_type == "transport":
            route = db.get(TransportRoute, it.item_id)
            if route:
                route.seats_available += it.quantity
    b.status = "cancelled"
    db.commit()
    return b
