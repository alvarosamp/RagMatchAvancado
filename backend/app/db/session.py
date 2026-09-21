import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings
from app.logs.config import logger 

#Engine = conexao com o banco
engine = create_engine(
    settings.sqlalchemy_database_url,
    pool_pre_ping=True,
    pool_size=max(1, int(os.getenv("DB_POOL_SIZE", "10"))),
    max_overflow=max(0, int(os.getenv("DB_MAX_OVERFLOW", "10"))),
    pool_timeout=max(1, int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "30"))),
)

#Sessionlocal = classe que cria sessões de banco de dados
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(Session, "after_begin")
def _restore_tenant_context(session, transaction, connection):
    """Reapply the transaction-local RLS context after commits/rollbacks."""
    tenant_id = session.info.get("tenant_id")
    if tenant_id is not None and connection.dialect.name == "postgresql":
        connection.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(int(tenant_id))},
        )


def set_tenant_context(db: Session, tenant_id: int | str) -> int:
    """Bind this session and all of its future transactions to one tenant."""
    try:
        normalized = int(tenant_id)
    except (TypeError, ValueError):
        # Rolling deploy compatibility: queued jobs created before the tenant-id
        # migration still carry the old slug in their Redis message.
        from app.auth.models import Tenant

        normalized = db.query(Tenant.id).filter(Tenant.slug == str(tenant_id)).scalar()
        if normalized is None:
            raise ValueError("Tenant inexistente para o contexto do banco.")
    db.info["tenant_id"] = normalized
    if db.get_bind().dialect.name != "postgresql":
        return normalized
    db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(normalized)},
    )
    return normalized

def get_db(): #cada request cria uma sessão de banco de dados nova, e a sessão é fechada ao final da request
    '''
    Dependency que fornece uma sessão de banco de dados para as rotas do FastAPI
    -abre a sessao
    - entrega pra rota
    - fecha ao final
    '''
    
    db = SessionLocal()
    try:
        logger.info("Sessão de banco de dados criada com sucesso.")
        yield db
    finally:
        db.close()
        logger.info("Sessão de banco de dados fechada.")
