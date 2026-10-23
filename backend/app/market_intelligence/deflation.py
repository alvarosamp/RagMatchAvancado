"""Explicit, index-level deflation. Monthly percentage changes are not levels."""

from .domain import number
from .metrics import benchmarks


def deflated_benchmarks(prices, indices, series, base_month=None):
    levels = {}
    for row in indices:
        attrs = row.get("attributes") or {}
        if f"{attrs.get('table')}:{attrs.get('variable')}" != series:
            continue
        # Operator must choose a published index-level series. Reject rates,
        # unsupported currencies and missing month observations.
        label = str(attrs.get("unit") or "").lower()
        if "ndice" not in label or "%" in label:
            continue
        level = number(row.get("unit_price"), positive=True)
        if level and attrs.get("month"):
            levels[str(attrs["month"])] = level
    base_month = base_month or max(levels, default=None)
    if not base_month or base_month not in levels:
        return {
            "status": "unavailable",
            "series": series,
            "reason": "Índice de nível ou mês-base indisponível.",
            "rows": [],
        }
    adjusted, excluded = [], 0
    for row in prices:
        month = row["event_at"].strftime("%Y%m")
        if (
            row.get("currency") != "BRL"
            or month not in levels
            or not row.get("unit_price")
        ):
            excluded += 1
            continue
        adjusted.append(
            {
                **row,
                "unit_price": row["unit_price"] * levels[base_month] / levels[month],
            }
        )
    rows, unmatched = benchmarks(adjusted)
    return {
        "status": "available",
        "series": series,
        "base_month": base_month,
        "excluded_observations": excluded + unmatched,
        "rows": rows,
        "method": "nominal_price * base_index / event_month_index",
    }
