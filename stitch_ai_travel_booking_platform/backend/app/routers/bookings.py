from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Booking, BookingItem, FoodPlace, Guide, Offer, Stay, TransportRoute, User, HolidayPackage, Experience
from ..schemas import BookingIn, BookingItemIn, BookingOut

router = APIRouter(prefix="/bookings", tags=["bookings"])
MODELS = {"stay": Stay, "food": FoodPlace, "transport": TransportRoute, "guide": Guide,
          "package": HolidayPackage, "experience": Experience}


def _price(item, obj, reserve=True) -> int:
    """Server-side pricing; client-supplied prices are never trusted."""
    import datetime as dt
    if item.item_type == "transport":
        if obj.seats_available < item.quantity:
            raise HTTPException(409, f"Only {obj.seats_available} seats left on route {obj.id}")
        if reserve:
            obj.seats_available -= item.quantity
        return obj.price_inr * item.quantity
    if item.item_type in {"food", "experience", "package"}:
        if not item.start_date or item.start_date < dt.date.today():
            raise HTTPException(422, f"Choose a valid date today or later for {item.item_type}")
        if item.item_type == "food" and item.quantity > 8:
            raise HTTPException(422, "Maximum 8 guests per table dining reservation")
        if item.item_type == "package" and item.end_date != item.start_date + dt.timedelta(days=obj.nights):
            raise HTTPException(422, "Package dates must match the package duration")
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


def validate_existing(items, user_id, db):
    """Check existing active requests across the traveler's other trips."""
    existing = list(db.scalars(select(BookingItem).join(Booking).where(Booking.user_id == user_id, Booking.status != "cancelled")))
    for proposed in items:
        for old in existing:
            if not proposed.start_date or not old.start_date:
                continue
            if proposed.item_type == old.item_type == "stay" and proposed.end_date and old.end_date:
                if proposed.start_date < old.end_date and old.start_date < proposed.end_date:
                    raise HTTPException(422, "This stay overlaps an existing booking request in another trip.")
            elif proposed.item_type != "stay" and old.item_type != "stay" and proposed.start_date == old.start_date and proposed.start_time and old.start_time:
                a, b = _minute(proposed), old.start_time.hour*60+old.start_time.minute
                if a < b+(old.duration_min or 90) and b < a+(proposed.duration_min or 90):
                    raise HTTPException(422, "This activity overlaps an existing booking request.")
            if proposed.item_type in {"experience", "food", "guide"} and old.item_type == "stay" and old.end_date and old.start_date <= proposed.start_date <= old.end_date:
                activity, stay = db.get(MODELS[proposed.item_type], proposed.item_id), db.get(Stay, old.item_id)
                if activity and stay and activity.destination_id != stay.destination_id:
                    raise HTTPException(422, "This activity is in a different city from the existing stay; plan a transfer first.")


def _validate_conflicts(items: list[BookingItemIn], db: Session | None = None) -> None:
    """Validate booking constraints:
    1. Stays must have valid date windows and not overlap with other stays.
    2. Food bookings require dates, have a max limit (cannot book 10 restaurants), and cannot double-book meal slots.
    3. Experiences and meals must fall within the stay window if a stay is booked.
    4. Geographic consistency: items booked for the same day must be in the same destination."""
    import datetime as dt
    today = dt.date.today()

    stays = [it for it in items if it.item_type == "stay"]
    for stay in stays:
        if not stay.start_date or not stay.end_date:
            raise HTTPException(422, "Stays need a check-in and check-out date")
        if stay.start_date < today:
            raise HTTPException(422, "Check-in date must be today or later")
        if stay.end_date <= stay.start_date:
            raise HTTPException(422, "Check-out date must be after check-in date")

    # Prevent overlapping stays
    for i in range(len(stays)):
        for j in range(i + 1, len(stays)):
            s1, s2 = stays[i], stays[j]
            if s1.start_date < s2.end_date and s2.start_date < s1.end_date:
                raise HTTPException(422, "Two stays have overlapping dates. Adjust your check-in and check-out dates.")

    # Food validation: cannot spam restaurant reservations without logic
    food_items = [it for it in items if it.item_type == "food"]
    if len(food_items) > 4:
        raise HTTPException(422, "Maximum 4 dining reservations per booking request. Please select your key meals.")

    for f in food_items:
        if not f.start_date or f.start_date < today:
            raise HTTPException(422, "Dining reservations require a valid date today or later.")

    # Check for same-day duplicate food bookings or slot clashes
    for i in range(len(food_items)):
        for j in range(i + 1, len(food_items)):
            f1, f2 = food_items[i], food_items[j]
            if f1.start_date == f2.start_date:
                if f1.item_id == f2.item_id:
                    raise HTTPException(422, f"Duplicate dining reservation for the same restaurant on {f1.start_date}.")
                slot1 = f1.meal_slot or ("lunch" if _minute(f1) and _minute(f1) < 960 else "dinner")
                slot2 = f2.meal_slot or ("lunch" if _minute(f2) and _minute(f2) < 960 else "dinner")
                if slot1 == slot2 and not (f1.start_time and f2.start_time and abs(_minute(f1) - _minute(f2)) >= 90):
                    raise HTTPException(422, f"You have multiple restaurant bookings for {slot1} on {f1.start_date}. Choose one per meal.")

    # Stay date boundary enforcement: activities & dining must be within the stay dates
    if stays:
        min_checkin = min(s.start_date for s in stays)
        max_checkout = max(s.end_date for s in stays)
        for it in items:
            if it.item_type in {"food", "experience", "guide"} and it.start_date:
                if it.start_date < min_checkin or it.start_date > max_checkout:
                    raise HTTPException(
                        422,
                        f"Your {it.item_type} reservation on {it.start_date} falls outside your stay dates ({min_checkin} to {max_checkout})."
                    )

    # Timed activity overlap check
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

    # Geographic consistency: items on the same date must belong to the same destination
    if db is not None:
        dest_by_date: dict[dt.date, tuple[int, str]] = {}
        for it in items:
            if it.item_type == "transport":
                continue
            model_cls = MODELS.get(it.item_type)
            if not model_cls:
                continue
            obj = db.get(model_cls, it.item_id)
            if not obj:
                continue
            item_dest_id = getattr(obj, "destination_id", None)
            item_name = getattr(obj, "name", str(it.item_id))
            if not item_dest_id:
                continue
            # Check for stay dates or single start_date
            dates_to_check = [it.start_date] if it.start_date else []
            if it.item_type == "stay" and it.start_date and it.end_date:
                curr = it.start_date
                while curr <= it.end_date:
                    dates_to_check.append(curr)
                    curr += dt.timedelta(days=1)
            for d in dates_to_check:
                if d in dest_by_date:
                    prev_dest_id, prev_name = dest_by_date[d]
                    if prev_dest_id != item_dest_id:
                        raise HTTPException(
                            422,
                            f"Geographic conflict on {d}: '{item_name}' is in a different destination from '{prev_name}'. Activities and stays on the same day must be in the same region."
                        )
                else:
                    dest_by_date[d] = (item_dest_id, item_name)


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
    return build_booking(body, user, db)


def build_booking(body: BookingIn, user: User, db: Session, *, commit=True):
    _validate_conflicts(body.items, db=db)
    validate_existing(body.items, user.id, db)
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
    if commit:
        db.commit()
    else:
        db.flush()
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
