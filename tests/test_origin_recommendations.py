"""Origin-specific fare arithmetic, explained recommendations, and complete browsing."""
# ruff: noqa: F811
import datetime as dt
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stitch_ai_travel_booking_platform/backend"))
from app.db import Base  # noqa: E402
from app.models import Destination, Stay, TransportRoute  # noqa: E402
from app import travel_planning  # noqa: E402
from app.fare_estimates import route_preview  # noqa: E402
from tests.test_application_integration import connected_app, trip, user  # noqa: E402,F401
from tests.test_tinyfish_chat import configure, send  # noqa: E402


@pytest.fixture
def fare_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        places = {}
        for name in ("New Delhi", "Mumbai", "Goa", "Pune"):
            row = Destination(name=name, slug=name.lower().replace(" ", "-"), state="Sample", lat=0, lng=0,
                              description="Sample destination", tags=["beach"], avg_cost_inr=19000)
            db.add(row)
            db.flush()
            places[name] = row
        db.add(Stay(name="Sample Goa Stay", destination_id=places["Goa"].id, kind="hotel", price_inr=1000, amenities=[]))
        for start, end, fare in (("New Delhi", "Goa", 1000), ("Goa", "New Delhi", 1100),
                                 ("Mumbai", "Goa", 2500), ("Goa", "Mumbai", 2700)):
            db.add(TransportRoute(origin_id=places[start].id, destination_id=places[end].id, mode="flight",
                                  operator="Sample flight", duration_min=100, price_inr=fare, seats_available=10))
        db.commit()
        yield db, places
    engine.dispose()


def constraints(**changes):
    return travel_planning.Constraints(destination="Goa", start_date=dt.date(2026, 12, 1),
        end_date=dt.date(2026, 12, 3), budget=50000, **changes)


def test_fares_change_with_origin_and_scale_with_the_party(fare_db):
    db, places = fare_db
    delhi = travel_planning.quote(db, constraints(origin="New Delhi", traveller_count=2), places["Goa"])
    mumbai = travel_planning.quote(db, constraints(origin="Mumbai", traveller_count=2), places["Goa"])
    assert delhi["categories"]["inbound"] == 2000
    assert delhi["categories"]["outbound"] == 2200
    assert mumbai["categories"]["inbound"] == 5000
    assert mumbai["categories"]["outbound"] == 5400
    assert delhi["costs_complete"] and mumbai["total_inr"] > delhi["total_inr"]
    assert mumbai["transport"]["origin"] == "Mumbai"
    assert mumbai["transport"]["round_trip_inr"] == 10400


@pytest.mark.parametrize("origin", [None, "Pune", "Unknown City"])
def test_unknown_origin_or_route_never_gets_a_generic_fare(fare_db, origin):
    db, places = fare_db
    quote = travel_planning.quote(db, constraints(origin=origin), places["Goa"])
    assert quote["trip_total_inr"] is None and quote["within_budget"] is None
    assert quote["remaining_inr"] is None and not quote["costs_complete"]
    assert quote["unknown_categories"] == ["inbound", "outbound"]
    assert quote["categories"]["inbound"] == quote["categories"]["outbound"] == 0
    assert quote["known_subtotal_inr"] == sum(quote["categories"].values())
    assert not travel_planning.build(db, constraints(origin=origin))["ready"]


def test_one_missing_leg_does_not_become_a_round_trip_quote(fare_db):
    db, places = fare_db
    preview = route_preview(db, "Mumbai", places["Goa"], travelers=2)
    db.delete(db.get(TransportRoute, preview["legs"][1]["route_id"]))
    db.commit()
    preview = route_preview(db, "Mumbai", places["Goa"], travelers=2)
    assert preview["round_trip_inr"] is None
    assert preview["legs"][0]["fare_inr"] == 5000 and preview["legs"][1]["fare_inr"] is None


def test_no_intercity_fare_when_starting_at_the_destination(fare_db):
    db, places = fare_db
    preview = route_preview(db, "Goa", places["Goa"])
    assert preview["costs_complete"] and preview["round_trip_inr"] == 0
    assert "Local travel is separate" in preview["notice"]


def test_city_collection_reasons_and_all_destination_pages(connected_app, monkeypatch):
    from agents.config import settings
    configure(monkeypatch)
    monkeypatch.setattr(settings, "dialogue_mode", "local")
    client, _ = connected_app
    headers = user(client, "origin_browsing")
    path = trip(client, headers)
    first = send(client, headers, path, "I want a relaxing solo trip with 50k")
    assert first["awaiting"] == "origin" and "origin" in first["workspace"]["missing_fields"]
    assert "starting from" in first["reply"]
    for card in first["cards"]:
        assert any("relaxed pace" in reason for reason in card["match_reasons"])
        assert card["transport"]["status"] == "needs_origin"
    chosen = send(client, headers, path, "Let's go to Munnar")
    assert chosen["workspace"]["draft"]["destination"] == "Munnar"
    assert "origin" not in chosen["workspace"]["draft"] and chosen["awaiting"] == "origin"
    city = send(client, headers, path, "Mumbai")
    assert city["workspace"]["draft"]["origin"] == "Mumbai"
    assert city["workspace"]["draft"]["destination"] == "Munnar"
    assert city["awaiting"] == "start_date"
    for item in city["workspace"]["options"]["destinations"]:
        assert item["transport"]["origin"] == "Mumbai"
    # Browsing is independent of committing a different destination.
    seen = set(first["workspace"]["dialogue"]["seen_destinations"])
    total = len(first["workspace"]["options"]["destinations"])
    revision = city["workspace"]["revision"]
    for _ in range(12):
        result = send(client, headers, path, "I don't like any of these, show more destinations")
        names = {c["name"] for c in result["cards"]}
        assert not (seen & names)
        seen |= names
        assert result["workspace"]["revision"] == revision
        assert not result["workspace"]["draft"]["hard_requirements"]
        if not result["workspace"]["dialogue"]["has_more_destinations"]:
            break
    assert len(seen) == total
    exhausted = send(client, headers, path, "Show more destinations")
    assert not exhausted["cards"] and "seen all" in exhausted["reply"]
    assert not exhausted["workspace"]["dialogue"]["has_more_destinations"]


def test_non_catalog_starting_city_is_saved_without_becoming_the_destination(connected_app, monkeypatch):
    from agents.config import settings
    configure(monkeypatch)
    monkeypatch.setattr(settings, "dialogue_mode", "local")
    client, _ = connected_app
    headers = user(client, "origin_unknown")
    path = trip(client, headers)
    send(client, headers, path, "A relaxing solo trip with 50k")
    response = send(client, headers, path, "Chandigarh")
    assert response["workspace"]["draft"]["origin"] == "Chandigarh"
    assert "destination" not in response["workspace"]["draft"]
    assert all(card["transport"]["round_trip_inr"] is None for card in response["cards"])


def test_natural_current_location_is_an_origin_not_a_destination():
    from app.query_intake import interpret
    places = [{"name": "Mumbai"}, {"name": "Kerala"}]
    for message in ("I'm currently in Mumbai", "My current location is Mumbai"):
        _, result = interpret(message, {"destination": "Kerala"}, places, {"awaiting": "origin"})
        assert result.updates["origin"] == "Mumbai"
        assert "destination" not in result.updates


def test_destination_refinement_is_saved_for_the_next_page():
    from app.query_intake import interpret
    _, result = interpret("Suggest beach destinations", {"pace": "relaxed"}, [])
    assert result.updates["interests"] == ["beach"]
