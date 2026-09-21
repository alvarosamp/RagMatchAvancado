import pytest
from pydantic import ValidationError

from app.auth.schemas import (
    ChangePasswordRequest,
    PasswordResetConfirm,
    RegisterRequest,
    UserCreate,
    UserProfileUpdate,
)


VALID = {
    "email": "Pessoa@Example.com",
    "full_name": "Pessoa da Silva",
    "cpf": "529.982.247-25",
    "phone": "(61) 99999-9999",
}


def test_new_user_requires_and_normalizes_identity_fields():
    payload = UserCreate(password="Senha1!x", role="editor", **VALID)

    assert payload.email == "pessoa@example.com"
    assert payload.cpf == "52998224725"
    assert payload.phone == "61999999999"


def test_tenant_registration_requires_complete_admin_profile():
    payload = RegisterRequest(
        tenant_slug="empresa-teste",
        tenant_name="Empresa Teste",
        password="Senha1!x",
        **VALID,
    )

    assert payload.full_name == "Pessoa da Silva"
    assert payload.cpf == "52998224725"


@pytest.mark.parametrize("cpf", ["111.111.111-11", "123.456.789-00", "123"])
def test_profile_rejects_invalid_cpf(cpf):
    with pytest.raises(ValidationError):
        UserProfileUpdate(**{**VALID, "cpf": cpf})


def test_profile_rejects_invalid_phone():
    with pytest.raises(ValidationError):
        UserProfileUpdate(**{**VALID, "phone": "9999-9999"})


@pytest.mark.parametrize("password", ["curta", "somenteletras", "SemSimbolo1"])
def test_password_change_and_reset_use_central_policy(password):
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password="Senha1!x", new_password=password)
    with pytest.raises(ValidationError):
        PasswordResetConfirm(token="token", new_password=password)
