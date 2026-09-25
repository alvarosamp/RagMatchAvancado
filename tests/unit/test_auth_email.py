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


def test_google_relay_uses_starttls_without_password(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp-relay.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "nao-responda@example.com")
    monkeypatch.setenv("PASSWORD_RESET_URL_BASE", "https://app.example.com/redefinir-senha")
    monkeypatch.setenv("SMTP_USE_TLS", "1")
    monkeypatch.setenv("SMTP_USE_SSL", "0")
    monkeypatch.setenv("SMTP_LOCAL_HOSTNAME", "api.example.com")
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    client = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = client
    smtp = MagicMock(return_value=context)
    monkeypatch.setattr(auth_email.smtplib, "SMTP", smtp)

    assert auth_email.send_password_reset_email("user@example.net", "token") is True

    assert smtp.call_args.kwargs["local_hostname"] == "api.example.com"
    client.starttls.assert_called_once()
    client.login.assert_not_called()
    client.send_message.assert_called_once()
    assert client.send_message.call_args.kwargs["from_addr"] == "nao-responda@example.com"


def test_smtp_rejects_partial_credentials(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp-relay.gmail.com")
    monkeypatch.setenv("SMTP_USER", "relay@example.com")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    message = auth_email.EmailMessage()
    message["From"] = "nao-responda@example.com"

    try:
        auth_email.send_email_message(message)
    except ValueError as exc:
        assert "definidos juntos" in str(exc)
    else:
        raise AssertionError("Credenciais SMTP parciais deveriam falhar")
