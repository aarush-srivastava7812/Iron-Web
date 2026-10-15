"""Weather notes for the Travel Support Agent.

No provider credentials are configured in this repository, so this tool only
produces clearly-labeled climatology hints derived from destination metadata.
It never claims a live forecast.
"""
from __future__ import annotations

import time

from agents.schemas import WeatherNote

from .destinations import get_destination


def weather_note(destination_id: int, location: str) -> WeatherNote:
    """Destination-climatology hint; explicitly NOT a live forecast."""
    response = get_destination(destination_id)
    climate = None
    if response.ok and response.data:
        climate = response.data[0].get("climate")
    return WeatherNote(
        location=location,
        summary=climate or "Seasonal patterns unavailable without a weather provider",
        freshness="climatology",
        note=f"Derived from destination metadata at {time.strftime('%Y-%m-%d', time.gmtime())}; "
             "check a live forecast closer to travel.",
    )
