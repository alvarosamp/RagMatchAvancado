"""Presentation of aggregated, tenant-scoped AI provider usage."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable


def build_ai_usage_summary(rows: Iterable[Any], start: datetime, end: datetime) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    for row in rows:
        groups.append({
            "provider": row.provider,
            "model": row.model,
            "operation": row.operation,
            "calls": int(row.calls or 0),
            "input_tokens_reported": int(row.input_tokens or 0),
            "output_tokens_reported": int(row.output_tokens or 0),
            "calls_without_token_counts": int(row.calls_without_token_counts or 0),
            "total_duration_ms": int(row.total_duration_ms or 0),
        })
    groups.sort(key=lambda item: (-item["calls"], item["provider"], item["model"], item["operation"]))
    return {
        "period_start_utc": start.isoformat().replace("+00:00", "Z") if start.tzinfo else start.isoformat() + "Z",
        "resets_at_utc": end.isoformat().replace("+00:00", "Z") if end.tzinfo else end.isoformat() + "Z",
        "total_calls": sum(item["calls"] for item in groups),
        "input_tokens_reported": sum(item["input_tokens_reported"] for item in groups),
        "output_tokens_reported": sum(item["output_tokens_reported"] for item in groups),
        "calls_without_token_counts": sum(item["calls_without_token_counts"] for item in groups),
        "groups": groups,
        "cost_available": False,
    }
