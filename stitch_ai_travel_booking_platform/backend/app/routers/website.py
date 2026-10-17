"""Backend contracts for the supplied Voyara frontend."""
import datetime as dt
import hashlib
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import (Booking, BookingRequestDetails, ContactEnquiry, Destination, Experience,
                      FoodPlace, HolidayPackage, NewsletterSubscription, Stay, TransportRoute, User, WebsiteStay)
from ..schemas import BookingIn, BookingItemIn, BookingOut
from .bookings import MODELS, _price, _validate_conflicts, build_booking
from agents.resource_manager.model_registry import get_nim_client

router = APIRouter(prefix="/website", tags=["website"])


@router.get("/catalog")
def catalog(db: Session = Depends(get_db)):
    from ..destination_content import KERALA
    packages = db.scalars(select(HolidayPackage).order_by(HolidayPackage.id)).all()
    stays = db.execute(select(Stay, WebsiteStay).join(WebsiteStay, Stay.id == WebsiteStay.stay_id)).all()
    experiences = db.scalars(select(Experience).order_by(Experience.id)).all()
    cities = db.scalars(select(Destination).where(Destination.id.in_(
        select(TransportRoute.origin_id).where(TransportRoute.mode == "flight")))).all()
    return {
        "destinations": [dict(p.display, id=p.id, destination_id=p.destination_id,
                              price=p.price_inr, nights=p.nights, name=p.name) for p in packages],
        "hotels": [dict(w.display, id=s.id, destination_id=s.destination_id, name=s.name,
                        price=s.price_inr, rating=str(s.rating), amenities=" · ".join(s.amenities)) for s, w in stays],
        "experiences": [dict(e.display, id=e.id, destination_id=e.destination_id, name=e.name,
                              price=e.price_inr) for e in experiences],
        "airports": [{"id": d.id, "name": d.name} for d in cities],
        "inventory_notice": "Illustrative catalog. Requests are saved by Voyara and require provider confirmation. No payment is collected.",
        "destination_guides": {"Kerala": KERALA},
    }


@router.get("/flights")
def flights(origin_id: int, destination_id: int, depart: dt.date,
            return_date: dt.date | None = None, travelers: int = Query(ge=1, le=6, default=1),
            cabin: Literal["Economy"] = "Economy", mode: str | None = None, db: Session = Depends(get_db)):
    if origin_id == destination_id or depart < dt.date.today() or (return_date and return_date < depart):
        raise HTTPException(422, "Choose different stations or airports and valid future dates")
    def routes(a, b, date):
        stmt = select(TransportRoute).where(TransportRoute.origin_id == a,
            TransportRoute.destination_id == b, TransportRoute.seats_available >= travelers)
        if mode and mode != "all":
            stmt = stmt.where(TransportRoute.mode == mode)
        rows = db.scalars(stmt.order_by(TransportRoute.price_inr)).all()
        return [dict(id=r.id, name=r.operator, mode=r.mode, duration_min=r.duration_min, price_inr=r.price_inr,
                     seats_available=r.seats_available, date=date, origin=db.get(Destination, a).name,
                     destination=db.get(Destination, b).name) for r in rows]
    return {"outbound": routes(origin_id, destination_id, depart),
            "return": routes(destination_id, origin_id, return_date) if return_date else [],
            "notice": "Stored travel routes (flights, trains & luxury buses). Dates are requested dates; schedules and availability require confirmation."}


class TravelerDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    first: str = Field(min_length=1, max_length=60)
    last: str = Field(min_length=1, max_length=60)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=20, pattern=r"^[0-9+\-\s()]+$")
    notes: str = Field(default="", max_length=2000)
    consent: Literal[True]


class QuoteIn(BookingIn):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def dated(self):
        if self.coupon_code:
            raise ValueError("Offers are not available for these catalog requests")
        for item in self.items:
            if not item.start_date or item.start_date < dt.date.today():
                raise ValueError("Choose dates today or later for every item")
            if item.end_date and item.end_date < item.start_date:
                raise ValueError("End date cannot precede departure")
        return self


class RequestIn(QuoteIn):
    request_key: UUID
    expected_total_inr: int = Field(ge=0)
    traveler: TravelerDetails


def price_quote(body, db):
    _validate_conflicts(body.items, db=db)
    lines, total = [], 0
    for item in body.items:
        obj = db.get(MODELS[item.item_type], item.item_id)
        if not obj:
            raise HTTPException(404, "Catalog item no longer exists")
        cost = _price(item, obj, reserve=False)
        total += cost
        name = getattr(obj, "name", None) or obj.operator
        lines.append({"name": name, "item_type": item.item_type, "item_id": item.item_id,
                      "total_inr": cost, "quantity": item.quantity})
    return {"total_inr": total, "lines": lines,
            "notice": "Booking request only. Provider confirmation is required; no payment will be taken."}


@router.post("/quote")
def quote(body: QuoteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return price_quote(body, db)


@router.post("/bookings", response_model=BookingOut, status_code=201)
def request_booking(body: RequestIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    fingerprint = hashlib.sha256(body.model_dump_json(exclude={"request_key"}).encode()).hexdigest()
    def existing():
        entry = db.scalar(select(BookingRequestDetails).where(BookingRequestDetails.request_key == str(body.request_key)))
        if entry:
            if entry.user_id != user.id or entry.fingerprint != fingerprint:
                raise HTTPException(409, "This request reference has already been used")
            return db.get(Booking, entry.booking_id)
    previous = existing()
    if previous:
        return previous
    current = price_quote(body, db)
    if current["total_inr"] != body.expected_total_inr:
        raise HTTPException(409, "The price changed. Review the latest quote before confirming.")
    try:
        booking = build_booking(body, user, db, commit=False)
        if booking.total_inr != body.expected_total_inr:
            raise HTTPException(409, "The price changed. Review the latest quote before confirming.")
        db.add(BookingRequestDetails(booking_id=booking.id, user_id=user.id, request_key=str(body.request_key),
                                    fingerprint=fingerprint, traveler=body.traveler.model_dump(mode="json")))
        db.commit()
    except IntegrityError as error:
        db.rollback()
        previous = existing()
        if previous:
            return previous
        raise HTTPException(409, "Request changed. Review and retry.") from error
    return booking


class EnquiryIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    topic: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    message: str = Field(min_length=5, max_length=4000)


@router.post("/enquiries", status_code=201)
def enquiry(body: EnquiryIn, db: Session = Depends(get_db)):
    email = str(body.email).lower()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    count = db.scalar(select(func.count()).select_from(ContactEnquiry).where(
        ContactEnquiry.email == email, ContactEnquiry.created_at >= cutoff))
    if count >= 5:
        raise HTTPException(429, "Please allow time for your previous enquiries before sending another.")
    row = ContactEnquiry(**body.model_dump(exclude={"email"}), email=email)
    db.add(row)
    db.commit()
    return {"reference": row.id, "status": "received", "message": "Your enquiry is saved. Email delivery is not configured."}


class SubscribeIn(BaseModel):
    email: EmailStr


@router.post("/newsletter")
def newsletter(body: SubscribeIn, db: Session = Depends(get_db)):
    email = str(body.email).lower()
    if not db.get(NewsletterSubscription, email):
        db.add(NewsletterSubscription(email=email))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # simultaneous subscriptions are also idempotent
    return {"status": "subscribed", "message": "Subscription saved. Email delivery is not configured."}
class AgentReviewIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    destination_name: str | None = None
    items: list[BookingItemIn]
    traveler: dict | None = None


@router.post("/agent-review")
def agent_review(body: AgentReviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # 1. Resolve destination
    dest = None
    if body.destination_name:
        dest = db.scalar(select(Destination).where(Destination.name.ilike(f"%{body.destination_name.strip()}%")))
    if not dest and body.items:
        first_item = body.items[0]
        model_cls = MODELS.get(first_item.item_type)
        if model_cls:
            obj = db.get(model_cls, first_item.item_id)
            if obj and getattr(obj, "destination_id", None):
                dest = db.get(Destination, obj.destination_id)
            elif obj and first_item.item_type == "package":
                dest = db.get(Destination, getattr(obj, "destination_id", None))
    if not dest:
        dest = db.scalar(select(Destination).where(Destination.name == "Kashmir")) or db.scalars(select(Destination)).first()

    # 2. Retrieve catalog entities for this specific destination
    stays = db.scalars(select(Stay).where(Stay.destination_id == dest.id).order_by(Stay.price_inr).limit(4)).all()
    foods = db.scalars(select(FoodPlace).where(FoodPlace.destination_id == dest.id).order_by(FoodPlace.price_inr).limit(4)).all()
    experiences = db.scalars(select(Experience).where(Experience.destination_id == dest.id).order_by(Experience.id).limit(4)).all()

    # 3. Format traveler & trip summary
    traveler_info = body.traveler or {}
    guest_name = traveler_info.get("first", "Traveler")
    party_size = body.items[0].quantity if body.items else 2
    start_date = body.items[0].start_date if body.items and body.items[0].start_date else dt.date.today()
    item_types = {it.item_type for it in body.items}

    # 4. Invoke NVIDIA NIM multi-agent analysis with structured schema
    nim_client = get_nim_client()
    system_prompt = (
        "You are Voyara's Multi-Agent Travel Review Council. Generate a rigorous, systematic review for a trip request. "
        "This is one hosted model review, not independently executed agents or supplier verification. All inventory is synthetic. Never claim verified amenities, availability, taxes or guaranteed savings. "
        "Return ONLY a JSON object with keys: trip_consultant, stay_agent, food_guide_agent, budget_booking_agent. "
        "Each key must map to an object with fields: verdict (1-2 sentences), score (e.g. '9.4/10'), and recommendation (concrete advice for this specific destination). "
        f"The destination is strictly {dest.name}, {dest.state}, India. "
        f"Available local food specialties: {', '.join(f.name + ' (' + f.cuisine + ')' for f in foods) if foods else 'Regional authentic dining'}. "
        f"Available stays: {', '.join(s.name for s in stays) if stays else 'Curated lodges'}. "
        f"Available experiences: {', '.join(e.name for e in experiences) if experiences else 'Scenic tours'}."
    )
    user_prompt = (
        f"Review trip request for {guest_name} to {dest.name}. "
        f"Party size: {party_size} guests. Travel date: {start_date}. "
        f"Requested items: {', '.join(item_types)}. "
        "Provide authentic destination-specific assessments for Kashmir or the requested destination without confusing it with other states."
    )

    ai_data = None
    try:
        ai_data = nim_client.chat_json([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
    except Exception:
        ai_data = None

    expected = ("trip_consultant", "stay_agent", "food_guide_agent", "budget_booking_agent")
    if not isinstance(ai_data, dict) or any(
        not isinstance(ai_data.get(key), dict)
        or not all(isinstance(ai_data[key].get(field), str) and ai_data[key][field].strip()
                   for field in ("verdict", "score", "recommendation"))
        for key in expected
    ):
        raise HTTPException(503, "Hosted booking review unavailable. Your quote is still available; no agent assessment was completed.")
    reviews = ai_data

    def _agent_card(agent_id, name, badge, color, icon, key):
        info = reviews.get(key, {})
        return {
            "id": agent_id,
            "name": name,
            "badge": badge,
            "color": color,
            "icon": icon,
            "verdict": info["verdict"],
            "score": info["score"],
            "recommendation": info["recommendation"]
        }

    agents_list = [
        _agent_card("trip_consultant", "Trip Consultant Agent", "Season & Pace Analysis", "sky", "compass", "trip_consultant"),
        _agent_card("stay_agent", "Stay Specialist Agent", "Catalog Stay Notes", "peach", "bed", "stay_agent"),
        _agent_card("food_guide_agent", "Food Guide Agent", f"{dest.name} Culinary Pairings", "orange", "sparkle", "food_guide_agent"),
        _agent_card("budget_booking_agent", "Fare & Booking Agent", "Indicative Cost Notes", "mint", "wallet", "budget_booking_agent")
    ]

    return {
        "status": "ok",
        "destination": {
            "id": dest.id,
            "name": dest.name,
            "state": dest.state,
            "best_season": dest.best_season or "All year",
            "climate": dest.climate or "Pleasant",
            "description": dest.description,
            "tag": "Signature Holiday",
            "rating": "4.8",
            "reviews": "12.4k"
        },
        "agents": agents_list,
        "curated_stays": [{"id": s.id, "name": s.name, "kind": s.kind, "price_inr": s.price_inr, "rating": s.rating, "amenities": s.amenities} for s in stays],
        "curated_experiences": [{"id": e.id, "name": e.name, "price_inr": e.price_inr} for e in experiences],
        "curated_food": [{"id": f.id, "name": f.name, "cuisine": f.cuisine, "price_inr": f.price_inr, "diet": f.diet} for f in foods]
    }


@router.get("/{unknown_path:path}", include_in_schema=False)
def unavailable_route(unknown_path: str):
    # Keep private intake records out of the generic catalog route namespace.
    raise HTTPException(404, "Not found")
