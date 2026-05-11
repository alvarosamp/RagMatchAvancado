from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.init_db import init_db
from app.routers.health     import router as health_router
from app.routers.switches   import router as switches_router
from app.routers.editais    import router as editais_router
from app.routers.crm        import router as crm_router
from app.routers.export     import router as export_router
from app.routers.analytics  import router as analytics_router  # ← NOVO
from app.auth.router        import router as auth_router
from app.jobs.router        import router as jobs_router
from app.logs.config import logger

app = FastAPI(
    title       = "Edital Matcher API",
    version     = "0.5.0",
    description = "Matching inteligente de produtos contra editais de licitação",
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(crm_router)
app.include_router(jobs_router)
app.include_router(switches_router)
app.include_router(editais_router)
app.include_router(export_router)
app.include_router(analytics_router)   # ← NOVO: /analytics/*


@app.on_event("startup")
def on_startup():
    db: Session = SessionLocal()
    try:
        result = init_db(db)
        logger.info(f"Banco inicializado: {result}")
    except Exception as e:
        logger.error(f"Erro no startup: {e}")
        raise
    finally:
        db.close()

    # Pré-aquece os modelos de OCR e parsing em thread separada para que
    # o primeiro job não paralise o servidor durante o carregamento.
    import threading
    def _warmup():
        try:
            logger.info("[Startup] Pré-aquecendo modelos OCR/Docling...")
            from app.pipeline.docling_parser import parse_pdf  # noqa: F401
            logger.info("[Startup] Modelos prontos.")
        except Exception as exc:
            logger.warning(f"[Startup] Falha no pré-aquecimento (não crítico): {exc}")
    threading.Thread(target=_warmup, daemon=True).start()
