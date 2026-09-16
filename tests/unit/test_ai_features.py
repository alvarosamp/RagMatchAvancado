from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import features


def tenant(overrides=None):
    return SimpleNamespace(ai_features=overrides)


def test_global_switch_blocks_provider_features(monkeypatch):
    monkeypatch.setattr(features, "AI_FEATURES_ENABLED", False)
    state = features.effective_ai_features(tenant({"edital_chat": True}))
    assert state["edital_chat"] == {
        "enabled": False,
        "configured": True,
        "source": "tenant",
        "reason": "global_disabled",
    }


def test_tenant_can_disable_one_feature_without_affecting_others(monkeypatch):
    monkeypatch.setattr(features, "AI_FEATURES_ENABLED", True)
    company = tenant({"edital_chat": False})
    assert features.ai_feature_enabled("edital_chat", company) is False
    assert features.ai_feature_enabled("matching", company) is True


def test_crm_matching_keeps_deterministic_fallback_when_ai_is_off(monkeypatch):
    monkeypatch.setattr(features, "AI_FEATURES_ENABLED", False)
    assert features.ai_feature_enabled("crm_matching", tenant()) is True
    assert features.ai_feature_enabled("crm_embeddings", tenant()) is False
    assert features.ai_feature_enabled("crm_llm_rerank", tenant()) is False


def test_update_can_set_and_clear_an_override():
    company = tenant({"matching": False})
    features.update_tenant_ai_features(company, {"edital_chat": False, "matching": None})
    assert company.ai_features == {"edital_chat": False}


def test_unknown_feature_is_rejected():
    with pytest.raises(ValueError, match="desconhecidas"):
        features.update_tenant_ai_features(tenant(), {"unknown": True})


def test_require_feature_returns_service_unavailable(monkeypatch):
    monkeypatch.setattr(features, "AI_FEATURES_ENABLED", True)
    with pytest.raises(HTTPException) as exc_info:
        features.require_ai_enabled("datasheet_extraction", tenant({"datasheet_extraction": False}))
    assert exc_info.value.status_code == 503
