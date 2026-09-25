from __future__ import annotations

import pytest
from app.integrations.bling.client import BlingConfigurationError
from app.integrations.bling.credentials import CredentialCipher
from cryptography.fernet import Fernet


def test_credentials_are_encrypted_and_can_be_decrypted():
    cipher = CredentialCipher(Fernet.generate_key())

    encrypted = cipher.encrypt("refresh-token-sensitive")

    assert encrypted != "refresh-token-sensitive"
    assert "refresh-token-sensitive" not in encrypted
    assert cipher.decrypt(encrypted) == "refresh-token-sensitive"


def test_credentials_cannot_be_decrypted_with_another_tenant_key():
    first = CredentialCipher(Fernet.generate_key())
    second = CredentialCipher(Fernet.generate_key())

    encrypted = first.encrypt("client-secret")

    with pytest.raises(BlingConfigurationError, match="descriptografar"):
        second.decrypt(encrypted)
