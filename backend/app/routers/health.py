import os

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.db.session import SessionLocal
from app.logs.config import logger
router = APIRouter(tags=["health"])

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
    finally:
        db.close()
    return {"status": "ready"}
