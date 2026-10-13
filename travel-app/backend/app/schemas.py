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
    item_type: Literal["stay", "transport", "guide"]
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
