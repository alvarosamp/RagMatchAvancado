from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.session import engine
from app.services.catalog_loader import load_switch_catalog

def init_db(db: Session) -> dict:
    """
    Cria tabelas e carrega catálogo.
    Roda no startup do FastAPI.
    """
    Base.metadata.create_all(bind=engine)
    inserted = load_switch_catalog(db)
    return {"tables_created": True, "switches_inserted": inserted}