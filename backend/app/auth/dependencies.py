'''
CONCEITO: O que são FastAPI Dependencies?
Dependencies são funções que o FastAPI executa ANTES da sua rota.
Você declara como parâmetro da rota e o FastAPI injeta automaticamente.
Exemplo:
@router.get("/editais")
def listar(current_user: User = Depends(get_current_user)):
# current_user já está preenchido, sem código extra
Por que usar ao invés de repetir código em cada rota?

DRY: lógica de autenticação em um único lugar
Testável: você pode substituir a dependency em testes
Composável: uma dependency pode depender de outra

HIERARQUIA DE DEPENDENCIES NESTE ARQUIVO:
get_token_from_header          → extrai o Bearer token do header
↓
get_current_user               → valida o JWT e retorna o User do banco
↓
get_current_tenant             → retorna o Tenant do usuário atual
↓
require_role("admin")          → garante que o usuário tem o role certo
'''

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import User, Tenant
from app.auth.security import decode_access_token
from app.logs.config import logger


# ─────────────────────────────────────────────────────────────────────────────
# OAuth2PasswordBearer — extrai o token do header Authorization
# ─────────────────────────────────────────────────────────────────────────────

# OAuth2PasswordBearer é um helper do FastAPI que:
#   1. Lê o header "Authorization: Bearer <token>"
#   2. Extrai só o token (sem o prefixo "Bearer ")
#   3. Adiciona o cadeado 🔒 na documentação /docs automaticamente
#
# tokenUrl = endpoint onde o cliente obtém o token (para o /docs saber onde fazer login)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ─────────────────────────────────────────────────────────────────────────────
# Dependency principal — get_current_user
# ─────────────────────────────────────────────────────────────────────────────

def get_current_user(
    token: str     = Depends(oauth2_scheme),  # extrai o Bearer token
    db:    Session = Depends(get_db),         # sessão do banco
) -> User:
    """
    Dependency que valida o JWT e retorna o usuário autenticado.

    Executada automaticamente pelo FastAPI antes de qualquer rota
    que declare: current_user: User = Depends(get_current_user)

    Fluxo:
        1. OAuth2PasswordBearer extrai o token do header
        2. decode_access_token valida assinatura + expiração
        3. Extrai o email (claim "sub") do payload
        4. Busca o usuário no banco pelo email
        5. Verifica se o usuário está ativo
        6. Retorna o objeto User

    Raises:
        401 UNAUTHORIZED: token inválido, expirado ou usuário não encontrado
        403 FORBIDDEN: usuário desativado
    """
    # Erro padrão para qualquer problema de autenticação
    # HTTP 401 = "não autenticado" (não confundir com 403 = "sem permissão")
    credentials_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail      = "Token inválido ou expirado. Faça login novamente.",
        headers     = {"WWW-Authenticate": "Bearer"},  # padrão OAuth2
    )

    try:
        # Valida assinatura e expiração, retorna o payload
        payload = decode_access_token(token)

        # "sub" = subject = email do usuário
        email: str = payload.get("sub")
        if not email:
            logger.warning("[Auth] Token sem claim 'sub'")
            raise credentials_exception

    except JWTError as e:
        # Token adulterado, expirado, ou com assinatura inválida
        logger.warning(f"[Auth] JWT inválido: {e}")
        raise credentials_exception

    # Busca o usuário no banco pelo email
    user = db.query(User).filter(User.email == email).first()
    if not user:
        logger.warning(f"[Auth] Usuário não encontrado: {email}")
        raise credentials_exception

    # Verifica se a conta está ativa
    if not user.is_active:
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN,
            detail      = "Conta desativada. Entre em contato com o administrador.",
        )

    return user


# ─────────────────────────────────────────────────────────────────────────────
# Dependency de tenant — get_current_tenant
# ─────────────────────────────────────────────────────────────────────────────

def get_current_tenant(
    current_user: User = Depends(get_current_user),
) -> Tenant:
    """
    Retorna o Tenant do usuário autenticado.

    Usada quando a rota precisa do tenant completo (ex: para logar o tenant_slug).
    Na maioria dos casos, current_user.tenant já basta.

    Raises:
        403 FORBIDDEN: tenant desativado
    """
    tenant = current_user.tenant

    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN,
            detail      = "Tenant desativado. Entre em contato com o suporte.",
        )

    return tenant


# ─────────────────────────────────────────────────────────────────────────────
# Dependency de autorização — require_role
# ─────────────────────────────────────────────────────────────────────────────

def require_role(*roles: str):
    """
    Factory de dependency que verifica se o usuário tem o role necessário.

    RBAC (Role-Based Access Control) — controla o que cada usuário pode fazer.

    Roles disponíveis:
        admin  → acesso total (criar usuários, ver todos os dados do tenant)
        editor → pode fazer upload e rodar matching
        viewer → somente leitura (ver resultados e exportar)

    Como usar:
        # Só admin pode criar usuários
        @router.post("/users")
        def criar_usuario(user: User = Depends(require_role("admin"))):
            ...

        # Admin e editor podem fazer upload
        @router.post("/editais/upload")
        def upload(user: User = Depends(require_role("admin", "editor"))):
            ...

    Args:
        *roles: um ou mais roles que têm permissão

    Returns:
        Uma dependency que retorna o User se autorizado, ou lança 403.
    """
    def _check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code = status.HTTP_403_FORBIDDEN,
                detail      = (
                    f"Permissão negada. "
                    f"Necessário: {list(roles)}. "
                    f"Seu role: {current_user.role}"
                ),
            )
        return current_user

    return _check_role


# ─────────────────────────────────────────────────────────────────────────────
# Dependency opcional — get_current_user_optional
# ─────────────────────────────────────────────────────────────────────────────

def get_current_user_optional(
    token: str     = Depends(oauth2_scheme),
    db:    Session = Depends(get_db),
) -> User | None:
    """
    Versão opcional de get_current_user.
    Retorna None se não houver token (em vez de lançar 401).

    Útil para endpoints que têm comportamento diferente
    para usuários autenticados vs anônimos.
    """
    try:
        return get_current_user(token=token, db=db)
    except HTTPException:
        return None