"""Integration tests for the HTTP boundary of the health router."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

_HEALTH_PATH = Path(__file__).resolve().parents[2] / "backend" / "app" / "routers" / "health.py"
_SPEC = importlib.util.spec_from_file_location("health_integration_under_test", _HEALTH_PATH)
health = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader

_db_session_stub = ModuleType("app.db.session")
_db_session_stub.SessionLocal = MagicMock()
_logs_config_stub = ModuleType("app.logs.config")
_logs_config_stub.logger = MagicMock()
with patch.dict(
    sys.modules,
    {
        "app.db.session": _db_session_stub,
        "app.logs.config": _logs_config_stub,
    },
):
    _SPEC.loader.exec_module(health)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(health.router)
    return TestClient(app, raise_server_exceptions=False)


def test_liveness_endpoint_is_available():
    response = _client().get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_checks_database_and_closes_session(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(health, "SessionLocal", MagicMock(return_value=session))
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("AI_FEATURES_ENABLED", "0")

    response = _client().get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    session.execute.assert_called_once()
    session.close.assert_called_once()


def test_readiness_returns_503_when_database_is_unavailable(monkeypatch):
    session = MagicMock()
    session.execute.side_effect = RuntimeError("connection refused")
    monkeypatch.setattr(health, "SessionLocal", MagicMock(return_value=session))
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("AI_FEATURES_ENABLED", "0")

    response = _client().get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Banco de dados indisponivel."}
    session.close.assert_called_once()


def test_readiness_does_not_depend_on_optional_ai(monkeypatch):
    session = MagicMock()
    check_ollama = MagicMock()
    monkeypatch.setattr(health, "SessionLocal", MagicMock(return_value=session))
    monkeypatch.setattr(health, "_check_ollama", check_ollama)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("AI_FEATURES_ENABLED", "true")

    response = _client().get("/health/ready")

    assert response.status_code == 200
    check_ollama.assert_not_called()
