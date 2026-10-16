import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import cast, or_, select, String
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import optional_current_user
from ..models import AIMemory, Destination, FoodPlace, Guide, Stay, TransportRoute, UserProfile
from ..models import User
from memory_adapter import CustomMemoryBridge, MemoryServiceError

router = APIRouter(tags=["catalog"])

KINDS = {"destinations": Destination, "stays": Stay, "food": FoodPlace,
         "transport": TransportRoute, "guides": Guide}
memory_bridge = CustomMemoryBridge()
image_catalog_path = Path(__file__).resolve().parents[3] / "image" / "images.json"
logger = logging.getLogger(__name__)


def _dict(o):
    return {c.name: getattr(o, c.name) for c in o.__table__.columns}


@router.get("/images.json", include_in_schema=False)
def get_image_catalog():
    with image_catalog_path.open(encoding="utf-8") as image_file:
        return json.load(image_file)


@router.get("/{kind}")
async def list_items(
    kind: str,
    response: Response,
    destination_id: int | None = None,
    max_price: int | None = Query(default=None, ge=0),
    min_rating: float | None = Query(default=None, ge=0, le=5),
    sub_kind: str | None = Query(default=None, alias="type"),
    search_term: str | None = Query(default=None, alias="q", max_length=120),
    cuisine: str | None = Query(default=None, max_length=60),
    diet: str | None = Query(default=None, max_length=20),
    amenity: str | None = Query(default=None, max_length=60),
    tag: str | None = Query(default=None, max_length=60),
    specialty: str | None = Query(default=None, max_length=60),
    origin_id: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User | None = Depends(optional_current_user),
):
    model = KINDS.get(kind)
    if not model:
        raise HTTPException(404, "Unknown catalog")
    stmt = select(model)
    if destination_id is not None and hasattr(model, "destination_id"):
        stmt = stmt.where(model.destination_id == destination_id)
    if max_price is not None and hasattr(model, "price_inr"):
        stmt = stmt.where(model.price_inr <= max_price)
    if min_rating is not None and hasattr(model, "rating"):
        stmt = stmt.where(model.rating >= min_rating)
    if sub_kind and hasattr(model, "kind"):
        stmt = stmt.where(model.kind == sub_kind)
    if sub_kind and hasattr(model, "mode"):
        stmt = stmt.where(model.mode == sub_kind)
    if origin_id is not None and hasattr(model, "origin_id"):
        stmt = stmt.where(model.origin_id == origin_id)
    if cuisine and kind == "food":
        stmt = stmt.where(FoodPlace.cuisine.ilike(f"%{cuisine}%"))
    if diet and kind == "food":
        stmt = stmt.where(FoodPlace.diet == diet)
    if tag and kind == "destinations":
        stmt = stmt.where(cast(Destination.tags, String).ilike(f"%{tag}%"))
    if specialty and kind == "guides":
        stmt = stmt.where(cast(Guide.specialties, String).ilike(f"%{specialty}%"))
    if search_term:
        columns = []
        for field in ("name", "description", "state", "country", "operator", "cuisine", "kind", "mode",
                      "languages", "specialties"):
            if hasattr(model, field):
                column = getattr(model, field)
                if field in ("languages", "specialties"):
                    columns.append(cast(column, String).ilike(f"%{search_term}%"))
                else:
                    columns.append(column.ilike(f"%{search_term}%"))
        if kind == "destinations":
            columns.append(cast(Destination.tags, String).ilike(f"%{search_term}%"))
        if columns:
            stmt = stmt.where(or_(*columns))
    # Rank the candidate catalog before paginating; otherwise early sample
    # flights can hide every train despite a saved train preference.
    records = [_dict(o) for o in db.scalars(stmt.order_by(model.id)
               .limit(1000 if user else limit).offset(0 if user else offset))]
    if amenity:
        records = [item for item in records if amenity in item.get("amenities", [])]
    items = records
    if user:
        if kind != "destinations":
            destination_ids = {item.get("destination_id") for item in items if item.get("destination_id")}
            related = db.scalars(select(Destination).where(Destination.id.in_(destination_ids))).all()
            by_id = {place.id: place for place in related}
            for item in items:
                place = by_id.get(item.get("destination_id"))
                if place:
                    item["destination_slug"] = place.slug
                    item["destination_name"] = place.name
                    item["destination_tags"] = place.tags
        for item in items:
            item["catalogKind"] = "food" if kind == "food" else kind.removesuffix("s")
        profile = db.get(UserProfile, user.id)
        saved_memory = db.scalars(
            select(AIMemory).where(AIMemory.user_id == user.id).order_by(AIMemory.updated_at.desc())
        ).all()
        preferences = {}
        if profile:
            preferences = {
                "budget_tier": profile.budget_range,
                "dietary_choices": profile.dietary_restrictions + profile.food_preferences,
                "preferred_transport": profile.preferred_transport,
                "travel_style": profile.travel_style,
                "favorite_environments": profile.favorite_destinations,
            }
        for memory in saved_memory:
            if isinstance(memory.value, dict):
                preferences.update(memory.value)
        try:
            external_preferences = await memory_bridge.get_user_long_term_preferences(user.id)
            preferences.update(external_preferences)
        except MemoryServiceError as exc:
            logger.warning("Memory preference lookup failed: %s", exc)
            response.headers["X-Memory-Status"] = "unavailable"
        if any(preferences.values()):
            items = memory_bridge.filter_inventory_by_preferences(items, preferences)
    return items[offset:offset + limit] if user else items


@router.get("/{kind}/{item_id}")
def get_item(kind: str, item_id: int, db: Session = Depends(get_db)):
    model = KINDS.get(kind)
    obj = db.get(model, item_id) if model else None
    if not obj:
        raise HTTPException(404, "Not found")
    return _dict(obj)
