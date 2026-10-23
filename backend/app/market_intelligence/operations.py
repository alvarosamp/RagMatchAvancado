"""Measured load health for one tenant; no source payloads or secrets."""

from collections import defaultdict
from datetime import timedelta
from math import ceil
from statistics import median

from sqlalchemy import case, func

from .domain import timestamp
from .models import SyncRun
from .repository import now, scoped

INGESTION_SOURCES = {"crm", "bling", "pncp", "ibge"}


def operations_report(db, tenant_id, *, days=30, clock=None, sample_limit=2000):
    clock = clock or now()
    cutoff = clock - timedelta(days=days)
    query = scoped(db, SyncRun, tenant_id)
    recent = query.filter(SyncRun.created_at >= cutoff)
    counts = defaultdict(dict)
    for source, status, count in recent.with_entities(
        SyncRun.source, SyncRun.status, func.count(SyncRun.id)
    ).group_by(SyncRun.source, SyncRun.status):
        counts[source][status] = count
    last_success = dict(
        query.with_entities(
            SyncRun.source,
            func.max(case((SyncRun.status == "completed", SyncRun.finished_at))),
        )
        .group_by(SyncRun.source)
        .all()
    )
    active = query.filter(SyncRun.status.in_(["queued", "running"]))
    oldest = {}
    for source, status, created, started, count in active.with_entities(
        SyncRun.source,
        SyncRun.status,
        func.min(SyncRun.created_at),
        func.min(SyncRun.started_at),
        func.count(SyncRun.id),
    ).group_by(SyncRun.source, SyncRun.status):
        oldest[(source, status)] = (timestamp(started or created), count)
    # Counts above cover the whole window. Quantiles use this bounded sample.
    samples = (
        recent.filter(SyncRun.finished_at.is_not(None))
        .order_by(SyncRun.finished_at.desc(), SyncRun.id)
        .limit(sample_limit)
        .all()
    )
    durations, waits = defaultdict(list), defaultdict(list)
    for run in samples:
        if run.started_at and run.finished_at:
            duration = (
                timestamp(run.finished_at) - timestamp(run.started_at)
            ).total_seconds()
            wait = (
                timestamp(run.started_at) - timestamp(run.created_at)
            ).total_seconds()
            if duration >= 0:
                durations[run.source].append(duration)
            if wait >= 0:
                waits[run.source].append(wait)
    sources, alerts = [], []
    for source in sorted({"crm", *counts, *last_success, *(key[0] for key in oldest)}):
        totals = counts[source]
        completed, failed = totals.get("completed", 0), totals.get("failed", 0)
        last = timestamp(last_success[source]) if last_success.get(source) else None
        age = max(0, (clock - last).total_seconds()) if last else None
        source_alerts = []
        if source in INGESTION_SOURCES and (age is None or age > 48 * 3600):
            source_alerts.append("source_not_loaded" if age is None else "source_stale")
        if failed:
            source_alerts.append("source_failures_in_window")
        queued, running = (
            oldest.get((source, "queued")),
            oldest.get((source, "running")),
        )
        if queued and clock - queued[0] > timedelta(minutes=15):
            source_alerts.append("queue_wait_exceeded")
        if running and clock - running[0] > timedelta(hours=4):
            source_alerts.append("running_job_exceeded")
        values = sorted(durations[source])
        terminal_count = completed + failed
        sources.append(
            {
                "source": source,
                "completed": completed,
                "failed": failed,
                "queued": queued[1] if queued else 0,
                "running": running[1] if running else 0,
                "failure_rate": failed / terminal_count if terminal_count else None,
                "last_success_at": last.isoformat() if last else None,
                "freshness_hours": age / 3600 if age is not None else None,
                "duration_p50_seconds": median(values) if values else None,
                "duration_p95_seconds": values[max(0, ceil(len(values) * 0.95) - 1)]
                if values
                else None,
                "queue_wait_p50_seconds": median(waits[source])
                if waits[source]
                else None,
                "duration_sample": len(values),
                "sample_truncated": len(samples) == sample_limit
                and sum(run.source == source for run in samples) < terminal_count,
                "alerts": source_alerts,
            }
        )
        alerts.extend({"source": source, "code": code} for code in source_alerts)
    return {
        "generated_at": clock.isoformat(),
        "window_days": days,
        "sources": sources,
        "alerts": alerts,
        "status": "alert" if alerts else "healthy",
        "thresholds": {
            "freshness_hours": 48,
            "queue_wait_minutes": 15,
            "running_hours": 4,
        },
        "automatic_retraining": False,
    }
