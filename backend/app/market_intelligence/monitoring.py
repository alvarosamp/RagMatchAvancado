"""Persist tenant-specific quality/drift snapshots; never auto-promote models."""

from datetime import timedelta

from .domain import timestamp
from .models import Feedback, ModelRun, Review, SyncRun
from .operations import operations_report
from .repository import now, scoped
from .service import report


def quality_snapshot(db, tenant_id):
    data = report(db, tenant_id)
    alerts = []
    pending = scoped(db, Review, tenant_id).filter_by(status="pending").count()
    latest = (
        scoped(db, SyncRun, tenant_id)
        .filter_by(source="crm", status="completed")
        .order_by(SyncRun.finished_at.desc())
        .first()
    )
    if not latest or timestamp(latest.finished_at) < now() - timedelta(hours=48):
        alerts.append("crm_stale_or_not_loaded")
    if pending:
        alerts.append("identity_review_required")
    quality = data["quality"]
    operations = operations_report(db, tenant_id)
    alerts.extend(
        f"{alert['source']}:{alert['code']}" for alert in operations["alerts"]
    )
    for field in ["reference_price", "unit"]:
        indicator = quality[field]
        if indicator["total"] and (indicator["rate"] or 0) < 0.5:
            alerts.append(f"low_{field}_coverage")
    decisions = (
        scoped(db, Feedback, tenant_id)
        .filter(Feedback.action.in_(["bid", "no_bid"]))
        .order_by(Feedback.available_at.desc())
        .limit(400)
        .all()
    )
    snapshots = [
        (row.payload or {}).get("_snapshot", {}).get("features", {})
        for row in decisions
    ]
    snapshots = [s for s in snapshots if s]
    drift = {
        "status": "insufficient_data",
        "samples": len(snapshots),
        "required_samples": 100,
    }
    if len(snapshots) >= 100:
        from scipy.stats import ks_2samp

        midpoint = len(snapshots) // 2
        columns = {}
        for name in snapshots[0]:
            current = [r[name] for r in snapshots[:midpoint] if r.get(name) is not None]
            reference = [
                r[name] for r in snapshots[midpoint:] if r.get(name) is not None
            ]
            if len(current) >= 20 and len(reference) >= 20:
                result = ks_2samp(reference, current)
                columns[name] = {
                    "ks": float(result.statistic),
                    "p_value": float(result.pvalue),
                    "drift": bool(result.pvalue < 0.01 and result.statistic > 0.2),
                }
        drift = {
            "status": "evaluated",
            "method": "ks",
            "columns": columns,
            "action": "review_quality_and_performance; no automatic retraining",
        }
        if any(c["drift"] for c in columns.values()):
            alerts.append("feature_drift_review_required")
        try:
            import pandas as pd
            from evidently import Report
            from evidently.presets import DataDriftPreset
        except ImportError:
            drift["evidently"] = "unavailable"
        else:
            evaluation = Report([DataDriftPreset()]).run(
                current_data=pd.DataFrame(snapshots[:midpoint]),
                reference_data=pd.DataFrame(snapshots[midpoint:]),
            )
            drift["evidently"] = evaluation.dict()
    snapshot = {
        "status": "alert" if alerts else "healthy",
        "alerts": alerts,
        "quality": quality,
        "pending_identity_reviews": pending,
        "drift": drift,
        "operations": operations,
        "automatic_retraining": False,
    }
    db.add(
        ModelRun(
            tenant_id=tenant_id,
            task="data_quality",
            status=snapshot["status"],
            report=snapshot,
            feature_version="commercial-v1",
        )
    )
    return {"status": snapshot["status"], "alerts": alerts}
