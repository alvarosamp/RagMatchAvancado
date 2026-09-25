from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

from app.integrations.bling.client import BlingConfigurationError


class CredentialCipher:
    """Encrypt integration credentials at rest with Fernet authenticated encryption."""

    def __init__(self, key: str | bytes) -> None:
        try:
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except (TypeError, ValueError) as exc:
            raise BlingConfigurationError(
                "BLING_CREDENTIALS_ENCRYPTION_KEY não é uma chave Fernet válida."
            ) from exc

    @classmethod
    def from_env(cls) -> CredentialCipher:
        key = os.getenv("BLING_CREDENTIALS_ENCRYPTION_KEY")
        if key:
            return cls(key)

        app_env = os.getenv("APP_ENV", "development").lower()
        if app_env in {"prod", "production"}:
            raise BlingConfigurationError(
                "Configure BLING_CREDENTIALS_ENCRYPTION_KEY em produção."
            )
        secret = os.getenv("SECRET_KEY")
        if not secret:
            raise BlingConfigurationError(
                "Configure BLING_CREDENTIALS_ENCRYPTION_KEY para proteger o Bling."
            )
        derived = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        return cls(derived)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise BlingConfigurationError(
                "Não foi possível descriptografar as credenciais do Bling."
            ) from exc
