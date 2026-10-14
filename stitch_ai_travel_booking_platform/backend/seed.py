"""Synthetic demo data. Run: python seed.py (idempotent)."""
from app.db import SessionLocal, create_schema
from app.models import Destination, FoodPlace, Guide, Stay, TransportRoute

DESTS = [
    ("goa", "Goa", "Goa", "Salt air, later mornings and old Portuguese lanes. Find a quiet cove, a family-run kitchen or a village that still moves at its own pace.", ["beach", "nightlife", "slow travel"], "Nov-Feb", 15.30, 74.12, 28000, "Tropical coast"),
    ("jaipur", "Jaipur", "Rajasthan", "Pink sandstone, courtyard cafes and lively bazaars. Jaipur brings royal architecture and everyday craft into the same afternoon.", ["heritage", "culture", "food"], "Oct-Mar", 26.91, 75.79, 22000, "Hot semi-arid"),
    ("manali", "Manali", "Himachal Pradesh", "Pine-scented walks, mountain mornings and winding roads into the valley. Come for the views; stay for the slower rhythm.", ["mountain", "adventure", "nature"], "Mar-Jun", 32.24, 77.19, 24000, "Alpine mountain"),
    ("munnar", "Munnar", "Kerala", "Tea gardens fold into the hills around Munnar. Misty trails, small farms and unhurried mornings make this a place to take your time.", ["nature", "relax", "mountain"], "Sep-Mar", 10.09, 77.06, 19000, "Cool highland"),
    ("varanasi", "Varanasi", "Uttar Pradesh", "A city of morning boat rides, temple bells and lanes with stories in every turn. Best explored slowly, with a local guide.", ["spiritual", "culture", "heritage"], "Oct-Mar", 25.32, 82.97, 16000, "Humid subtropical"),
    ("udaipur", "Udaipur", "Rajasthan", "Lakeside courtyards, hilltop palaces and dinner as the light leaves the water. A gentle, storybook escape in Rajasthan.", ["heritage", "slow travel", "romance"], "Oct-Mar", 24.58, 73.68, 26000, "Hot semi-arid"),
    ("rishikesh", "Rishikesh", "Uttarakhand", "River paths, forest air and quiet mornings beside the Ganga. A soft landing for yoga, day hikes and time outdoors.", ["river", "wellness", "adventure"], "Sep-Nov", 30.09, 78.27, 18000, "Temperate foothills"),
    ("kochi", "Kochi", "Kerala", "A harbor city layered with spice markets, art spaces and backwater day trips. Let the ferry set the pace.", ["coastal", "culture", "food"], "Oct-Mar", 9.93, 76.26, 21000, "Tropical monsoon"),
    ("andaman", "Andaman Islands", "Andaman and Nicobar Islands", "Clear water, forest trails and long stretches of island quiet. Leave space for the sea to make the itinerary.", ["island", "beach", "nature"], "Nov-Apr", 11.74, 92.74, 34000, "Tropical island"),
]


def run():
    create_schema()
    with SessionLocal() as db:
        by_slug = {destination.slug: destination for destination in db.query(Destination).all()}
        for slug, name, state, description, tags, season, lat, lng, avg_cost, climate in DESTS:
            destination = by_slug.get(slug)
            if destination is None:
                destination = Destination(
                    slug=slug, name=name, state=state, description=description, tags=tags,
                    best_season=season, lat=lat, lng=lng, avg_cost_inr=avg_cost, climate=climate,
                )
                db.add(destination)
                by_slug[slug] = destination
            else:
                destination.avg_cost_inr = destination.avg_cost_inr or avg_cost
                destination.climate = destination.climate or climate
        db.flush()
        ds = list(by_slug.values())
        for i, d in enumerate(ds):
            if not db.query(Stay).filter_by(destination_id=d.id).first():
                db.add_all([
                    Stay(destination_id=d.id, name=f"{d.name} Courtyard House", kind="hotel", price_inr=3200 + i * 250, rating=4.6, amenities=["wifi", "breakfast"]),
                    Stay(destination_id=d.id, name=f"{d.name} Backpackers' Nook", kind="hostel", price_inr=750 + i * 55, rating=4.3, amenities=["wifi"]),
                    Stay(destination_id=d.id, name=f"{d.name} Slow Living Homestay", kind="homestay", price_inr=1850 + i * 125, rating=4.8, amenities=["home-food", "wifi"]),
                ])
            if not db.query(FoodPlace).filter_by(destination_id=d.id).first():
                db.add_all([
                    FoodPlace(destination_id=d.id, name=f"{d.name} Family Kitchen", kind="restaurant", cuisine="Regional", diet="veg", price_inr=480 + i * 35, rating=4.7),
                    FoodPlace(destination_id=d.id, name=f"{d.name} Corner Cafe", kind="cafe", cuisine="Cafe", diet="both", price_inr=550 + i * 25, rating=4.5),
                    FoodPlace(destination_id=d.id, name=f"{d.name} Market Bites", kind="street_stall", cuisine="Street food", diet="both", price_inr=180 + i * 20, rating=4.6),
                ])
            if not db.query(Guide).filter_by(destination_id=d.id).first():
                db.add(Guide(destination_id=d.id, name=f"{d.name} Story Walk", languages=["English", "Hindi"], specialties=["history", "food walks"], price_inr=1800 + i * 150, rating=4.9))
            if not db.query(TransportRoute).filter_by(destination_id=d.id).first():
                first_origin = ds[(i + 1) % len(ds)]
                second_origin = ds[(i + 2) % len(ds)]
                db.add_all([
                    TransportRoute(origin_id=first_origin.id, destination_id=d.id, mode="flight", operator="Voyara Air Sample", duration_min=145 + i * 24, price_inr=4900 + i * 380, seats_available=40),
                    TransportRoute(origin_id=second_origin.id, destination_id=d.id, mode="train", operator="Indian Railways (sample)", duration_min=420 + i * 55, price_inr=1150 + i * 140, seats_available=120),
                    TransportRoute(origin_id=first_origin.id, destination_id=d.id, mode="bus", operator="Local Routes (sample)", duration_min=540 + i * 65, price_inr=850 + i * 95, seats_available=32),
                ])
        db.commit()
        print(f"seeded {len(ds)} destinations")


if __name__ == "__main__":
    run()
