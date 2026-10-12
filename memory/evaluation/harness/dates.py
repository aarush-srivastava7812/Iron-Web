"""Dataset dates are interpreted consistently in UTC, independent of host timezone."""
from datetime import datetime, timezone


def parse_timestamp(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = value.strip()
    formats = ("%Y/%m/%d (%a) %H:%M", "%I:%M %p on %d %B, %Y", "%Y-%m-%d %H:%M:%S",
               "%Y-%m-%d", "%Y/%m/%d", "%d %B %Y", "%B %d, %Y")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        for fmt in formats:
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"Unrecognized dataset date: {value!r}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())
