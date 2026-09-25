from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BlingSalesOrderPayload(BaseModel):
    """Required core of POST /pedidos/vendas; extra Bling fields pass through."""

    model_config = ConfigDict(extra="allow")

    data: date
    dataSaida: date
    dataPrevista: date
    contato: dict[str, Any]
    itens: list[dict[str, Any]] = Field(min_length=1)
    parcelas: list[dict[str, Any]]

    @model_validator(mode="after")
    def validate_references(self) -> BlingSalesOrderPayload:
        if not self.contato.get("id"):
            raise ValueError("contato.id é obrigatório para criar o pedido no Bling")
        for index, item in enumerate(self.itens):
            product = item.get("produto")
            if not isinstance(product, dict) or not product.get("id"):
                raise ValueError(f"itens[{index}].produto.id é obrigatório")
        return self


class BlingInvoicePayload(BaseModel):
    """Required core of POST /nfe; fiscal details remain API-compatible extras."""

    model_config = ConfigDict(extra="allow")

    tipo: Literal[0, 1]
    numero: str
    dataOperacao: str
    contato: dict[str, Any]
    naturezaOperacao: dict[str, Any]
    itens: list[dict[str, Any]] = Field(min_length=1)
    parcelas: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("numero", "dataOperacao")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("o valor não pode ficar vazio")
        return value

    @model_validator(mode="after")
    def validate_references(self) -> BlingInvoicePayload:
        if not self.naturezaOperacao.get("id"):
            raise ValueError("naturezaOperacao.id é obrigatório")
        required_contact = ("nome", "tipoPessoa", "numeroDocumento", "contribuinte")
        missing = [field for field in required_contact if self.contato.get(field) in (None, "")]
        if missing:
            raise ValueError(
                "campos obrigatórios ausentes em contato: " + ", ".join(missing)
            )
        return self


class BlingResponse(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class BlingCredentialsPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    client_id: str = Field(alias="clientId", min_length=10, max_length=255)
    client_secret: str = Field(alias="clientSecret", min_length=10, max_length=1000)


class BlingOAuthStartResponse(BaseModel):
    authorization_url: str = Field(alias="authorizationUrl")


class BlingIntegrationStatus(BaseModel):
    configured: bool
    connected: bool
    client_id_hint: str | None = Field(alias="clientIdHint")
    token_expires_at: datetime | None = Field(alias="tokenExpiresAt")
    scopes: list[str] = Field(default_factory=list)
