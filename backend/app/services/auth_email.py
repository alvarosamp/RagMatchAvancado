"""Transactional authentication e-mails using the Python standard library."""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote

from app.logs.config import logger


def password_reset_email_configured() -> bool:
    return bool(
        os.getenv("SMTP_HOST")
        and os.getenv("SMTP_FROM_EMAIL")
        and os.getenv("PASSWORD_RESET_URL_BASE")
    )


def send_email_message(message: EmailMessage) -> None:
    """Send one message using the configured SMTP relay."""
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    use_ssl = os.getenv("SMTP_USE_SSL", "0").lower() in {"1", "true", "yes"}
    use_tls = os.getenv("SMTP_USE_TLS", "1").lower() in {"1", "true", "yes"}
    timeout = max(1, int(os.getenv("SMTP_TIMEOUT_SECONDS", "15")))
    local_hostname = os.getenv("SMTP_LOCAL_HOSTNAME") or None
    if bool(username) != bool(password):
        raise ValueError("SMTP_USER e SMTP_PASSWORD devem ser definidos juntos ou ambos vazios.")
    if use_ssl and use_tls:
        raise ValueError("Use SMTP_USE_SSL ou SMTP_USE_TLS, não ambos.")

    tls_context = ssl.create_default_context()
    if use_ssl:
        client_context = smtplib.SMTP_SSL(
            host,
            port,
            timeout=timeout,
            local_hostname=local_hostname,
            context=tls_context,
        )
    else:
        client_context = smtplib.SMTP(
            host,
            port,
            timeout=timeout,
            local_hostname=local_hostname,
        )

    with client_context as client:
        client.ehlo()
        if use_tls:
            client.starttls(context=tls_context)
            client.ehlo()
        if username:
            client.login(username, password)
        client.send_message(message, from_addr=message["From"])


def send_password_reset_email(recipient: str, token: str) -> bool:
    """Send a reset link without logging or persisting the raw token."""
    if not password_reset_email_configured():
        logger.error("[Auth] SMTP de recuperacao de senha nao configurado.")
        return False

    base_url = os.environ["PASSWORD_RESET_URL_BASE"]
    separator = "&" if "?" in base_url else "?"
    reset_url = f"{base_url}{separator}token={quote(token, safe='')}"

    message = EmailMessage()
    message["Subject"] = "Redefinicao de senha"
    message["From"] = os.environ["SMTP_FROM_EMAIL"]
    message["To"] = recipient
    message.set_content(
        "Recebemos uma solicitacao para redefinir sua senha.\n\n"
        f"Acesse: {reset_url}\n\n"
        "O link expira em breve e pode ser usado apenas uma vez. "
        "Se voce nao fez esta solicitacao, ignore este e-mail."
    )

    send_email_message(message)
    return True
