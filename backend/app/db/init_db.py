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

    Imports necessários para registrar todos os modelos no Base.metadata
    antes do create_all() — sem eles, as tabelas não são criadas.
    """
    import app.auth.models  # noqa: F401 — registra Tenant e User
    import app.jobs.models  # noqa: F401 — registra Job

    try:
        ensure_pgvector_extension(db)
        Base.metadata.create_all(bind=engine)
        logger.info("Tabelas criadas (products, editais, tenants, users, jobs, ...)")

        inserted = load_switch_catalog(db)
        logger.info(f"Switches inseridos: {inserted}")

        return {"tables_created": True, "switches_inserted": inserted}

    except Exception as e:
        logger.error(f"Erro ao inicializar banco: {e}")
        raise