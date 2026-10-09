"""Fail closed when production accidentally points to an empty database."""

from __future__ import annotations

import os


def require_explicit_empty_database_bootstrap() -> None:
    if os.getenv("APP_ENV", "development").strip().lower() not in {"production", "prod"}:
        return
    if os.getenv("ALLOW_EMPTY_DATABASE_BOOTSTRAP", "0").strip() == "1":
        return
    raise RuntimeError(
        "Banco vazio em producao: inicializacao bloqueada para preservar o CRM. "
        "Confira o projeto Docker, o volume PostgreSQL e o banco configurado. "
        "Somente para uma instalacao nova, defina ALLOW_EMPTY_DATABASE_BOOTSTRAP=1 "
        "temporariamente e remova depois da inicializacao."
    )
