from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import AnalysisDocument, DocumentSchema
from app.services.analysis_normalizer import normalize_analysis_result
from app.services.analysis_store import persist_analysis_document
from app.services.document_identity import (
    edital_business_key_from_result,
    is_unidentified_edital_result,
    normalize_identifier,
)


@dataclass(frozen=True)
class DocumentSchemaSpec:
    name: str
    version: str
    title: str
    description: str
    required_fields: tuple[str, ...]
    item_collection_path: str | None = None
    item_identity_fields: tuple[str, ...] = ()
    business_key_fields: tuple[str, ...] = ()
    sync_targets: tuple[str, ...] = ()
    export_templates: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, tuple):
                payload[key] = list(value)
        return payload


DEFAULT_DOCUMENT_SCHEMAS: dict[str, DocumentSchemaSpec] = {
    "edital": DocumentSchemaSpec(
        name="edital",
        version="7.4",
        title="Edital analisado",
        description="Documento de licitacao com cabecalho, itens, riscos e caracteristicas de BI.",
        required_fields=("edital",),
        item_collection_path="itens_elegiveis",
        item_identity_fields=("numero_item_edital", "numero_item", "item"),
        business_key_fields=(
            "n_interno",
            "edital.numero_pregao",
            "edital.orgao",
            "edital.data_disputa",
            "edital.hora_disputa",
        ),
        sync_targets=("crm",),
        export_templates=("bi_edital_pdf",),
    ),
    "datasheet_tor": DocumentSchemaSpec(
        name="datasheet_tor",
        version="1.0",
        title="Datasheet TOR",
        description="Ficha tecnica normalizada no padrao TOR para produtos variados.",
        required_fields=("produto",),
        item_collection_path="produtos",
        item_identity_fields=("modelo", "part_number", "sku"),
        business_key_fields=("produto.fabricante", "produto.modelo", "produto.part_number"),
        sync_targets=(),
        export_templates=("datasheet_tor_pdf",),
    ),
    "generic": DocumentSchemaSpec(
        name="generic",
        version="1.0",
        title="Documento generico",
        description="JSON estruturado armazenado para reuso por servicos internos.",
        required_fields=(),
        item_collection_path=None,
        item_identity_fields=(),
        business_key_fields=("id", "codigo", "numero"),
        sync_targets=(),
        export_templates=(),
    ),
}


def list_document_schemas(db: Session, tenant_id: int) -> list[dict[str, Any]]:
    schemas = [schema.to_payload() for schema in DEFAULT_DOCUMENT_SCHEMAS.values()]
    custom_schemas = (
        db.query(DocumentSchema)
        .filter(DocumentSchema.tenant_id == tenant_id, DocumentSchema.is_active.is_(True))
        .order_by(DocumentSchema.name.asc(), DocumentSchema.version.desc())
        .all()
    )
    schemas.extend(_serialize_db_schema(schema) for schema in custom_schemas)
    return schemas


def store_structured_document(
    db: Session,
    *,
    tenant_id: int,
    document_type: str,
    payload: dict[str, Any],
    source_name: str | None = None,
    full_text: str | None = None,
    schema_name: str | None = None,
    schema_version: str | None = None,
    tokens_used: int = 0,
    processing_ms: int | None = None,
    status: str = "done",
) -> tuple[AnalysisDocument, bool, DocumentSchemaSpec, dict[str, Any]]:
    document_type = _clean_type(document_type)
    schema = resolve_document_schema(
        document_type,
        schema_name=schema_name,
        schema_version=schema_version,
    )
    normalized_payload = normalize_document_payload(document_type, payload)
    validate_document_payload(document_type, normalized_payload, schema)
    business_key = build_document_business_key(document_type, normalized_payload, schema)

    return (
        *persist_analysis_document(
            db,
            tenant_id=tenant_id,
            source_kind=document_type,
            source_name=source_name,
            full_text=full_text,
            result=normalized_payload,
            schema_name=schema.name,
            schema_version=schema.version,
            business_key=business_key,
            tokens_used=tokens_used,
            processing_ms=processing_ms,
            status=status,
        ),
        schema,
        normalized_payload,
    )


def resolve_document_schema(
    document_type: str,
    *,
    schema_name: str | None = None,
    schema_version: str | None = None,
) -> DocumentSchemaSpec:
    key = _clean_type(schema_name or document_type)
    schema = DEFAULT_DOCUMENT_SCHEMAS.get(key) or DEFAULT_DOCUMENT_SCHEMAS["generic"]
    if schema_version and schema_version != schema.version:
        return DocumentSchemaSpec(
            **{**schema.to_payload(), "version": schema_version},
        )
    return schema


def normalize_document_payload(document_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if _clean_type(document_type) == "edital":
        return normalize_analysis_result(payload)
    return payload


def validate_document_payload(
    document_type: str,
    payload: dict[str, Any],
    schema: DocumentSchemaSpec,
) -> None:
    if _clean_type(document_type) == "edital" and is_unidentified_edital_result(payload):
        raise HTTPException(
            status_code=422,
            detail=(
                "Documento nao identificado. Informe n_interno ou dados do edital "
                "(pregao, orgao e data) antes de importar."
            ),
        )

    missing = [
        field
        for field in schema.required_fields
        if not _meaningful(_get_path(payload, field))
    ]
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Documento fora do schema esperado.",
                "missing_fields": missing,
                "schema": schema.name,
                "version": schema.version,
            },
        )


def build_document_business_key(
    document_type: str,
    payload: dict[str, Any],
    schema: DocumentSchemaSpec,
) -> str | None:
    if _clean_type(document_type) == "edital":
        return edital_business_key_from_result(payload)

    values = [
        normalize_identifier(_get_path(payload, field))
        for field in schema.business_key_fields
        if _meaningful(_get_path(payload, field))
    ]
    if not values:
        return None
    digest = hashlib.sha1("|".join(values).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{schema.name}|meta|{digest}"


def _serialize_db_schema(schema: DocumentSchema) -> dict[str, Any]:
    return {
        "name": schema.name,
        "version": schema.version,
        "title": schema.title,
        "description": schema.description,
        "required_fields": schema.required_fields or [],
        "item_collection_path": schema.item_collection_path,
        "item_identity_fields": schema.item_identity_fields or [],
        "business_key_fields": schema.business_key_fields or [],
        "sync_targets": schema.sync_targets or [],
        "export_templates": schema.export_templates or [],
    }


def _get_path(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _clean_type(value: str | None) -> str:
    return (value or "generic").strip().lower()


def _meaningful(value: Any) -> bool:
    return value is not None and str(value).strip() not in ("", "-", "N/C", "n/c")
