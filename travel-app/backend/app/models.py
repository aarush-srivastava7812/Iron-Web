import datetime as dt
import uuid

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(10), default="user")  # user | admin
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")


class Destination(Base):
    __tablename__ = "destinations"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(80))
    country: Mapped[str] = mapped_column(String(80), default="India")
    description: Mapped[str] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    best_season: Mapped[str | None] = mapped_column(String(80))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)


class _PlaceMixin:
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    rating: Mapped[float] = mapped_column(Float, default=0.0)


class Stay(_PlaceMixin, Base):
    __tablename__ = "stays"
    destination_id: Mapped[int] = mapped_column(ForeignKey("destinations.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # hotel|hostel|homestay|resort
    price_inr: Mapped[int] = mapped_column(Integer)  # per night
    amenities: Mapped[list] = mapped_column(JSON, default=list)


class FoodPlace(_PlaceMixin, Base):
    __tablename__ = "food_places"
    destination_id: Mapped[int] = mapped_column(ForeignKey("destinations.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # restaurant|cafe|street_stall
    cuisine: Mapped[str] = mapped_column(String(60))
    diet: Mapped[str] = mapped_column(String(10))  # veg|non_veg|both
    price_inr: Mapped[int] = mapped_column(Integer)  # avg cost for two


class TransportRoute(Base):
    __tablename__ = "transport_routes"
    id: Mapped[int] = mapped_column(primary_key=True)
    origin_id: Mapped[int] = mapped_column(ForeignKey("destinations.id"), index=True)
    destination_id: Mapped[int] = mapped_column(ForeignKey("destinations.id"), index=True)
    mode: Mapped[str] = mapped_column(String(10))  # flight|train|bus|cab|ferry
    operator: Mapped[str] = mapped_column(String(80))
    duration_min: Mapped[int] = mapped_column(Integer)
    price_inr: Mapped[int] = mapped_column(Integer)  # per seat
    seats_available: Mapped[int] = mapped_column(Integer)


class Guide(Base):
    __tablename__ = "guides"
    id: Mapped[int] = mapped_column(primary_key=True)
    destination_id: Mapped[int] = mapped_column(ForeignKey("destinations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    languages: Mapped[list] = mapped_column(JSON, default=list)
    specialties: Mapped[list] = mapped_column(JSON, default=list)
    price_inr: Mapped[int] = mapped_column(Integer)  # per day
    rating: Mapped[float] = mapped_column(Float, default=0.0)


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="confirmed")  # confirmed|cancelled
    total_inr: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    user: Mapped[User] = relationship(back_populates="bookings")
    items: Mapped[list["BookingItem"]] = relationship(back_populates="booking", cascade="all, delete-orphan")


class BookingItem(Base):
    __tablename__ = "booking_items"
    __table_args__ = (Index("ix_item_ref", "item_type", "item_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True)
    item_type: Mapped[str] = mapped_column(String(10))  # stay|transport|guide
    item_id: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_inr: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[dt.date | None] = mapped_column(Date)
    end_date: Mapped[dt.date | None] = mapped_column(Date)
    booking: Mapped[Booking] = relationship(back_populates="items")
