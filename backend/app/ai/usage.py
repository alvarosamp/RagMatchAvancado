"""Tenant-scoped provider telemetry without persisting prompts or responses."""

from __future__ import annotations

import uuid
import time
from contextvars import ContextVar, Token
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Any

from app.logs.config import logger


@dataclass(frozen=True)
class AIUsageContext:
    tenant_slug: str
    operation: str
    correlation_id: str | None = None


_usage_context: ContextVar[AIUsageContext | None] = ContextVar("ai_usage_context", default=None)


def set_ai_usage_context(tenant_slug: str, operation: str, correlation_id: str | None = None) -> Token:
    return _usage_context.set(AIUsageContext(tenant_slug, operation, correlation_id))


def reset_ai_usage_context(token: Token) -> None:
    _usage_context.reset(token)


@contextmanager
def ai_usage_scope(tenant_slug: str, operation: str, correlation_id: str | None = None):
    token = set_ai_usage_context(tenant_slug, operation, correlation_id)
    try:
        yield
    finally:
        reset_ai_usage_context(token)


def track_user_ai_usage(operation: str):
    """Scope a service call to its user's tenant when no job scope exists."""
    def decorate(function):
        @wraps(function)
        def wrapped(db, current_user, *args, **kwargs):
            if _usage_context.get() is not None:
                return function(db, current_user, *args, **kwargs)
            tenant = getattr(current_user, "tenant", None)
            slug = getattr(tenant, "slug", None)
            if not slug:
                return function(db, current_user, *args, **kwargs)
            token = set_ai_usage_context(slug, operation)
            try:
                return function(db, current_user, *args, **kwargs)
            finally:
                reset_ai_usage_context(token)
        return wrapped
    return decorate


def _field(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def extract_token_counts(response: Any, provider: str) -> tuple[int | None, int | None]:
    """Read reported token counts only; never estimate missing values."""
    usage = _field(response, "usage") if provider == "openai" else response
    input_name = "prompt_tokens" if provider == "openai" else "prompt_eval_count"
    output_name = "completion_tokens" if provider == "openai" else "eval_count"
    return _nonnegative_int(_field(usage, input_name)), _nonnegative_int(_field(usage, output_name))


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def record_provider_usage(
    *, provider: str, model: str, response: Any, duration_ms: int,
) -> None:
    """Best-effort independent write so telemetry never breaks inference."""
    context = _usage_context.get()
    if context is None:
        return
    input_tokens, output_tokens = extract_token_counts(response, provider)
    try:
        from app.ai.usage_models import AIUsageEvent
        from app.db.session import SessionLocal

        with SessionLocal() as db:
            db.add(AIUsageEvent(
                id=str(uuid.uuid4()),
                tenant_slug=context.tenant_slug,
                operation=context.operation,
                correlation_id=context.correlation_id,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=max(0, duration_ms),
            ))
            db.commit()
    except Exception:
        logger.warning(
            "[AI Usage] Falha ao registrar consumo | tenant=%s | provider=%s | operation=%s",
            context.tenant_slug, provider, context.operation, exc_info=True,
        )


def measured_provider_call(provider: str, model: str, call):
    """Measure one successful provider call without changing its response."""
    started = time.perf_counter()
    response = call()
    record_provider_usage(
        provider=provider,
        model=model,
        response=response,
        duration_ms=round((time.perf_counter() - started) * 1000),
    )
    return response
