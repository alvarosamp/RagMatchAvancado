from __future__ import annotations

import email
import imaplib
import os
import re
import time
from email.header import decode_header
from email.message import Message
from threading import Thread
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.crm.models import CrmNotice, CrmNoticeHistory
from app.db.session import SessionLocal
from app.logs.config import logger


def email_monitor_configured() -> bool:
    return bool(os.getenv("EMAIL_MONITOR_IMAP_HOST") and os.getenv("EMAIL_MONITOR_USER") and os.getenv("EMAIL_MONITOR_PASSWORD"))


def run_email_monitor_once(db: Session, *, limit: int | None = None) -> dict[str, Any]:
    if not email_monitor_configured():
        return {"configured": False, "processed": 0, "matched": 0, "message": "Configure EMAIL_MONITOR_IMAP_HOST, EMAIL_MONITOR_USER e EMAIL_MONITOR_PASSWORD."}

    limit = limit or int(os.getenv("EMAIL_MONITOR_MAX_MESSAGES", "25"))
    mailbox = os.getenv("EMAIL_MONITOR_MAILBOX", "INBOX")
    only_unseen = os.getenv("EMAIL_MONITOR_ONLY_UNSEEN", "1").lower() in {"1", "true", "yes", "sim"}
    processed = 0
    matched = 0
    notices = _load_candidate_notices(db)

    with _connect_imap() as client:
        client.select(mailbox)
        status, data = client.search(None, "UNSEEN" if only_unseen else "ALL")
        if status != "OK":
            return {"configured": True, "processed": 0, "matched": 0, "message": "Nao foi possivel buscar mensagens no IMAP."}
        ids = (data[0] or b"").split()[-limit:]
        for message_id in ids:
            status, payload = client.fetch(message_id, "(RFC822)")
            if status != "OK" or not payload:
                continue
            raw = next((part[1] for part in payload if isinstance(part, tuple)), None)
            if not raw:
                continue
            processed += 1
            msg = email.message_from_bytes(raw)
            match = _match_message_to_notice(db, msg, notices)
            if match is not None:
                matched += 1
                _record_message(db, match, msg)
    db.commit()
    return {"configured": True, "processed": processed, "matched": matched}


def start_email_monitor_loop() -> None:
    if not email_monitor_configured():
        logger.info("[EmailMonitor] IMAP nao configurado; rotina desativada.")
        return
    if os.getenv("EMAIL_MONITOR_ENABLED", "0").lower() not in {"1", "true", "yes", "sim"}:
        logger.info("[EmailMonitor] Configure EMAIL_MONITOR_ENABLED=1 para ativar a rotina automatica.")
        return

    interval = max(60, int(os.getenv("EMAIL_MONITOR_INTERVAL_SECONDS", "300")))

    def _loop() -> None:
        while True:
            db = SessionLocal()
            try:
                summary = run_email_monitor_once(db)
                logger.info("[EmailMonitor] Ciclo concluido: %s", summary)
            except Exception as exc:
                logger.warning("[EmailMonitor] Falha no ciclo: %s", exc)
            finally:
                db.close()
            time.sleep(interval)

    Thread(target=_loop, daemon=True).start()


def _connect_imap() -> imaplib.IMAP4_SSL:
    host = os.environ["EMAIL_MONITOR_IMAP_HOST"]
    port = int(os.getenv("EMAIL_MONITOR_IMAP_PORT", "993"))
    client = imaplib.IMAP4_SSL(host, port)
    client.login(os.environ["EMAIL_MONITOR_USER"], os.environ["EMAIL_MONITOR_PASSWORD"])
    return client


def _load_candidate_notices(db: Session) -> list[CrmNotice]:
    return (
        db.query(CrmNotice)
        .options(joinedload(CrmNotice.organ), joinedload(CrmNotice.portal))
        .order_by(CrmNotice.updated_at.desc())
        .limit(int(os.getenv("EMAIL_MONITOR_NOTICE_LIMIT", "500")))
        .all()
    )


def _match_message_to_notice(db: Session, msg: Message, notices: list[CrmNotice]) -> CrmNotice | None:
    haystack = _normalize(" ".join([_decode_header(msg.get("Subject")), msg.get("From") or "", _message_text(msg)[:8000]]))
    for notice in notices:
        tokens = [
            notice.tor_id,
            notice.number,
            getattr(notice, "bid_number", None),
            notice.uasg,
            notice.organ.name if notice.organ else None,
        ]
        for token in tokens:
            clean = _normalize(token)
            if clean and len(clean) >= 4 and clean in haystack:
                return notice
    return None


def _record_message(db: Session, notice: CrmNotice, msg: Message) -> None:
    provider_id = msg.get("Message-ID") or f"{msg.get('Date')}|{msg.get('Subject')}|{msg.get('From')}"
    action = f"Email monitorado: {provider_id}"
    exists = (
        db.query(CrmNoticeHistory.id)
        .filter(CrmNoticeHistory.notice_id == notice.id, CrmNoticeHistory.action == action)
        .first()
    )
    if exists:
        return
    db.add(
        CrmNoticeHistory(
            tenant_id=notice.tenant_id,
            notice_id=notice.id,
            action=action,
            details={
                "from": msg.get("From"),
                "subject": _decode_header(msg.get("Subject")),
                "date": msg.get("Date"),
                "message_id": msg.get("Message-ID"),
            },
        )
    )


def _message_text(msg: Message) -> str:
    parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_content_type() not in {"text/plain", "text/html"}:
                continue
            parts.append(_payload_text(part))
    else:
        parts.append(_payload_text(msg))
    return "\n".join(parts)


def _payload_text(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset() or "utf-8"
    text = payload.decode(charset, errors="ignore")
    return re.sub(r"<[^>]+>", " ", text)


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    chunks = decode_header(value)
    output = []
    for text, charset in chunks:
        if isinstance(text, bytes):
            output.append(text.decode(charset or "utf-8", errors="ignore"))
        else:
            output.append(text)
    return "".join(output)


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()
