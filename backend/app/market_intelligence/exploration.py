from collections import defaultdict

from .models import Entity, Fact
from .repository import scoped


def explore_task(db, tenant_id, task):
    if task == "catalog_clusters":
        from sklearn.cluster import MiniBatchKMeans
        from sklearn.feature_extraction.text import TfidfVectorizer

        records = (
            scoped(db, Entity, tenant_id).filter_by(kind="product", active=True).all()
        )
        if len(records) < 10:
            return {
                "status": "insufficient_data",
                "required_products": 10,
                "products": len(records),
            }
        texts = [
            f"{r.brand or ''} {r.category or ''} {r.name} {(r.attributes or {}).get('specification') or ''}"
            for r in records
        ]
        matrix = TfidfVectorizer(ngram_range=(1, 2), max_features=5000).fit_transform(
            texts
        )
        labels = MiniBatchKMeans(
            n_clusters=min(8, max(2, len(records) // 5)), random_state=42, n_init=3
        ).fit_predict(matrix)
        groups = defaultdict(list)
        for record, label in zip(records, labels):
            groups[int(label)].append({"id": record.id, "name": record.name})
        return {
            "status": "exploratory",
            "method": "tfidf_kmeans",
            "clusters": dict(groups),
            "decision": "human_review_required; similarity does not imply technical equivalence",
        }
    from .metrics import benchmarks
    from .service import as_dict

    prices = [
        as_dict(r)
        for r in scoped(db, Fact, tenant_id).filter_by(kind="price", active=True).all()
    ]
    groups, _ = benchmarks(prices, min_sample=10)
    alerts = []
    for benchmark in groups:
        if not benchmark["sufficient"]:
            continue
        spread = benchmark["p75"] - benchmark["p25"]
        lower, upper = benchmark["p25"] - 1.5 * spread, benchmark["p75"] + 1.5 * spread
        for row in prices:
            if (
                all(
                    row.get(key) == benchmark.get(key)
                    for key in ["product_id", "unit", "currency", "state", "price_type"]
                )
                and row.get("unit_price") is not None
                and not lower <= float(row["unit_price"]) <= upper
            ):
                alerts.append(
                    {
                        "id": row["id"],
                        "unit_price": float(row["unit_price"]),
                        "lower": lower,
                        "upper": upper,
                        "sample": benchmark["sample"],
                    }
                )
    return {
        "status": "exploratory" if groups else "insufficient_data",
        "method": "comparable_price_iqr",
        "alerts": alerts,
        "decision": "review; no automatic pricing change",
    }
