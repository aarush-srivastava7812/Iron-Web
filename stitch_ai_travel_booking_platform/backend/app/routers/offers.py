import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Offer
from ..schemas import OfferOut, OfferValidateIn, OfferValidateOut

router = APIRouter(prefix="/offers", tags=["offers"])


def _live(stmt):
    today = dt.date.today()
    return stmt.where(Offer.active.is_(True), (Offer.valid_till.is_(None)) | (Offer.valid_till >= today))


def discount_for(offer: Offer, subtotal_inr: int) -> tuple[bool, int, str]:
    if not offer.active:
        return False, 0, "This offer is no longer active."
    if offer.valid_till and offer.valid_till < dt.date.today():
        return False, 0, f"This offer expired on {offer.valid_till.isoformat()}."
    if offer.min_amount_inr and subtotal_inr < offer.min_amount_inr:
        return False, 0, f"Add trips worth ₹{offer.min_amount_inr:,} to use this offer."
    amount = 0
    if offer.discount_percent:
        amount += round(subtotal_inr * offer.discount_percent / 100)
    if offer.discount_flat_inr:
        amount += offer.discount_flat_inr
    amount = min(amount, subtotal_inr)
    if amount <= 0:
        return False, 0, "No discount applies to this subtotal."
    return True, amount, "Offer applied."


@router.get("", response_model=list[OfferOut])
def list_offers(
    module: str | None = Query(default=None, max_length=20),
    db: Session = Depends(get_db),
):
    stmt = _live(select(Offer).order_by(Offer.id))
    if module and module != "any":
        stmt = stmt.where((Offer.module == module) | (Offer.module == "any"))
    return db.scalars(stmt).all()


@router.post("/validate", response_model=OfferValidateOut)
def validate(body: OfferValidateIn, db: Session = Depends(get_db)):
    offer = db.scalar(_live(select(Offer)).where(Offer.code == body.code.strip().upper()))
    if not offer:
        return OfferValidateOut(code=body.code.upper(), valid=False, message="We couldn't find that offer code.")
    valid, amount, message = discount_for(offer, body.subtotal_inr)
    return OfferValidateOut(code=offer.code, valid=valid, discount_inr=amount if valid else 0, message=message)
