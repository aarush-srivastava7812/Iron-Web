"""Deterministic travel decisions shared by APIs, editors and agent tools.

Catalog prices are sample estimates. Missing hours, accessibility and routes
remain unknown until separately verified research supplies evidence.
"""

from __future__ import annotations

from copy import deepcopy
import datetime as dt
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from .models import Destination, Experience, Stay, TransportRoute


class Constraints(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    destination: str | None = Field(default=None, max_length=120)
    origin: str | None = Field(default=None, max_length=120)
    start_date: dt.date
    end_date: dt.date
    traveller_count: int = Field(default=1, ge=1, le=30, strict=True)
    budget: int = Field(gt=0, le=10**9, strict=True)
    pace: Literal["relaxed", "moderate", "packed"] = "moderate"
    group_type: Literal["solo", "couple", "family", "friends", "seniors"] = "friends"
    interests: list[str] = Field(default_factory=list, max_length=256)
    hard_tags: list[str] = Field(default_factory=list, max_length=16)
    hard_requirements: list[str] = Field(default_factory=list, max_length=256)
    soft_preferences: list[str] = Field(default_factory=list, max_length=256)
    dietary: str | None = Field(default=None, max_length=80)
    transport_mode: Literal["flight", "train", "bus", "car"] | None = None
    hotel_style: Literal["budget", "mid-range", "luxury"] = "budget"
    stay_amenities: list[str] = Field(default_factory=list, max_length=16)
    max_transport_minutes: int = Field(default=1440, ge=15, le=10080)
    arrival_hour: int = Field(default=13, ge=0, le=23)
    departure_hour: int = Field(default=16, ge=0, le=23)

    @model_validator(mode="after")
    def dates(self):
        if not 1 <= (self.end_date - self.start_date).days + 1 <= 60:
            raise ValueError("Trip dates must span one to sixty days.")
        return self

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1


def from_draft(draft):
    return Constraints.model_validate(
        {
            k: v
            for k, v in draft.items()
            if k in Constraints.model_fields and v is not None
        }
    )


def city(db, value):
    if value is None:
        return None
    return next(
        (
            d
            for d in db.scalars(select(Destination))
            if value.casefold() in {d.name.casefold(), d.slug.casefold()}
        ),
        None,
    )


def distance_km(a_lat, a_lng, b_lat, b_lng):
    lat1, lat2 = math.radians(a_lat), math.radians(b_lat)
    value = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(math.radians(b_lng - a_lng) / 2) ** 2
    )
    return 6371 * 2 * math.asin(min(1, math.sqrt(value)))


def quote(db, constraints, destination, *, activity_cost=None, stay_id=None):
    """Integer INR calculation; each unit and missing-data assumption is explicit."""
    c = constraints
    stays = list(
        db.scalars(
            select(Stay)
            .where(Stay.destination_id == destination.id)
            .order_by(Stay.price_inr)
        )
    )
    stays = [
        s
        for s in stays
        if set(x.casefold() for x in c.stay_amenities)
        <= set(x.casefold() for x in s.amenities)
    ]
    selected = (
        next((s for s in stays if s.id == stay_id), None)
        if stay_id
        else (stays[0] if stays else None)
    )
    if stay_id and selected is None:
        raise ValueError(
            "Selected stay is outside this destination or violates required amenities."
        )
    room_rate = (
        selected.price_inr
        if selected
        else {"budget": 1800, "mid-range": 3500, "luxury": 8000}[c.hotel_style]
    )
    assumptions = [
        "Sample INR estimates, not live availability or a booking quote.",
        "Two guests per room; final day included for food and local travel.",
        "Food ₹700/person/day; local travel ₹500/group/day; two terminal transfers ₹600 each; miscellaneous ₹250/person; contingency 10%.",
    ]
    if not selected:
        assumptions.append(
            "No eligible catalog stay; illustrative room allowance only. Accommodation suitability is unverified."
        )
    from .fare_estimates import route_preview
    transport = route_preview(db, c.origin, destination, travelers=c.traveller_count,
                              mode=c.transport_mode, max_minutes=c.max_transport_minutes)
    routes = [db.get(TransportRoute, leg["route_id"]) if leg["route_id"] else None for leg in transport["legs"]]
    route_unknown = not transport["costs_complete"]
    if route_unknown:
        assumptions.append(
            transport["notice"] + " Unknown fares are excluded from the known subtotal; no generic fare allowance is added."
        )
    guests, nights, rooms = (
        c.traveller_count,
        max(0, c.days - 1),
        math.ceil(c.traveller_count / 2),
    )
    categories = dict(
        inbound=transport["legs"][0]["fare_inr"] or 0,
        outbound=transport["legs"][1]["fare_inr"] or 0,
        local_transport=500 * c.days,
        terminal_transfers=1200,
        accommodation=room_rate * rooms * nights,
        food=700 * guests * c.days,
        activities=activity_cost
        if activity_cost is not None
        else 500 * guests * c.days,
        miscellaneous=250 * guests,
    )
    categories["contingency"] = math.ceil(sum(categories.values()) / 10)
    total = sum(categories.values())
    alternatives = []
    if total > c.budget:
        if room_rate > 1800 and nights:
            alternatives.append(
                dict(
                    change="Use a ₹1800 room allowance",
                    estimated_saving_inr=math.floor(
                        (room_rate - 1800) * rooms * nights * 1.1
                    ),
                )
            )
        if c.days > 1:
            alternatives.append(
                dict(
                    change="Shorten by one day/night",
                    estimated_saving_inr=math.floor(
                        (room_rate * rooms + 700 * guests + 500 + 500 * guests) * 1.1
                    ),
                )
            )
        alternatives.append(
            dict(change="Increase the total budget", extra_inr=total - c.budget)
        )
    return dict(
        currency="INR",
        categories=categories,
        total_inr=total,
        known_subtotal_inr=total,
        trip_total_inr=None if route_unknown else total,
        costs_complete=not route_unknown,
        unknown_categories=[key for key, leg in zip(("inbound", "outbound"), transport["legs"]) if leg["fare_inr"] is None],
        transport=transport,
        per_person_inr=math.ceil(total / guests),
        per_day_inr=math.ceil(total / c.days),
        remaining_inr=None if route_unknown else c.budget - total,
        within_budget=None if route_unknown else total <= c.budget,
        estimate=True,
        basis="seed catalog + explicit sample allowances",
        estimated_on=dt.date.today().isoformat(),
        assumptions=assumptions,
        alternatives=alternatives,
        stay_id=selected.id if selected else None,
        routes=[
            dict(
                id=r.id,
                mode=r.mode,
                duration_min=r.duration_min,
                operator=r.operator,
                sample=True,
            )
            if r
            else None
            for r in routes
        ],
        transport_verified=not route_unknown,
    )


def discover(db, c):
    accepted, rejected = [], []
    for d in db.scalars(select(Destination).order_by(Destination.name)):
        if c.destination and c.destination.casefold() not in {
            d.name.casefold(),
            d.slug.casefold(),
        }:
            continue
        reasons = []
        missing = set(x.casefold() for x in c.hard_tags) - set(
            x.casefold() for x in d.tags
        )
        if missing:
            reasons.append(
                "Missing required destination tags: " + ", ".join(sorted(missing))
            )
        if c.hard_requirements:
            reasons.append(
                "Mandatory conditions need sourced verification: "
                + "; ".join(c.hard_requirements)
            )
        estimate = quote(db, c, d)
        if estimate["total_inr"] > c.budget:
            reasons.append(
                f"Estimated budget needs ₹{estimate['total_inr'] - c.budget} more"
            )
        if c.stay_amenities and estimate["stay_id"] is None:
            reasons.append("No catalog stay verifies all required amenities")
        if not estimate["transport_verified"]:
            reasons.append(
                estimate["transport"]["notice"]
            )
        matched = sorted(
            set(x.casefold() for x in c.interests) & set(x.casefold() for x in d.tags)
        )
        fit = round(100 * len(matched) / max(1, len(set(c.interests))))
        item = dict(
            id=d.id,
            name=d.name,
            tags=d.tags,
            score=fit,
            matched_interests=matched,
            score_basis="Percentage of requested interests matching catalog tags; hard constraints filtered first.",
            budget=estimate,
            seasonal_note=d.best_season or "unknown",
            seasonal_source="seed catalog, unverified",
            accessibility="unknown",
            reasons=reasons,
        )
        (rejected if reasons else accepted).append(item)
    accepted.sort(key=lambda r: (-r["score"], r["budget"]["total_inr"], r["id"]))
    rejected.sort(
        key=lambda r: (
            len(r["reasons"]),
            max(0, r["budget"]["total_inr"] - c.budget),
            r["id"],
        )
    )
    return dict(
        status="matched" if accepted else "no_match",
        matches=accepted[:20],
        compromises=rejected[:3] if not accepted else [],
        explanation="No option satisfies every hard constraint. Review the listed compromises before changing any requirement."
        if not accepted
        else "Ranked after applying all known hard constraints.",
    )


def itinerary(db, c, destination, selected_ids=None):
    experiences = list(
        db.scalars(
            select(Experience)
            .where(Experience.destination_id == destination.id)
            .order_by(Experience.id)
        )
    )
    if selected_ids is not None:
        if not set(selected_ids) <= {e.id for e in experiences}:
            raise ValueError("Selected experiences must belong to this destination.")
        experiences = [e for e in experiences if e.id in selected_ids]
    limit = {"relaxed": 4, "moderate": 6, "packed": 8}[c.pace]
    if c.group_type in {"family", "seniors"}:
        limit = max(3, limit - 1)
    remaining = list(experiences)
    days = []
    for index in range(c.days):
        date = c.start_date + dt.timedelta(days=index)
        start = max(9 * 60, c.arrival_hour * 60 + 90) if index == 0 else 9 * 60
        end = (
            min(17 * 60, c.departure_hour * 60 - 120)
            if index == c.days - 1
            else 17 * 60
        )
        end = min(end, start + limit * 60)
        minute, items, previous = start, [], None
        while remaining and minute + 90 <= end:
            # Catalog coordinates are optional; never imply exact routing.
            def proximity(e):
                a, b = previous.display if previous else {}, e.display or {}
                if all(k in a and k in b for k in ("lat", "lng")):
                    return distance_km(a["lat"], a["lng"], b["lat"], b["lng"])
                return e.id

            candidate = min(remaining, key=proximity)
            details = candidate.display or {}
            duration = max(30, min(240, int(details.get("duration_min", 90))))
            transfer = 30 if previous else 0
            open_min = int(details.get("opens_minute", 9 * 60))
            close_min = int(details.get("closes_minute", 17 * 60))
            scheduled = max(minute + transfer, open_min)
            if scheduled < 13 * 60 and scheduled + duration > 12 * 60:
                items.append(
                    dict(
                        kind="rest",
                        title="Lunch and rest",
                        start_minute=12 * 60,
                        end_minute=13 * 60,
                        city=destination.name,
                    )
                )
                scheduled = max(scheduled, 13 * 60)
            if scheduled + duration > min(end, close_min):
                break
            items.append(
                dict(
                    kind="activity",
                    id=candidate.id,
                    title=candidate.name,
                    city=destination.name,
                    date=date.isoformat(),
                    start_minute=scheduled,
                    end_minute=scheduled + duration,
                    duration_min=duration,
                    transfer_min=transfer,
                    price_inr=candidate.price_inr,
                    timing_verified=all(
                        k in details
                        for k in ("opens_minute", "closes_minute", "duration_min")
                    ),
                    assumptions="Catalog timing where present; otherwise sample 09:00–17:00 hours, 90-minute visit, 30-minute transfer. Verify before travel.",
                )
            )
            minute, previous = scheduled + duration, candidate
            remaining.remove(candidate)
        active_minutes = sum(
            i["end_minute"] - i["start_minute"] + i.get("transfer_min", 0)
            for i in items
        )
        days.append(
            dict(
                date=date.isoformat(),
                items=items,
                effort_minutes=active_minutes,
                effort="high"
                if active_minutes > 360
                else "moderate"
                if active_minutes > 180
                else "low",
                contingency=dict(
                    rain="Replace outdoor visits with a verified indoor alternative or rest; verify availability.",
                    half_day="Keep the first visit and remove later optional visits.",
                    skip="Remove the last optional activity; preserve travel and rest windows.",
                ),
            )
        )
    return dict(
        days=days,
        unscheduled=[
            dict(id=e.id, title=e.name, reason="Outside timing/pace capacity")
            for e in remaining
        ],
        caveats=[
            "Opening hours and transfers are provisional unless the item says timing_verified."
        ],
    )


def conflicts(c, plan, reservations=None):
    issues, seen = [], set()

    def issue(code, message, *ids):
        issues.append(dict(code=code, message=message, item_ids=list(ids)))

    for day in plan.get("days", []):
        date = dt.date.fromisoformat(day["date"])
        if not c.start_date <= date <= c.end_date:
            issue("outside_trip", "Day falls outside the trip dates", day["date"])
        previous = None
        effort = 0
        for item in sorted(day.get("items", []), key=lambda i: i["start_minute"]):
            identifier = str(item.get("id", item.get("title", "")))
            start, end = item["start_minute"], item["end_minute"]
            if not 0 <= start < end <= 1440:
                issue(
                    "invalid_time",
                    "Item times must be ordered within the day",
                    identifier,
                )
            if item.get("kind") == "activity":
                if identifier in seen:
                    issue("duplicate", "Attraction appears more than once", identifier)
                seen.add(identifier)
            if (
                previous
                and previous["end_minute"] + item.get("transfer_min", 0) > start
            ):
                issue(
                    "overlap",
                    "Items overlap or leave insufficient transfer time",
                    identifier,
                )
            if date == c.start_date and start < c.arrival_hour * 60 + 90:
                issue(
                    "before_arrival",
                    "Activity starts before arrival and the transfer buffer",
                    identifier,
                )
            if date == c.end_date and end > c.departure_hour * 60 - 120:
                issue(
                    "after_departure",
                    "Activity leaves insufficient time for departure",
                    identifier,
                )
            if (
                c.destination
                and item.get("city", c.destination).casefold()
                != c.destination.casefold()
            ):
                issue(
                    "city_mismatch",
                    "Activity is in a different city; an intercity transfer is required",
                    identifier,
                )
            effort += end - start + item.get("transfer_min", 0)
            previous = item
        if effort > {"relaxed": 240, "moderate": 360, "packed": 480}[c.pace]:
            issue("pace", "Day exceeds the selected daily effort limit", day["date"])
    hotels = sorted(
        [r for r in reservations or [] if r["kind"] == "stay"],
        key=lambda r: dt.datetime.fromisoformat(r["start"]),
    )
    for previous, current in zip(hotels, hotels[1:]):
        if dt.datetime.fromisoformat(previous["end"]) > dt.datetime.fromisoformat(
            current["start"]
        ):
            issue(
                "stay_overlap",
                "Hotel reservations overlap",
                previous["id"],
                current["id"],
            )
        elif (
            not previous.get("foreign_trip")
            and not current.get("foreign_trip")
            and dt.datetime.fromisoformat(previous["end"])
            < dt.datetime.fromisoformat(current["start"])
        ):
            issue(
                "stay_gap",
                "Gap between stays needs a transfer and luggage plan",
                previous["id"],
                current["id"],
            )
    for reservation in reservations or []:
        if reservation.get("foreign_trip"):
            continue
        if (
            reservation["kind"] == "return"
            and reservation["city"].casefold() != (c.destination or "").casefold()
        ):
            issue(
                "wrong_return_city",
                "Return transport leaves from a different final city",
                reservation["id"],
            )
        if reservation["kind"] == "stay" and reservation.get(
            "arrival_hour", c.arrival_hour
        ) > reservation.get("checkin_closes_hour", 23):
            issue(
                "late_checkin",
                "Arrival is after the property's check-in closing time",
                reservation["id"],
            )
    return issues


def validate_schedule(db, c, destination, schedule):
    """Accept times/order from the editor, reload identity and prices from SQL."""
    source = deepcopy(schedule)
    if not isinstance(source.get("days"), list) or len(source["days"]) != c.days:
        raise ValueError(
            "The schedule must contain exactly one entry for every trip day."
        )
    expected = {
        (c.start_date + dt.timedelta(days=i)).isoformat() for i in range(c.days)
    }
    dates = [day["date"] for day in source["days"]]
    if len(set(dates)) != len(dates) or set(dates) != expected:
        raise ValueError("Schedule dates must cover the trip without duplicates.")
    catalog = {
        e.id: e
        for e in db.scalars(
            select(Experience).where(Experience.destination_id == destination.id)
        )
    }
    for day in source["days"]:
        if not isinstance(day.get("items"), list) or len(day["items"]) > 20:
            raise ValueError("Use at most twenty items per day.")
        previous_activity = False
        for item in sorted(day["items"], key=lambda i: i["start_minute"]):
            if any(
                type(item.get(k)) is not int for k in ("start_minute", "end_minute")
            ):
                raise ValueError("Item times must be integer minutes.")
            if item.get("kind") not in {"activity", "rest"}:
                raise ValueError("Unsupported itinerary item kind.")
            if item["kind"] == "activity":
                if type(item.get("id")) is not int or item["id"] not in catalog:
                    raise ValueError(
                        "An activity must reference this destination's catalog."
                    )
                activity = catalog[item["id"]]
                item.update(
                    title=activity.name,
                    price_inr=activity.price_inr,
                    city=destination.name,
                    date=day["date"],
                    duration_min=item["end_minute"] - item["start_minute"],
                    transfer_min=30 if previous_activity else 0,
                    timing_verified=False,
                )
                previous_activity = True
                details = activity.display or {}
                if item["start_minute"] < details.get("opens_minute", 9 * 60) or item[
                    "end_minute"
                ] > details.get("closes_minute", 17 * 60):
                    raise ValueError(
                        "Activity falls outside its catalog or sample opening window."
                    )
            else:
                item.pop("price_inr", None)
                item["transfer_min"] = 0
        day["effort_minutes"] = sum(
            i["end_minute"] - i["start_minute"] + i.get("transfer_min", 0)
            for i in day["items"]
        )
        day["effort"] = (
            "high"
            if day["effort_minutes"] > 360
            else "moderate"
            if day["effort_minutes"] > 180
            else "low"
        )
    issues = conflicts(c, source)
    if issues:
        raise ValueError("; ".join(i["message"] for i in issues))
    return source


def build(db, c, selections=None):
    destination = city(db, c.destination)
    if destination is None:
        raise ValueError("Choose a known destination before building a plan.")
    selections = selections or {}
    schedule = itinerary(db, c, destination, selections.get("experience"))
    activity = sum(
        i.get("price_inr", 0) * c.traveller_count
        for d in schedule["days"]
        for i in d["items"]
    )
    budget = quote(
        db, c, destination, activity_cost=activity, stay_id=selections.get("stay")
    )
    validation = conflicts(c, schedule)
    unknowns = list(c.hard_requirements)
    if not budget["transport_verified"]:
        unknowns.append(budget["transport"]["notice"])
    return dict(
        constraints=c.model_dump(mode="json"),
        destination_id=destination.id,
        itinerary=schedule,
        budget=budget,
        conflicts=validation,
        unverified_requirements=unknowns,
        ready=not validation and budget["within_budget"] is True and not unknowns,
        summary=dict(
            duration_days=c.days,
            activity_count=sum(
                i["kind"] == "activity" for d in schedule["days"] for i in d["items"]
            ),
            pace=c.pace,
            stay_standard=c.hotel_style,
            preference_fit_score=round(
                100
                * len(
                    set(v.casefold() for v in c.interests)
                    & set(v.casefold() for v in destination.tags)
                )
                / max(1, len(set(c.interests)))
            )
            if c.interests
            else 100,
            transport_minutes=sum(route["duration_min"] for route in budget["routes"])
            if all(budget["routes"])
            else None,
            effort_minutes=sum(d["effort_minutes"] for d in schedule["days"]),
        ),
        packing=[
            "Photo ID and tickets",
            "Medication and prescriptions",
            "Charger and offline copies",
            "Weather-appropriate layers",
        ],
        readiness=[
            dict(
                task="Verify opening hours, permits and accessibility", complete=False
            ),
            dict(task="Confirm transport and accommodation directly", complete=False),
        ],
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        demo=True,
    )


def compare(plans):
    rows = []
    for identifier, plan in plans:
        budget, summary = plan["budget"], plan["summary"]
        score = max(
            0,
            100
            - 25 * len(plan["conflicts"])
            - 15 * len(plan["unverified_requirements"])
            - (25 if budget["within_budget"] is False else 0),
        )
        rows.append(
            dict(
                id=identifier,
                **summary,
                total_cost_inr=budget["total_inr"],
                costs_complete=budget.get("costs_complete", True),
                score=round(
                    0.5 * score + 0.5 * summary.get("preference_fit_score", 100)
                ),
                score_basis="Equal weights for requested-interest fit and readiness. Readiness starts at 100, minus 25 per conflict, 15 per unverified requirement and 25 when over budget. Unknown transport time remains unknown.",
                tradeoffs=plan["unverified_requirements"]
                + [v["message"] for v in plan["conflicts"]]
                + (["Over budget"] if budget["within_budget"] is False else []),
            )
        )
    return sorted(rows, key=lambda p: (-p["score"], p["total_cost_inr"]))
