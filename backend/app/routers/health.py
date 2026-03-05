from fastapi import APIRouter
from app.logs.config import logger
router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    logger.info("Health check requested.")
    return {"status": "ok"}