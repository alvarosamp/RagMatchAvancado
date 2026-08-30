import os

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.db.session import SessionLocal
from app.logs.config import logger
router = APIRouter(tags=["health"])


def _is_enabled(name: str) -> bool:
    return os.getenv(name, "0").strip().lower() in {"1", "true", "yes", "sim"}


def _check_ollama() -> None:
    """Ensure the models required by enabled AI features are available."""
    try:
        import ollama

        client = ollama.Client(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))
        available = {model.model for model in client.list().models}
        required = {
            os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
            os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        }
        missing = sorted(model for model in required if model and model not in available)
        if missing:
            raise RuntimeError(f"modelos ausentes: {', '.join(missing)}")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IA indisponivel.",
        ) from exc

@router.get("/health")
def health():
    logger.info("Health check requested.")
    return {"status": "ok"}


@router.get("/health/live")
def live():
    """Liveness probe: the API process can receive traffic."""
    return {"status": "ok"}


@router.get("/health/ready")
def ready():
    """Readiness probe: dependencies needed to handle CRM requests work."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                from redis import Redis
                Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1).ping()
            except Exception as exc:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis indisponivel.") from exc
        if _is_enabled("AI_FEATURES_ENABLED"):
            _check_ollama()
    finally:
        db.close()
    return {"status": "ready"}
