"""Provider-independent travel tools shared by the specialist agents.

Every tool has two backends:
- ``TravelApiBackend`` — the real travel application API (TRAVEL_API_URL).
- ``MockTravelBackend`` — deterministic sample data, always labeled kind="mock".

Nothing here invents live prices, hours, availability or booking status; when
only mock data is available it is labeled as such end to end.
"""
from .base import ToolResponse, get_tools
