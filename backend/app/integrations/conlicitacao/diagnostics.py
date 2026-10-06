from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.integrations.conlicitacao.client import ConlicitacaoClient
from app.integrations.conlicitacao.exceptions import ConlicitacaoError

AsyncCall = Callable[[], Awaitable[Any]]


def describe_shape(value: Any, *, depth: int = 0) -> Any:
    """Describe a provider payload without returning any of its values."""
    if depth >= 5:
        return type(value).__name__
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return {
            "type": "array",
            "count": len(value),
            "items": describe_shape(value[0], depth=depth + 1) if value else "unknown",
        }
    if isinstance(value, dict):
        return {
            "type": "object",
            "fields": {
                str(key): describe_shape(item, depth=depth + 1)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            },
        }
    return type(value).__name__


async def _probe(name: str, call: AsyncCall) -> tuple[dict[str, Any], Any | None]:
    started = time.perf_counter()
    try:
        result = await call()
        if hasattr(result, "model_dump"):
            result = result.model_dump(mode="json")
        return (
            {
                "endpoint": name,
                "ok": True,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "shape": describe_shape(result),
            },
            result,
        )
    except ConlicitacaoError as exc:
        return (
            {
                "endpoint": name,
                "ok": False,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "error": str(exc),
            },
            None,
        )


def _first_integer(payload: Any, keys: tuple[str, ...]) -> int | None:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
        for value in payload.values():
            found = _first_integer(value, keys)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _first_integer(value, keys)
            if found is not None:
                return found
    return None


def _first_integer_in(
    payload: Any, collection: str, keys: tuple[str, ...]
) -> int | None:
    if not isinstance(payload, dict):
        return None
    return _first_integer(payload.get(collection), keys)


def _add_counts(result: dict[str, Any], payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    counts: dict[str, int] = {}
    for key, value in payload.items():
        if isinstance(value, list):
            counts[str(key)] = len(value)
    if counts:
        result["counts"] = counts


async def run_readonly_diagnostics(
    client: ConlicitacaoClient,
    *,
    filter_id: int | None = None,
    bulletin_id: int | None = None,
) -> dict[str, Any]:
    """Exercise every read-only provider endpoint and return value-free metadata."""
    correlation_id = str(uuid.uuid4())
    results: list[dict[str, Any]] = []

    filters_result, filters = await _probe(
        "GET /api/filtros",
        lambda: client.get_filters(correlation_id=correlation_id),
    )
    _add_counts(filters_result, filters)
    results.append(filters_result)

    selected_filter_id = filter_id or _first_integer_in(filters, "filtros", ("id",))
    bulletins = None
    if selected_filter_id is not None:
        bulletins_result, bulletins = await _probe(
            "GET /api/filtro/{filter_id}/boletins",
            lambda: client.list_bulletins(
                selected_filter_id,
                page=1,
                per_page=5,
                correlation_id=correlation_id,
            ),
        )
        _add_counts(bulletins_result, bulletins)
        results.append(bulletins_result)
    else:
        results.append(
            {
                "endpoint": "GET /api/filtro/{filter_id}/boletins",
                "ok": None,
                "skipped": "Nenhum filtro foi retornado e nenhum filter_id foi informado.",
            }
        )

    selected_bulletin_id = bulletin_id or _first_integer_in(
        bulletins, "boletins", ("id",)
    )
    if selected_bulletin_id is not None:
        bulletin_result, bulletin = await _probe(
            "GET /api/boletim/{bulletin_id}",
            lambda: client.get_bulletin(
                selected_bulletin_id, correlation_id=correlation_id
            ),
        )
        _add_counts(bulletin_result, bulletin)
        results.append(bulletin_result)
    else:
        results.append(
            {
                "endpoint": "GET /api/boletim/{bulletin_id}",
                "ok": None,
                "skipped": "Nenhum boletim foi retornado e nenhum bulletin_id foi informado.",
            }
        )

    monitored_result, monitored = await _probe(
        "GET /api/monitored_biddings",
        lambda: client.get_monitored_biddings(
            page=1, per_page=5, correlation_id=correlation_id
        ),
    )
    _add_counts(monitored_result, monitored)
    results.append(monitored_result)

    bidding_id = _first_integer(monitored, ("bidding_id", "licitacao_id", "id"))
    if bidding_id is not None:
        messages_result, messages = await _probe(
            "GET /api/monitored_biddings/messages",
            lambda: client.get_messages(
                bidding_id, page=1, per_page=5, correlation_id=correlation_id
            ),
        )
        _add_counts(messages_result, messages)
        results.append(messages_result)
    else:
        results.append(
            {
                "endpoint": "GET /api/monitored_biddings/messages",
                "ok": None,
                "skipped": "Nenhuma licitação acompanhada foi encontrada para consultar mensagens.",
            }
        )

    users_result, users = await _probe(
        "GET /api/users",
        lambda: client.get_users(correlation_id=correlation_id),
    )
    _add_counts(users_result, users)
    results.append(users_result)

    completed = sum(item.get("ok") is True for item in results)
    failed = sum(item.get("ok") is False for item in results)
    skipped = sum(item.get("ok") is None for item in results)
    return {
        "provider": "conlicitacao",
        "mode": "read_only",
        "generated_at": datetime.now(UTC).isoformat(),
        "correlation_id": correlation_id,
        "summary": {
            "total": len(results),
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
        },
        "results": results,
        "privacy": "Valores não são incluídos; somente tipos, campos, contagens e latência.",
    }
