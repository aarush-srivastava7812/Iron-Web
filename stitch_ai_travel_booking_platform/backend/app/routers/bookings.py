from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Booking, BookingItem, FoodPlace, Guide, Offer, Stay, TransportRoute, User
from ..schemas import BookingIn, BookingItemIn, BookingOut

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


def _minute(item: BookingItemIn) -> int:
    if not item.start_time:
        return 0
    return item.start_time.hour * 60 + item.start_time.minute


def _validate_conflicts(items: list[BookingItemIn]) -> None:
    """Mirror the client-side schedule rules: timed activities on the same date
    must not overlap, and stays need a valid date window."""
    stays = [it for it in items if it.item_type == "stay"]
    for stay in stays:
        if not stay.start_date or not stay.end_date:
            raise HTTPException(422, "Stays need a start and end date")
    timed = [it for it in items if it.item_type != "stay" and it.start_date and it.start_time]
    for first in range(len(timed)):
        for second in range(first + 1, len(timed)):
            a, b = timed[first], timed[second]
            if a.start_date != b.start_date:
                continue
            a_start, a_end = _minute(a), _minute(a) + (a.duration_min or 0)
            b_start, b_end = _minute(b), _minute(b) + (b.duration_min or 0)
            if a_start < b_end and b_start < a_end:
                raise HTTPException(422, "Two timed activities overlap on the same date. Adjust the times.")


def _apply_coupon(db: Session, code: str | None, subtotal: int, item_types: set[str]) -> tuple[Offer | None, int]:
    if not code:
        return None, 0
    offer = db.scalar(select(Offer).where(Offer.code == code.strip().upper()))
    today = __import__("datetime").date.today()
    if not offer or not offer.active or (offer.valid_till and offer.valid_till < today):
        raise HTTPException(422, "That offer code is not valid.")
    module_to_type = {"stays": "stay", "food": "food", "transport": "transport", "guides": "guide", "any": "any"}
    wanted = module_to_type.get(offer.module, offer.module)
    if wanted != "any" and wanted not in item_types:
        raise HTTPException(422, f"That offer only applies to {offer.module} items.")
    if offer.min_amount_inr and subtotal < offer.min_amount_inr:
        raise HTTPException(422, f"Minimum trip amount of ₹{offer.min_amount_inr:,} needed for that offer.")
    discount = 0
    if offer.discount_percent:
        discount += round(subtotal * offer.discount_percent / 100)
    if offer.discount_flat_inr:
        discount += offer.discount_flat_inr
    return offer, min(discount, subtotal)


@router.post("", response_model=BookingOut, status_code=201)
def create(body: BookingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _validate_conflicts(body.items)
    booking, total, item_types = Booking(user_id=user.id, total_inr=0, status="requested"), 0, set()
    for it in body.items:
        item_types.add(it.item_type)
        obj = db.get(MODELS[it.item_type], it.item_id, with_for_update=True)
        if not obj:
            raise HTTPException(404, f"{it.item_type} {it.item_id} not found")
        cost = _price(it, obj)
        total += cost
        unit = cost // it.quantity if it.item_type != "transport" else obj.price_inr
        booking.items.append(BookingItem(item_type=it.item_type, item_id=it.item_id, quantity=it.quantity,
                                         unit_price_inr=unit, start_date=it.start_date, end_date=it.end_date,
                                         start_time=it.start_time, duration_min=it.duration_min))
    offer, discount = _apply_coupon(db, body.coupon_code, total, item_types)
    booking.total_inr = max(total - discount, 0)
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
