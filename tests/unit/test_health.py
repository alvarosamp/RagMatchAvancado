import sys
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


_HEALTH_PATH = Path(__file__).resolve().parents[2] / "backend" / "app" / "routers" / "health.py"
_SPEC = importlib.util.spec_from_file_location("health_under_test", _HEALTH_PATH)
health = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(health)


def _ollama_with_models(*models: str):
    return SimpleNamespace(
        Client=lambda **_: SimpleNamespace(
            list=lambda: SimpleNamespace(models=[SimpleNamespace(model=model) for model in models])
        )
    )


def test_ollama_readiness_accepts_required_models(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "ollama",
        _ollama_with_models("llama3.2:1b", "nomic-embed-text"),
    )

    health._check_ollama()


def test_ollama_readiness_rejects_missing_model(monkeypatch):
    monkeypatch.setitem(sys.modules, "ollama", _ollama_with_models("llama3.2:1b"))

    with pytest.raises(HTTPException) as error:
        health._check_ollama()

    assert error.value.status_code == 503
