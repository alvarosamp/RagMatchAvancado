"""Validação de política de senha.

Centraliza as regras para manter consistência entre endpoints (register, create_user, etc).

Política ("melhor forma" / baseline seguro):
- >= 8 caracteres
- pelo menos 1 letra minúscula
- pelo menos 1 letra maiúscula
- pelo menos 1 número
- pelo menos 1 caractere especial

Observação: não tentamos medir vazamento/comprometimento de senha (HIBP) aqui
para evitar depender de serviços externos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")


@dataclass(frozen=True)
class PasswordPolicyResult:
    ok: bool
    errors: list[str]


def validate_password(password: str) -> PasswordPolicyResult:
    errors: list[str] = []

    if password is None:
        errors.append("A senha é obrigatória")
        return PasswordPolicyResult(ok=False, errors=errors)

    if len(password) < 8:
        errors.append("A senha deve ter pelo menos 8 caracteres")

    if not any(c.islower() for c in password):
        errors.append("A senha deve conter pelo menos 1 letra minúscula")

    if not any(c.isupper() for c in password):
        errors.append("A senha deve conter pelo menos 1 letra maiúscula")

    if not any(c.isdigit() for c in password):
        errors.append("A senha deve conter pelo menos 1 número")

    if not _SPECIAL_RE.search(password):
        errors.append("A senha deve conter pelo menos 1 símbolo (ex: !@#$%&*)")

    return PasswordPolicyResult(ok=len(errors) == 0, errors=errors)


def assert_valid_password(password: str) -> str:
    """Compatível com validators do Pydantic: retorna a senha se ok, senão lança ValueError."""
    result = validate_password(password)
    if not result.ok:
        # Pydantic/FastAPI vão serializar isso como detail, então juntamos
        # as mensagens para o usuário entender rapidamente o que falta.
        raise ValueError("; ".join(result.errors))
    return password
