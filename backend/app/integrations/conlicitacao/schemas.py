from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProviderModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class ConlicitacaoClientInfo(ProviderModel):
    id: int
    razao_social: str | None = None


class ConlicitacaoBulletinPointer(ProviderModel):
    id: int
    datahora_fechamento: str | None = None
    numero_edicao: int | None = None


class ConlicitacaoFilter(ProviderModel):
    id: int
    descricao: str | None = None
    periodos: dict[str, bool] = Field(default_factory=dict)
    ultimo_boletim: ConlicitacaoBulletinPointer | None = None


class ConlicitacaoFiltersResponse(ProviderModel):
    cliente: ConlicitacaoClientInfo | None = None
    filtros: list[ConlicitacaoFilter] = Field(default_factory=list)


class ConlicitacaoBulletinSummary(ProviderModel):
    id: int
    filtro_id: int | None = None
    numero_edicao: int | None = None
    datahora_fechamento: str | None = None


class ConlicitacaoBulletinsResponse(ProviderModel):
    parameters: dict[str, Any] = Field(default_factory=dict)
    filtro: dict[str, Any] = Field(default_factory=dict)
    boletins: list[ConlicitacaoBulletinSummary] = Field(default_factory=list)


class ConlicitacaoDocument(ProviderModel):
    filename: str = "documento"
    url: str


class ConlicitacaoPublicBody(ProviderModel):
    nome: str | None = None
    codigo: str | None = None
    cidade: str | None = None
    uf: str | None = None
    endereco: str | None = None
    telefone: list[Any] = Field(default_factory=list)
    site: str | None = None


class ConlicitacaoTender(ProviderModel):
    id: int
    orgao: ConlicitacaoPublicBody = Field(default_factory=ConlicitacaoPublicBody)
    objeto: str | None = None
    situacao: str | None = None
    datahora_abertura: str | None = None
    datahora_documento: str | None = None
    datahora_retirada: str | None = None
    datahora_visita: str | None = None
    datahora_prazo: str | None = None
    edital: str | None = None
    documento: list[ConlicitacaoDocument] = Field(default_factory=list)
    processo: str | None = None
    observacao: str | None = None
    item: str | None = None
    preco_edital: float | None = None
    valor_estimado: float | None = None

    @field_validator("documento", mode="before")
    @classmethod
    def normalize_documents(cls, value: Any) -> list[Any]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [{"filename": "documento", "url": value}]
        return value


class ConlicitacaoBulletin(ProviderModel):
    boletim: dict[str, Any] = Field(default_factory=dict)
    licitacoes: list[ConlicitacaoTender] = Field(default_factory=list)
    acompanhamentos: list[dict[str, Any]] = Field(default_factory=list)
