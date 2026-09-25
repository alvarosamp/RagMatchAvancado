from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.integrations.bling.client import (
    BlingAPIError,
    BlingClient,
    BlingSettings,
)


def _response(status_code: int, payload: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


def test_create_sales_order_uses_v3_endpoint_and_jwt_headers():
    session = MagicMock()
    session.request.return_value = _response(201, {"data": {"id": 42}})
    client = BlingClient(
        BlingSettings(access_token="secret-token"), session=session
    )

    result = client.create_sales_order({"contato": {"id": 7}})

    assert result == {"data": {"id": 42}}
    _, url = session.request.call_args.args
    assert url.endswith("/pedidos/vendas")
    headers = session.request.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer secret-token"
    assert headers["enable-jwt"] == "1"


def test_unauthorized_request_refreshes_token_and_retries_once():
    session = MagicMock()
    token_update = MagicMock()
    session.request.side_effect = [
        _response(401, {"error": {"description": "expired"}}),
        _response(201, {"data": {"idNotaFiscal": 99}}),
    ]
    session.post.return_value = _response(
        200, {"access_token": "new-token", "refresh_token": "new-refresh"}
    )
    client = BlingClient(
        BlingSettings(
            access_token="old-token",
            refresh_token="old-refresh",
            client_id="client",
            client_secret="secret",
        ),
        session=session,
        token_update_handler=token_update,
    )

    result = client.create_invoice_from_sales_order(55)

    assert result["data"]["idNotaFiscal"] == 99
    assert session.request.call_count == 2
    retry_headers = session.request.call_args.kwargs["headers"]
    assert retry_headers["Authorization"] == "Bearer new-token"
    refresh_headers = session.post.call_args.kwargs["headers"]
    assert refresh_headers["enable-jwt"] == "1"
    token_update.assert_called_once_with(
        {"access_token": "new-token", "refresh_token": "new-refresh"}
    )


def test_exchange_authorization_code_uses_basic_auth_and_persists_tokens():
    session = MagicMock()
    session.post.return_value = _response(
        200,
        {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 21600,
        },
    )
    token_update = MagicMock()
    client = BlingClient(
        BlingSettings(client_id="client-id", client_secret="client-secret"),
        session=session,
        token_update_handler=token_update,
    )

    result = client.exchange_authorization_code("one-minute-code")

    assert result["access_token"] == "access"
    assert session.post.call_args.kwargs["data"] == {
        "grant_type": "authorization_code",
        "code": "one-minute-code",
    }
    auth = session.post.call_args.kwargs["auth"]
    assert auth.username == "client-id"
    assert auth.password == "client-secret"
    token_update.assert_called_once_with(result)


def test_bling_validation_error_is_sanitized_and_keeps_status():
    session = MagicMock()
    session.request.return_value = _response(
        400, {"error": {"description": "produto inexistente"}}
    )
    client = BlingClient(BlingSettings(access_token="token"), session=session)

    with pytest.raises(BlingAPIError) as exc_info:
        client.create_invoice({"tipo": 1})

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Bling: produto inexistente"


def test_authorize_invoice_sends_email_query_as_lowercase_boolean():
    session = MagicMock()
    session.request.return_value = _response(200, {"data": {"xml": "..."}})
    client = BlingClient(BlingSettings(access_token="token"), session=session)

    client.authorize_invoice(10, send_email=True)

    assert session.request.call_args.kwargs["params"] == {"enviarEmail": "true"}
