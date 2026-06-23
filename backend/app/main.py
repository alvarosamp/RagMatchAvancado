import os

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
from app.routers.ops        import router as ops_router
from app.routers.reports    import router as reports_router
from app.routers.analysis   import router as analysis_router
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
app.include_router(ops_router)
app.include_router(reports_router)
app.include_router(analysis_router)
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

        # Garante que o modelo Ollama está disponível (puxa se necessário).
        try:
            import time
            import ollama as _ollama
            _host  = os.getenv("OLLAMA_HOST",  "http://localhost:11434")
            _model = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
            _auto_pull = os.getenv("OLLAMA_AUTO_PULL", "0").lower() in {
                "1",
                "true",
                "yes",
                "sim",
            }
            _client = _ollama.Client(host=_host)
            # Aguarda o Ollama subir (até 60 s)
            for _ in range(12):
                try:
                    _client.list()
                    break
                except Exception:
                    time.sleep(5)
            available = [m.model for m in _client.list().models]
            if not any(m.startswith(_model.split(":")[0]) and _model in m or m == _model
                       for m in available):
                logger.info("[Startup] Modelo Ollama '%s' não encontrado — iniciando pull...", _model)
                if not _auto_pull:
                    logger.warning(
                        "[Startup] Modelo Ollama '%s' ausente. "
                        "Use OLLAMA_AUTO_PULL=1 ou o servico ollama-setup.",
                        _model,
                    )
                    return
                _client.pull(_model)
                logger.info("[Startup] Pull do modelo '%s' concluído.", _model)
            else:
                logger.info("[Startup] Modelo Ollama '%s' já disponível.", _model)
        except Exception as exc:
            logger.warning("[Startup] Falha ao garantir modelo Ollama (não crítico): %s", exc)

    threading.Thread(target=_warmup, daemon=True).start()
