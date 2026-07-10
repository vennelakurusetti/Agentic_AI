import json

# Mock available interview slots for demo
AVAILABLE_SLOTS = [
    {"date": "2026-07-15", "time": "10:00 AM", "format": "online"},
    {"date": "2026-07-15", "time": "2:00 PM", "format": "online"},
    {"date": "2026-07-16", "time": "11:00 AM", "format": "offline"},
    {"date": "2026-07-16", "time": "3:00 PM", "format": "online"},
    {"date": "2026-07-17", "time": "9:00 AM", "format": "online"},
]


def get_availability() -> str:
    """Return available interview slots as JSON string."""
    return json.dumps({"available_slots": AVAILABLE_SLOTS})