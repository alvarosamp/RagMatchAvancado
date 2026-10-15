"""Human-reviewed technical and identity baselines with grouped temporal tests."""

from collections import Counter

from .domain import timestamp
from .models import Feedback, Review
from .repository import scoped

TECHNICAL_FEATURES = ("lexical_score", "semantic_score", "score", "conflict_count")
VERDICTS = ("ATENDE", "VERIFICAR", "NAO_ATENDE")


def technical_snapshot(match):
    attrs = (match.attributes or {}) if match else {}
    return {
        "lexical_score": attrs.get("lexical_score"),
        "semantic_score": attrs.get("semantic_score"),
        "score": attrs.get("score"),
        "conflict_count": len(attrs.get("conflicts") or []),
    }


def reviewed_dataset(db, tenant_id, task):
    records = []
    if task == "technical_match":
        for row in (
            scoped(db, Feedback, tenant_id)
            .filter_by(action="technical_review")
            .order_by(Feedback.available_at)
        ):
            snapshot = (row.payload or {}).get("_snapshot", {})
            features = snapshot.get("technical")
            verdict = row.payload.get("verdict")
            if features and verdict in VERDICTS and snapshot.get("split_group"):
                records.append(
                    {
                        "item_id": row.item_id,
                        "group": snapshot["split_group"],
                        "decision_at": timestamp(row.available_at),
                        "features": features,
                        "target": verdict,
                    }
                )
    else:
        for row in (
            scoped(db, Review, tenant_id)
            .filter(
                Review.status.in_(["accepted", "rejected"]),
                Review.reason == "similar_name",
            )
            .order_by(Review.reviewed_at)
        ):
            score = (row.evidence or {}).get("score")
            if score is not None and row.reviewed_at:
                records.append(
                    {
                        "item_id": row.id,
                        "group": f"{row.source}:{row.kind}:{row.source_id}",
                        "decision_at": timestamp(row.reviewed_at),
                        "features": {"name_similarity": score},
                        "target": row.status,
                    }
                )
    latest = {}
    for row in records:
        latest[row["item_id"]] = row
    return list(latest.values())


def evaluate_reviews(db, tenant_id, task):
    from .training import temporal_split

    rows = reviewed_dataset(db, tenant_id, task)
    train, test = temporal_split(rows)
    classes = VERDICTS if task == "technical_match" else ("accepted", "rejected")
    reasons = []
    if len(rows) < 100 or len({r["group"] for r in rows}) < 20:
        reasons.append(
            "São necessários 100 rótulos revisados e 20 grupos independentes."
        )
    for name, subset in [("treino", train), ("teste", test)]:
        counts = Counter(r["target"] for r in subset)
        if any(counts[label] < 5 for label in classes):
            reasons.append(f"{name}: pelo menos cinco exemplos de cada classe.")
    report = {
        "status": "insufficient_data",
        "samples": len(rows),
        "reasons": reasons,
        "split": "chronological, source/notice-group disjoint",
        "automatic_matching": False,
    }
    if reasons:
        return rows, report
    import numpy as np
    from sklearn.dummy import DummyClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report, confusion_matrix, f1_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    names = TECHNICAL_FEATURES if task == "technical_match" else ("name_similarity",)

    def matrix(subset):
        return np.array(
            [
                [
                    r["features"].get(name)
                    if r["features"].get(name) is not None
                    else np.nan
                    for name in names
                ]
                for r in subset
            ]
        )

    x_train, x_test = matrix(train), matrix(test)
    y_train, y_test = [r["target"] for r in train], [r["target"] for r in test]
    model = make_pipeline(
        SimpleImputer(strategy="median", keep_empty_features=True),
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42),
    )
    model.fit(x_train, y_train)
    prediction = model.predict(x_test)
    baseline = (
        DummyClassifier(strategy="most_frequent").fit(x_train, y_train).predict(x_test)
    )
    report.update(
        status="evaluated",
        model="logistic_regression",
        features=list(names),
        macro_f1=float(f1_score(y_test, prediction, average="macro")),
        baseline_macro_f1=float(f1_score(y_test, baseline, average="macro")),
        class_metrics=classification_report(
            y_test, prediction, output_dict=True, zero_division=0
        ),
        classes=list(classes),
        confusion_matrix=confusion_matrix(y_test, prediction, labels=classes).tolist(),
        promotion="shadow_only",
        drivers=model[-1].coef_.tolist(),
    )
    report["performance_gate"] = report["macro_f1"] >= report["baseline_macro_f1"]
    if task == "technical_match":
        accepted = prediction == "ATENDE"
        report["false_accept_rate"] = (
            float(np.mean(np.array(y_test)[accepted] != "ATENDE"))
            if accepted.any()
            else None
        )
    return rows, report
