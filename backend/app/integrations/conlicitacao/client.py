from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Self

import httpx
from pydantic import SecretStr

from app.core.config import settings as app_settings
from app.integrations.conlicitacao import metrics
from app.integrations.conlicitacao.exceptions import (
    ConlicitacaoAPIError,
    ConlicitacaoAuthenticationError,
    ConlicitacaoConfigurationError,
    ConlicitacaoRateLimitError,
    ConlicitacaoResponseError,
)
from app.integrations.conlicitacao.schemas import (
    ConlicitacaoBulletin,
    ConlicitacaoBulletinsResponse,
    ConlicitacaoFiltersResponse,
)
from app.logs.config import logger


@dataclass(frozen=True)
class ConlicitacaoSettings:
    enabled: bool = False
    base_url: str = "https://consultaonline.conlicitacao.com.br"
    token: SecretStr | None = None
    timeout_seconds: float = 15.0
    max_attempts: int = 3
    backoff_base_seconds: float = 0.5

    @classmethod
    def from_app_settings(cls) -> ConlicitacaoSettings:
        return cls(
            enabled=app_settings.conlicitacao_enabled,
            base_url=app_settings.conlicitacao_base_url.rstrip("/"),
            token=app_settings.conlicitacao_token,
            timeout_seconds=app_settings.conlicitacao_timeout_seconds,
        )


class ConlicitacaoClient:
    """Async API client with bounded retries and credential-safe logs."""

    def __init__(
        self,
        settings: ConlicitacaoSettings | None = None,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.settings = settings or ConlicitacaoSettings.from_app_settings()
        self._client = client or httpx.AsyncClient(
            timeout=self.settings.timeout_seconds,
            follow_redirects=False,
        )
        self._owns_client = client is None
        self._sleep = sleep

    @property
    def configured(self) -> bool:
        return self.settings.enabled and bool(self.settings.token)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_filters(self, *, correlation_id: str | None = None) -> ConlicitacaoFiltersResponse:
        body = await self._request("GET", "/api/filtros", "filters", correlation_id=correlation_id)
        return self._validate(ConlicitacaoFiltersResponse, body)

    async def list_bulletins(
        self,
        filter_id: int,
        *,
        page: int = 1,
        per_page: int = 100,
        order: str = "desc",
        correlation_id: str | None = None,
    ) -> ConlicitacaoBulletinsResponse:
        body = await self._request(
            "GET",
            f"/api/filtro/{filter_id}/boletins",
            "filter_bulletins",
            params={"page": page, "per_page": per_page, "order": order},
            correlation_id=correlation_id,
        )
        return self._validate(ConlicitacaoBulletinsResponse, body)

    async def get_bulletin(
        self, bulletin_id: int, *, correlation_id: str | None = None
    ) -> ConlicitacaoBulletin:
        body = await self._request(
            "GET", f"/api/boletim/{bulletin_id}", "bulletin", correlation_id=correlation_id
        )
        return self._validate(ConlicitacaoBulletin, body)

    async def get_monitored_biddings(
        self, *, page: int = 1, per_page: int = 15, correlation_id: str | None = None
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/api/monitored_biddings",
            "monitored_biddings",
            params={"page": page, "per_page": per_page},
            correlation_id=correlation_id,
        )

    async def get_messages(
        self,
        bidding_id: int,
        *,
        page: int = 1,
        per_page: int = 100,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/api/monitored_biddings/messages",
            "monitored_bidding_messages",
            params={"bidding_id": bidding_id, "page": page, "per_page": per_page},
            correlation_id=correlation_id,
        )

    async def get_users(self, *, correlation_id: str | None = None) -> dict[str, Any]:
        return await self._request("GET", "/api/users", "users", correlation_id=correlation_id)

    async def start_monitoring(
        self, bidding_id: int, user_id: int, *, correlation_id: str | None = None
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/monitored_biddings/add",
            "monitoring_add",
            json={"bidding_id": bidding_id, "user_id": user_id},
            correlation_id=correlation_id,
        )

    async def stop_monitoring(
        self, bidding_id: int, user_id: int, *, correlation_id: str | None = None
    ) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            f"/api/monitored_biddings/{bidding_id}",
            "monitoring_delete",
            params={"user_id": user_id},
            correlation_id=correlation_id,
        )

    async def _request(
        self,
        method: str,
        path: str,
        endpoint: str,
        *,
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not self.settings.enabled:
            raise ConlicitacaoConfigurationError("Integração ConLicitação desabilitada.")
        if not self.settings.token:
            raise ConlicitacaoConfigurationError("CONLICITACAO_TOKEN não configurado.")

        correlation_id = correlation_id or str(uuid.uuid4())
        headers = dict(kwargs.pop("headers", {}))
        headers.update(
            {
                "Accept": "application/json",
                "x-auth-token": self.settings.token.get_secret_value(),
                "X-Correlation-ID": correlation_id,
            }
        )
        url = f"{self.settings.base_url.rstrip('/')}{path}"
        response: httpx.Response | None = None

        for attempt in range(1, max(1, self.settings.max_attempts) + 1):
            started = time.perf_counter()
            try:
                response = await self._client.request(
                    method,
                    url,
                    headers=headers,
                    timeout=self.settings.timeout_seconds,
                    **kwargs,
                )
            except httpx.RequestError as exc:
                metrics.REQUEST_ERRORS.labels(method, endpoint, "network").inc()
                self._log("request_error", correlation_id, endpoint, attempt=attempt, kind="network")
                if attempt >= self.settings.max_attempts:
                    raise ConlicitacaoAPIError(
                        502, "Não foi possível conectar à API ConLicitação."
                    ) from exc
                await self._sleep(self._backoff(attempt))
                continue
            finally:
                metrics.REQUEST_LATENCY.labels(method, endpoint).observe(
                    time.perf_counter() - started
                )

            status = response.status_code
            metrics.REQUESTS.labels(method, endpoint, str(status)).inc()
            if 200 <= status < 300:
                self._log("request_ok", correlation_id, endpoint, status=status, attempt=attempt)
                return self._decode(response)

            if status in (401, 403):
                metrics.REQUEST_ERRORS.labels(method, endpoint, "authentication").inc()
                self._log("request_error", correlation_id, endpoint, status=status, kind="authentication")
                raise ConlicitacaoAuthenticationError(
                    status, "A ConLicitação rejeitou o token ou o IP de origem."
                )

            retryable = status == 429 or status >= 500
            kind = "rate_limit" if status == 429 else "server" if status >= 500 else "client"
            metrics.REQUEST_ERRORS.labels(method, endpoint, kind).inc()
            self._log("request_error", correlation_id, endpoint, status=status, attempt=attempt, kind=kind)
            if retryable and attempt < self.settings.max_attempts:
                await self._sleep(self._retry_delay(response, attempt))
                continue
            if status == 429:
                raise ConlicitacaoRateLimitError(
                    status, "Limite de requisições da ConLicitação atingido."
                )
            raise ConlicitacaoAPIError(status, "A API ConLicitação rejeitou a operação.")

        raise ConlicitacaoAPIError(502, "Falha inesperada ao consultar a ConLicitação.")

    @staticmethod
    def _validate(model: Any, body: dict[str, Any]) -> Any:
        try:
            return model.model_validate(body)
        except Exception as exc:
            raise ConlicitacaoResponseError(
                502, "A ConLicitação retornou dados fora do contrato esperado."
            ) from exc

    @staticmethod
    def _decode(response: httpx.Response) -> dict[str, Any]:
        if response.status_code == 204:
            return {}
        try:
            body = response.json()
        except ValueError as exc:
            raise ConlicitacaoResponseError(
                502, "A ConLicitação retornou JSON inválido."
            ) from exc
        if not isinstance(body, dict):
            raise ConlicitacaoResponseError(
                502, "A ConLicitação retornou uma resposta inválida."
            )
        return body

    def _backoff(self, attempt: int) -> float:
        return min(8.0, self.settings.backoff_base_seconds * (2 ** max(0, attempt - 1)))

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(60.0, max(0.0, float(retry_after)))
            except ValueError:
                try:
                    parsed = parsedate_to_datetime(retry_after)
                    return min(60.0, max(0.0, parsed.timestamp() - time.time()))
                except (TypeError, ValueError, OverflowError):
                    pass
        return self._backoff(attempt)

    @staticmethod
    def _log(event: str, correlation_id: str, endpoint: str, **fields: Any) -> None:
        # Deliberately log only the stable endpoint label, never URL/query/token.
        payload = {
            "event": event,
            "provider": "conlicitacao",
            "correlation_id": correlation_id,
            "endpoint": endpoint,
            **fields,
        }
        logger.info("%s", json.dumps(payload, ensure_ascii=False, default=str))
