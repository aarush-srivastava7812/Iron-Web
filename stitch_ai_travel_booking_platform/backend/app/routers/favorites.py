from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Favorite, User, Stay, FoodPlace, TransportRoute, Guide, HolidayPackage
from ..schemas import FavoriteIn, FavoriteOut

router = APIRouter(prefix="/favorites", tags=["favorites"])
_MODELS = {"stay": Stay, "food": FoodPlace, "transport": TransportRoute, "guide": Guide, "package": HolidayPackage}


@router.get("", response_model=list[FavoriteOut])
def list_favorites(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Favorite).where(Favorite.user_id == user.id).order_by(Favorite.created_at.desc())
    ).all()


@router.post("", status_code=201, response_model=FavoriteOut)
def add_favorite(body: FavoriteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.item_type not in _MODELS:
        raise HTTPException(422, "Unknown catalog type")
    if not db.get(_MODELS[body.item_type], body.item_id):
        raise HTTPException(404, "Catalog item not found")
    existing = db.scalar(
        select(Favorite).where(
            Favorite.user_id == user.id,
            Favorite.item_type == body.item_type,
            Favorite.item_id == body.item_id,
        )
    )
    if existing:
        return existing
    favorite = Favorite(user_id=user.id, item_type=body.item_type, item_id=body.item_id)
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return favorite


@router.delete("/{item_type}/{item_id}", status_code=204)
def remove_favorite(item_type: str, item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(
        delete(Favorite).where(
            Favorite.user_id == user.id, Favorite.item_type == item_type, Favorite.item_id == item_id
        )
    )
    db.commit()
