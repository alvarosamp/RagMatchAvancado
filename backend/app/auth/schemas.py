# =============================================================================
# auth/schemas.py
# =============================================================================
#
# CONCEITO: O que são schemas Pydantic?
#
# Schemas são os "contratos" da API — definem o formato dos dados
# que entram (request body) e saem (response body).
#
# Por que separar schemas de models SQLAlchemy?
#   - Models SQLAlchemy = estrutura do banco (como os dados são armazenados)
#   - Schemas Pydantic  = estrutura da API (o que o cliente envia/recebe)
#
# Benefícios:
#   - Validação automática pelo FastAPI (tipos, campos obrigatórios, etc.)
#   - Documentação automática no /docs (Swagger)
#   - Nunca expor campos internos do banco (ex: hashed_password, tenant_id interno)
#
# Convenção de nomenclatura usada aqui:
#   - TenantCreate:   dados para CRIAR um tenant (request)
#   - TenantResponse: dados retornados AO CLIENTE (response)
#   - UserCreate:     dados para criar usuário
#   - UserResponse:   dados retornados ao cliente
#   - LoginRequest:   dados para fazer login
#   - TokenResponse:  JWT retornado após login
#
# =============================================================================

from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Tenant schemas
# ─────────────────────────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    """
    Dados para criar um novo tenant (empresa).
    Enviado pelo cliente no body da requisição.
    """
    slug: str        # identificador único (ex: "prefeitura-sp")
    name: str        # nome legível (ex: "Prefeitura de São Paulo")

    @field_validator("slug")
    @classmethod
    def slug_valido(cls, v: str) -> str:
        """
        Garante que o slug só tem letras minúsculas, números e hífens.
        Exemplo válido: "prefeitura-sp-2024"
        Exemplo inválido: "Prefeitura SP" (espaço e maiúscula)
        """
        import re
        if not re.match(r'^[a-z0-9\-]+$', v):
            raise ValueError("slug deve conter apenas letras minúsculas, números e hífens")
        return v


class TenantResponse(BaseModel):
    """
    Dados do tenant retornados ao cliente.
    Não inclui IDs internos ou dados sensíveis.
    """
    slug:      str
    name:      str
    is_active: bool

    # Permite criar a partir de um objeto SQLAlchemy (ORM mode)
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# User schemas
# ─────────────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """
    Dados para criar um novo usuário.
    O tenant é inferido do JWT de quem está criando (admin).
    """
    email:     EmailStr   # Pydantic valida o formato do email automaticamente
    password:  str
    full_name: Optional[str] = None
    role:      str = "editor"   # padrão: editor (não admin)

    @field_validator("password")
    @classmethod
    def senha_forte(cls, v: str) -> str:
        """
        Validação básica de força de senha.
        Em produção, adicione mais regras (maiúscula, número, símbolo).
        """
        if len(v) < 8:
            raise ValueError("A senha deve ter pelo menos 8 caracteres")
        return v

    @field_validator("role")
    @classmethod
    def role_valido(cls, v: str) -> str:
        roles_permitidos = {"admin", "editor", "viewer"}
        if v not in roles_permitidos:
            raise ValueError(f"role deve ser um de: {roles_permitidos}")
        return v


class UserResponse(BaseModel):
    """
    Dados do usuário retornados ao cliente.
    NUNCA inclui hashed_password.
    """
    id:        int
    email:     str
    full_name: Optional[str]
    role:      str
    is_active: bool
    tenant:    TenantResponse   # inclui dados do tenant embutidos

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Auth schemas (login + token)
# ─────────────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """
    Credenciais para fazer login.
    Enviado no body de POST /auth/login.
    """
    email:    EmailStr
    password: str


class TokenResponse(BaseModel):
    """
    JWT retornado após login bem-sucedido.

    O cliente deve guardar o access_token e enviá-lo em todas as
    requisições subsequentes no header:
        Authorization: Bearer <access_token>

    token_type é sempre "bearer" — padrão OAuth2.
    """
    access_token: str
    token_type:   str = "bearer"
    expires_in:   int            # segundos até expirar (para o cliente saber quando renovar)
    tenant_slug:  str            # slug do tenant (útil para o frontend filtrar dados)
    role:         str            # papel do usuário (para o frontend mostrar/esconder opções)


# ─────────────────────────────────────────────────────────────────────────────
# Registro (tenant + admin em um único passo)
# ─────────────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """
    Registra um novo tenant e cria o usuário admin em um único passo.

    Fluxo:
        1. Cria o Tenant com slug + name
        2. Cria o User com role="admin" dentro desse tenant
        3. Retorna o JWT pronto para uso

    Assim o cliente já fica autenticado após o cadastro.
    """
    # Dados do tenant
    tenant_slug: str
    tenant_name: str

    # Dados do usuário admin
    email:       EmailStr
    password:    str
    full_name:   Optional[str] = None

    @field_validator("tenant_slug")
    @classmethod
    def slug_valido(cls, v: str) -> str:
        import re
        if not re.match(r'^[a-z0-9\-]+$', v):
            raise ValueError("tenant_slug deve conter apenas letras minúsculas, números e hífens")
        return v

    @field_validator("password")
    @classmethod
    def senha_forte(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("A senha deve ter pelo menos 8 caracteres")
        return v