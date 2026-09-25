"""Send an operational SMTP test using the same code path as the API."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.auth_email import password_reset_email_configured, send_email_message


def main() -> None:
    parser = argparse.ArgumentParser(description="Envia um e-mail de teste pelo relay configurado.")
    parser.add_argument("--to", required=True, help="Destinatário do teste")
    args = parser.parse_args()
    if not password_reset_email_configured():
        raise RuntimeError("Configure SMTP_HOST, SMTP_FROM_EMAIL e PASSWORD_RESET_URL_BASE.")

    message = EmailMessage()
    message["Subject"] = "Teste SMTP RagMatch"
    message["From"] = os.environ["SMTP_FROM_EMAIL"]
    message["To"] = args.to
    message.set_content(
        "Envio SMTP do RagMatch validado em "
        f"{datetime.now(timezone.utc).isoformat()}.\n"
    )
    send_email_message(message)
    print(f"E-mail de teste aceito pelo relay para {args.to}.")


if __name__ == "__main__":
    main()
