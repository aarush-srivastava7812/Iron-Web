from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import AIConversation, AIMemory, User, UserProfile
from ..plan_drafts import invalidate
from ..schemas import ProfileOut, ProfilePatch
from ..agent_runtime import get_agent_runtime

router = APIRouter(prefix="/profile", tags=["profile"])
PREFERENCE_FIELDS = (
    "budget_range",
    "travel_style",
    "food_preferences",
    "dietary_restrictions",
    "accessibility_needs",
    "preferred_transport",
    "favorite_destinations",
)


@router.get("", response_model=ProfileOut)
def get_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        db.commit()
    return profile


@router.patch("", response_model=ProfileOut)
def update_profile(
    body: ProfilePatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    runtime = Depends(get_agent_runtime),
):
    with runtime.for_user(user.id).lock:
        return _save_profile(body, user, db)


def _save_profile(body, user, db):
    profile = db.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    db.flush()
    snapshot = {key: getattr(profile, key) for key in PREFERENCE_FIELDS}
    memory = db.scalar(
        select(AIMemory).where(AIMemory.user_id == user.id, AIMemory.category == "travel_preferences")
    )
    if memory is None:
        db.add(AIMemory(user_id=user.id, category="travel_preferences", value=snapshot))
    else:
        memory.value = snapshot
    for trip_id in db.scalars(select(AIConversation.id).where(AIConversation.user_id == user.id)):
        invalidate(db, trip_id)
    db.commit()
    return profile


@router.get("/bookings")
def booking_history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..models import Booking

    return db.scalars(
        select(Booking).where(Booking.user_id == user.id).order_by(Booking.created_at.desc())
    ).all()
