"""Deterministic acceptance for this small, explicitly quoted travel catalog.

This is a bounded example, not a general booking engine. Unsupported mandatory
requirements/quote terms stop for review; model prose never relaxes a rule.
"""

from collections import Counter
from datetime import date, time, timedelta
from decimal import Decimal
import math
import re

from examples.travel_intake import date_range

PLAN_KEYS = {
    "decision",
    "flight_id",
    "hotel_id",
    "activity_ids",
    "activity_days",
    "total_inr",
    "budget_inr",
    "max_walk_metres",
    "reasons",
    "evidence_claim_ids",
}
REQUIRED_KEYS = PLAN_KEYS - {"reasons", "evidence_claim_ids"}
SUPPORTED = {
    "destination",
    "dates",
    "budget",
    "currency",
    "departure_city",
    "traveller_count",
    "dietary",
    "accessibility",
    "max_walk_metres",
    "avoid_boats",
    "max_activities_per_day",
    "flight_time_preference",
}
GOALS = ("A-ACCESSIBLE-BEACH", "A-TERRACE")


def finite_number(value, *, integer=False, minimum=0):
    return (
        type(value) in {int, float}
        and minimum <= value <= 10**12
        and math.isfinite(value)
        and (not integer or value == int(value))
    )


def money(value):
    if not finite_number(value):
        raise ValueError("Catalog money must be finite and nonnegative.")
    amount = Decimal(str(value))
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Catalog money must use at most two decimal places.")
    return amount


def json_money(amount):
    return int(amount) if amount == int(amount) else float(amount)


def clock(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value):
        raise ValueError("Catalog flight times need HH:MM.")
    return time.fromisoformat(value)


def catalog(fixture):
    groups = []
    for key in ("flight_offers", "hotel_offers", "activity_offers"):
        rows = fixture[key]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 64:
            raise ValueError("Use a bounded nonempty supplier catalog.")
        if any(
            not isinstance(r, dict) or not isinstance(r.get("id"), str) or not r["id"]
            for r in rows
        ):
            raise ValueError("Offers require nonempty string IDs.")
        by_id = {r["id"]: r for r in rows}
        if len(by_id) != len(rows):
            raise ValueError("Offer IDs must be unique.")
        groups.append(by_id)
    flights, hotels, activities = groups
    for f in flights.values():
        money(f["total_for_two"])
        clock(f["departure"])
        clock(f["return_departure"])
    for h in hotels.values():
        money(h["four_night_total"])
        if (
            type(h["step_free"]) is not bool
            or type(h["vegetarian_food"]) is not bool
            or not finite_number(h["walk_from_dropoff_metres"])
        ):
            raise ValueError("Hotel access/food/distance metadata is invalid.")
    for a in activities.values():
        money(a["cost_for_two"])
        if type(a["boat"]) is not bool or not finite_number(a["walking_metres"]):
            raise ValueError("Activity constraints are invalid.")
        if type(a.get("serves_food")) is not bool or (
            a["serves_food"] and type(a.get("vegetarian_food")) is not bool
        ):
            raise ValueError("Activities need explicit food/dietary metadata.")
    fixed = fixture["fixed_costs"]
    if not isinstance(fixed, dict) or not fixed:
        raise ValueError("Explicit fixed costs are required.")
    sum((money(v) for v in fixed.values()), Decimal(0))
    return flights, hotels, activities


def requirements_from_context(packet, fixture):
    if packet.get("status") != "ready" or not packet.get("fields"):
        raise ValueError("A complete structured current brief is required.")
    values = {}
    for field in packet["fields"]:
        p = field["predicate"]
        if field["required"] and p not in SUPPORTED:
            raise ValueError("Unsupported mandatory requirement: " + p)
        if field["required"] and field["status"] != "supported":
            raise ValueError("Unresolved mandatory requirement: " + p)
        if field["status"] == "supported" and p in SUPPORTED:
            if len(field["values"]) != 1:
                raise ValueError("Ambiguous field: " + p)
            v = field["values"][0]
            if p in values and values[p] != v:
                raise ValueError("Conflicting scopes for " + p)
            # Ordinary preferences do not become hard rules in this calculator.
            if field["required"] or p in {"departure_city", "traveller_count"}:
                values[p] = v
    needed = {
        "destination",
        "dates",
        "budget",
        "currency",
        "departure_city",
        "traveller_count",
        "max_walk_metres",
    }
    if not needed <= values.keys():
        raise ValueError(
            "Travel approval needs explicit "
            + ", ".join(sorted(needed - values.keys()))
        )
    return validate_requirements(values, fixture)


def validate_requirements(values, fixture):
    values = dict(values)
    terms = fixture.get("quote_terms")
    if not isinstance(terms, dict):
        raise ValueError(
            "Supplier quotes need explicit dates, route, currency and party terms."
        )
    start, end = date_range(values["dates"])
    if not finite_number(values["budget"]) or not finite_number(
        values["max_walk_metres"], integer=True
    ):
        raise ValueError("Invalid budget/walking requirement.")
    if values["currency"] != "INR" or terms.get("currency") != "INR":
        raise ValueError("This quoted catalog supports INR only.")
    if (
        type(values["traveller_count"]) is not int
        or values["traveller_count"] != 2
        or terms.get("party_size") != 2
    ):
        raise ValueError("Quoted prices cover exactly two travellers.")
    if (
        terms.get("dates") != values["dates"]
        or terms.get("nights") != (end - start).days
        or terms.get("nights") != 4
    ):
        raise ValueError("Quoted dates/nights differ from the current trip.")
    for key in ("destination", "departure_city"):
        if (
            not isinstance(values[key], str)
            or values[key].casefold() != str(terms.get(key, "")).casefold()
        ):
            raise ValueError("Quoted route differs from the current trip.")
    if values.get("dietary") not in (None, "vegetarian"):
        raise ValueError("Catalog cannot establish this dietary requirement.")
    if values.get("accessibility") not in (None, "step-free", "wheelchair-accessible"):
        raise ValueError("Catalog cannot establish this access requirement.")
    # step_free alone is insufficient evidence for broader wheelchair access.
    if values.get("accessibility") == "wheelchair-accessible":
        raise ValueError(
            "Wheelchair access requires more supplier evidence than step_free."
        )
    if type(values.get("avoid_boats", False)) is not bool:
        raise ValueError("Invalid boat rule.")
    limit = values.get("max_activities_per_day", 1)
    if type(limit) is not int or not 0 <= limit <= 24:
        raise ValueError("Invalid daily activity limit.")
    if values.get("flight_time_preference") not in (
        None,
        "morning",
        "afternoon",
        "evening",
    ):
        raise ValueError("Unsupported flight time requirement.")
    values["max_activities_per_day"] = limit
    for p in ("accessibility", "dietary", "flight_time_preference"):
        values.setdefault(p, None)
    values.setdefault("avoid_boats", False)
    return values


def time_fits(value, preference):
    hour = clock(value).hour
    return (
        preference is None
        or {
            "morning": hour < 12,
            "afternoon": 12 <= hour < 18,
            "evening": hour >= 18,
        }[preference]
    )


def activity_fits(activity, req):
    return (
        activity["walking_metres"] <= req["max_walk_metres"]
        and (not req.get("avoid_boats", True) or not activity["boat"])
        and (
            req.get("dietary", "vegetarian") != "vegetarian"
            or not activity["serves_food"]
            or activity["vegetarian_food"]
        )
    )


def activity_goals(activities, req):
    if not all(i in activities for i in GOALS):
        raise ValueError("This small example requires explicit beach/food goal offers.")
    if req["max_activities_per_day"] == 0:
        return []
    return [i for i in GOALS if activity_fits(activities[i], req)]


def offer_checks(flight, hotel, activities, req):
    return dict(
        morning=all(
            time_fits(flight[k], req.get("flight_time_preference", "morning"))
            for k in ("departure", "return_departure")
        ),
        step_free=not req.get("accessibility", "step-free") or hotel["step_free"],
        vegetarian=req.get("dietary", "vegetarian") != "vegetarian"
        or (
            hotel["vegetarian_food"]
            and all(not a["serves_food"] or a["vegetarian_food"] for a in activities)
        ),
        hotel_walking=hotel["walk_from_dropoff_metres"] <= req["max_walk_metres"],
        activity_walking=all(
            a["walking_metres"] <= req["max_walk_metres"] for a in activities
        ),
        no_boats=not req.get("avoid_boats", True)
        or all(not a["boat"] for a in activities),
    )


def selected_total(flight, hotel, activities, fixture):
    return (
        money(flight["total_for_two"])
        + money(hotel["four_night_total"])
        + sum((money(a["cost_for_two"]) for a in activities), Decimal(0))
        + sum((money(v) for v in fixture["fixed_costs"].values()), Decimal(0))
    )


def feasible_plans(fixture, req):
    flights, hotels, activities = catalog(fixture)
    start, end = date_range(req["dates"])
    ids = activity_goals(activities, req)
    if len(ids) > ((end - start).days + 1) * req["max_activities_per_day"]:
        return []
    days = {
        a: (
            start + timedelta(days=i // max(1, req["max_activities_per_day"]))
        ).isoformat()
        for i, a in enumerate(ids)
    }
    choices = []
    for f in flights.values():
        for h in hotels.values():
            selected = [activities[i] for i in ids]
            total = selected_total(f, h, selected, fixture)
            if total <= money(req["budget"]) and all(
                offer_checks(f, h, selected, req).values()
            ):
                choices.append(
                    dict(
                        decision="plan",
                        flight_id=f["id"],
                        hotel_id=h["id"],
                        activity_ids=ids,
                        activity_days=days,
                        total_inr=json_money(total),
                        budget_inr=req["budget"],
                        max_walk_metres=req["max_walk_metres"],
                    )
                )
    return sorted(
        choices,
        key=lambda p: (
            not flights[p["flight_id"]].get("comfortable", False),
            hotels[p["hotel_id"]].get("style") != "resort",
            p["total_inr"],
            p["flight_id"],
            p["hotel_id"],
        ),
    )


def check_plan(plan, fixture, *, budget, walking, requirements=None):
    """Fail-closed application checks, also used by the example evaluator.

    Application callers pass structured current requirements. The legacy
    budget/walking-only form checks the original bounded fixture contract.
    """
    try:
        req = (
            validate_requirements(requirements, fixture)
            if requirements is not None
            else dict(
                budget=budget,
                max_walk_metres=walking,
                dates=fixture.get("dates")
                or fixture.get("quote_terms", {}).get("dates"),
                max_activities_per_day=1,
                avoid_boats=True,
                accessibility="step-free",
                dietary="vegetarian",
                flight_time_preference="morning",
            )
        )
        flights, hotels, activities = catalog(fixture)
        if (
            not isinstance(plan, dict)
            or not REQUIRED_KEYS <= plan.keys()
            or plan.keys() - PLAN_KEYS
        ):
            return dict(valid_schema=False)
        if (
            plan["decision"] not in {"plan", "pause"}
            or not isinstance(plan["activity_ids"], list)
            or not isinstance(plan["activity_days"], dict)
        ):
            return dict(valid_schema=False)
        ids = plan["activity_ids"]
        if any(not isinstance(i, str) for i in ids) or len(ids) != len(set(ids)):
            return dict(valid_schema=False)
        if not finite_number(plan["budget_inr"]) or not finite_number(
            plan["max_walk_metres"], integer=True
        ):
            return dict(valid_schema=False)
        if "reasons" in plan and (
            not isinstance(plan["reasons"], list)
            or any(not isinstance(v, str) for v in plan["reasons"])
        ):
            return dict(valid_schema=False)
        if "evidence_claim_ids" in plan and (
            not isinstance(plan["evidence_claim_ids"], list)
            or any(not isinstance(v, str) for v in plan["evidence_claim_ids"])
        ):
            return dict(valid_schema=False)
        shared = dict(
            valid_schema=True,
            current_budget=plan["budget_inr"] == budget,
            current_walking=plan["max_walk_metres"] == walking,
        )
        if plan["decision"] == "pause":
            return dict(
                shared,
                correct_pause=not feasible_plans(fixture, req),
                no_supplier_ids=plan["flight_id"] is None
                and plan["hotel_id"] is None
                and not ids
                and not plan["activity_days"],
                null_total=plan["total_inr"] is None,
            )
        if (
            not isinstance(plan["flight_id"], str)
            or not isinstance(plan["hotel_id"], str)
            or plan["flight_id"] not in flights
            or plan["hotel_id"] not in hotels
            or any(i not in activities for i in ids)
        ):
            return dict(shared, known_offers=False)
        if not finite_number(plan["total_inr"]):
            return dict(valid_schema=False)
        f, h, selected = (
            flights[plan["flight_id"]],
            hotels[plan["hotel_id"]],
            [activities[i] for i in ids],
        )
        start, end = date_range(req["dates"])
        days = plan["activity_days"]
        dates = []
        valid_dates = set(days) == set(ids)
        for i in ids:
            value = days.get(i)
            if not isinstance(value, str) or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}", value
            ):
                valid_dates = False
                continue
            day = date.fromisoformat(value)
            valid_dates = valid_dates and start <= day <= end
            dates.append(day)
        daily_limit = valid_dates and all(
            n <= req["max_activities_per_day"] for n in Counter(dates).values()
        )
        total = selected_total(f, h, selected, fixture)
        return dict(
            shared,
            known_offers=True,
            total_correct=money(plan["total_inr"]) == total,
            within_budget=total <= money(budget),
            **offer_checks(f, h, selected, req),
            required_activities=set(activity_goals(activities, req)) <= set(ids),
            one_activity_per_day=daily_limit,
        )
    except (ValueError, TypeError, KeyError, OverflowError):
        return dict(valid_schema=False)


def canonical_plan(fixture, req, claim_ids, proposal=None):
    choices = feasible_plans(fixture, req)
    checks = check_plan(
        proposal,
        fixture,
        budget=req["budget"],
        walking=req["max_walk_metres"],
        requirements=req,
    )
    cited = proposal.get("evidence_claim_ids") if isinstance(proposal, dict) else None
    checks["complete_current_evidence"] = (
        isinstance(cited, list)
        and all(isinstance(i, str) for i in cited)
        and len(cited) == len(set(cited))
        and set(cited) == set(claim_ids)
    )
    valid = all(checks.values())
    if valid:
        selected = {
            k: v
            for k, v in proposal.items()
            if k not in {"reasons", "evidence_claim_ids"}
        }
    elif choices:
        selected = dict(choices[0])
    else:
        selected = dict(
            decision="pause",
            flight_id=None,
            hotel_id=None,
            activity_ids=[],
            activity_days={},
            total_inr=None,
            budget_inr=req["budget"],
            max_walk_metres=req["max_walk_metres"],
        )
    reasons = (
        [
            f"Catalog total INR {selected['total_inr']} is within the current INR {req['budget']} budget; all programmed requirements pass."
        ]
        if selected["decision"] == "plan"
        else [
            "No supplied combination satisfies the current requirements and total budget; no suppliers selected."
        ]
    )
    selected.update(reasons=reasons, evidence_claim_ids=list(claim_ids))
    return (
        selected,
        checks,
        "validated_model_proposal" if valid else "deterministic_catalog_solver",
    )


def canonical_review(draft, fixture, req, claim_ids):
    checks = check_plan(
        draft,
        fixture,
        budget=req["budget"],
        walking=req["max_walk_metres"],
        requirements=req,
    )
    cited = draft.get("evidence_claim_ids") if isinstance(draft, dict) else None
    checks["complete_current_evidence"] = (
        isinstance(cited, list)
        and all(isinstance(i, str) for i in cited)
        and len(cited) == len(set(cited))
        and set(cited) == set(claim_ids)
    )
    valid = all(checks.values())
    decision = (
        ("pause" if draft["decision"] == "pause" else "approve") if valid else "reject"
    )
    return dict(
        decision=decision,
        issues=[k for k, v in checks.items() if not v],
        budget_inr=req["budget"],
        max_walk_metres=req["max_walk_metres"],
        checked_claim_ids=list(claim_ids),
    ), checks
