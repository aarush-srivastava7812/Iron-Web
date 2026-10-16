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
                      HolidayPackage, NewsletterSubscription, Stay, TransportRoute, User, WebsiteStay)
from ..schemas import BookingIn, BookingOut
from .bookings import MODELS, _price, _validate_conflicts, build_booking

router = APIRouter(prefix="/website", tags=["website"])


@router.get("/catalog")
def catalog(db: Session = Depends(get_db)):
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
    }


@router.get("/flights")
def flights(origin_id: int, destination_id: int, depart: dt.date,
            return_date: dt.date | None = None, travelers: int = Query(ge=1, le=6, default=1),
            cabin: Literal["Economy"] = "Economy", db: Session = Depends(get_db)):
    if origin_id == destination_id or depart < dt.date.today() or (return_date and return_date < depart):
        raise HTTPException(422, "Choose different airports and valid future dates")
    def routes(a, b, date):
        rows = db.scalars(select(TransportRoute).where(TransportRoute.origin_id == a,
            TransportRoute.destination_id == b, TransportRoute.mode == "flight",
            TransportRoute.seats_available >= travelers).order_by(TransportRoute.price_inr)).all()
        return [dict(id=r.id, name=r.operator, duration_min=r.duration_min, price_inr=r.price_inr,
                     seats_available=r.seats_available, date=date, origin=db.get(Destination, a).name,
                     destination=db.get(Destination, b).name) for r in rows]
    return {"outbound": routes(origin_id, destination_id, depart),
            "return": routes(destination_id, origin_id, return_date) if return_date else [],
            "notice": "Stored sample routes, not live airline fares. Dates are requested dates; schedules and availability require confirmation."}


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
    _validate_conflicts(body.items)
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
    return {"status": "subscribed", "message": "Subscription saved. Newsletters will start when email delivery is configured."}


@router.get("/{unknown_path:path}", include_in_schema=False)
def unavailable_route(unknown_path: str):
    # Keep private intake records out of the generic catalog route namespace.
    raise HTTPException(404, "Not found")
