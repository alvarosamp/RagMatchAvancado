from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.session import engine
from app.logs.config import logger
from app.services.catalog_loader import load_switch_catalog
from app.vector.pgvector_store import ensure_pgvector_extension


def init_db(db: Session) -> dict:
    """
    Cria tabelas do portal principal e do CRM no mesmo banco.
    """
    import app.auth.models
    import app.crm.models
    import app.jobs.models

    try:
        ensure_pgvector_extension(db)
        Base.metadata.create_all(bind=engine)
        logger.info("Tabelas do portal e do CRM criadas com sucesso.")

        inserted = load_switch_catalog(db)
        logger.info("Switches inseridos: %s", inserted)

        return {"tables_created": True, "switches_inserted": inserted}
    except Exception as exc:
        logger.error(f"Erro ao inicializar banco: {exc}")
        raise
