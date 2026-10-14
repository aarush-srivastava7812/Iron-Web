import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)


class LoginIn(BaseModel):
    identifier: str  # email or username
    password: str


class UserPatch(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    username: str
    full_name: str | None
    phone: str | None
    created_at: dt.datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class BookingItemIn(BaseModel):
    item_type: Literal["stay", "food", "transport", "guide"]
    item_id: int
    quantity: int = Field(default=1, ge=1, le=20)
    start_date: dt.date | None = None
    end_date: dt.date | None = None


class BookingIn(BaseModel):
    items: list[BookingItemIn] = Field(min_length=1, max_length=20)


class BookingItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    item_type: str
    item_id: int
    quantity: int
    unit_price_inr: int
    start_date: dt.date | None
    end_date: dt.date | None


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    total_inr: int
    created_at: dt.datetime
    items: list[BookingItemOut]


class ProfilePatch(BaseModel):
    budget_range: str | None = Field(default=None, max_length=40)
    travel_style: str | None = Field(default=None, max_length=80)
    food_preferences: list[str] | None = Field(default=None, max_length=20)
    dietary_restrictions: list[str] | None = Field(default=None, max_length=20)
    accessibility_needs: list[str] | None = Field(default=None, max_length=20)
    preferred_transport: list[str] | None = Field(default=None, max_length=10)
    favorite_destinations: list[str] | None = Field(default=None, max_length=30)


class ProfileOut(ProfilePatch):
    model_config = ConfigDict(from_attributes=True)
    updated_at: dt.datetime


class ItineraryIn(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    destination_id: int | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    notes: str = Field(default="", max_length=4000)
    booking_ids: list[int] = Field(default_factory=list, max_length=100)


class ItineraryOut(ItineraryIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: str
    created_at: dt.datetime


class ConversationIn(BaseModel):
    title: str = Field(default="New travel chat", min_length=1, max_length=140)


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class MemoryIn(BaseModel):
    category: str = Field(min_length=1, max_length=60)
    value: dict
    source_conversation_id: str | None = None
