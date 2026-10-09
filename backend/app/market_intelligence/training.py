"""Commercial baselines with time/group separation and explicit readiness gates."""

import itertools
import math
import os
from collections import defaultdict
from statistics import median
from zoneinfo import ZoneInfo

from .domain import payload_hash, ratio, timestamp
from .models import Fact, Feedback, ModelRun
from .repository import scoped

FEATURES = (
    "quantity",
    "reference_price",
    "cost_to_reference",
    "bid_to_reference",
    "technical_label_present",
)
VERSION = "commercial-v1"
FORECAST_VERSION = "forecast-v2"


def feature_snapshot(demand, offer=None):
    offer = offer or demand
    return {
        "quantity": float(demand.quantity) if demand.quantity is not None else None,
        "reference_price": float(demand.reference_price)
        if demand.reference_price is not None
        else None,
        "cost_to_reference": ratio(offer.cost, offer.reference_price),
        "bid_to_reference": ratio(offer.offered_price, offer.reference_price),
        "technical_label_present": int(
            bool((demand.attributes or {}).get("technical_verdict"))
        ),
    }


def temporal_split(rows):
    """Keep every notice wholly on one side; remove overlapping temporal groups."""
    groups = defaultdict(list)
    for row in rows:
        groups[row["group"]].append(row)
    ordered = sorted(groups, key=lambda key: max(r["decision_at"] for r in groups[key]))
    cutoff = max(1, int(len(ordered) * 0.8))
    test = [r for key in ordered[cutoff:] for r in groups[key]]
    if not test:
        return [], []
    earliest_test = min(r["decision_at"] for r in test)
    train = [
        r
        for key in ordered[:cutoff]
        if max(r["decision_at"] for r in groups[key]) < earliest_test
        for r in groups[key]
    ]
    return train, test


def readiness(rows, min_rows=100, min_groups=20):
    train, test = temporal_split(rows)
    reasons = []
    if len(rows) < min_rows:
        reasons.append(
            f"At least {min_rows} prospective labels required; found {len(rows)}."
        )
    if len({r["group"] for r in rows}) < min_groups:
        reasons.append(f"At least {min_groups} independent notice groups required.")
    for name, split in [("train", train), ("test", test)]:
        labels = [r["target"] for r in split]
        if labels.count(0) < 5 or labels.count(1) < 5:
            reasons.append(f"{name}: at least five labels of each class required.")
    return (
        {
            "ready": not reasons,
            "reasons": reasons,
            "samples": len(rows),
            "train_samples": len(train),
            "test_samples": len(test),
            "split": "chronological, notice-group disjoint",
            "feature_version": VERSION,
        },
        train,
        test,
    )


def commercial_dataset(db, tenant_id, task):
    decisions = (
        scoped(db, Feedback, tenant_id)
        .filter(
            Feedback.action.in_(
                ["supplier_selected"] if task == "supplier_delay" else ["bid", "no_bid"]
            )
        )
        .order_by(Feedback.available_at)
        .all()
    )
    awards = (
        scoped(db, Fact, tenant_id)
        .filter_by(kind="award", source="crm", active=True)
        .all()
    )
    award_map = {
        r.item_id: r for r in awards if r.outcome in {"won", "lost", "disqualified"}
    }
    rows = []
    for feedback in decisions:
        snapshot = (feedback.payload or {}).get("_snapshot")
        if not snapshot or any(
            key not in snapshot.get("features", {}) for key in FEATURES
        ):
            continue
        decision_at = timestamp(feedback.available_at)
        if task == "bid_no_bid":
            target = int(feedback.action == "bid")
        elif task == "win_probability":
            if snapshot.get("result_known", True):
                continue
            award = award_map.get(feedback.item_id)
            if (
                feedback.action != "bid"
                or not award
                or timestamp(award.event_at) <= decision_at
            ):
                continue
            target = int(award.outcome == "won")
        elif task == "supplier_delay":
            from .suppliers import canonical_id

            purchases = (
                scoped(db, Fact, tenant_id)
                .filter_by(
                    kind="purchase",
                    item_id=feedback.item_id,
                    supplier_id=canonical_id(
                        db, tenant_id, feedback.payload.get("supplier_id")
                    ),
                    active=True,
                )
                .all()
            )
            labeled = [
                p
                for p in purchases
                if (p.attributes or {}).get("received_at")
                and (p.attributes or {}).get("promised_at")
                and timestamp(p.attributes["received_at"]) > decision_at
            ]
            if not labeled:
                continue
            target = int(
                any(
                    timestamp(p.attributes["received_at"])
                    > timestamp(p.attributes["promised_at"])
                    for p in labeled
                )
            )
        else:
            continue
        rows.append(
            {
                "item_id": feedback.item_id,
                "group": snapshot["split_group"],
                "decision_at": decision_at,
                "features": snapshot["features"],
                "target": target,
            }
        )
    # Repeated decisions on the same item cannot inflate labels.
    by_item = {}
    for row in rows:
        by_item[row["item_id"]] = row
    return list(by_item.values())


def forecast_report(rows, kind):
    series = defaultdict(list)
    for row in rows:
        if kind == "price_forecast" and (
            row.price_type != "winning_price"
            or row.unit_price is None
            or not row.product_id
            or not row.unit
        ):
            continue
        if kind == "demand_forecast" and row.kind != "demand":
            continue
        key = (
            f"{row.product_id}:{row.unit}:{row.currency}:{row.state}"
            if kind == "price_forecast"
            else f"{row.source}:{row.category or 'unknown'}"
        )
        series[key].append(row)
    forecasts = []
    for key, records in series.items():
        context = {
            "series": key,
            "source": records[0].source if kind == "demand_forecast" else None,
            "category": records[0].category if kind == "demand_forecast" else None,
            "product_id": records[0].product_id if kind == "price_forecast" else None,
            "measurement_unit": records[0].unit
            if kind == "price_forecast"
            else "items",
            "currency": records[0].currency if kind == "price_forecast" else None,
            "state": records[0].state if kind == "price_forecast" else None,
        }
        monthly = defaultdict(list)
        for row in records:
            monthly[
                timestamp(row.event_at)
                .astimezone(ZoneInfo("America/Sao_Paulo"))
                .strftime("%Y-%m")
            ].append(float(row.unit_price) if kind == "price_forecast" else 1.0)
        months = sorted(monthly)
        values = [
            sum(monthly[m]) if kind == "demand_forecast" else median(monthly[m])
            for m in months
        ]
        if len(values) < 24:
            forecasts.append(
                {
                    **context,
                    "status": "insufficient_data",
                    "months": len(values),
                    "required_months": 24,
                }
            )
            continue
        # Missing months are unknown coverage, not observed zero demand.
        ordinals = [int(m[:4]) * 12 + int(m[5:]) for m in months]
        if any(b - a != 1 for a, b in itertools.pairwise(ordinals)):
            forecasts.append({**context, "status": "incomplete_month_coverage"})
            continue
        errors = [
            abs(values[i] - values[i - 12]) for i in range(len(values) - 6, len(values))
        ]
        naive_errors = [
            abs(values[i] - values[i - 1]) for i in range(len(values) - 6, len(values))
        ]
        predictors = {
            "naive": lambda i, data=values: data[i - 1],
            "moving_median_3": lambda i, data=values: median(data[i - 3 : i]),
            "seasonal_naive": lambda i, data=values: data[i - 12],
        }
        holdout = range(len(values) - 6, len(values))
        scores = {
            name: sum(abs(values[i] - predict(i)) for i in holdout) / 6
            for name, predict in predictors.items()
        }
        method = min(scores, key=scores.get)
        point = predictors[method](len(values))
        calibration = sorted(
            abs(values[i] - predictors[method](i)) for i in range(12, len(values) - 6)
        )
        interval = None
        if len(calibration) >= 12:
            # Empirical historical error range, not guaranteed coverage under
            # serial dependence or late revisions. Holdout stays out of calibration.
            radius = calibration[math.ceil((len(calibration) + 1) * 0.9) - 1]
            interval = {
                "lower": max(0, point - radius),
                "upper": point + radius,
                "nominal_coverage": 0.9,
                "calibration_months": len(calibration),
                "method": "historical_absolute_error_quantile",
                "holdout_coverage": sum(
                    abs(values[i] - predictors[method](i)) <= radius for i in holdout
                )
                / 6,
                "coverage_guaranteed": False,
            }
        last = ordinals[-1]
        forecasts.append(
            {
                **context,
                "status": "baseline",
                "next_month": point,
                "forecast_month": f"{last // 12:04d}-{last % 12 + 1:02d}",
                "seasonal_mae": sum(errors) / len(errors),
                "naive_mae": sum(naive_errors) / len(naive_errors),
                "moving_median_mae": scores["moving_median_3"],
                "selected_mae": scores[method],
                "method": method,
                "last_month": months[-1],
                "backtest": "last six observed months; retrospective latest-source revisions",
                "interval": interval,
                "interval_status": "available"
                if interval
                else "insufficient_calibration_history",
                "interval_required_calibration_months": 12,
                "historical_months": len(values),
                "unit": "items" if kind == "demand_forecast" else records[0].currency,
            }
        )
    return {
        "status": "baseline"
        if any(r["status"] == "baseline" for r in forecasts)
        else "insufficient_data",
        "series": forecasts,
    }


def train_task(db, tenant_id, task):
    rows = []
    dataset_version = None
    record_count = None
    if task in {"technical_match", "entity_resolution"}:
        from .review_models import evaluate_reviews

        rows, report = evaluate_reviews(db, tenant_id, task)
    elif task in {"demand_forecast", "price_forecast"}:
        records = (
            scoped(db, Fact, tenant_id)
            .filter(
                Fact.active.is_(True),
                Fact.kind == ("demand" if task == "demand_forecast" else "price"),
            )
            .all()
        )
        report = forecast_report(records, task)
        if task == "price_forecast":
            from .models import Entity

            names = dict(
                scoped(db, Entity, tenant_id)
                .filter_by(kind="product")
                .with_entities(Entity.id, Entity.name)
                .all()
            )
            for series in report["series"]:
                series["product_name"] = names.get(series.get("product_id"))
        record_count = len(records)
        dataset_version = payload_hash(
            [
                {
                    "id": row.id,
                    "source": row.source,
                    "kind": row.kind,
                    "event_at": timestamp(row.event_at).isoformat(),
                    "available_at": timestamp(row.available_at).isoformat(),
                    "unit_price": str(row.unit_price),
                    "product": row.product_id,
                    "category": row.category,
                    "unit": row.unit,
                    "currency": row.currency,
                    "state": row.state,
                    "price_type": row.price_type,
                }
                for row in sorted(records, key=lambda row: row.id)
            ]
        )
    elif task in {"catalog_clusters", "price_anomaly"}:
        from .exploration import explore_task

        report = explore_task(db, tenant_id, task)
    else:
        rows = commercial_dataset(db, tenant_id, task)
        report, train, test = readiness(rows)
        report["status"] = "insufficient_data" if not report["ready"] else "evaluated"
        if report["ready"]:
            import numpy as np
            from sklearn.impute import SimpleImputer
            from sklearn.linear_model import LogisticRegression
            from sklearn.metrics import (
                average_precision_score,
                brier_score_loss,
                log_loss,
                roc_auc_score,
            )
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import StandardScaler

            def matrix(data):
                return np.array(
                    [
                        [
                            r["features"].get(f)
                            if r["features"].get(f) is not None
                            else np.nan
                            for f in FEATURES
                        ]
                        for r in data
                    ],
                    dtype=float,
                )

            x_train, x_test = matrix(train), matrix(test)
            y_train, y_test = (
                np.array([r["target"] for r in train]),
                np.array([r["target"] for r in test]),
            )
            model = Pipeline(
                [
                    (
                        "impute",
                        SimpleImputer(strategy="median", keep_empty_features=True),
                    ),
                    ("scale", StandardScaler()),
                    ("model", LogisticRegression(max_iter=2000, random_state=42)),
                ]
            )
            model.fit(x_train, y_train)
            predicted = model.predict_proba(x_test)[:, 1]
            prior = np.full(len(y_test), float(y_train.mean()))

            def metrics(values):
                return {
                    "pr_auc": float(average_precision_score(y_test, values)),
                    "roc_auc": float(roc_auc_score(y_test, values)),
                    "brier": float(brier_score_loss(y_test, values)),
                    "log_loss": float(log_loss(y_test, values)),
                }

            report.update(
                metrics=metrics(predicted),
                baseline=metrics(prior),
                coefficients={
                    f: float(c) for f, c in zip(FEATURES, model["model"].coef_[0])
                },
                calibration_bins=[
                    {
                        "low": low,
                        "high": low + 0.2,
                        "samples": int(
                            ((predicted >= low) & (predicted < low + 0.2)).sum()
                        ),
                        "observed_rate": float(
                            y_test[(predicted >= low) & (predicted < low + 0.2)].mean()
                        )
                        if ((predicted >= low) & (predicted < low + 0.2)).any()
                        else None,
                    }
                    for low in [0, 0.2, 0.4, 0.6, 0.8]
                ],
                promotion="shadow_only; explicit performance gate required",
            )
            report["serving_parameters"] = {
                "features": list(FEATURES),
                "medians": [
                    float(v) if math.isfinite(v) else 0.0
                    for v in model["impute"].statistics_
                ],
                "means": model["scale"].mean_.tolist(),
                "scales": model["scale"].scale_.tolist(),
                "weights": model["model"].coef_[0].tolist(),
                "intercept": float(model["model"].intercept_[0]),
            }
            report["performance_gate"] = (
                report["metrics"]["brier"] <= report["baseline"]["brier"]
                and report["metrics"]["pr_auc"] >= report["baseline"]["pr_auc"]
            )
            # Evaluate a nonlinear challenger on exactly the same holdout. It
            # does not replace the explainable baseline without a separate gate.
            try:
                from xgboost import XGBClassifier
            except ImportError:
                report["challenger"] = {"status": "dependency_unavailable"}
            else:
                challenger = XGBClassifier(
                    n_estimators=100,
                    max_depth=3,
                    learning_rate=0.05,
                    random_state=42,
                    n_jobs=1,
                    eval_metric="logloss",
                )
                challenger.fit(x_train, y_train)
                report["challenger"] = {
                    "status": "evaluated",
                    "model": "xgboost",
                    "metrics": metrics(challenger.predict_proba(x_test)[:, 1]),
                }
            if os.getenv("MLFLOW_TRACKING_URI"):
                import mlflow.sklearn

                import mlflow

                mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
                mlflow.set_experiment(f"market-intelligence-tenant-{tenant_id}")
                with mlflow.start_run() as run:
                    mlflow.log_params(
                        {
                            "tenant_id": tenant_id,
                            "task": task,
                            "feature_version": VERSION,
                            "git_sha": os.getenv("GIT_SHA", "unknown"),
                            "split": report["split"],
                        }
                    )
                    mlflow.log_metrics(report["metrics"])
                    info = mlflow.sklearn.log_model(model, artifact_path="model")
                    report["model_uri"], report["mlflow_run_id"] = (
                        info.model_uri,
                        run.info.run_id,
                    )
                    # Logging is not automatic model promotion.
    dataset_version = dataset_version or (
        payload_hash([{**r, "decision_at": r["decision_at"].isoformat()} for r in rows])
        if rows
        else None
    )
    report["artifact"] = {
        "git_sha": os.getenv("GIT_SHA", "unknown"),
        "dataset_version": dataset_version,
        "feature_version": FORECAST_VERSION
        if task in {"demand_forecast", "price_forecast"}
        else VERSION,
        "mode": "shadow; human decision required",
    }
    db.add(
        ModelRun(
            tenant_id=tenant_id,
            task=task,
            status=report["status"],
            report=report,
            model_uri=report.get("model_uri"),
            dataset_version=dataset_version,
            feature_version=FORECAST_VERSION
            if task in {"demand_forecast", "price_forecast"}
            else VERSION,
        )
    )
    return {
        "task": task,
        "status": report["status"],
        "samples": record_count if record_count is not None else len(rows),
    }


def predict_snapshot(snapshot, parameters):
    drivers = []
    score = parameters["intercept"]
    for i, feature in enumerate(parameters["features"]):
        value = snapshot.get(feature)
        value = parameters["medians"][i] if value is None else float(value)
        contribution = (
            (value - parameters["means"][i])
            / parameters["scales"][i]
            * parameters["weights"][i]
        )
        score += contribution
        drivers.append(
            {"feature": feature, "value": value, "contribution": contribution}
        )
    probability = 1 / (1 + math.exp(-max(-700, min(700, score))))
    return {
        "probability": probability,
        "drivers": sorted(drivers, key=lambda r: abs(r["contribution"]), reverse=True),
        "mode": "shadow",
        "decision": "human",
    }
