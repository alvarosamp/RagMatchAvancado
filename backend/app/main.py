from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.init_db import init_db

from app.routers.health import router as health_router
from app.routers.switches import router as switches_router

app = FastAPI(title="Edital Matcher API", version="0.1.0")

# Registra rotas
app.include_router(health_router)
app.include_router(switches_router)

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
    finally:
        db.close()