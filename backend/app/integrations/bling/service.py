from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.integrations.bling.client import (
    BlingClient,
    BlingConfigurationError,
    BlingSettings,
)
from app.integrations.bling.credentials import CredentialCipher
from app.integrations.bling.models import BlingTenantIntegration

DEFAULT_AUTHORIZE_URL = "https://www.bling.com.br/Api/v3/oauth/authorize"


def get_integration(db: Session, tenant_id: int) -> BlingTenantIntegration | None:
    return (
        db.query(BlingTenantIntegration)
        .filter(BlingTenantIntegration.tenant_id == tenant_id)
        .one_or_none()
    )


def save_credentials(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    client_secret: str,
    cipher: CredentialCipher | None = None,
) -> BlingTenantIntegration:
    cipher = cipher or CredentialCipher.from_env()
    record = get_integration(db, tenant_id)
    if record is None:
        record = BlingTenantIntegration(tenant_id=tenant_id, client_id=client_id)
        db.add(record)
    record.client_id = client_id
    record.client_secret_encrypted = cipher.encrypt(client_secret)
    record.access_token_encrypted = None
    record.refresh_token_encrypted = None
    record.token_expires_at = None
    record.scopes = None
    record.connected_at = None
    record.pending_state_hash = None
    record.pending_state_expires_at = None
    db.commit()
    db.refresh(record)
    return record


def disconnect(db: Session, *, tenant_id: int) -> bool:
    record = get_integration(db, tenant_id)
    if record is None:
        return False
    db.delete(record)
    db.commit()
    return True


def integration_status(record: BlingTenantIntegration | None) -> dict[str, Any]:
    if record is None:
        return {
            "configured": False,
            "connected": False,
            "clientIdHint": None,
            "tokenExpiresAt": None,
            "scopes": [],
        }
    scopes = record.scopes.split() if record.scopes else []
    client_hint = (
        f"••••{record.client_id[-6:]}" if len(record.client_id) > 6 else record.client_id
    )
    return {
        "configured": True,
        "connected": bool(
            record.access_token_encrypted and record.refresh_token_encrypted
        ),
        "clientIdHint": client_hint,
        "tokenExpiresAt": record.token_expires_at,
        "scopes": scopes,
    }


def start_oauth(
    db: Session, *, tenant_id: int, cipher: CredentialCipher | None = None
) -> str:
    record = _require_configured(db, tenant_id)
    cipher = cipher or CredentialCipher.from_env()
    cipher.decrypt(record.client_secret_encrypted)

    state = secrets.token_urlsafe(32)
    record.pending_state_hash = _state_hash(state)
    record.pending_state_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.commit()

    authorize_url = os.getenv("BLING_AUTHORIZE_URL", DEFAULT_AUTHORIZE_URL)
    query = urlencode(
        {"response_type": "code", "client_id": record.client_id, "state": state}
    )
    return f"{authorize_url}?{query}"


def complete_oauth(
    db: Session,
    *,
    tenant_id: int,
    state: str,
    code: str,
    cipher: CredentialCipher | None = None,
) -> BlingTenantIntegration:
    record = _require_configured(db, tenant_id)
    now = datetime.now(timezone.utc)
    expires_at = record.pending_state_expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if (
        not record.pending_state_hash
        or not expires_at
        or expires_at < now
        or not secrets.compare_digest(record.pending_state_hash, _state_hash(state))
    ):
        raise BlingConfigurationError("Estado OAuth do Bling inválido ou expirado.")

    cipher = cipher or CredentialCipher.from_env()
    environment = BlingSettings.from_env()
    settings = BlingSettings(
        client_id=record.client_id,
        client_secret=cipher.decrypt(record.client_secret_encrypted),
        api_url=environment.api_url,
        oauth_url=environment.oauth_url,
        timeout_seconds=environment.timeout_seconds,
        enable_jwt=environment.enable_jwt,
    )
    client = BlingClient(settings=settings)
    token_data = client.exchange_authorization_code(code)
    _persist_token_data(record, token_data, cipher)
    record.pending_state_hash = None
    record.pending_state_expires_at = None
    db.commit()
    db.refresh(record)
    return record


def build_tenant_client(
    db: Session,
    *,
    tenant_id: int,
    cipher: CredentialCipher | None = None,
    session: Any = None,
) -> BlingClient:
    record = _require_connected(db, tenant_id)
    cipher = cipher or CredentialCipher.from_env()
    environment = BlingSettings.from_env()

    def persist_refresh(token_data: dict[str, Any]) -> None:
        _persist_token_data(record, token_data, cipher)
        db.commit()

    settings = BlingSettings(
        access_token=cipher.decrypt(record.access_token_encrypted),
        refresh_token=cipher.decrypt(record.refresh_token_encrypted),
        client_id=record.client_id,
        client_secret=cipher.decrypt(record.client_secret_encrypted),
        api_url=environment.api_url,
        oauth_url=environment.oauth_url,
        timeout_seconds=environment.timeout_seconds,
        enable_jwt=environment.enable_jwt,
    )
    return BlingClient(
        settings=settings,
        session=session,
        token_update_handler=persist_refresh,
    )


def _persist_token_data(
    record: BlingTenantIntegration,
    token_data: dict[str, Any],
    cipher: CredentialCipher,
) -> None:
    access_token = token_data.get("access_token")
    if not access_token:
        raise BlingConfigurationError("O Bling não retornou um access token.")
    record.access_token_encrypted = cipher.encrypt(str(access_token))
    refresh_token = token_data.get("refresh_token")
    if refresh_token:
        record.refresh_token_encrypted = cipher.encrypt(str(refresh_token))
    expires_in = token_data.get("expires_in")
    record.token_expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        if expires_in
        else None
    )
    record.scopes = str(token_data.get("scope") or "") or None
    record.connected_at = datetime.now(timezone.utc)


def _require_configured(db: Session, tenant_id: int) -> BlingTenantIntegration:
    record = get_integration(db, tenant_id)
    if record is None or not record.client_id or not record.client_secret_encrypted:
        raise BlingConfigurationError(
            "Configure o Client ID e o Client Secret do Bling antes de conectar."
        )
    return record


def _require_connected(db: Session, tenant_id: int) -> BlingTenantIntegration:
    record = _require_configured(db, tenant_id)
    if not record.access_token_encrypted or not record.refresh_token_encrypted:
        raise BlingConfigurationError("A empresa ainda não conectou uma conta Bling.")
    return record


def _state_hash(state: str) -> str:
    return hashlib.sha256(state.encode()).hexdigest()
