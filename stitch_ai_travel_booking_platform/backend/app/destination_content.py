"""Independent editorial demo content; no live supplier or weather claims."""
REGIONS = {"kerala": ("kochi", "munnar", "alleppey")}
KERALA = {
    "slug": "kerala", "name": "Kerala", "eyebrow": "Backwaters, hills & living traditions",
    "description": "Trace a gentler route from Kochi's harbour lanes to Munnar's tea-covered hills and the palm-lined backwaters of Alleppey.",
    "photo": "/travel/kerala.jpg", "themes": ["Nature & relaxation", "Backwater experiences", "Local cuisine", "Culture & heritage"],
    "season_note": "The demo guide suggests October–March. Check conditions and opening times close to departure.",
    "packing": "Light layers, comfortable shoes, a rain shell and sun protection; adjust to your dates and activities.",
    "cuisine": "Appam, vegetable stew, Kerala sadya and regional seafood. Ask each venue about dietary suitability.",
    "route_notice": "Illustrative route diagram; travel times and road conditions are not verified.",
    "cities": [
        {"slug": "kochi", "name": "Kochi", "lat": 9.93, "lng": 76.26,
         "description": "Harbour-side lanes, trading stories, galleries and local kitchens.",
         "experiences": ["Fort Kochi heritage walk", "Harbour sunset", "Local food discovery"]},
        {"slug": "munnar", "name": "Munnar", "lat": 10.09, "lng": 77.06,
         "description": "Tea gardens, misty hills and time to slow down in the highlands.",
         "experiences": ["Tea garden walk", "Scenic viewpoints", "Village trail"]},
        {"slug": "alleppey", "name": "Alleppey", "lat": 9.50, "lng": 76.34,
         "description": "Palm-lined waterways, village life and quiet stretches beside the backwaters.",
         "experiences": ["Backwater cruise", "Village canoe trail", "Waterside sunset"]},
    ],
}


def destination_ids(db, destination_id):
    from sqlalchemy import select
    from .models import Destination
    destination = db.get(Destination, destination_id)
    slugs = REGIONS.get(destination.slug, ()) if destination else ()
    return {destination_id, *db.scalars(select(Destination.id).where(Destination.slug.in_(slugs))).all()}


def seed_kerala(db):
    from sqlalchemy import select
    from .models import Destination, Experience, FoodPlace, Guide, HolidayPackage, Stay, WebsiteStay
    destinations = {d.slug: d for d in db.scalars(select(Destination))}
    if "alleppey" not in destinations:
        city = KERALA["cities"][2]
        row = Destination(slug=city["slug"], name=city["name"], state="Kerala", country="India",
                          description=city["description"], tags=["backwaters", "nature", "culture"],
                          best_season="Oct-Mar", lat=city["lat"], lng=city["lng"], avg_cost_inr=21000, climate="Tropical coast")
        db.add(row)
        db.flush()
        destinations["alleppey"] = row
    package = db.scalar(select(HolidayPackage).where(HolidayPackage.destination_id == destinations["kerala"].id))
    if package:
        package.display = dict(package.display, desc=KERALA["description"], route=[c["name"] for c in KERALA["cities"]],
                               themes=KERALA["themes"], tag="Backwaters & hills")
    for index, city in enumerate(KERALA["cities"]):
        dest = destinations[city["slug"]]
        for tier, price in [("Courtyard Stay", 2400 + index * 350), ("Garden Retreat", 3900 + index * 450)]:
            name = f"Voyara Demo {city['name']} {tier}"
            stay = db.scalar(select(Stay).where(Stay.name == name))
            if stay is None:
                stay = Stay(destination_id=dest.id, name=name, kind="hotel", price_inr=price,
                            rating=4.5, amenities=["wifi", "breakfast"])
                db.add(stay)
                db.flush()
            if not db.get(WebsiteStay, stay.id):
                db.add(WebsiteStay(stay_id=stay.id, display=dict(name=name, place=city["name"], type=tier,
                    price=price, rating="4.5", img="photo-1602216056096-3b40cc0c9944", amenities="Wi-Fi · Breakfast", demo=True)))
        for experience_name, price in [(city["experiences"][0], 900 + index * 600), (city["experiences"][1], 600 + index * 350)]:
            name = "Demo " + experience_name
            if not db.scalar(select(Guide).where(Guide.name == name)):
                db.add(Guide(destination_id=dest.id, name=name, languages=["English", "Hindi"],
                             specialties=["nature", "culture", "history"], price_inr=price, rating=4.5))
            if not db.scalar(select(Experience).where(Experience.name == name)):
                db.add(Experience(destination_id=dest.id, name=name, price_inr=price,
                    display=dict(name=name, place=city["name"], type="Nature" if index else "Culture",
                                 price=price, img="photo-1602216056096-3b40cc0c9944", desc=city["description"], demo=True)))
        name = f"Demo {city['name']} Vegetarian Kitchen"
        if not db.scalar(select(FoodPlace).where(FoodPlace.name == name)):
            db.add(FoodPlace(destination_id=dest.id, name=name, kind="restaurant", cuisine="Kerala vegetarian",
                             diet="veg", price_inr=550 + index * 80, rating=4.5))
    # Fix the existing backwater experience's region fallback without changing its price.
    cruise = db.scalar(select(Experience).where(Experience.name == "Kerala backwater cruise"))
    if cruise:
        cruise.destination_id = destinations["alleppey"].id
        guide=db.scalar(select(Guide).where(Guide.name==cruise.name))
        if guide:
            guide.destination_id=cruise.destination_id
