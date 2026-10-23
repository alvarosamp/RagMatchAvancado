import hashlib
import hmac
from unittest.mock import Mock

import pytest
from app.market_intelligence.connectors import (
    BlingReader,
    ReadClient,
    verify_bling_signature,
)
from app.services.pncp_client import parse_pncp_id


def test_webhook_authenticates_exact_bytes():
    body = b'{"companyId":1}'
    signature = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_bling_signature(body, signature, "secret")
    assert not verify_bling_signature(body + b" ", signature, "secret")


def test_rate_limit_is_retried_before_page_is_published():
    throttled = Mock(status_code=429, headers={"Retry-After": "1"})
    success = Mock(status_code=200)
    success.json.return_value = {"data": [{"id": 1}]}
    session = Mock()
    session.get.side_effect = [throttled, success]
    sleeper = Mock()
    result = ReadClient(session, sleeper).get("https://source.invalid")
    assert result["data"] == [{"id": 1}]
    sleeper.assert_called_once_with(1)


def test_incomplete_bling_pagination_raises_instead_of_advancing_watermark():
    client = Mock()
    client._request.side_effect = [{"data": [{"id": i} for i in range(100)]}] + [
        {"data": {"id": i}} for i in range(100)
    ]
    with pytest.raises(ValueError, match="Limite"):
        list(
            BlingReader(client, sleeper=lambda _: None).records("product", max_pages=1)
        )


def test_pncp_id_accepts_new_cnpj_format():
    result = parse_pncp_id("00000000E08G12-1-123/2026")
    assert result.cnpj == "00000000E08G12"
