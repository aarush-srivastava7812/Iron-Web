"""Synthetic demo data. Run: python seed.py (idempotent)."""
from app.db import Base, SessionLocal, engine
from app.models import Destination, FoodPlace, Guide, Stay, TransportRoute

DESTS = [
    ("goa", "Goa", "Goa", "Beaches, Portuguese heritage, nightlife.", ["beach", "nightlife"], "Nov-Feb", 15.30, 74.12),
    ("jaipur", "Jaipur", "Rajasthan", "Forts, palaces and bazaars.", ["heritage", "culture"], "Oct-Mar", 26.91, 75.79),
    ("manali", "Manali", "Himachal Pradesh", "Mountains, trekking, snow.", ["mountain", "adventure"], "Mar-Jun", 32.24, 77.19),
    ("munnar", "Munnar", "Kerala", "Tea estates and misty hills.", ["nature", "relax"], "Sep-Mar", 10.09, 77.06),
    ("varanasi", "Varanasi", "Uttar Pradesh", "Ghats, temples, ancient city.", ["spiritual", "culture"], "Oct-Mar", 25.32, 82.97),
]


def run():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.query(Destination).first():
            print("already seeded")
            return
        ds = [Destination(slug=s, name=n, state=st, description=d, tags=t, best_season=b, lat=la, lng=lo)
              for s, n, st, d, t, b, la, lo in DESTS]
        db.add_all(ds)
        db.flush()
        for i, d in enumerate(ds):
            db.add_all([
                Stay(destination_id=d.id, name=f"{d.name} Heritage Hotel", kind="hotel", price_inr=3500 + i * 400, rating=4.3, amenities=["wifi", "breakfast"]),
                Stay(destination_id=d.id, name=f"{d.name} Backpackers", kind="hostel", price_inr=700 + i * 50, rating=4.1, amenities=["wifi"]),
                Stay(destination_id=d.id, name=f"{d.name} Homestay", kind="homestay", price_inr=1800 + i * 100, rating=4.6, amenities=["home-food"]),
                FoodPlace(destination_id=d.id, name=f"{d.name} Local Thali House", kind="restaurant", cuisine="Regional", diet="veg", price_inr=500, rating=4.4),
                FoodPlace(destination_id=d.id, name=f"{d.name} Brew Cafe", kind="cafe", cuisine="Cafe", diet="both", price_inr=600, rating=4.2),
                FoodPlace(destination_id=d.id, name=f"{d.name} Street Eats", kind="street_stall", cuisine="Street food", diet="both", price_inr=200, rating=4.5),
                Guide(destination_id=d.id, name=f"{d.name} Local Guide", languages=["English", "Hindi"], specialties=["history", "food walks"], price_inr=2000, rating=4.7),
                TransportRoute(origin_id=ds[0].id if d.id != ds[0].id else ds[1].id, destination_id=d.id, mode="flight", operator="SkyAir", duration_min=150, price_inr=5200, seats_available=40),
                TransportRoute(origin_id=ds[1].id if d.id != ds[1].id else ds[2].id, destination_id=d.id, mode="train", operator="Indian Railways", duration_min=600, price_inr=1400, seats_available=120),
            ])
        db.commit()
        print("seeded")


if __name__ == "__main__":
    run()
