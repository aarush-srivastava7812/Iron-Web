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
    start_time: dt.time | None = None
    duration_min: int | None = Field(default=None, ge=1, le=1440)


class BookingIn(BaseModel):
    items: list[BookingItemIn] = Field(min_length=1, max_length=20)
    coupon_code: str | None = Field(default=None, max_length=40)


class BookingItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    item_type: str
    item_id: int
    quantity: int
    unit_price_inr: int
    start_date: dt.date | None
    end_date: dt.date | None
    start_time: dt.time | None
    duration_min: int | None


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


class OfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    title: str
    description: str | None
    discount_percent: float | None
    discount_flat_inr: int | None
    module: str
    min_amount_inr: int | None
    valid_till: dt.date | None
    active: bool


class OfferValidateIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    subtotal_inr: int = Field(ge=0)


class OfferValidateOut(BaseModel):
    code: str
    valid: bool
    discount_inr: int = 0
    message: str


class FavoriteIn(BaseModel):
    item_type: Literal["stay", "food", "transport", "guide"]
    item_id: int = Field(ge=1)


class FavoriteOut(BaseModel):
    item_type: str
    item_id: int
    created_at: dt.datetime


class LeadIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=20, pattern=r"^[0-9+\-\s()]+$")
    email: EmailStr | None = None
    interest: str | None = Field(default=None, max_length=120)
    preferred_time: str | None = Field(default=None, max_length=80)


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    phone: str
    email: str | None
    interest: str | None
    preferred_time: str | None
    created_at: dt.datetime
