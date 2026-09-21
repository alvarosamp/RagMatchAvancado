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

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.models import PasswordResetToken, Tenant, User, UserRoleAudit
from app.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    TenantAIFeaturesUpdate,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserRoleUpdate,
    UserProfileUpdate,
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
from app.core.features import effective_ai_features, update_tenant_ai_features
from app.services.auth_email import password_reset_email_configured, send_password_reset_email
from app.services.rate_limit import rate_limit_exceeded, reset_rate_limit

router = APIRouter(prefix="/auth", tags=["autenticação"])
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "access_token")
COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "lax").lower()
PASSWORD_RESET_RESPONSE = {
    "message": "Se o e-mail estiver cadastrado, enviaremos as instrucoes de recuperacao."
}


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


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def _enforce_rate_limit(scope: str, identity: str, *, limit: int, window_seconds: int) -> None:
    if rate_limit_exceeded(scope, identity, limit=limit, window_seconds=window_seconds):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas. Aguarde e tente novamente.",
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
        cpf             = payload.cpf,
        phone           = payload.phone,
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
        auth_version = user.auth_version or 0,
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
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
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
    _enforce_rate_limit("login-ip", _client_ip(request), limit=30, window_seconds=900)
    _enforce_rate_limit("login-account", payload.email, limit=10, window_seconds=900)

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
        auth_version = user.auth_version or 0,
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


@router.get("/tenant/ai-features")
def get_tenant_ai_features(
    current_user: User = Depends(require_role("admin")),
):
    """Exibe overrides e estado efetivo das capacidades de IA do tenant."""
    return {
        "tenant_slug": current_user.tenant.slug,
        "overrides": dict(current_user.tenant.ai_features or {}),
        "features": effective_ai_features(current_user.tenant),
    }


@router.patch("/tenant/ai-features")
def patch_tenant_ai_features(
    payload: TenantAIFeaturesUpdate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Altera somente o tenant autenticado; null restaura o padrao global."""
    changes = {field: getattr(payload, field) for field in payload.model_fields_set}
    update_tenant_ai_features(current_user.tenant, changes)
    db.add(current_user.tenant)
    db.commit()
    db.refresh(current_user.tenant)
    logger.info(
        "[AI Features] Rollout atualizado | tenant=%s | keys=%s",
        current_user.tenant.slug,
        sorted(changes),
    )
    return {
        "tenant_slug": current_user.tenant.slug,
        "overrides": dict(current_user.tenant.ai_features or {}),
        "features": effective_ai_features(current_user.tenant),
    }


@router.patch("/me/profile", response_model=UserResponse)
def update_my_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.email != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A troca de e-mail exige confirmacao. Entre em contato com o suporte.",
        )

    reset_rate_limit("login-account", payload.email)

    current_user.full_name = payload.full_name
    current_user.cpf = payload.cpf
    current_user.phone = payload.phone
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/password/change")
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta.",
        )
    if verify_password(payload.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve ser diferente da senha atual.",
        )

    current_user.hashed_password = hash_password(payload.new_password)
    current_user.auth_version = int(current_user.auth_version or 0) + 1
    db.commit()
    _clear_auth_cookie(response)
    logger.info("[Auth] Senha alterada e sessoes revogadas | user_id=%s", current_user.id)
    return {"message": "Senha alterada. Entre novamente em todos os dispositivos."}


@router.post("/password/reset/request")
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _enforce_rate_limit("password-reset-ip", _client_ip(request), limit=10, window_seconds=3600)
    _enforce_rate_limit("password-reset-account", payload.email, limit=5, window_seconds=3600)

    user = db.query(User).filter(User.email == payload.email).first()
    if (
        user
        and user.is_active
        and user.tenant
        and user.tenant.is_active
        and password_reset_email_configured()
    ):
        now = datetime.now(timezone.utc)
        for previous in db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        ).all():
            previous.used_at = now

        raw_token = secrets.token_urlsafe(32)
        reset = PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            expires_at=now + timedelta(minutes=int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))),
        )
        db.add(reset)
        db.commit()
        try:
            send_password_reset_email(user.email, raw_token)
        except Exception as exc:
            logger.error(
                "[Auth] Falha ao enviar recuperacao de senha | user_id=%s | erro=%s",
                user.id,
                exc,
            )

    return PASSWORD_RESET_RESPONSE


@router.post("/password/reset/confirm")
def confirm_password_reset(
    payload: PasswordResetConfirm,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _enforce_rate_limit("password-reset-confirm-ip", _client_ip(request), limit=20, window_seconds=3600)
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    reset = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
        .first()
    )
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Link de recuperacao invalido ou expirado.",
    )
    if reset is None or reset.used_at is not None:
        raise invalid
    expires_at = reset.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise invalid

    user = db.query(User).filter(User.id == reset.user_id).with_for_update().first()
    if user is None or not user.is_active or not user.tenant or not user.tenant.is_active:
        raise invalid
    if verify_password(payload.new_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve ser diferente da senha atual.",
        )

    now = datetime.now(timezone.utc)
    for token in db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).all():
        token.used_at = now
    user.hashed_password = hash_password(payload.new_password)
    user.auth_version = int(user.auth_version or 0) + 1
    db.commit()
    _clear_auth_cookie(response)
    logger.info("[Auth] Senha redefinida e sessoes revogadas | user_id=%s", user.id)
    return {"message": "Senha redefinida. Voce ja pode entrar novamente."}


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
        cpf             = payload.cpf,
        phone           = payload.phone,
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
