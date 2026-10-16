"""Persist the supplied design's illustrative catalog alongside existing data."""
import json
from pathlib import Path

from sqlalchemy import select

from app.models import Destination, Experience, HolidayPackage, Stay, TransportRoute, WebsiteStay

LOCATIONS = {
    "Kashmir": ("kashmir", "Jammu and Kashmir", 34.08, 74.80),
    "Kerala": ("kerala", "Kerala", 9.50, 76.33),
    "Darjeeling": ("darjeeling", "West Bengal", 27.04, 88.26),
    "New Delhi": ("new-delhi", "Delhi", 28.61, 77.21),
    "Mumbai": ("mumbai", "Maharashtra", 19.07, 72.87),
    "Bengaluru": ("bengaluru", "Karnataka", 12.97, 77.59),
    "Hyderabad": ("hyderabad", "Telangana", 17.39, 78.49),
    "Chennai": ("chennai", "Tamil Nadu", 13.08, 80.27),
}


def seed_website(db):
    data = json.loads((Path(__file__).with_name("website_catalog.json")).read_text(encoding="utf-8"))
    by_name = {d.name: d for d in db.scalars(select(Destination)).all()}
    by_name["Andaman"] = by_name["Andaman Islands"]
    for name, (slug, state, lat, lng) in LOCATIONS.items():
        if name not in by_name:
            d = Destination(name=name, slug=slug, state=state, lat=lat, lng=lng,
                            description=f"Explore {name} at your own pace.", tags=["travel"],
                            avg_cost_inr=25000, climate="Seasonal")
            db.add(d)
            by_name[name] = d
    db.flush()
    for entry in data["destinations"]:
        d = by_name[entry["name"]]
        if not db.scalar(select(HolidayPackage).where(HolidayPackage.destination_id == d.id)):
            db.add(HolidayPackage(destination_id=d.id, name=entry["name"], price_inr=entry["price"],
                                  nights=entry["nights"], display=entry))
    for entry in data["hotels"]:
        stay = db.scalar(select(Stay).where(Stay.name == entry["name"]))
        if not stay:
            stay = Stay(name=entry["name"], destination_id=by_name[entry["place"]].id,
                        price_inr=entry["price"], rating=float(entry["rating"]), kind="hotel",
                        amenities=entry["amenities"].split(" · "))
            db.add(stay)
            db.flush()
        if not db.get(WebsiteStay, stay.id):
            db.add(WebsiteStay(stay_id=stay.id, display=entry))
    for entry in data["experiences"]:
        if not db.scalar(select(Experience).where(Experience.name == entry["name"])):
            db.add(Experience(name=entry["name"], destination_id=by_name.get(entry["place"], by_name["Kerala"]).id,
                              price_inr=entry["price"], display=entry))
    origins = [by_name[n] for n in ["New Delhi", "Mumbai", "Bengaluru", "Hyderabad", "Chennai"]]
    for i, origin in enumerate(origins):
        for j, target in enumerate([by_name[n] for n in ["Kashmir", "Goa", "Jaipur", "Kochi", "Varanasi"]]):
            for a, b in [(origin, target), (target, origin)]:
                if not db.scalar(select(TransportRoute).where(TransportRoute.origin_id == a.id,
                                                              TransportRoute.destination_id == b.id,
                                                              TransportRoute.mode == "flight")):
                    db.add(TransportRoute(origin_id=a.id, destination_id=b.id, mode="flight",
                                          operator="Voyara sample flight", duration_min=120 + j * 15,
                                          price_inr=4900 + i * 400 + j * 300, seats_available=40))
    db.commit()
