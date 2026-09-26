from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from app.integrations.conlicitacao.client import (
    ConlicitacaoClient,
    ConlicitacaoSettings,
)
from app.integrations.conlicitacao.exceptions import (
    ConlicitacaoAuthenticationError,
    ConlicitacaoRateLimitError,
)
from pydantic import SecretStr

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "conlicitacao"


def _settings(**changes) -> ConlicitacaoSettings:
    values = {
        "enabled": True,
        "base_url": "https://provider.example.test",
        "token": SecretStr("top-secret-token"),
        "timeout_seconds": 2,
        "max_attempts": 3,
        "backoff_base_seconds": 0,
    }
    values.update(changes)
    return ConlicitacaoSettings(**values)


@pytest.mark.asyncio
async def test_filters_use_auth_and_correlation_headers(caplog):
    payload = json.loads((FIXTURES / "filters.json").read_text(encoding="utf-8"))
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.headers)
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = ConlicitacaoClient(_settings(), client=http_client)
        result = await client.get_filters(correlation_id="corr-123")

    assert result.filtros[0].id == 115425
    assert captured["x-auth-token"] == "top-secret-token"
    assert captured["x-correlation-id"] == "corr-123"
    assert "top-secret-token" not in caplog.text


@pytest.mark.asyncio
async def test_rate_limit_retries_with_retry_after():
    attempts = 0
    delays = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"message": "wait"})
        return httpx.Response(200, json={"users": []})

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = ConlicitacaoClient(_settings(), client=http_client, sleep=fake_sleep)
        assert await client.get_users() == {"users": []}

    assert attempts == 3
    assert delays == [0.0, 0.0]


@pytest.mark.asyncio
async def test_authentication_error_is_not_retried():
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(403, json={"message": "forbidden"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = ConlicitacaoClient(_settings(), client=http_client)
        with pytest.raises(ConlicitacaoAuthenticationError):
            await client.get_users()

    assert attempts == 1


@pytest.mark.asyncio
async def test_rate_limit_raises_after_bounded_attempts():
    transport = httpx.MockTransport(
        lambda _: httpx.Response(429, headers={"Retry-After": "0"}, json={})
    )

    async def no_sleep(_: float) -> None:
        return None

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = ConlicitacaoClient(
            _settings(max_attempts=2), client=http_client, sleep=no_sleep
        )
        with pytest.raises(ConlicitacaoRateLimitError):
            await client.get_users()


@pytest.mark.asyncio
async def test_server_error_retries_and_recovers():
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503 if attempts == 1 else 200, json={"users": []})

    async def no_sleep(_: float) -> None:
        return None

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = ConlicitacaoClient(_settings(), client=http_client, sleep=no_sleep)
        assert await client.get_users() == {"users": []}

    assert attempts == 2
