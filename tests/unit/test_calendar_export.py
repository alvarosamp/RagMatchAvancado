from datetime import datetime

from app.services.calendar_export import build_google_calendar_url, build_ics


def test_naive_calendar_datetime_is_brasilia_time():
    starts_at = datetime(2026, 8, 4, 15, 0)

    google_url = build_google_calendar_url(
        title="Pregao",
        starts_at=starts_at,
        description="Sessao",
    )
    ics = build_ics(
        uid="test",
        title="Pregao",
        starts_at=starts_at,
        description="Sessao",
    )

    assert "dates=20260804T180000Z%2F20260804T190000Z" in google_url
    assert "DTSTART:20260804T180000Z" in ics
