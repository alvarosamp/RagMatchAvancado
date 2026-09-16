from __future__ import annotations

import os
from typing import Any

from fastapi import HTTPException, status


def _env_enabled(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "sim", "on"}


AI_FEATURES_ENABLED = _env_enabled("AI_FEATURES_ENABLED", "0")
CRM_MATCH_USE_LLM = _env_enabled("CRM_MATCH_USE_LLM", "0")
AI_DISABLED_DETAIL = "Recursos de IA temporariamente desabilitados neste ambiente."

AI_FEATURE_DEFAULTS: dict[str, bool] = {
    "document_processing": True,
    "matching": True,
    "edital_chat": True,
    "datasheet_extraction": True,
    "crm_matching": True,
    "crm_embeddings": True,
    "crm_llm_rerank": True,
}
# O matching base do CRM possui fallback lexical completo e nao depende de
# provedor de IA. Embeddings e reranking continuam protegidos pelo master switch.
_DETERMINISTIC_FEATURES = {"crm_matching"}


def _tenant_overrides(tenant: Any | None) -> dict[str, bool]:
    raw = getattr(tenant, "ai_features", None) if tenant is not None else None
    if not isinstance(raw, dict):
        return {}
    return {
        key: value
        for key, value in raw.items()
        if key in AI_FEATURE_DEFAULTS and isinstance(value, bool)
    }


def ai_feature_enabled(feature: str, tenant: Any | None = None) -> bool:
    """Resolve uma capacidade usando master switch + override do tenant."""
    if feature not in AI_FEATURE_DEFAULTS:
        raise ValueError(f"Capacidade de IA desconhecida: {feature}")
    enabled_for_tenant = _tenant_overrides(tenant).get(feature, AI_FEATURE_DEFAULTS[feature])
    if not enabled_for_tenant:
        return False
    return feature in _DETERMINISTIC_FEATURES or AI_FEATURES_ENABLED


def effective_ai_features(tenant: Any | None = None) -> dict[str, dict[str, Any]]:
    """Retorna estado efetivo e a causa de bloqueio para operacao/UI."""
    overrides = _tenant_overrides(tenant)
    result: dict[str, dict[str, Any]] = {}
    for feature, default in AI_FEATURE_DEFAULTS.items():
        configured = overrides.get(feature, default)
        enabled = ai_feature_enabled(feature, tenant)
        if not configured:
            reason = "tenant_disabled"
        elif feature not in _DETERMINISTIC_FEATURES and not AI_FEATURES_ENABLED:
            reason = "global_disabled"
        else:
            reason = "enabled"
        result[feature] = {
            "enabled": enabled,
            "configured": configured,
            "source": "tenant" if feature in overrides else "default",
            "reason": reason,
        }
    return result


def require_ai_enabled(feature: str | None = None, tenant: Any | None = None) -> None:
    enabled = AI_FEATURES_ENABLED if feature is None else ai_feature_enabled(feature, tenant)
    if not enabled:
        detail = AI_DISABLED_DETAIL
        if feature is not None:
            detail = f"Recurso de IA '{feature}' desabilitado para esta empresa ou ambiente."
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )


def update_tenant_ai_features(tenant: Any, changes: dict[str, bool | None]) -> dict[str, bool]:
    """Aplica overrides validados; None remove a chave e volta a herdar."""
    unknown = set(changes) - set(AI_FEATURE_DEFAULTS)
    if unknown:
        raise ValueError(f"Capacidades de IA desconhecidas: {', '.join(sorted(unknown))}")
    overrides = _tenant_overrides(tenant)
    for feature, value in changes.items():
        if value is None:
            overrides.pop(feature, None)
        elif isinstance(value, bool):
            overrides[feature] = value
        else:
            raise ValueError(f"Valor invalido para a capacidade '{feature}'.")
    tenant.ai_features = overrides
    return overrides
