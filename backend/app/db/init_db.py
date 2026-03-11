from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.session import engine
from app.services.catalog_loader import load_switch_catalog
from app.logs.config import logger
from app.vector.pgvector_store import ensure_pgvector_extension

def init_db(db: Session) -> dict:
    """
    Cria tabelas e carrega catálogo.
    Roda no startup do FastAPI.

    IMPORTANTE: importamos app.auth.models aqui para que os modelos
    Tenant e User sejam registrados no Base.metadata antes do create_all().
    Sem esse import, as tabelas 'tenants' e 'users' não seriam criadas.
    """
    # Importa modelos auth para registrar no metadata do SQLAlchemy
    # O import é suficiente — não precisamos usar diretamente aqui
    import app.auth.models  # noqa: F401 — registra Tenant e User no Base.metadata

    try:
        # Habilita extensão pgvector antes de criar tabelas
        ensure_pgvector_extension(db)

        # Cria TODAS as tabelas registradas no Base (incluindo tenants e users)
        Base.metadata.create_all(bind=engine)
        logger.info("Tabelas criadas com sucesso (incluindo tenants e users)")

        # Carrega catálogo de switches
        inserted = load_switch_catalog(db)
        logger.info(f"Switches inseridos: {inserted}")

        return {"tables_created": True, "switches_inserted": inserted}

    except Exception as e:
        logger.error(f"Erro ao inicializar banco: {e}")
        raise