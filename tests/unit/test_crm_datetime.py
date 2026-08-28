from datetime import datetime

from app.crm.timezone import brasilia_wall_clock


def test_datetime_values_with_utc_offset_are_stored_as_brasilia_wall_clock():
    value = brasilia_wall_clock(datetime.fromisoformat("2026-08-26T17:00:00+00:00"))

    assert value == datetime(2026, 8, 26, 14, 0)
    assert value.tzinfo is None


def test_datetime_values_without_offset_keep_the_entered_clock_time():
    value = brasilia_wall_clock(datetime.fromisoformat("2026-08-26T14:00:00"))

    assert value == datetime(2026, 8, 26, 14, 0)
