import hmac
import os
import re
import secrets
from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.db.session import get_db
from app.integrations.evolution.client import EvolutionUnavailable, configured, enabled, send_text
from app.integrations.evolution.models import WhatsAppContact
from app.integrations.evolution.service import (
    aware, company_answer, digest, process_message, utcnow, valid_user,
)

router = APIRouter(prefix="/integrations/whatsapp", tags=["whatsapp"])


def require_configured():
    if not configured():
        raise HTTPException(503, "WhatsApp ainda não configurado pelo administrador.")


@router.get("/me")
def status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contact = db.get(WhatsAppContact, user.id)
    linked = bool(contact and contact.phone and valid_user(db, contact))
    return {
        "enabled": enabled(), "configured": configured(), "linked": linked,
        "phone_suffix": contact.phone[-4:] if linked else None,
        "notifications_enabled": bool(linked and contact.notifications_enabled),
        "provider": "Evolution API",
    }


@router.post("/link", dependencies=[Depends(require_configured)])
def link(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bot = os.environ["EVOLUTION_BOT_PHONE"]
    if not re.fullmatch(r"[1-9][0-9]{7,14}", bot):
        raise HTTPException(503, "Número do atendimento não configurado corretamente.")
    contact = db.query(WhatsAppContact).filter(WhatsAppContact.user_id == user.id).with_for_update().first()
    if not contact:
        contact = WhatsAppContact(user_id=user.id, tenant_id=user.tenant_id)
        db.add(contact)
    # Relinking revokes the old phone and requires fresh consent for notifications.
    token = secrets.token_hex(16)
    contact.phone = None
    contact.notifications_enabled = False
    contact.token_hash = digest(token)
    contact.token_expires_at = utcnow() + timedelta(minutes=10)
    contact.auth_version = int(user.auth_version or 0)
    contact.tenant_id = user.tenant_id
    db.commit()
    text = f"VINCULAR {token}"
    return {"message": text, "expires_in_seconds": 600, "url": f"https://wa.me/{bot}?text={quote(text)}"}


@router.delete("/me")
def unlink(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contact = db.query(WhatsAppContact).filter(WhatsAppContact.user_id == user.id).with_for_update().first()
    if contact:
        db.delete(contact)
        db.commit()
    return {"linked": False}


class Preferences(BaseModel):
    notifications_enabled: bool


@router.patch("/me", dependencies=[Depends(require_configured)])
def preferences(payload: Preferences, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contact = db.query(WhatsAppContact).filter(WhatsAppContact.user_id == user.id).with_for_update().first()
    if not contact or not contact.phone or not valid_user(db, contact):
        raise HTTPException(409, "Vincule seu WhatsApp primeiro.")
    contact.notifications_enabled = payload.notifications_enabled
    db.commit()
    return {"notifications_enabled": contact.notifications_enabled}


@router.post("/test", dependencies=[Depends(require_configured)])
def test_message(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contact = db.query(WhatsAppContact).filter(WhatsAppContact.user_id == user.id).with_for_update().first()
    if not contact or not contact.phone or not valid_user(db, contact):
        raise HTTPException(409, "Vincule seu WhatsApp primeiro.")
    if contact.last_request_at and (utcnow() - aware(contact.last_request_at)).total_seconds() < 30:
        raise HTTPException(429, "Aguarde 30 segundos entre os testes.")
    contact.last_request_at = utcnow()
    phone = contact.phone
    text = company_answer(db, user, "resumo")
    db.commit()
    try:
        send_text(phone, text)
    except EvolutionUnavailable as exc:
        raise HTTPException(502, str(exc)) from None
    return {"sent": True}


@router.post("/webhook", dependencies=[Depends(require_configured)])
def webhook(payload: dict, x_webhook_secret: str = Header(default=""), db: Session = Depends(get_db)):
    expected = os.environ["EVOLUTION_WEBHOOK_SECRET"]
    if not hmac.compare_digest(x_webhook_secret.encode(), expected.encode()):
        raise HTTPException(401, "Webhook não autorizado.")
    try:
        return {"status": process_message(db, payload)}
    except IntegrityError:
        db.rollback()
        return {"status": "ignored"}
    except EvolutionUnavailable:
        # State/dedupe is already committed. Do not repeat an uncertain send.
        return {"status": "send_failed"}
