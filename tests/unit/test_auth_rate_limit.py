"""Tests for Redis-backed limits on public authentication endpoints."""

import sys
from types import ModuleType
from unittest.mock import MagicMock

from app.services import rate_limit


def _redis_module(client):
    module = ModuleType("redis")
    redis_class = MagicMock()
    redis_class.from_url.return_value = client
    module.Redis = redis_class
    return module


def test_rate_limit_uses_hashed_identity_and_atomic_expiry(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example/0")
    client = MagicMock()
    client.eval.return_value = 6
    monkeypatch.setitem(sys.modules, "redis", _redis_module(client))

    assert rate_limit.rate_limit_exceeded(
        "login-account", "Person@Example.com", limit=5, window_seconds=900
    ) is True

    args = client.eval.call_args.args
    assert args[1] == 1
    assert args[3] == 900
    assert "person@example.com" not in args[2]


def test_successful_login_counter_can_be_cleared(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example/0")
    client = MagicMock()
    monkeypatch.setitem(sys.modules, "redis", _redis_module(client))

    rate_limit.reset_rate_limit("login-account", "person@example.com")

    client.delete.assert_called_once()
