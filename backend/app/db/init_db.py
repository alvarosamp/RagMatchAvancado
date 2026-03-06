from requests import Session

from app.db.models import Base
from app.db.session import engine
from app.services.catalog_loader import load_switch_catalog
from app.logs.config import logger
from app.vector.pgvector_store import ensure_pgvector_extension

def init_db(db: Session) -> dict:
    """
    Cria tabelas e carrega catálogo.
    Roda no startup do FastAPI.
    """
    try:
        #habilita expensao antes de criar a tabela
        ensure_pgvector_extension(db)
        #Cria todas as tabelas
        Base.metadata.create_all(bind=engine)
        
        logger.info('Tabelas criadas com sucesso')
        #Carrega catálogo de switches
        inserted = load_switch_catalog(db)
        logger.info(f"Switches inseridos: {inserted}")
        return {"tables_created": True, "switches_inserted": inserted}
    
    except Exception as e:
        logger.error(f"Erro ao inicializar banco: {e}")
        raise