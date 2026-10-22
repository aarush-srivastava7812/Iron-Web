"""Owned, revision-checked trip resources over the existing SQL workspace."""

from copy import deepcopy
import datetime as dt
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..agent_runtime import get_agent_runtime
from ..models import (
    AIConversation,
    TripWorkspace,
    User,
    Destination,
    DestinationResearch,
    MapPlace,
    AIMemory,
    Stay,
    Experience,
    TransportRoute,
)
from .. import journey
from .. import travel_planning as planning

router = APIRouter(tags=["travel planning"])


class Versioned(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


class TripIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="My trip", min_length=1, max_length=140)
    constraints: planning.Constraints


class TripUpdate(Versioned):
    constraints: planning.Constraints | None = None
    status: Literal["draft", "planned", "completed"] | None = None


class ItineraryUpdate(Versioned):
    itinerary: dict


class Reservation(Versioned):
    kind: Literal["stay", "activity", "outbound", "return"]
    item_id: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=120)
    start: dt.datetime
    end: dt.datetime
    arrival_hour: int | None = Field(default=None, ge=0, le=23)
    checkin_closes_hour: int = Field(default=23, ge=0, le=23)


class Feedback(Versioned):
    preference: Literal["pace", "dietary", "interests", "hotel_style"]
    value: str | list[str]
    remember: bool = False
    note: str = Field(default="", max_length=2000)


class Collaboration(Versioned):
    action: Literal["invite", "comment", "vote"]
    user_id: str | None = Field(default=None, max_length=36)
    text: str = Field(default="", max_length=2000)
    option_id: str | None = Field(default=None, max_length=100)


class ResearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topics: list[str] = Field(
        default_factory=lambda: ["season", "permits", "hours", "accessibility"],
        min_length=1,
        max_length=12,
    )
    force: bool = False


class MemoryRecallIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topics: list[str] = Field(default_factory=lambda: ["hours", "permits", "accessibility"], min_length=1, max_length=12)
    auto_refresh: bool = True


class Readiness(Versioned):
    checks: dict[str, bool] = Field(max_length=32)


class Replan(Versioned):
    date: dt.date
    action: Literal["half_day", "rest_day", "replace"]
    item_id: int | None = None
    alternative_id: int | None = None


def owned(db, user, identifier, *, editor=True):
    conversation = db.get(AIConversation, identifier)
    if conversation is None:
        raise HTTPException(404, "Trip not found.")
    row = db.get(TripWorkspace, identifier)
    owner = conversation.user_id == user.id
    member = row and user.id in row.data.get("travel", {}).get("members", [])
    if not owner and (editor or not member):
        raise HTTPException(404, "Trip not found.")
    if row is None:
        row = journey.workspace(db, identifier)
    return conversation, row


def save(db, row, data, expected):
    if row.revision != expected:
        raise HTTPException(409, "Trip changed. Reload its latest revision.")
    travel = data.get("travel", {})
    if (
        travel.get("plan_revision") == row.revision
        and data.get("draft") == row.data.get("draft")
        and data.get("selections") == row.data.get("selections")
    ):
        travel["plan_revision"] = expected + 1
    result = db.execute(
        update(TripWorkspace)
        .where(
            TripWorkspace.conversation_id == row.conversation_id,
            TripWorkspace.revision == expected,
        )
        .values(data=data, revision=expected + 1)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Trip changed. Reload its latest revision.")
    from .. import plan_drafts

    plan_drafts.invalidate(db, row.conversation_id)
    db.commit()
    db.refresh(row)
    return present(row)


def present(row):
    return dict(
        id=row.conversation_id,
        revision=row.revision,
        draft=row.data.get("draft", {}),
        selections=row.data.get("selections", {}),
        **row.data.get("travel", {"status": "draft"}),
    )


def checked_build(db, constraints, selections=None):
    try:
        return planning.build(db, constraints, selections)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


def current_constraints(row):
    travel = row.data.get("travel", {})
    try:
        # Existing website edits are always authoritative over saved plan inputs.
        extra = travel.get("constraints", {})
        return planning.from_draft({**extra, **row.data.get("draft", {})})
    except ValueError as error:
        raise HTTPException(
            422, "Add valid destination, dates, guests and budget before planning."
        ) from error


def publish_plan(row, plan):
    data = deepcopy(row.data)
    travel = data.setdefault("travel", {"status": "draft"})
    if travel.get("plan"):
        versions = travel.setdefault("versions", [])
        versions.append(dict(revision=row.revision, plan=travel["plan"]))
        travel["versions"] = versions[-50:]
    travel.update(
        plan=plan, constraints=plan["constraints"], plan_revision=row.revision + 1
    )
    travel["input_selections"] = deepcopy(row.data.get("selections", {}))
    travel["research_stale"] = True
    return data


def current_plan(db, row, constraints):
    plan = checked_build(db, constraints, row.data.get("selections"))
    saved = row.data.get("travel", {})
    if saved.get("plan", {}).get("constraints") == plan["constraints"] and saved.get(
        "input_selections", {}
    ) == row.data.get("selections", {}):
        try:
            plan["itinerary"] = planning.validate_schedule(
                db,
                constraints,
                planning.city(db, constraints.destination),
                saved["plan"]["itinerary"],
            )
            cost = sum(
                i.get("price_inr", 0) * constraints.traveller_count
                for day in plan["itinerary"]["days"]
                for i in day["items"]
            )
            plan["budget"] = planning.quote(
                db,
                constraints,
                planning.city(db, constraints.destination),
                activity_cost=cost,
                stay_id=row.data.get("selections", {}).get("stay"),
            )
            plan["summary"]["activity_count"] = sum(
                i["kind"] == "activity"
                for day in plan["itinerary"]["days"]
                for i in day["items"]
            )
            plan["summary"]["effort_minutes"] = sum(
                day["effort_minutes"] for day in plan["itinerary"]["days"]
            )
            plan["ready"] = (
                not plan["conflicts"]
                and not plan["unverified_requirements"]
                and plan["budget"]["within_budget"]
            )
        except (KeyError, ValueError, TypeError) as error:
            raise HTTPException(
                422, "Saved itinerary needs review: " + str(error)
            ) from error
    return plan


@router.post("/travel/plan")
def preview(
    body: planning.Constraints,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return dict(
        discovery=planning.discover(db, body),
        plan=checked_build(db, body) if body.destination else None,
    )


@router.post("/travel/destinations/search")
def search(
    body: planning.Constraints,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return planning.discover(db, body)


@router.get("/travel/destinations/{destination_id}")
def destination(
    destination_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    item = db.get(Destination, destination_id)
    if item is None:
        raise HTTPException(404, "Destination not found.")
    nearby = sorted(
        [
            dict(
                id=d.id,
                name=d.name,
                distance_km=round(
                    planning.distance_km(item.lat, item.lng, d.lat, d.lng), 1
                ),
            )
            for d in db.scalars(select(Destination))
            if d.id != item.id
        ],
        key=lambda d: d["distance_km"],
    )[:10]
    return dict(
        id=item.id,
        name=item.name,
        description=item.description,
        tags=item.tags,
        season=item.best_season,
        season_source="sample catalog, verify before travel",
        nearby=nearby,
        accessibility="unknown",
        weather="unknown; no current weather source",
        permits="unknown",
        map_places=[
            dict(
                id=p.osm_id,
                name=p.name,
                category=p.category,
                lat=p.lat,
                lng=p.lng,
                tags=p.tags,
                provenance=p.provenance,
            )
            for p in db.scalars(
                select(MapPlace).where(MapPlace.destination_id == item.id).limit(100)
            )
        ],
    )


@router.post("/travel/destinations/{destination_id}/research", status_code=202)
def research(
    destination_id: int,
    body: ResearchIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if db.get(Destination, destination_id) is None:
        raise HTTPException(404, "Destination not found.")
    from .. import destination_research

    try:
        job = destination_research.start(
            db, user.id, destination_id, body.topics, body.force
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return dict(id=job.id, status=job.status, status_url="/travel/research/" + job.id)


@router.get("/travel/research/{identifier}")
def research_status(
    identifier: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    job = db.get(DestinationResearch, identifier)
    if job is None or job.requested_by != user.id:
        raise HTTPException(404, "Research job not found.")
    return dict(id=job.id, status=job.status, topics=job.topics, **job.payload)


@router.get("/travel/destinations/{destination_id}/research-needs")
def research_needs(
    destination_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if db.get(Destination, destination_id) is None:
        raise HTTPException(404, "Destination not found.")
    from ..destination_research import research_needs

    return research_needs(db, user.id, destination_id)


@router.post("/travel/destinations/{destination_id}/memory/recall")
def recall_external_memory(
    destination_id: int, body: MemoryRecallIn, user: User = Depends(current_user),
    db: Session = Depends(get_db), runtime=Depends(get_agent_runtime),
):
    from .. import external_memory
    if db.get(Destination, destination_id) is None:
        raise HTTPException(404, "Destination not found.")
    try:
        traveler = runtime.for_user(user.id)
        with traveler.lock:
            return external_memory.recall(db, user.id, destination_id, body.topics, traveler=traveler, auto_refresh=body.auto_refresh)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/travel/destinations/{destination_id}/memory")
def external_memory_history(destination_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..external_memory import Version, present
    rows = db.scalars(select(Version).where(Version.user_id == user.id, Version.destination_id == destination_id).order_by(Version.created_at.desc()).limit(100))
    return dict(versions=[present(row) for row in rows], notice="Owner-scoped source observations; fresh does not mean verified.")


@router.post("/trips", status_code=201)
def create(
    body: TripIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    plan = checked_build(db, body.constraints)
    conversation = AIConversation(user_id=user.id, title=body.title)
    db.add(conversation)
    db.flush()
    draft = {
        k: v
        for k, v in body.constraints.model_dump(mode="json").items()
        if k in journey.JourneyDraft.model_fields
    }
    row = TripWorkspace(
        conversation_id=conversation.id,
        revision=1,
        data=dict(
            draft=draft,
            selections={},
            travel=dict(
                status="draft",
                plan=plan,
                constraints=body.constraints.model_dump(mode="json"),
                plan_revision=1,
            ),
        ),
    )
    db.add(row)
    db.commit()
    return present(row)


@router.get("/trips")
def list_trips(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(AIConversation, TripWorkspace)
        .outerjoin(TripWorkspace)
        .where(AIConversation.user_id == user.id)
        .order_by(AIConversation.updated_at.desc())
        .limit(100)
    ).all()
    return [
        dict(
            id=c.id,
            title=c.title,
            revision=w.revision if w else 0,
            status=(w.data.get("travel", {}).get("status", "draft") if w else "draft"),
        )
        for c, w in rows
    ]


@router.post("/trips/compare")
def compare(
    body: list[str], user: User = Depends(current_user), db: Session = Depends(get_db)
):
    if not 2 <= len(body) <= 8:
        raise HTTPException(422, "Compare two to eight trips.")
    plans = []
    for identifier in body:
        _, row = owned(db, user, identifier)
        plans.append((identifier, current_plan(db, row, current_constraints(row))))
    return planning.compare(plans)


@router.get("/trips/{identifier}")
def get(
    identifier: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _, row = owned(db, user, identifier, editor=False)
    result = present(row)
    result["plan_stale"] = (
        row.data.get("travel", {}).get("plan_revision") != row.revision
    )
    return result


@router.patch("/trips/{identifier}")
def revise(
    identifier: str,
    body: TripUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, row = owned(db, user, identifier)
    constraints = body.constraints or current_constraints(row)
    plan = current_plan(db, row, constraints)
    if body.status == "planned" and not plan["ready"]:
        raise HTTPException(
            422,
            "Resolve conflicts, budget and unverified mandatory conditions before marking planned.",
        )
    data = publish_plan(row, plan)
    data["draft"] = {
        k: v
        for k, v in constraints.model_dump(mode="json").items()
        if k in journey.JourneyDraft.model_fields
    }
    data["travel"]["status"] = body.status or data["travel"].get("status", "draft")
    return save(db, row, data, body.expected_revision)


@router.post("/trips/{identifier}/duplicate", status_code=201)
def duplicate(
    identifier: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    old, row = owned(db, user, identifier)
    conversation = AIConversation(user_id=user.id, title=(old.title + " · copy")[:140])
    db.add(conversation)
    db.flush()
    data = deepcopy(row.data)
    data["travel"] = {
        k: v
        for k, v in data.get("travel", {}).items()
        if k in {"constraints", "plan", "versions"}
    }
    data["travel"].update(status="draft", plan_revision=1)
    data.pop("confirmed", None)
    copy = TripWorkspace(conversation_id=conversation.id, revision=1, data=data)
    db.add(copy)
    db.commit()
    return present(copy)


@router.delete("/trips/{identifier}", status_code=204)
def delete(
    identifier: str,
    expected_revision: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    runtime=Depends(get_agent_runtime),
):
    conversation, row = owned(db, user, identifier)
    if row.revision != expected_revision:
        raise HTTPException(409, "Trip changed. Reload before deleting.")
    runtime.for_user(user.id).forget_trip(identifier)
    db.delete(conversation)
    db.commit()


@router.post("/trips/{identifier}/itinerary/generate")
@router.post("/trips/{identifier}/budget/recalculate")
def generate(
    identifier: str,
    body: Versioned,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, row = owned(db, user, identifier)
    c = current_constraints(row)
    plan = (
        current_plan(db, row, c)
        if request.url.path.endswith("recalculate")
        else checked_build(db, c, row.data.get("selections"))
    )
    return save(db, row, publish_plan(row, plan), body.expected_revision)


@router.patch("/trips/{identifier}/itinerary")
def edit_itinerary(
    identifier: str,
    body: ItineraryUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, row = owned(db, user, identifier)
    c = current_constraints(row)
    plan = checked_build(db, c, row.data.get("selections"))
    try:
        if (
            len(body.itinerary.get("days", [])) > 60
            or sum(len(d.get("items", [])) for d in body.itinerary.get("days", []))
            > 500
        ):
            raise ValueError("Itinerary exceeds the editing limit.")
        schedule = planning.validate_schedule(
            db, c, planning.city(db, c.destination), body.itinerary
        )
        issues = planning.conflicts(c, schedule)
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(422, "Malformed itinerary dates or items.") from error
    if issues:
        raise HTTPException(
            422, dict(message="Resolve itinerary conflicts", conflicts=issues)
        )
    plan["itinerary"] = schedule
    cost = sum(
        i.get("price_inr", 0) * c.traveller_count
        for day in schedule["days"]
        for i in day["items"]
    )
    plan["budget"] = planning.quote(
        db,
        c,
        planning.city(db, c.destination),
        activity_cost=cost,
        stay_id=row.data.get("selections", {}).get("stay"),
    )
    plan["summary"]["activity_count"] = sum(
        i["kind"] == "activity" for day in schedule["days"] for i in day["items"]
    )
    plan["summary"]["effort_minutes"] = sum(
        day["effort_minutes"] for day in schedule["days"]
    )
    plan["ready"] = (
        not plan["unverified_requirements"] and plan["budget"]["within_budget"]
    )
    plan["conflicts"] = []
    return save(db, row, publish_plan(row, plan), body.expected_revision)


@router.get("/trips/{identifier}/recommendations")
def recommendations(
    identifier: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    runtime=Depends(get_agent_runtime),
):
    _, row = owned(db, user, identifier, editor=False)
    c = current_constraints(row)
    options = planning.discover(db, c.model_copy(update={"destination": None}))
    preference_conflicts, memory_status = [], "ready"
    try:
        traveler = runtime.for_user(user.id)
        traveler.sync_profile(db)
        engine = traveler.service.engine(user.id)
        for field in ("pace", "dietary", "hotel_style"):
            answer = engine.recall(
                field, subject="Traveller", predicate=field, scope={}
            )
            saved = [
                e for e in answer.get("evidence", []) if e["accepted_for_current_use"]
            ]
            if saved and getattr(c, field) and saved[0]["value"] != getattr(c, field):
                preference_conflicts.append(
                    dict(
                        field=field,
                        remembered=saved[0]["value"],
                        trip=getattr(c, field),
                        claim_id=saved[0]["claim_id"],
                        choices=[
                            "Keep this trip choice",
                            "Revise to the remembered preference",
                        ],
                    )
                )
    except Exception:
        memory_status = "unavailable; preference conflict check is pending"
    return dict(
        discovery=options,
        packing=checked_build(db, c)["packing"],
        readiness=checked_build(db, c)["readiness"],
        research_stale=row.data.get("travel", {}).get("research_stale", True),
        preference_conflicts=preference_conflicts,
        memory_status=memory_status,
    )


@router.post("/trips/{identifier}/readiness")
def readiness(
    identifier: str,
    body: Readiness,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, row = owned(db, user, identifier)
    allowed = {
        "id_and_tickets",
        "medication",
        "charger",
        "clothing",
        "hours_and_permits",
        "transport_and_stays",
    }
    if not set(body.checks) <= allowed:
        raise HTTPException(422, "Unknown readiness item.")
    data = deepcopy(row.data)
    data.setdefault("travel", {}).setdefault("readiness_checks", {}).update(body.checks)
    return save(db, row, data, body.expected_revision)


@router.post("/trips/{identifier}/replan")
def replan(
    identifier: str,
    body: Replan,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, row = owned(db, user, identifier)
    c = current_constraints(row)
    plan = current_plan(db, row, c)
    day = next(
        (
            day
            for day in plan["itinerary"]["days"]
            if day["date"] == body.date.isoformat()
        ),
        None,
    )
    if day is None:
        raise HTTPException(422, "Choose a day inside this trip.")
    if body.action == "half_day":
        activity = next(
            (item for item in day["items"] if item["kind"] == "activity"), None
        )
        day["items"] = [activity] if activity else []
    elif body.action == "rest_day":
        day["items"] = []
    else:
        item = next(
            (
                item
                for item in day["items"]
                if item.get("id") == body.item_id and item["kind"] == "activity"
            ),
            None,
        )
        alternative = (
            db.get(Experience, body.alternative_id) if body.alternative_id else None
        )
        if (
            item is None
            or alternative is None
            or alternative.destination_id != plan["destination_id"]
        ):
            raise HTTPException(
                422, "Choose a catalog alternative in this trip's city."
            )
        item["id"] = alternative.id
        item["end_minute"] = item["start_minute"] + int(
            (alternative.display or {}).get("duration_min", 90)
        )
    try:
        schedule = planning.validate_schedule(
            db, c, planning.city(db, c.destination), plan["itinerary"]
        )
    except ValueError as error:
        raise HTTPException(422, "Alternative does not fit: " + str(error)) from error
    cost = sum(
        item.get("price_inr", 0) * c.traveller_count
        for day in schedule["days"]
        for item in day["items"]
    )
    plan["itinerary"] = schedule
    plan["budget"] = planning.quote(
        db,
        c,
        planning.city(db, c.destination),
        activity_cost=cost,
        stay_id=row.data.get("selections", {}).get("stay"),
    )
    plan["summary"]["activity_count"] = sum(
        item["kind"] == "activity" for day in schedule["days"] for item in day["items"]
    )
    plan["summary"]["effort_minutes"] = sum(
        day["effort_minutes"] for day in schedule["days"]
    )
    plan["ready"] = (
        not plan["unverified_requirements"] and plan["budget"]["within_budget"]
    )
    return save(db, row, publish_plan(row, plan), body.expected_revision)


@router.post("/trips/{identifier}/demo-reservations")
def reserve(
    identifier: str,
    body: Reservation,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, row = owned(db, user, identifier)
    if body.start.tzinfo is None or body.end.tzinfo is None or body.start >= body.end:
        raise HTTPException(422, "Use ordered timezone-aware reservation times.")
    c = current_constraints(row)
    if body.start.astimezone(
        ZoneInfo("Asia/Kolkata")
    ).date() < c.start_date or body.end.astimezone(
        ZoneInfo("Asia/Kolkata")
    ).date() > c.end_date + dt.timedelta(days=1):
        raise HTTPException(422, "Reservation falls outside the trip.")
    destination = planning.city(db, c.destination)
    try:
        item_id = int(body.item_id)
    except ValueError as error:
        raise HTTPException(422, "Use a catalog item ID.") from error
    model = (
        Stay
        if body.kind == "stay"
        else Experience
        if body.kind == "activity"
        else TransportRoute
    )
    catalog = db.get(model, item_id)
    if catalog is None or (
        body.kind in {"stay", "activity"} and catalog.destination_id != destination.id
    ):
        raise HTTPException(
            422, "Catalog item does not belong to this trip destination."
        )
    if (
        body.kind in {"stay", "activity"}
        and body.city.casefold() != destination.name.casefold()
    ):
        raise HTTPException(422, "Reservation city disagrees with its catalog item.")
    if body.kind in {"outbound", "return"}:
        origin = planning.city(db, c.origin)
        expected = (
            (origin.id if origin else None, destination.id)
            if body.kind == "outbound"
            else (destination.id, origin.id if origin else None)
        )
        if (catalog.origin_id, catalog.destination_id) != expected:
            raise HTTPException(
                422,
                "Transport does not connect this trip's origin and final destination.",
            )
    from .bookings import validate_existing
    from ..schemas import BookingItemIn

    local_start, local_end = (
        body.start.astimezone(ZoneInfo("Asia/Kolkata")),
        body.end.astimezone(ZoneInfo("Asia/Kolkata")),
    )
    try:
        proposed = BookingItemIn(
            item_type="stay"
            if body.kind == "stay"
            else "experience"
            if body.kind == "activity"
            else "transport",
            item_id=item_id,
            quantity=1,
            start_date=local_start.date(),
            end_date=local_end.date(),
            start_time=local_start.time() if body.kind != "stay" else None,
            duration_min=int((body.end - body.start).total_seconds() / 60)
            if body.kind != "stay"
            else None,
        )
    except ValueError as error:
        raise HTTPException(
            422, "Reservation duration is outside the supported daily window."
        ) from error
    validate_existing([proposed], user.id, db)
    data = deepcopy(row.data)
    item = dict(
        id=uuid4().hex,
        **body.model_dump(
            mode="json", exclude={"expected_revision"}, exclude_none=True
        ),
        demo=True,
        status="simulated",
        notice="No supplier reservation or payment has been made.",
    )
    travel = data.setdefault("travel", {})
    reservations = travel.setdefault("reservations", [])
    if len(reservations) >= 100:
        raise HTTPException(422, "Reservation limit reached.")
    reservations.append(item)
    foreign = list(
        db.scalars(
            select(TripWorkspace)
            .join(AIConversation)
            .where(
                AIConversation.user_id == user.id,
                TripWorkspace.conversation_id != identifier,
            )
        )
    )
    other_stays = [
        dict(r, foreign_trip=workspace.conversation_id)
        for workspace in foreign
        for r in workspace.data.get("travel", {}).get("reservations", [])
        if r["kind"] == "stay"
    ]
    issues = planning.conflicts(
        c, travel.get("plan", {}).get("itinerary", {}), reservations + other_stays
    )
    if issues:
        raise HTTPException(422, dict(conflicts=issues))
    return save(db, row, data, body.expected_revision)


@router.post("/trips/{identifier}/collaboration")
def collaborate(
    identifier: str,
    body: Collaboration,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, row = owned(db, user, identifier, editor=body.action == "invite")
    data = deepcopy(row.data)
    travel = data.setdefault("travel", {})
    if body.action == "invite":
        if not body.user_id or db.get(User, body.user_id) is None:
            raise HTTPException(422, "Choose an existing user ID.")
        travel["members"] = list(
            dict.fromkeys(travel.get("members", []) + [body.user_id])
        )[:30]
    else:
        entries = travel.setdefault("collaboration", [])
        entries.append(
            dict(
                actor=user.id,
                action=body.action,
                text=body.text,
                option_id=body.option_id,
                at=dt.datetime.now(dt.timezone.utc).isoformat(),
            )
        )
        travel["collaboration"] = entries[-200:]
    return save(db, row, data, body.expected_revision)


@router.post("/trips/{identifier}/feedback")
def feedback(
    identifier: str,
    body: Feedback,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    runtime=Depends(get_agent_runtime),
):
    _, row = owned(db, user, identifier)
    if row.revision != body.expected_revision:
        raise HTTPException(409, "Reload the latest revision.")
    trial = {
        **current_constraints(row).model_dump(mode="json"),
        body.preference: body.value,
    }
    try:
        planning.Constraints.model_validate(trial)
    except ValueError as error:
        raise HTTPException(
            422, "Feedback value is invalid for this preference."
        ) from error
    if body.remember:
        db.add(
            AIMemory(
                user_id=user.id,
                category="explicit_feedback",
                value={body.preference: body.value},
                source_conversation_id=identifier,
            )
        )
    data = deepcopy(row.data)
    entries = data.setdefault("travel", {}).setdefault("feedback", [])
    entries.append(body.model_dump(exclude={"expected_revision"}))
    data["travel"]["feedback"] = entries[-100:]
    result = save(db, row, data, body.expected_revision)
    if body.remember:
        # The committed SQL preference is the replayable input. A memory outage
        # must not publish a preference for a trip revision that failed its CAS.
        try:
            traveler = runtime.for_user(user.id)
            with traveler.lock:
                traveler.sync_profile(
                    db, source_text="Explicit trip feedback: " + str(body.value)
                )
            result["memory_status"] = "ready"
        except Exception:
            result["memory_status"] = (
                "pending; saved preference will retry on the next agent or catalog read"
            )
    return result
