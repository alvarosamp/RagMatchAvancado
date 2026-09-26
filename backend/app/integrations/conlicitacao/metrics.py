from __future__ import annotations

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
except ImportError:  # pragma: no cover - only supports minimal dev/test environments
    class _NoopMetric:
        def labels(self, *_: object) -> _NoopMetric:
            return self

        def inc(self, *_: object) -> None:
            return None

        def observe(self, *_: object) -> None:
            return None

        def set(self, *_: object) -> None:
            return None

    class CollectorRegistry:  # type: ignore[no-redef]
        pass

    def Counter(*_: object, **__: object) -> _NoopMetric:  # type: ignore[misc]
        return _NoopMetric()

    Gauge = Histogram = Counter  # type: ignore[misc]

    def generate_latest(_: object) -> bytes:
        return b""

REGISTRY = CollectorRegistry()

REQUESTS = Counter(
    "conlicitacao_requests_total",
    "Requests sent to ConLicitacao.",
    ("method", "endpoint", "status"),
    registry=REGISTRY,
)
REQUEST_ERRORS = Counter(
    "conlicitacao_request_errors_total",
    "Failed ConLicitacao requests.",
    ("method", "endpoint", "kind"),
    registry=REGISTRY,
)
REQUEST_LATENCY = Histogram(
    "conlicitacao_request_latency_seconds",
    "ConLicitacao request latency.",
    ("method", "endpoint"),
    registry=REGISTRY,
)
TENDERS_IMPORTED = Counter(
    "tenders_imported_total", "New normalized tenders.", ("provider",), registry=REGISTRY
)
TENDERS_DEDUPLICATED = Counter(
    "tenders_deduplicated_total",
    "Existing normalized tenders updated without duplication.",
    ("provider",),
    registry=REGISTRY,
)
LAST_SYNC_SUCCESS = Gauge(
    "conlicitacao_last_sync_success_timestamp_seconds",
    "Unix timestamp of the last successful tenant sync.",
    ("tenant_id",),
    registry=REGISTRY,
)


def render_metrics() -> bytes:
    return generate_latest(REGISTRY)
