import os
import re
from urllib.parse import quote

import httpx


class EvolutionUnavailable(RuntimeError):
    pass


def enabled() -> bool:
    return os.getenv("EVOLUTION_ENABLED", "0").lower() in {"1", "true"}


def configured() -> bool:
    return enabled() and all(os.getenv(name, "").strip() for name in (
        "EVOLUTION_BASE_URL", "EVOLUTION_API_KEY", "EVOLUTION_INSTANCE",
        "EVOLUTION_WEBHOOK_SECRET", "EVOLUTION_BOT_PHONE",
    ))


def send_text(phone: str, text: str) -> None:
    if not configured():
        raise EvolutionUnavailable("WhatsApp não configurado.")
    if not re.fullmatch(r"[1-9][0-9]{7,14}", phone):
        raise ValueError("Número deve incluir código do país.")
    base = os.environ["EVOLUTION_BASE_URL"].rstrip("/")
    instance = quote(os.environ["EVOLUTION_INSTANCE"], safe="")
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            response = client.post(
                f"{base}/message/sendText/{instance}",
                headers={"apikey": os.environ["EVOLUTION_API_KEY"]},
                json={"number": phone, "text": text[:3500], "linkPreview": False},
            )
            response.raise_for_status()
    except httpx.HTTPError:
        # Do not expose upstream response bodies, URLs or credentials in logs/API.
        raise EvolutionUnavailable("Não foi possível enviar pelo WhatsApp.") from None
