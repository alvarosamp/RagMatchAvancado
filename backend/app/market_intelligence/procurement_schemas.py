from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class StockInput(StrictInput):
    product_id: str = Field(min_length=1, max_length=36)
    unit: str = Field(min_length=1, max_length=40)
    quantity: Decimal = Field(ge=0, lt=Decimal("1e14"), decimal_places=6)
    reserved: Decimal = Field(ge=0, lt=Decimal("1e14"), decimal_places=6)
    observed_at: datetime
    notes: str = Field(min_length=3, max_length=2000)

    @model_validator(mode="after")
    def balance(self):
        if self.reserved > self.quantity:
            raise ValueError("Reserva não pode superar o saldo físico.")
        if self.observed_at.tzinfo is None:
            raise ValueError("A data do saldo exige fuso horário.")
        return self


class PlanningFilters(StrictInput):
    date_from: date | None = None
    date_to: date | None = None
    source: str = Field(default="crm", pattern="^(crm|manual|pncp|bling)$")
    category: str | None = Field(default=None, max_length=160)
    brand: str | None = Field(default=None, max_length=160)
    state: str | None = Field(default=None, max_length=2)
    search: str | None = Field(default=None, max_length=200)
    supplier_id: str | None = Field(default=None, max_length=36)


class InquiryInput(StrictInput):
    product_id: str = Field(min_length=1, max_length=36)
    quantity: Decimal = Field(gt=0, lt=Decimal("1e14"), decimal_places=6)
    unit: str = Field(min_length=1, max_length=40)
    needed_by: date | None = None
    notes: str = Field(min_length=3, max_length=2000)
    filters: PlanningFilters = Field(default_factory=PlanningFilters)


class QuoteInput(StrictInput):
    supplier_id: str = Field(min_length=1, max_length=36)
    unit_price: Decimal = Field(gt=0, lt=Decimal("1e14"), decimal_places=6)
    shipping: Decimal | None = Field(
        default=None, ge=0, lt=Decimal("1e14"), decimal_places=6
    )
    taxes: Decimal | None = Field(
        default=None, ge=0, lt=Decimal("1e14"), decimal_places=6
    )
    available_quantity: Decimal | None = Field(
        default=None, ge=0, lt=Decimal("1e14"), decimal_places=6
    )
    minimum_quantity: Decimal | None = Field(
        default=None, ge=0, lt=Decimal("1e14"), decimal_places=6
    )
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    valid_until: date
    notes: str = Field(min_length=3, max_length=2000)


class SelectionInput(StrictInput):
    quote_id: str = Field(min_length=1, max_length=36)
    reason: str = Field(min_length=3, max_length=2000)
