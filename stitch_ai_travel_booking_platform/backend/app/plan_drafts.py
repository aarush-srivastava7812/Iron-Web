"""Versioned hackathon drafts. Clients send edit operations, never prices."""
from copy import deepcopy

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from typing import Literal

from agents.budget_booking_agent import BudgetBookingAgent
from agents.schemas import AgentResult, DraftItinerary, TripBrief
from agents.validation.itinerary_validator import validate_itinerary
from .models import PlanVersion, TripWorkspace


class PlanEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    action: Literal["remove", "replace", "move_up", "move_down", "stay", "restore"]
    day: int = Field(default=0, ge=0, le=59)
    stop: int = Field(default=0, ge=0, le=100)
    candidate: int = Field(default=0, ge=0, le=100)


def versions(db, conversation_id):
    return db.scalars(select(PlanVersion).where(PlanVersion.conversation_id == conversation_id)
                      .order_by(PlanVersion.version.desc())).all()


def invalidate(db, conversation_id):
    db.execute(update(PlanVersion).where(PlanVersion.conversation_id == conversation_id).values(stale=True))


def save_generated(db, conversation_id, result):
    if result.get("status") != "ok" or not result.get("itinerary") or not result.get("budget"):
        return None
    rows = versions(db, conversation_id)
    source = {k: deepcopy(result[k]) for k in ("trip_brief", "itinerary", "budget", "agent_results")}
    stay = next((r.get("stay_options", [])[0] for r in result["agent_results"]
                 if r["agent_id"] == "itinerary_planner" and r.get("stay_options")), None)
    source["selected_stay_id"] = stay.get("stay_id") if stay else None
    source["change"] = "Travel team generated this draft"
    row = PlanVersion(conversation_id=conversation_id, version=rows[0].version + 1 if rows else 1,
                      payload=source)
    db.add(row)
    work=db.get(TripWorkspace,conversation_id)
    if work is not None:
        from .journey import _from_brief, fingerprint
        draft=dict(work.data.get("draft",{}),**_from_brief(result["trip_brief"]))
        selections=dict(work.data.get("selections",{}))
        if source["selected_stay_id"]:
            selections["stay"]=source["selected_stay_id"]
        work.data=dict(work.data,draft=draft,confirmed=fingerprint(draft),selections=selections)
        work.revision+=1
    return row


def view(row, rows):
    return dict(version=row.version, stale=row.stale, plan=row.payload,
                history=[dict(version=r.version, total_inr=r.payload["budget"]["total_inr"],
                              change=r.payload.get("change", "Saved draft")) for r in rows])


def edit(db, conversation_id, body):
    rows = versions(db, conversation_id)
    if not rows:
        raise HTTPException(404, "Generate a trip plan first")
    current = rows[0]
    if current.version != body.expected_version:
        raise HTTPException(409, "This draft changed in another window. Reopen the latest version.")
    if current.stale:
        raise HTTPException(409, "Trip requirements changed. Ask the travel team to plan again before editing.")
    source = current
    if body.action == "restore":
        source = next((r for r in rows if r.version == body.candidate), None)
        if source is None or source.stale:
            raise HTTPException(409, "That version is unavailable or uses outdated requirements.")
    payload = deepcopy(source.payload)
    brief = TripBrief.model_validate(payload["trip_brief"])
    results = [AgentResult.model_validate(r) for r in payload["agent_results"]]
    get = lambda agent, field: next((getattr(r, field) for r in results if r.agent_id == agent), [])
    stays = get("stay_agent", "stay_options")
    itinerary = DraftItinerary.model_validate(payload["itinerary"])
    try:
        if body.action == "stay":
            payload["selected_stay_id"] = stays[body.candidate].stay_id
        elif body.action != "restore":
            day = itinerary.days[body.day]
            stop = day.stops[body.stop]
            if stop.kind not in {"food", "attraction"}:
                raise ValueError("Only meals and activities can be edited here")
            if body.action == "remove":
                day.stops.pop(body.stop)
            elif body.action == "replace":
                options = get("food_guide_agent", "food_options") if stop.kind == "food" else get("tour_guide_agent", "attractions")
                option = options[body.candidate]
                stop.title = ("Lunch at " if stop.kind == "food" else "") + option.name
                stop.est_cost_inr = (option.approx_price_per_guest_inr if stop.kind == "food" else option.price_per_person_inr) or 0
                stop.location, stop.evidence = option.location, option.evidence
                stop.notes = option.dietary_fit if stop.kind == "food" else option.why_fit
            else:
                other_index = body.stop + (-1 if body.action == "move_up" else 1)
                if not 0 <= other_index < len(day.stops):
                    raise ValueError("No neighboring slot in that direction")
                other = day.stops[other_index]
                if other.kind not in {"food", "attraction"}:
                    raise ValueError("Arrival and departure slots remain fixed")
                # Move contents between chronological slots; retain slot times.
                first_times = stop.start_time, stop.end_time
                stop.start_time, stop.end_time = other.start_time, other.end_time
                other.start_time, other.end_time = first_times
                day.stops[body.stop], day.stops[other_index] = other, stop
        itinerary.total_est_cost_inr = sum(s.est_cost_inr for d in itinerary.days for s in d.stops)
        itinerary.assumptions = [a for a in itinerary.assumptions if not a.startswith("Assumes a room")]
        stay = next((s for s in stays if s.stay_id == payload.get("selected_stay_id")), None)
        if stay:
            itinerary.assumptions.append(f"Assumes a room at {stay.name}; occupancy and availability unverified.")
        validation = validate_itinerary(itinerary, brief)
        if validation.errors:
            raise ValueError(" ".join(i.message for i in validation.errors))
        estimate = BudgetBookingAgent().estimate(brief, itinerary=itinerary,
            stay_options=[stay] if stay else [], food_options=get("food_guide_agent", "food_options"),
            attractions=get("tour_guide_agent", "attractions"), nights=max((brief.duration_days or 1)-1, 1),
            party_size=brief.party_size or 1, per_person=False)
        if estimate.status != "ok" or estimate.budget is None:
            raise ValueError("Could not calculate this edit")
        if brief.budget_total_inr is not None and estimate.budget.total_inr > brief.budget_total_inr:
            raise ValueError("This edit exceeds the confirmed total budget; choose a lower-cost option")
    except (IndexError, ValueError) as error:
        raise HTTPException(422, str(error) or "Invalid edit selection") from error
    payload["itinerary"] = itinerary.model_dump(mode="json")
    payload["budget"] = estimate.budget.model_dump(mode="json")
    payload["change"] = (f"Restored version {body.candidate}" if body.action == "restore" else f"Edited {body.action.replace('_', ' ')}")
    payload["delta_inr"] = estimate.budget.total_inr - current.payload["budget"]["total_inr"]
    row = PlanVersion(conversation_id=conversation_id, version=current.version+1, payload=payload)
    db.add(row)
    work=db.get(TripWorkspace,conversation_id)
    if work is not None:
        selections=dict(work.data.get("selections",{}))
        if payload.get("selected_stay_id"):
            selections["stay"]=payload["selected_stay_id"]
        else:
            selections.pop("stay",None)
        work.data=dict(work.data,selections=selections)
        work.revision+=1
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Another edit won the save. Reopen the latest version.") from error
    return view(row, [row, *rows])
