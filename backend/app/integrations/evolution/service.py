from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm.models import CrmNotice, CrmNoticeOutcome
from app.db.session import set_tenant_context
from app.integrations.evolution.client import EvolutionUnavailable, configured, send_text
from app.integrations.evolution.models import WhatsAppContact, WhatsAppDelivery
from app.logs.config import logger

LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
MENU = (
    "Comandos disponíveis:\n"
    "RESUMO — quantidade de editais da empresa\n"
    "EDITAIS — últimos 5 editais cadastrados no CRM\n"
    "PRAZOS — próximas sessões em até 7 dias\n"
    "PARAR — desativar resumo diário\n"
    "VOLTAR — ativar resumo diário\n"
    "DESVINCULAR — remover acesso pelo WhatsApp\n"
    "Nesta versão, use os comandos acima para consultar os dados."
)


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def command(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower().strip())
                   if not unicodedata.combining(c))


def parse_message(payload: dict) -> tuple[str, str, str] | None:
    """Accept direct, textual, live upserts only; never trust a payload tenant id."""
    event = payload.get("event")
    if not isinstance(event, str) or event.lower().replace("_", ".") != "messages.upsert":
        return None
    if payload.get("instance") != os.getenv("EVOLUTION_INSTANCE"):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    key, message = data.get("key"), data.get("message")
    if not isinstance(key, dict) or not isinstance(message, dict):
        return None
    if key.get("fromMe") is not False:
        return None
    jid = key.get("remoteJid", "")
    # For a direct LID chat, use only the PN identity provided by Evolution.
    # Never treat LID digits as a phone or use group participant identities.
    if isinstance(jid, str) and re.fullmatch(r"[0-9]+@lid", jid):
        jid = key.get("remoteJidAlt", "")
    if not isinstance(jid, str) or not re.fullmatch(r"[1-9][0-9]{7,14}@s\.whatsapp\.net", jid):
        return None
    message_id = key.get("id")
    if not isinstance(message_id, str) or not 1 <= len(message_id) <= 200:
        return None
    extended = message.get("extendedTextMessage") or {}
    text = message.get("conversation") or (extended.get("text") if isinstance(extended, dict) else None)
    if not isinstance(text, str) or not 1 <= len(text) <= 500:
        return None
    # Ignore stale events so old commands cannot re-enable notifications/relink.
    try:
        timestamp = float(data.get("messageTimestamp", 0))
        if not -60 <= utcnow().timestamp() - timestamp <= 300:
            return None
    except (TypeError, ValueError, OverflowError):
        return None
    return jid.split("@")[0], text.strip(), message_id


def valid_user(db: Session, contact: WhatsAppContact) -> User | None:
    user = db.get(User, contact.user_id)
    if (not user or not user.is_active or not user.tenant or not user.tenant.is_active
            or user.tenant_id != contact.tenant_id
            or int(user.auth_version or 0) != contact.auth_version):
        return None
    set_tenant_context(db, user.tenant_id)
    return user


def reserve_delivery(db: Session, key: str) -> bool:
    """Reserve before the network call: at most one attempt, including timeouts."""
    try:
        with db.begin_nested():
            db.add(WhatsAppDelivery(key=digest(key), created_at=utcnow()))
            db.flush()
    except IntegrityError:
        return False
    return True


def company_answer(db: Session, user: User, text: str) -> str:
    query = db.query(CrmNotice).filter(CrmNotice.tenant_id == user.tenant_id)
    cmd = command(text)
    heading = f"Empresa: {user.tenant.name[:120]}\n"
    if cmd in {"resumo", "1"}:
        total = query.count()
        pending = query.filter(CrmNotice.outcome == CrmNoticeOutcome.PENDING).count()
        return heading + f"Editais no CRM: {total}\nCom resultado pendente: {pending}\nEnvie PRAZOS ou EDITAIS para detalhes."
    if cmd in {"editais", "2"}:
        notices = query.order_by(CrmNotice.created_at.desc(), CrmNotice.id).limit(5).all()
        lines = [f"• {n.number[:70]}: {(n.title or 'Sem título')[:180]} — {getattr(n.stage, 'value', n.stage)}" for n in notices]
        return heading + ("Últimos editais cadastrados:\n" + "\n".join(lines) if lines else "Nenhum edital cadastrado no CRM.")
    if cmd in {"prazos", "3"}:
        # CRM auction_date is a timezone-naive Brazilian local datetime.
        now = utcnow().astimezone(LOCAL_TZ).replace(tzinfo=None)
        notices = query.filter(
            CrmNotice.auction_date >= now,
            CrmNotice.auction_date <= now + timedelta(days=7),
            CrmNotice.outcome == CrmNoticeOutcome.PENDING,
        ).order_by(CrmNotice.auction_date, CrmNotice.id).limit(5).all()
        lines = [f"• {n.number[:70]}: {n.auction_date:%d/%m/%Y %H:%M}" for n in notices]
        return heading + ("Próximas sessões (horário de Brasília):\n" + "\n".join(lines) if lines else "Nenhuma sessão pendente nos próximos 7 dias.")
    return MENU


def process_message(db: Session, payload: dict) -> str:
    parsed = parse_message(payload)
    if not parsed:
        return "ignored"
    phone, text, message_id = parsed
    cmd = command(text)
    linking = cmd.startswith("vincular ")
    if linking:
        token = text.split(maxsplit=1)[1]
        contact = db.query(WhatsAppContact).filter(
            WhatsAppContact.token_hash == digest(token),
        ).with_for_update().first()
        if not contact or not contact.token_expires_at or aware(contact.token_expires_at) <= utcnow():
            return "ignored"
        existing = db.query(WhatsAppContact).filter(WhatsAppContact.phone == phone).first()
        if existing and existing.user_id != contact.user_id:
            return "ignored"
    else:
        contact = db.query(WhatsAppContact).filter(WhatsAppContact.phone == phone).with_for_update().first()
    if not contact:
        return "ignored"
    user = valid_user(db, contact)
    if not user:
        return "ignored"
    if contact.last_request_at and (utcnow() - aware(contact.last_request_at)).total_seconds() < 3:
        return "ignored"
    if not reserve_delivery(db, f"in:{os.environ['EVOLUTION_INSTANCE']}:{phone}:{message_id}"):
        return "duplicate"
    contact.last_request_at = utcnow()
    if linking:
        contact.phone, contact.token_hash, contact.token_expires_at = phone, None, None
        answer = "WhatsApp vinculado à sua conta.\n" + MENU
    elif cmd in {"parar", "stop", "sair"}:
        contact.notifications_enabled = False
        answer = "Resumo diário desativado. Você ainda pode consultar os dados. Envie VOLTAR para reativar."
    elif cmd == "voltar":
        contact.notifications_enabled = True
        answer = "Resumo diário ativado. Envie PARAR para desativar."
    elif cmd == "desvincular":
        db.delete(contact)
        answer = "Acesso pelo WhatsApp removido. Para reconectar, use as configurações do sistema."
    else:
        answer = company_answer(db, user, text)
    # Commit state/dedupe before sending: uncertain network outcomes are not retried.
    db.commit()
    send_text(phone, answer)
    return "processed"


def send_daily_summaries(db: Session) -> int:
    if not configured():
        return 0
    local_now = utcnow().astimezone(LOCAL_TZ)
    if local_now.hour < int(os.getenv("EVOLUTION_DIGEST_HOUR", "9")):
        return 0
    db.query(WhatsAppDelivery).filter(WhatsAppDelivery.created_at < utcnow() - timedelta(days=14)).delete()
    db.commit()
    ids = [row.user_id for row in db.query(WhatsAppContact).filter(
        WhatsAppContact.phone.isnot(None), WhatsAppContact.notifications_enabled.is_(True),
    ).all()]
    sent = 0
    for user_id in ids:
        try:
            contact = db.query(WhatsAppContact).filter(
                WhatsAppContact.user_id == user_id,
            ).with_for_update().first()
            if not contact or not contact.phone or not contact.notifications_enabled:
                continue
            user = valid_user(db, contact)
            if not user:
                continue
            if not reserve_delivery(db, f"daily:{local_now.date()}:{user_id}"):
                continue
            phone = contact.phone
            answer = "Resumo diário\n" + company_answer(db, user, "resumo") + "\n\n" + company_answer(db, user, "prazos") + "\n\nEnvie PARAR para desativar."
            db.commit()
            send_text(phone, answer)
            sent += 1
        except EvolutionUnavailable:
            logger.warning("[WhatsApp] Resumo diário não enviado para user_id=%s", user_id)
        except Exception:
            db.rollback()
            logger.warning("[WhatsApp] Falha ao preparar resumo para user_id=%s", user_id)
        finally:
            # Release row locks even for skipped contacts; clear prior tenant context.
            db.rollback()
    return sent
