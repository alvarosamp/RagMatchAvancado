from __future__ import annotations

import os

from fastapi import HTTPException, status


def _env_enabled(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "sim", "on"}


AI_FEATURES_ENABLED = _env_enabled("AI_FEATURES_ENABLED", "0")
CRM_MATCH_USE_LLM = _env_enabled("CRM_MATCH_USE_LLM", "0")
AI_DISABLED_DETAIL = "Recursos de IA temporariamente desabilitados neste ambiente."


def require_ai_enabled() -> None:
    if not AI_FEATURES_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AI_DISABLED_DETAIL,
        )
