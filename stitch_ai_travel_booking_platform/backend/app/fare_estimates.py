"""Origin-specific sample route prices. Missing routes never get a made-up fare."""
from sqlalchemy import select
from .models import Destination, TransportRoute


def route_preview(db, origin_name, destination, *, travelers=1, mode=None, max_minutes=1440, places=None, route_rows=None):
    places = list(db.scalars(select(Destination))) if places is None else places
    origin = next((d for d in places
                   if origin_name and origin_name.casefold() in {d.name.casefold(), d.slug.casefold()}), None)
    gateway = next((d for d in places if d.slug == "kochi"), destination) if destination.slug == "kerala" else destination
    same_city = bool(origin and gateway and origin.id == gateway.id)
    routes = []
    for start, end in ((origin, gateway), (gateway, origin)):
        route = None
        if start and end and not same_city:
            if route_rows is not None:
                candidates = [r for r in route_rows if r.origin_id == start.id and r.destination_id == end.id
                              and r.duration_min <= max_minutes and r.seats_available >= travelers
                              and (not mode or r.mode == ("cab" if mode == "car" else mode))]
                route = min(candidates, key=lambda r: (r.price_inr, r.id), default=None)
                routes.append(route)
                continue
            query = select(TransportRoute).where(TransportRoute.origin_id == start.id,
                TransportRoute.destination_id == end.id, TransportRoute.duration_min <= max_minutes,
                TransportRoute.seats_available >= travelers)
            if mode:
                query = query.where(TransportRoute.mode == ("cab" if mode == "car" else mode))
            route = db.scalar(query.order_by(TransportRoute.price_inr, TransportRoute.id).limit(1))
        routes.append(route)
    complete = same_city or all(routes)
    legs = [dict(direction=direction, origin=(origin.name if direction == "outbound" else gateway.name) if origin else None,
                 destination=(gateway.name if direction == "outbound" else origin.name) if origin else gateway.name,
                 fare_inr=(0 if same_city else route.price_inr * travelers) if route or same_city else None,
                 mode=route.mode if route else None, route_id=route.id if route else None,
                 duration_minutes=route.duration_min if route else None)
            for direction, route in zip(("outbound", "return"), routes)]
    if not origin_name:
        notice = "Starting city needed — travel fares are not included in the destination guide price."
    elif not complete:
        notice = f"Travel from {origin_name}: one or both sample routes are unavailable; a fare quote is needed."
    elif same_city:
        notice = f"You are starting in {origin.name}; no intercity fare is needed. Local travel is separate."
    else:
        notice = f"Sample round-trip travel from {origin.name} for {travelers} traveler(s); dates and live fares still need checking."
    if gateway.id != destination.id:
        notice += f" Uses {gateway.name} as the gateway; travel within {destination.name} is separate."
    return dict(status="needs_origin" if not origin_name else "sample" if complete else "unavailable",
                origin=origin_name, destination=destination.name, gateway=gateway.name,
                travelers=travelers, legs=legs, costs_complete=bool(complete),
                round_trip_inr=sum(leg["fare_inr"] for leg in legs) if complete else None,
                notice=notice, sample=True)
