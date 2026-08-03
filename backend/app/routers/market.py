from fastapi import APIRouter

from app.core.config import settings
from app.market_profiles import get_market_profile


router = APIRouter(prefix="/market", tags=["mercado"])


@router.get("/profile")
def market_profile():
    return get_market_profile(settings.market_profile)
