from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo


LOCAL_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def build_google_calendar_url(*, title: str, starts_at: datetime, description: str | None = None) -> str:
    start = _as_utc(starts_at)
    end = start + timedelta(hours=1)
    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{_stamp(start)}/{_stamp(end)}",
        "details": description or "",
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def build_ics(*, uid: str, title: str, starts_at: datetime, description: str | None = None) -> str:
    start = _as_utc(starts_at)
    end = start + timedelta(hours=1)
    now = datetime.now(timezone.utc)
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//TOR//RagMatch CRM//PT-BR",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:{_escape(uid)}",
            f"DTSTAMP:{_stamp(now)}",
            f"DTSTART:{_stamp(start)}",
            f"DTEND:{_stamp(end)}",
            f"SUMMARY:{_escape(title)}",
            f"DESCRIPTION:{_escape(description or '')}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


def session_calendar_payload(session: Any, notice: Any) -> dict[str, Any]:
    title = session.outcome_summary or _default_title(notice)
    description = session.notes or ""
    starts_at = session.scheduled_at or notice.auction_date
    return {
        "title": title,
        "description": description,
        "starts_at": starts_at,
        "google_calendar_url": build_google_calendar_url(
            title=title,
            starts_at=starts_at,
            description=description,
        )
        if starts_at
        else None,
    }


def _default_title(notice: Any) -> str:
    organ = notice.organ.name if getattr(notice, "organ", None) else None
    return " ".join(part for part in [notice.tor_id or notice.number, "Pregao", f"- {organ}" if organ else None] if part)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=LOCAL_TIMEZONE).astimezone(timezone.utc)
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return _as_utc(value).strftime("%Y%m%dT%H%M%SZ")


def _escape(value: Any) -> str:
    text = str(value or "")
    return (
        text.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )
