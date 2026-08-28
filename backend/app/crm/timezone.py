from datetime import datetime
from zoneinfo import ZoneInfo


BRASILIA_TIME_ZONE = ZoneInfo("America/Sao_Paulo")


def brasilia_wall_clock(value: datetime) -> datetime:
    """Return the local Brasilia clock value for CRM naive DateTime columns."""
    if value.tzinfo is None:
        return value
    return value.astimezone(BRASILIA_TIME_ZONE).replace(tzinfo=None)
