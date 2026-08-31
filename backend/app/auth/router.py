# =============================================================================
# auth/router.py
# =============================================================================
#
# Endpoints de autenticação e gerenciamento de usuários.
#
# POST /auth/register  → cria tenant + usuário admin (primeiro acesso)
# POST /auth/login     → faz login, retorna JWT
# GET  /auth/me        → dados do usuário atual (valida token)
# POST /auth/users     → admin cria usuário dentro do mesmo tenant
# GET  /auth/users     → admin lista usuários do tenant
#
# =============================================================================

import os

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.models import Tenant, User, UserRoleAudit
from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserRoleUpdate,
)
from app.auth.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    hash_password,
    verify_password,
)
from app.services.crm_workflow import ensure_not_last_active_admin
from app.auth.dependencies import get_current_user, require_role
from app.logs.config import logger

router = APIRouter(prefix="/auth", tags=["autenticação"])
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "access_token")
COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "lax").lower()


def _register_enabled() -> bool:
    return os.getenv("REGISTER_ENABLED", "1").lower() in {"1", "true", "yes", "sim"}


def _token_body_enabled() -> bool:
    default = "0" if os.getenv("APP_ENV", "development").lower() in {"prod", "production"} else "1"
    return os.getenv("AUTH_TOKEN_IN_BODY", default).lower() in {"1", "true", "yes", "sim"}


def _cookie_secure() -> bool:
    default = "1" if os.getenv("APP_ENV", "development").lower() in {"prod", "production"} else "0"
    return os.getenv("AUTH_COOKIE_SECURE", default).lower() in {"1", "true", "yes", "sim"}


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        httponly=True,
        secure=_cookie_secure(),
        samesite=COOKIE_SAMESITE,  # type: ignore[arg-type]
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        secure=_cookie_secure(),
        samesite=COOKIE_SAMESITE,  # type: ignore[arg-type]
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /auth/register — cria tenant + admin
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    """
    Registra uma nova empresa (tenant) e cria o usuário administrador.

    Este é o endpoint de "onboarding" — usado uma vez para criar a conta.
    Após isso, o admin usa POST /auth/users para criar outros usuários.

    Fluxo:
        1. Verifica se o tenant_slug já existe
        2. Verifica se o email já está cadastrado
        3. Cria o Tenant
        4. Cria o User com role="admin"
        5. Retorna JWT pronto para uso

    Body:
        {
            "tenant_slug": "prefeitura-sp",
            "tenant_name": "Prefeitura de São Paulo",
            "email": "admin@prefeitura.sp.gov.br",
            "password": "senhaforte123",
            "full_name": "João Silva"
        }
    """
    if not _register_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cadastro publico desativado neste ambiente.",
        )

    # Verifica se o slug já está em uso
    tenant_existente = db.query(Tenant).filter(Tenant.slug == payload.tenant_slug).first()
    if tenant_existente:
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail      = f"Tenant '{payload.tenant_slug}' já existe.",
        )

    # Verifica se o email já está em uso
    usuario_existente = db.query(User).filter(User.email == payload.email).first()
    if usuario_existente:
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail      = f"Email '{payload.email}' já está cadastrado.",
        )

    # Cria o Tenant
    tenant = Tenant(
        slug  = payload.tenant_slug,
        name  = payload.tenant_name,
    )
    db.add(tenant)
    db.flush()  # flush gera tenant.id sem commit final (transação atômica)

    # Cria o usuário admin
    # hash_password usa bcrypt — nunca armazenamos senha em texto puro
    user = User(
        email           = payload.email,
        hashed_password = hash_password(payload.password),
        full_name       = payload.full_name,
        role            = "admin",   # primeiro usuário é sempre admin
        tenant_id       = tenant.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"[Auth] Novo tenant registrado: {tenant.slug} | admin: {user.email}")

    # Gera o JWT e retorna — cliente já fica autenticado
    token = create_access_token(
        subject     = user.email,
        tenant_slug = tenant.slug,
        user_id     = user.id,
        role        = user.role,
    )
    _set_auth_cookie(response, token)

    return TokenResponse(
        access_token = token if _token_body_enabled() else "",
        expires_in   = ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        tenant_slug  = tenant.slug,
        role         = user.role,
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /auth/login — faz login
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """
    Autentica o usuário e retorna um JWT.

    Por que retornamos HTTP 401 tanto para usuário inexistente quanto para
    senha errada? Para não revelar se o email existe no sistema
    (prevenção de enumeração de usuários).

    Body:
        {
            "email": "admin@prefeitura.sp.gov.br",
            "password": "senhaforte123"
        }

    Response:
        {
            "access_token": "eyJ...",
            "token_type": "bearer",
            "expires_in": 3600,
            "tenant_slug": "prefeitura-sp",
            "role": "admin"
        }
    """
    # Busca o usuário pelo email
    user = db.query(User).filter(User.email == payload.email).first()

    # Verifica senha — verify_password usa bcrypt para comparar
    # A mensagem de erro é PROPOSITALMENTE genérica (não revela se o email existe)
    if not user or not verify_password(payload.password, user.hashed_password):
        logger.warning(f"[Auth] Tentativa de login falhou: {payload.email}")
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Email ou senha incorretos.",
            headers     = {"WWW-Authenticate": "Bearer"},
        )

    # Verifica conta ativa
    if not user.is_active:
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN,
            detail      = "Conta desativada. Entre em contato com o administrador.",
        )

    # Verifica tenant ativo
    if not user.tenant.is_active:
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN,
            detail      = "Conta da empresa desativada. Entre em contato com o suporte.",
        )

    logger.info(f"[Auth] Login bem-sucedido: {user.email} | tenant={user.tenant.slug}")

    token = create_access_token(
        subject     = user.email,
        tenant_slug = user.tenant.slug,
        user_id     = user.id,
        role        = user.role,
    )
    _set_auth_cookie(response, token)

    return TokenResponse(
        access_token = token if _token_body_enabled() else "",
        expires_in   = ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        tenant_slug  = user.tenant.slug,
        role         = user.role,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /auth/me — dados do usuário atual
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/logout")
def logout(response: Response):
    _clear_auth_cookie(response)
    return {"message": "Sessao encerrada."}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    """
    Retorna os dados do usuário autenticado.

    Útil para o frontend verificar se o token ainda é válido
    e para exibir o nome/role do usuário na interface.

    Requer: Authorization: Bearer <token>
    """
    return current_user


# ─────────────────────────────────────────────────────────────────────────────
# POST /auth/users — admin cria usuário no mesmo tenant
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload:      UserCreate,
    current_user: User    = Depends(require_role("admin")),  # só admin pode criar usuários
    db:           Session = Depends(get_db),
):
    """
    Cria um novo usuário dentro do mesmo tenant do admin autenticado.

    O tenant é inferido automaticamente do JWT — o admin não pode
    criar usuários em outros tenants (isolamento garantido).

    Requer: role = "admin"

    Body:
        {
            "email": "analista@prefeitura.sp.gov.br",
            "password": "senhaforte123",
            "full_name": "Maria Santos",
            "role": "editor"
        }
    """
    # Verifica se o email já existe no sistema
    existente = db.query(User).filter(User.email == payload.email).first()
    if existente:
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail      = f"Email '{payload.email}' já está cadastrado.",
        )

    # Cria o usuário no mesmo tenant do admin
    # ISOLAMENTO: tenant_id vem do current_user, não do payload
    user = User(
        email           = payload.email,
        hashed_password = hash_password(payload.password),
        full_name       = payload.full_name,
        role            = payload.role,
        tenant_id       = current_user.tenant_id,  # sempre o tenant do admin
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(
        f"[Auth] Usuário criado: {user.email} | "
        f"role={user.role} | tenant={current_user.tenant.slug}"
    )
    return user


# ─────────────────────────────────────────────────────────────────────────────
# GET /auth/users — admin lista usuários do tenant
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserResponse])
def list_users(
    current_user: User    = Depends(require_role("admin")),
    db:           Session = Depends(get_db),
):
    """
    Lista todos os usuários do tenant do admin autenticado.

    ISOLAMENTO: filtra por tenant_id — nunca retorna usuários de outros tenants.

    Requer: role = "admin"
    """
    users = (
        db.query(User)
        .filter(User.tenant_id == current_user.tenant_id)
        .all()
    )
    return users


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Troca o papel em uma unica transacao e protege o ultimo admin ativo."""
    target = (
        db.query(User)
        .filter(User.id == user_id, User.tenant_id == current_user.tenant_id)
        .with_for_update()
        .first()
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado.")
    previous_role = target.role
    if previous_role == payload.role:
        return target
    if previous_role == "admin" and payload.role != "admin" and target.is_active:
        active_admins = db.query(User).filter(
            User.tenant_id == current_user.tenant_id,
            User.role == "admin",
            User.is_active.is_(True),
        ).count()
        try:
            ensure_not_last_active_admin(
                previous_role=previous_role, new_role=payload.role,
                target_is_active=target.is_active, active_admin_count=active_admins,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
    target.role = payload.role
    db.add(UserRoleAudit(
        tenant_id=current_user.tenant_id,
        administrator_id=current_user.id,
        target_user_id=target.id,
        previous_role=previous_role,
        new_role=payload.role,
    ))
    db.commit()
    db.refresh(target)
    return target
