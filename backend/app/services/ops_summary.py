from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from typing import Any, Iterable


ACTIVE_JOB_STATUSES = {"pending", "running"}
OPEN_NOTICE_OUTCOMES = {"pending"}


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _coerce_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _coerce_date(value: date | None) -> date | None:
    return value if isinstance(value, date) else None


def _duration_seconds(started_at: datetime | None, finished_at: datetime | None, now: datetime) -> float | None:
    started = _coerce_datetime(started_at)
    finished = _coerce_datetime(finished_at) or now
    if not started:
        return None
    return max((finished - started).total_seconds(), 0.0)


def summarize_jobs(jobs: Iterable[Any], now: datetime | None = None) -> dict[str, Any]:
    current_time = _coerce_datetime(now) or datetime.now(timezone.utc)
    status_counts = Counter()
    type_counts = Counter()
    active_jobs: list[dict[str, Any]] = []
    recent_failures: list[dict[str, Any]] = []
    durations: list[float] = []
    stale_count = 0

    for job in jobs:
        status = str(_enum_value(getattr(job, "status", "unknown")) or "unknown")
        job_type = str(_enum_value(getattr(job, "job_type", "unknown")) or "unknown")
        progress = float(getattr(job, "progress", 0.0) or 0.0)
        progress_pct = round(progress * 100) if progress <= 1 else round(progress)
        status_counts[status] += 1
        type_counts[job_type] += 1

        duration = _duration_seconds(getattr(job, "started_at", None), getattr(job, "finished_at", None), current_time)
        if duration is not None and status == "done":
            durations.append(duration)

        payload = getattr(job, "payload", None) or {}
        result = getattr(job, "result", None) or {}
        label = payload.get("filename") or result.get("filename") or f"Job {str(getattr(job, 'id', ''))[:8]}"

        if status in ACTIVE_JOB_STATUSES:
            if status == "running" and duration is not None and duration >= 20 * 60:
                stale_count += 1
            active_jobs.append(
                {
                    "id": getattr(job, "id", None),
                    "job_type": job_type,
                    "status": status,
                    "progress_pct": progress_pct,
                    "label": label,
                    "created_at": _coerce_datetime(getattr(job, "created_at", None)).isoformat()
                    if getattr(job, "created_at", None)
                    else None,
                    "started_at": _coerce_datetime(getattr(job, "started_at", None)).isoformat()
                    if getattr(job, "started_at", None)
                    else None,
                    "duration_seconds": round(duration, 1) if duration is not None else None,
                }
            )

        finished_at = _coerce_datetime(getattr(job, "finished_at", None))
        if status == "failed" and finished_at and (current_time - finished_at).total_seconds() <= 24 * 60 * 60:
            recent_failures.append(
                {
                    "id": getattr(job, "id", None),
                    "job_type": job_type,
                    "label": label,
                    "finished_at": finished_at.isoformat(),
                    "error_message": getattr(job, "error_message", None),
                }
            )

    active_jobs.sort(key=lambda item: (item.get("status") != "running", item.get("started_at") or "", item.get("created_at") or ""))
    recent_failures.sort(key=lambda item: item.get("finished_at") or "", reverse=True)

    return {
        "total": sum(status_counts.values()),
        "active_count": status_counts.get("pending", 0) + status_counts.get("running", 0),
        "stale_count": stale_count,
        "failed_last_24h": len(recent_failures),
        "avg_duration_seconds": round(sum(durations) / len(durations), 1) if durations else None,
        "status_counts": {
            "pending": status_counts.get("pending", 0),
            "running": status_counts.get("running", 0),
            "done": status_counts.get("done", 0),
            "failed": status_counts.get("failed", 0),
        },
        "type_counts": dict(type_counts),
        "active_jobs": active_jobs[:5],
        "recent_failures": recent_failures[:5],
    }


def summarize_editais(editais: Iterable[Any]) -> dict[str, Any]:
    rows = list(editais)
    total_chunks = 0
    total_requirements = 0
    last_parsed_at: datetime | None = None

    for edital in rows:
        total_chunks += len(getattr(edital, "chunks", []) or [])
        total_requirements += len(getattr(edital, "requirements", []) or [])
        parsed_at = _coerce_datetime(getattr(edital, "parsed_at", None))
        if parsed_at and (last_parsed_at is None or parsed_at > last_parsed_at):
            last_parsed_at = parsed_at

    return {
        "total_editais": len(rows),
        "total_chunks": total_chunks,
        "total_requirements": total_requirements,
        "last_parsed_at": last_parsed_at.isoformat() if last_parsed_at else None,
    }


def summarize_crm(notices: Iterable[Any], now: datetime | None = None) -> dict[str, Any]:
    current_time = _coerce_datetime(now) or datetime.now(timezone.utc)
    today = current_time.date()
    rows = list(notices)
    stage_counts = Counter()
    outcome_counts = Counter()
    upcoming_auctions: list[dict[str, Any]] = []
    overdue_post_auction = 0
    attention_required = 0
    active_pipeline = 0

    for notice in rows:
        stage = str(_enum_value(getattr(notice, "stage", "triage")) or "triage")
        outcome = str(_enum_value(getattr(notice, "outcome", "pending")) or "pending")
        post_phase = _enum_value(getattr(notice, "post_auction_phase", None))

        stage_counts[stage] += 1
        outcome_counts[outcome] += 1

        if outcome in OPEN_NOTICE_OUTCOMES:
            active_pipeline += 1

        auction_date = _coerce_datetime(getattr(notice, "auction_date", None))
        if auction_date and outcome in OPEN_NOTICE_OUTCOMES:
            delta_days = (auction_date.date() - today).days
            if 0 <= delta_days <= 7:
                upcoming_auctions.append(
                    {
                        "id": getattr(notice, "id", None),
                        "number": getattr(notice, "number", None),
                        "title": getattr(notice, "title", None),
                        "auction_date": auction_date.isoformat(),
                        "organ_name": getattr(getattr(notice, "organ", None), "name", None),
                    }
                )
            if delta_days < 0:
                attention_required += 1

        post_deadline = _coerce_date(getattr(notice, "post_auction_deadline", None))
        if post_deadline and outcome in OPEN_NOTICE_OUTCOMES and post_deadline < today:
            overdue_post_auction += 1
            attention_required += 1

    upcoming_auctions.sort(key=lambda item: item.get("auction_date") or "")

    return {
        "total_notices": len(rows),
        "active_pipeline": active_pipeline,
        "won_count": outcome_counts.get("won", 0),
        "lost_count": outcome_counts.get("lost", 0),
        "attention_required": attention_required,
        "upcoming_auctions_count": len(upcoming_auctions),
        "overdue_post_auction_count": overdue_post_auction,
        "stage_counts": dict(stage_counts),
        "outcome_counts": dict(outcome_counts),
        "upcoming_auctions": upcoming_auctions[:5],
    }
