import datetime as dt
import uuid

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, Time
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
    profile: Mapped["UserProfile | None"] = relationship(back_populates="user", cascade="all, delete-orphan")


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
    avg_cost_inr: Mapped[int | None] = mapped_column(Integer)
    climate: Mapped[str | None] = mapped_column(String(120))


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
    status: Mapped[str] = mapped_column(String(12), default="requested")  # requested|cancelled
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
    start_time: Mapped[dt.time | None] = mapped_column(Time)
    duration_min: Mapped[int | None] = mapped_column(Integer)
    booking: Mapped[Booking] = relationship(back_populates="items")


class UserProfile(Base):
    __tablename__ = "user_profiles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    budget_range: Mapped[str | None] = mapped_column(String(40))
    travel_style: Mapped[str | None] = mapped_column(String(80))
    food_preferences: Mapped[list] = mapped_column(JSON, default=list)
    dietary_restrictions: Mapped[list] = mapped_column(JSON, default=list)
    accessibility_needs: Mapped[list] = mapped_column(JSON, default=list)
    preferred_transport: Mapped[list] = mapped_column(JSON, default=list)
    favorite_destinations: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    user: Mapped[User] = relationship(back_populates="profile")


class Itinerary(Base):
    __tablename__ = "itineraries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(140))
    destination_id: Mapped[int | None] = mapped_column(ForeignKey("destinations.id", ondelete="SET NULL"))
    start_date: Mapped[dt.date | None] = mapped_column(Date)
    end_date: Mapped[dt.date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    booking_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AIConversation(Base):
    __tablename__ = "ai_conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(140), default="New travel chat")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    messages: Mapped[list["AIMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="AIMessage.created_at"
    )


class AIMessage(Base):
    __tablename__ = "ai_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(12))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    conversation: Mapped[AIConversation] = relationship(back_populates="messages")


class AIMemory(Base):
    __tablename__ = "ai_memory"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(60))
    value: Mapped[dict] = mapped_column(JSON)
    source_conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="SET NULL")
    )
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Offer(Base):
    __tablename__ = "offers"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    discount_percent: Mapped[float | None] = mapped_column(Float, default=None)  # e.g. 20.0 = 20%
    discount_flat_inr: Mapped[int | None] = mapped_column(Integer, default=None)  # e.g. 250
    module: Mapped[str] = mapped_column(String(20))  # stays|food|transport|guides|any
    min_amount_inr: Mapped[int | None] = mapped_column(Integer, default=None)
    valid_till: Mapped[dt.date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(default=True)


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    item_type: Mapped[str] = mapped_column(String(10))  # stay|food|transport|guide
    item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(120), default=None)
    interest: Mapped[str | None] = mapped_column(String(120), default=None)  # e.g. "Goa in December"
    preferred_time: Mapped[str | None] = mapped_column(String(80), default=None)  # e.g. "Evening"
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
