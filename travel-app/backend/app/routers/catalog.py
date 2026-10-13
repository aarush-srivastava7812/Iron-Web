from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Destination, FoodPlace, Guide, Stay, TransportRoute

router = APIRouter(tags=["catalog"])

KINDS = {"destinations": Destination, "stays": Stay, "food": FoodPlace,
         "transport": TransportRoute, "guides": Guide}


def _dict(o):
    return {c.name: getattr(o, c.name) for c in o.__table__.columns}


@router.get("/{kind}")
def list_items(
    kind: str,
    destination_id: int | None = None,
    max_price: int | None = Query(default=None, ge=0),
    min_rating: float | None = Query(default=None, ge=0, le=5),
    sub_kind: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    model = KINDS.get(kind)
    if not model:
        raise HTTPException(404, "Unknown catalog")
    q = select(model)
    if destination_id is not None and hasattr(model, "destination_id"):
        q = q.where(model.destination_id == destination_id)
    if max_price is not None and hasattr(model, "price_inr"):
        q = q.where(model.price_inr <= max_price)
    if min_rating is not None and hasattr(model, "rating"):
        q = q.where(model.rating >= min_rating)
    if sub_kind and hasattr(model, "kind"):
        q = q.where(model.kind == sub_kind)
    if sub_kind and hasattr(model, "mode"):
        q = q.where(model.mode == sub_kind)
    return [_dict(o) for o in db.scalars(q.order_by(model.id).limit(limit).offset(offset))]


@router.get("/{kind}/{item_id}")
def get_item(kind: str, item_id: int, db: Session = Depends(get_db)):
    model = KINDS.get(kind)
    obj = db.get(model, item_id) if model else None
    if not obj:
        raise HTTPException(404, "Not found")
    return _dict(obj)
