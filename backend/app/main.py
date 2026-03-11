from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.init_db import init_db
from app.routers.health   import router as health_router
from app.routers.switches import router as switches_router
from app.routers.editais  import router as editais_router
from app.routers.export   import router as export_router
from app.auth.router      import router as auth_router   # ← NOVO
from app.logs.config import logger

app = FastAPI(
    title       = "Edital Matcher API",
    version     = "0.3.0",
    description = "Matching inteligente de produtos contra editais de licitação",
)

# Registra rotas
app.include_router(health_router)
app.include_router(auth_router)      # ← NOVO: /auth/register, /auth/login, /auth/me
app.include_router(switches_router)
app.include_router(editais_router)
app.include_router(export_router)


@app.on_event("startup")
def on_startup():
    """
    Startup:
    - cria extensão pgvector
    - cria tabelas (incluindo tenants e users)
    - carrega catálogo
    """
    db: Session = SessionLocal()
    try:
        result = init_db(db)
        logger.info(f"Banco inicializado: {result}")
    except Exception as e:
        logger.error(f"Erro no startup: {e}")
        raise
    finally:
        db.close()