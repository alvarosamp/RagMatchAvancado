"""Security properties of password-reset e-mail delivery."""

from unittest.mock import MagicMock

from app.services import auth_email


def test_reset_email_requires_configuration(monkeypatch):
    for name in ("SMTP_HOST", "SMTP_FROM_EMAIL", "PASSWORD_RESET_URL_BASE"):
        monkeypatch.delenv(name, raising=False)

    assert auth_email.send_password_reset_email("user@example.com", "secret-token") is False


def test_reset_email_uses_encoded_one_time_token(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "no-reply@example.com")
    monkeypatch.setenv("PASSWORD_RESET_URL_BASE", "https://app.example.com/redefinir-senha")
    monkeypatch.setenv("SMTP_USE_TLS", "0")
    client = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = client
    smtp = MagicMock(return_value=context)
    monkeypatch.setattr(auth_email.smtplib, "SMTP", smtp)

    assert auth_email.send_password_reset_email("user@example.com", "token/with+chars") is True

    message = client.send_message.call_args.args[0]
    assert "token%2Fwith%2Bchars" in message.get_content()
    assert message["To"] == "user@example.com"
