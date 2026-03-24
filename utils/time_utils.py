"""
Time utilities — all user-facing timestamps in Hong Kong Time (HKT = UTC+8).

Internal storage remains UTC.  These helpers convert for display only.
"""

from datetime import datetime, timezone, timedelta

HKT = timezone(timedelta(hours=8), name="HKT")


def to_hkt(iso_string: str) -> str:
    """
    Convert a UTC ISO timestamp to a full HKT display string.

    Example: "2025-01-15T08:30:00+00:00" → "2025-01-15  16:30 HKT"
    """
    if not iso_string:
        return ""
    try:
        dt = datetime.fromisoformat(iso_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hkt_dt = dt.astimezone(HKT)
        return hkt_dt.strftime("%Y-%m-%d  %H:%M HKT")
    except (ValueError, TypeError):
        return iso_string[:16].replace("T", "  ")


def to_hkt_short(iso_string: str) -> str:
    """
    Convert to short HKT date only.

    Example: "2025-01-15T08:30:00+00:00" → "2025-01-15"
    """
    if not iso_string:
        return ""
    try:
        dt = datetime.fromisoformat(iso_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hkt_dt = dt.astimezone(HKT)
        return hkt_dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return iso_string[:10]
