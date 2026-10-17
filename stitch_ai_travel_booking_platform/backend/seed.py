"""Synthetic demo data. Run: python seed.py (idempotent)."""
import datetime as dt

from app.db import SessionLocal, create_schema
from app.models import Destination, FoodPlace, Guide, Offer, Stay, TransportRoute

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
    ("leh-ladakh", "Leh Ladakh", "Ladakh", "High-altitude deserts, turquoise monasteries perched on cliffs and Pangong Lake's colour-shifting waters. Ladakh is otherworldly — and worth every bit of the journey.", ["mountain", "adventure", "heritage", "offbeat"], "Jun-Sep", 34.15, 77.58, 35000, "Cold desert"),
    ("hampi", "Hampi", "Karnataka", "Boulders, banana groves and the ruins of a once-great empire spread across an ancient landscape. Hampi rewards those who wander without a fixed plan.", ["heritage", "culture", "offbeat", "adventure"], "Oct-Feb", 15.34, 76.46, 12000, "Tropical savanna"),
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
        from seed_website import seed_website
        seed_website(db)
        from app.destination_content import seed_kerala
        seed_kerala(db)
        db.flush()
        ds = db.query(Destination).all()
        for i, d in enumerate(ds):
            if not db.query(Stay).filter_by(destination_id=d.id, kind="hostel").first():
                db.add(Stay(destination_id=d.id, name=f"{d.name} Backpackers' Nook", kind="hostel", price_inr=750 + i * 55, rating=4.3, amenities=["wifi"]))
            if not db.query(Stay).filter_by(destination_id=d.id, kind="hotel").first():
                db.add(Stay(destination_id=d.id, name=f"{d.name} Courtyard House", kind="hotel", price_inr=3200 + i * 250, rating=4.6, amenities=["wifi", "breakfast"]))
            if not db.query(Stay).filter_by(destination_id=d.id, kind="homestay").first():
                db.add(Stay(destination_id=d.id, name=f"{d.name} Slow Living Homestay", kind="homestay", price_inr=1850 + i * 125, rating=4.8, amenities=["home-food", "wifi"]))
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
        # A small, explicitly fictional Goa scenario makes ranking, swapping
        # and price deltas demonstrable; avoid expanding the whole marketplace.
        goa = by_slug["goa"]
        demo_choices = {
            Stay: [dict(name="Demo Goa Garden Homestay", kind="homestay", price_inr=1850, rating=4.6, amenities=["wifi", "breakfast"]),
                   dict(name="Demo Goa Coast Lodge", kind="hotel", price_inr=2800, rating=4.7, amenities=["wifi", "breakfast"])],
            FoodPlace: [dict(name="Demo Goa Vegetarian Kitchen", kind="restaurant", cuisine="Goan vegetarian", diet="veg", price_inr=600, rating=4.5),
                        dict(name="Demo Goa Market Cafe", kind="cafe", cuisine="Cafe", diet="veg", price_inr=400, rating=4.4)],
            Guide: [dict(name="Demo Goa Heritage Walk", languages=["English", "Hindi"], specialties=["history", "culture"], price_inr=1200, rating=4.7),
                    dict(name="Demo Goa Village Trail", languages=["English", "Hindi"], specialties=["nature", "culture"], price_inr=800, rating=4.6)],
        }
        for model, choices in demo_choices.items():
            for choice in choices:
                if not db.query(model).filter_by(destination_id=goa.id, name=choice["name"]).first():
                    db.add(model(destination_id=goa.id, **choice))
        db.commit()

        OFFERS = [
            ("SLOWTRAVEL15", "15% off slow-travel stays", "Take it easy: 15% off any homestay or resort request.", 15.0, None, "stays", None, dt.date(2026, 12, 31)),
            ("FIRSTBITE", "₹250 off your first food stop", "Flat ₹250 off food requests above ₹1,000.", None, 250, "food", 1000, dt.date(2026, 12, 31)),
            ("SCENICROUTE", "10% off any transport route", "Trains, buses or flights — 10% off your seats.", 10.0, None, "transport", None, dt.date(2026, 12, 31)),
            ("LOCALGUIDE500", "₹500 off a local guide day", "Flat ₹500 off guide days above ₹1,500.", None, 500, "guide", 1500, dt.date(2026, 12, 31)),
            ("WANDER10", "10% off any trip request", "Applies to any combination of trip items.", 10.0, None, "any", 5000, dt.date(2026, 12, 31)),
        ]
        existing_codes = {offer.code for offer in db.query(Offer).all()}
        for code, title, description, percent, flat, module, min_amount, valid_till in OFFERS:
            if code not in existing_codes:
                db.add(Offer(code=code, title=title, description=description, discount_percent=percent,
                             discount_flat_inr=flat, module=module, min_amount_inr=min_amount,
                             valid_till=valid_till, active=True))
        db.commit()
        print(f"seeded {len(ds)} destinations, {len(OFFERS)} offers")


if __name__ == "__main__":
    run()
