from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests
from requests import Response, Session
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException

DEFAULT_API_URL = "https://api.bling.com.br/Api/v3"
DEFAULT_OAUTH_URL = "https://api.bling.com.br/Api/v3/oauth/token"


class BlingError(RuntimeError):
    """Base error for failures while communicating with Bling."""


class BlingConfigurationError(BlingError):
    """Raised when required credentials are missing."""


class BlingAPIError(BlingError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class BlingSettings:
    access_token: str | None = None
    refresh_token: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    api_url: str = DEFAULT_API_URL
    oauth_url: str = DEFAULT_OAUTH_URL
    timeout_seconds: float = 30.0
    enable_jwt: bool = True

    @classmethod
    def from_env(cls) -> BlingSettings:
        return cls(
            access_token=os.getenv("BLING_ACCESS_TOKEN"),
            refresh_token=os.getenv("BLING_REFRESH_TOKEN"),
            client_id=os.getenv("BLING_CLIENT_ID"),
            client_secret=os.getenv("BLING_CLIENT_SECRET"),
            api_url=os.getenv("BLING_API_URL", DEFAULT_API_URL).rstrip("/"),
            oauth_url=os.getenv("BLING_OAUTH_URL", DEFAULT_OAUTH_URL),
            timeout_seconds=float(os.getenv("BLING_TIMEOUT_SECONDS", "30")),
            enable_jwt=os.getenv("BLING_ENABLE_JWT", "1").lower()
            in {"1", "true", "yes", "sim"},
        )


class BlingClient:
    """Small server-side client for the Bling API v3."""

    def __init__(
        self,
        settings: BlingSettings | None = None,
        session: Session | None = None,
        token_update_handler: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.settings = settings or BlingSettings.from_env()
        self.session = session or requests.Session()
        self._access_token = self.settings.access_token
        self._refresh_token = self.settings.refresh_token
        self._token_update_handler = token_update_handler

    @property
    def configured(self) -> bool:
        return bool(self._access_token or self._can_refresh())

    def create_sales_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/pedidos/vendas", json=payload)

    def create_invoice_from_sales_order(self, sales_order_id: int) -> dict[str, Any]:
        return self._request(
            "POST", f"/pedidos/vendas/{sales_order_id}/gerar-nfe"
        )

    def create_invoice(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/nfe", json=payload)

    def authorize_invoice(
        self, invoice_id: int, *, send_email: bool = False
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/nfe/{invoice_id}/enviar",
            params={"enviarEmail": str(send_email).lower()},
        )

    def exchange_authorization_code(self, code: str) -> dict[str, Any]:
        return self._request_token(
            {"grant_type": "authorization_code", "code": code}
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if not self._access_token:
            self._refresh_access_token()

        response = self._send(method, path, **kwargs)
        if response.status_code == 401 and self._can_refresh():
            self._refresh_access_token()
            response = self._send(method, path, **kwargs)
        return self._decode_response(response)

    def _send(self, method: str, path: str, **kwargs: Any) -> Response:
        if not self._access_token:
            raise BlingConfigurationError(
                "Integração Bling sem access token e sem credenciais de renovação."
            )
        headers = dict(kwargs.pop("headers", {}))
        headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {self._access_token}",
            }
        )
        if self.settings.enable_jwt:
            headers["enable-jwt"] = "1"
        try:
            return self.session.request(
                method,
                f"{self.settings.api_url}{path}",
                headers=headers,
                timeout=self.settings.timeout_seconds,
                **kwargs,
            )
        except RequestException as exc:
            raise BlingAPIError(502, "Não foi possível conectar à API do Bling.") from exc

    def _can_refresh(self) -> bool:
        return bool(
            self._refresh_token
            and self.settings.client_id
            and self.settings.client_secret
        )

    def _refresh_access_token(self) -> None:
        if not self._can_refresh():
            raise BlingConfigurationError(
                "A conexão Bling não possui token e credenciais de renovação válidos."
            )

        data = self._request_token(
            {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            }
        )
        self._access_token = str(data["access_token"])
        if data.get("refresh_token"):
            self._refresh_token = str(data["refresh_token"])

    def _request_token(self, grant_data: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.client_id or not self.settings.client_secret:
            raise BlingConfigurationError("Credenciais OAuth do Bling ausentes.")
        headers = {"Accept": "application/json"}
        if self.settings.enable_jwt:
            headers["enable-jwt"] = "1"
        try:
            response = self.session.post(
                self.settings.oauth_url,
                data=grant_data,
                headers=headers,
                auth=HTTPBasicAuth(
                    self.settings.client_id or "", self.settings.client_secret or ""
                ),
                timeout=self.settings.timeout_seconds,
            )
        except RequestException as exc:
            raise BlingAPIError(502, "Não foi possível renovar o token do Bling.") from exc

        data = self._decode_response(response)
        if not data.get("access_token"):
            raise BlingAPIError(502, "O Bling não retornou um novo access token.")
        if self._token_update_handler:
            self._token_update_handler(data)
        return data

    @staticmethod
    def _decode_response(response: Response) -> dict[str, Any]:
        if response.status_code == 204:
            return {}
        try:
            body = response.json()
        except ValueError:
            body = None

        if not 200 <= response.status_code < 300:
            detail = BlingClient._error_detail(body)
            raise BlingAPIError(response.status_code, detail)
        if not isinstance(body, dict):
            raise BlingAPIError(502, "O Bling retornou uma resposta inválida.")
        return body

    @staticmethod
    def _error_detail(body: Any) -> str:
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                for key in ("description", "message", "type"):
                    value = error.get(key)
                    if value:
                        return f"Bling: {value}"
            for key in ("message", "detail", "error_description"):
                value = body.get(key)
                if isinstance(value, str) and value:
                    return f"Bling: {value}"
        return "A API do Bling rejeitou a operação."
