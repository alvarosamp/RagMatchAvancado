from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.init_db import init_db
from app.routers.health import router as health_router
from app.routers.switches import router as switches_router
from app.logs.config import logger


app = FastAPI(title="Edital Matcher API", version="0.2.0", description = 'Matching inteligente de produtos contra editais')

# Registra rotas
app.include_router(health_router)
app.include_router(switches_router)
app.include_router(editais_router)  # Rota para editais (a ser implementada)

@app.on_event("startup")
def on_startup():
    """
    Quando a API subir:
    - abre sessão
    - cria tabelas
    - carrega catálogo
    - fecha sessão
    """
    db: Session = SessionLocal()
    try:
        init_db(db)
        logger.info('Banco inicializado com sucesso')
    except Exception as e:
        logger.error(f"Erro ao inicializar banco: {e}")
        raise
    finally:
        db.close()