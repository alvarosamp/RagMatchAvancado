from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["crm", "bling", "pncp", "ibge", "models", "quality", "marts"] = (
        "crm"
    )
    date_from: date | None = None
    date_to: date | None = None
    resources: list[
        Literal[
            "product",
            "supplier",
            "product_supplier",
            "purchase",
            "sale",
            "proposal",
            "inventory",
        ]
    ] = Field(
        default_factory=lambda: [
            "product",
            "supplier",
            "product_supplier",
            "purchase",
            "sale",
            "proposal",
            "inventory",
        ]
    )
    modalities: list[int] = Field(
        default_factory=lambda: [6], min_length=1, max_length=20
    )
    task: Literal[
        "technical_match",
        "entity_resolution",
        "win_probability",
        "bid_no_bid",
        "supplier_delay",
        "demand_forecast",
        "price_forecast",
        "catalog_clusters",
        "price_anomaly",
    ] = "win_probability"
    table: Literal[1737, 6903] = 1737
    variable: int = Field(default=2266, gt=0)

    @model_validator(mode="after")
    def dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("Período invertido.")
        if (
            self.date_from
            and self.date_to
            and (self.date_to - self.date_from).days > 3660
        ):
            raise ValueError("Backfill limitado a dez anos por execução.")
        if len(set(self.resources)) != len(self.resources):
            raise ValueError("Recursos duplicados.")
        return self


class ImportRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal[
        "product",
        "supplier",
        "brand",
        "category",
        "product_supplier",
        "demand",
        "match",
        "offer",
        "purchase",
        "sale",
        "award",
        "price",
        "inventory",
        "index",
    ]
    data: dict[str, Any]

    @model_validator(mode="after")
    def contract(self):
        data = self.data
        if not data.get("id") or len(str(data["id"])) > 180:
            raise ValueError(
                "Cada registro exige identidade de origem de até 180 caracteres."
            )
        if self.kind not in {
            "product",
            "supplier",
            "brand",
            "category",
            "product_supplier",
        }:
            if not data.get("event_at"):
                raise ValueError("Fatos importados exigem data do evento.")
            datetime.fromisoformat(str(data["event_at"]).replace("Z", "+00:00"))
        for key in (
            "quantity",
            "unit_price",
            "cost",
            "reference_price",
            "total_value",
            "winning_price",
            "offered_price",
        ):
            if key in data and data[key] is not None:
                try:
                    value = Decimal(str(data[key]))
                except InvalidOperation as error:
                    raise ValueError(f"Valor inválido: {key}.") from error
                if not value.is_finite() or value < 0 or value >= Decimal("1e14"):
                    raise ValueError(f"Valor inválido: {key}.")
        if self.kind == "price" and data.get("price_type") not in {
            "reference_price",
            "supplier_cost",
            "minimum_viable_price",
            "offered_price",
            "winning_price",
            "sales_price",
            "list_price",
        }:
            raise ValueError("Tipo semântico de preço inválido.")
        if (
            len(str(data.get("name", ""))) > 500
            or len(str(data.get("category", ""))) > 160
        ):
            raise ValueError("Nome ou categoria excede o limite.")
        return self


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["manual", "cnpj"] = "manual"
    records: list[ImportRecord] = Field(min_length=1, max_length=1000)


class ReviewRequest(BaseModel):
    decision: Literal["accepted", "rejected"]


class AliasRequest(BaseModel):
    alias: str = Field(min_length=1, max_length=160)
    canonical: str = Field(min_length=1, max_length=160)


class FeedbackRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=180)
    action: Literal[
        "bid",
        "no_bid",
        "supplier_selected",
        "price_adjusted",
        "technical_review",
        "confirmed_gap",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def evidence(self):
        if self.action in {
            "no_bid",
            "confirmed_gap",
            "technical_review",
        } and not self.payload.get("reason"):
            raise ValueError("Esta decisão exige motivo documentado.")
        if self.action == "technical_review" and self.payload.get("verdict") not in {
            "ATENDE",
            "VERIFICAR",
            "NAO_ATENDE",
        }:
            raise ValueError("Veredito técnico inválido.")
        if self.action == "supplier_selected" and not self.payload.get("supplier_id"):
            raise ValueError("Informe o fornecedor canônico.")
        if self.action == "price_adjusted":
            try:
                value = Decimal(str(self.payload.get("price", "NaN")))
            except InvalidOperation as error:
                raise ValueError("Preço deve ser numérico.") from error
            if not value.is_finite() or value <= 0 or value >= Decimal("1e14"):
                raise ValueError("Preço deve ser positivo.")
        return self
