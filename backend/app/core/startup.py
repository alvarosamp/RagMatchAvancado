from __future__ import annotations

import os
import threading
import time

from sqlalchemy.orm import Session

from app.core.features import AI_FEATURES_ENABLED
from app.logs.config import logger


def register_startup_tasks(app) -> None:
    @app.on_event("startup")
    def on_startup():
        _init_database()
        _start_warmup_thread()


def _init_database() -> None:
    from app.db.init_db import init_db
    from app.db.session import SessionLocal

    db: Session = SessionLocal()
    try:
        result = init_db(db)
        logger.info("Banco inicializado: %s", result)
    except Exception as exc:
        logger.error("Erro no startup: %s", exc)
        raise
    finally:
        db.close()


def _start_warmup_thread() -> None:
    threading.Thread(target=_warmup_models, daemon=True).start()


def _warmup_models() -> None:
    try:
        logger.info("[Startup] Pre-aquecendo modelos OCR/Docling...")
        from app.pipeline.docling_parser import parse_pdf  # noqa: F401

        logger.info("[Startup] Modelos prontos.")
    except Exception as exc:
        logger.warning("[Startup] Falha no pre-aquecimento (nao critico): %s", exc)

    if AI_FEATURES_ENABLED:
        _ensure_ollama_models()
    else:
        logger.info("[Startup] Recursos de IA desabilitados; pulando inicializacao do Ollama.")


def _ensure_ollama_models() -> None:
    try:
        import ollama as _ollama

        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        models = [
            os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
            os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        ]
        auto_pull = os.getenv("OLLAMA_AUTO_PULL", "0").lower() in {
            "1",
            "true",
            "yes",
            "sim",
        }
        client = _ollama.Client(host=host)

        for _ in range(12):
            try:
                client.list()
                break
            except Exception:
                time.sleep(5)

        available = [model.model for model in client.list().models]
        for model in dict.fromkeys(candidate for candidate in models if candidate):
            if any(candidate == model or candidate.startswith(f"{model}:") for candidate in available):
                logger.info("[Startup] Modelo Ollama '%s' ja disponivel.", model)
                continue

            logger.info("[Startup] Modelo Ollama '%s' nao encontrado; iniciando pull...", model)
            if not auto_pull:
                logger.warning(
                    "[Startup] Modelo Ollama '%s' ausente. Use OLLAMA_AUTO_PULL=1 ou o servico ollama-setup.",
                    model,
                )
                continue
            client.pull(model)
            logger.info("[Startup] Pull do modelo '%s' concluido.", model)
    except Exception as exc:
        logger.warning("[Startup] Falha ao garantir modelo Ollama (nao critico): %s", exc)
