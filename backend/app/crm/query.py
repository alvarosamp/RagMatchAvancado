from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Integer, Float
from sqlalchemy.orm import Session, joinedload

from app.auth.models import User
from app.crm.models import (
    CrmCatalogProduct,
    CrmChecklistTemplate,
    CrmChecklistTemplateItem,
    CrmItemWinnerType,
    CrmNotice,
    CrmNoticeCompetitor,
    CrmNoticeDocument,
    CrmNoticeHistory,
    CrmNoticeItemResult,
    CrmNoticeOutcome,
    CrmNoticeProduct,
    CrmNoticeSession,
    CrmNoticeStage,
    CrmOrgan,
    CrmPortal,
    CrmPostAuctionPhase,
)


CRM_TO_MAIN_ROLE = {
    "admin": "admin",
    "analyst": "editor",
    "viewer": "viewer",
}

MAIN_TO_CRM_ROLE = {
    "admin": "admin",
    "editor": "analyst",
    "viewer": "viewer",
}

USER_ID_FIELDS = {"owner_id", "created_by", "user_id", "post_auction_owner"}

DEFAULT_TEMPLATE_ITEMS = [
    ("Contrato Social / Estatuto", "Habilitacao Juridica", True, 1),
    ("CNPJ atualizado", "Habilitacao Juridica", True, 2),
    ("Procuracao (se aplicavel)", "Habilitacao Juridica", False, 3),
    ("Certidao Negativa Federal", "Regularidade Fiscal", True, 10),
    ("Certidao Negativa Estadual", "Regularidade Fiscal", True, 11),
    ("Certidao Negativa Municipal", "Regularidade Fiscal", True, 12),
    ("CRF FGTS", "Regularidade Fiscal", True, 13),
    ("CNDT (Trabalhista)", "Regularidade Fiscal", True, 14),
    ("Atestado de Capacidade Tecnica", "Qualificacao Tecnica", True, 20),
    ("Registro em orgao competente", "Qualificacao Tecnica", False, 21),
    ("Balanco Patrimonial", "Qualificacao Economico-Financeira", True, 30),
    ("Certidao Negativa de Falencia", "Qualificacao Economico-Financeira", True, 31),
    ("Declaracao de Menor (LGPD/Trabalho)", "Declaracoes", True, 40),
    ("Declaracao de Inexistencia de Fato Impeditivo", "Declaracoes", True, 41),
    ("Proposta Comercial", "Proposta", True, 50),
]


@dataclass(frozen=True)
class TableConfig:
    model: type | None = None
    insert_roles: set[str] = field(default_factory=lambda: {"admin", "editor"})
    update_roles: set[str] = field(default_factory=lambda: {"admin", "editor"})
    delete_roles: set[str] = field(default_factory=lambda: {"admin", "editor"})
    eager_loads: tuple[Any, ...] = ()
    virtual: bool = False


TABLES: dict[str, TableConfig] = {
    "organs": TableConfig(model=CrmOrgan, delete_roles={"admin"}),
    "portals": TableConfig(model=CrmPortal, delete_roles={"admin"}),
    "checklist_templates": TableConfig(model=CrmChecklistTemplate, delete_roles={"admin"}),
    "checklist_template_items": TableConfig(model=CrmChecklistTemplateItem, delete_roles={"admin"}),
    "catalog_products": TableConfig(model=CrmCatalogProduct, delete_roles={"admin"}),
    "notices": TableConfig(
        model=CrmNotice,
        eager_loads=(
            joinedload(CrmNotice.organ),
            joinedload(CrmNotice.portal),
            joinedload(CrmNotice.notice_documents),
        ),
        delete_roles={"admin"},
    ),
    "notice_products": TableConfig(
        model=CrmNoticeProduct,
        eager_loads=(joinedload(CrmNoticeProduct.catalog_product),),
    ),
    "notice_documents": TableConfig(model=CrmNoticeDocument),
    "notice_history": TableConfig(model=CrmNoticeHistory, update_roles=set(), delete_roles=set()),
    "notice_sessions": TableConfig(model=CrmNoticeSession, delete_roles={"admin"}),
    "notice_item_results": TableConfig(model=CrmNoticeItemResult, delete_roles={"admin", "editor"}),
    "notice_competitors": TableConfig(model=CrmNoticeCompetitor, delete_roles={"admin"}),
    "profiles": TableConfig(virtual=True, insert_roles=set(), update_roles=set(), delete_roles=set()),
    "user_roles": TableConfig(virtual=True, insert_roles={"admin"}, update_roles={"admin"}, delete_roles={"admin"}),
}


def ensure_default_template(db: Session, current_user: User) -> None:
    existing = (
        db.query(CrmChecklistTemplate)
        .filter(CrmChecklistTemplate.tenant_id == current_user.tenant_id, CrmChecklistTemplate.is_default.is_(True))
        .first()
    )
    if existing:
        return

    template = CrmChecklistTemplate(
        tenant_id=current_user.tenant_id,
        name="Habilitacao Padrao",
        description="Template padrao de documentos de habilitacao para licitacoes",
        is_default=True,
    )
    db.add(template)
    db.flush()

    for name, category, is_required, sort_order in DEFAULT_TEMPLATE_ITEMS:
        db.add(
            CrmChecklistTemplateItem(
                tenant_id=current_user.tenant_id,
                template_id=template.id,
                name=name,
                category=category,
                is_required=is_required,
                sort_order=sort_order,
            )
        )

    db.commit()


def list_records(
    db: Session,
    current_user: User,
    table_name: str,
    *,
    filters: list[dict[str, Any]] | None = None,
    orders: list[dict[str, Any]] | None = None,
    limit: int | None = None,
    head: bool = False,
) -> tuple[list[dict[str, Any]] | None, int | None]:
    ensure_default_template(db, current_user)
    config = TABLES[table_name]

    if config.virtual:
        rows = _list_virtual_table(db, current_user, table_name, filters or [], orders or [], limit)
        if head:
            return None, len(rows)
        return rows, None

    query = db.query(config.model)
    for load in config.eager_loads:
        query = query.options(load)
    if hasattr(config.model, "tenant_id"):
        query = query.filter(config.model.tenant_id == current_user.tenant_id)

    query = _apply_filters(query, config.model, filters or [])
    if head:
        return None, query.count()

    query = _apply_orders(query, config.model, orders or [])
    if limit is not None:
        query = query.limit(limit)
    rows = query.all()
    return [serialize_record(row) for row in rows], None


def insert_records(
    db: Session,
    current_user: User,
    table_name: str,
    values: list[dict[str, Any]] | dict[str, Any],
) -> list[dict[str, Any]]:
    ensure_default_template(db, current_user)
    config = TABLES[table_name]
    _require_role(current_user, config.insert_roles)

    if config.virtual:
        row = values[0] if isinstance(values, list) else values
        return [_insert_virtual_table(db, current_user, table_name, row)]

    rows = values if isinstance(values, list) else [values]
    instances = []
    for row in rows:
        payload = _prepare_payload(config.model, row, current_user, existing=None)
        instance = config.model(**payload)
        db.add(instance)
        instances.append(instance)

    db.commit()
    for instance in instances:
        db.refresh(instance)
    return [serialize_record(instance) for instance in instances]


def update_records(
    db: Session,
    current_user: User,
    table_name: str,
    values: dict[str, Any],
    filters: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    ensure_default_template(db, current_user)
    config = TABLES[table_name]
    _require_role(current_user, config.update_roles)

    if config.virtual:
        return [_update_virtual_table(db, current_user, table_name, values, filters or [])]

    query = db.query(config.model)
    if hasattr(config.model, "tenant_id"):
        query = query.filter(config.model.tenant_id == current_user.tenant_id)
    query = _apply_filters(query, config.model, filters or [])
    rows = query.all()

    for row in rows:
        payload = _prepare_payload(config.model, values, current_user, existing=row)
        for key, value in payload.items():
            setattr(row, key, value)

    db.commit()
    for row in rows:
        db.refresh(row)
    return [serialize_record(row) for row in rows]


def delete_records(
    db: Session,
    current_user: User,
    table_name: str,
    filters: list[dict[str, Any]] | None = None,
) -> int:
    ensure_default_template(db, current_user)
    config = TABLES[table_name]
    _require_role(current_user, config.delete_roles)

    if config.virtual:
        _delete_virtual_table(db, current_user, table_name, filters or [])
        return 1

    query = db.query(config.model)
    if hasattr(config.model, "tenant_id"):
        query = query.filter(config.model.tenant_id == current_user.tenant_id)
    query = _apply_filters(query, config.model, filters or [])
    rows = query.all()
    count = len(rows)
    for row in rows:
        db.delete(row)
    db.commit()
    return count


def crm_user_payload(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "role": MAIN_TO_CRM_ROLE.get(user.role, "viewer"),
        "user_metadata": {
            "full_name": user.full_name,
        },
    }


def serialize_record(row: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        if column.name in USER_ID_FIELDS and value is not None:
            data[column.name] = str(value)
        else:
            data[column.name] = _json_value(value)

    if isinstance(row, CrmCatalogProduct):
        data["min_price"] = row.min_price
    elif isinstance(row, CrmNotice):
        data["organs"] = serialize_related(row.organ, ("id", "name")) if row.organ else None
        data["portals"] = serialize_related(row.portal, ("id", "name", "url")) if row.portal else None
        data["notice_documents"] = [serialize_record(doc) for doc in sorted(row.notice_documents, key=lambda item: item.sort_order or 0)]
    elif isinstance(row, CrmNoticeProduct):
        data["catalog_products"] = serialize_record(row.catalog_product) if row.catalog_product else None
    return data


def serialize_related(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in fields:
        payload[field] = _json_value(getattr(row, field))
    return payload


def _json_value(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _apply_filters(query: Any, model: type, filters: list[dict[str, Any]]) -> Any:
    for filter_def in filters:
        column_name = filter_def.get("column")
        operator = filter_def.get("op", "eq")
        raw_value = filter_def.get("value")
        if not column_name or not hasattr(model, column_name):
            continue

        column = getattr(model, column_name)
        value = _cast_column_value(column, raw_value)

        if operator == "eq":
            query = query.filter(column == value)
        elif operator == "neq":
            query = query.filter(column != value)
        elif operator == "is":
            query = query.filter(column.is_(None) if value is None else column == value)
        elif operator == "not_is":
            query = query.filter(column.is_not(None) if value is None else column != value)
        elif operator == "in":
            values = [_cast_column_value(column, item) for item in (raw_value or [])]
            query = query.filter(column.in_(values))
    return query


def _apply_orders(query: Any, model: type, orders: list[dict[str, Any]]) -> Any:
    for order_def in orders:
        column_name = order_def.get("column")
        if not column_name or not hasattr(model, column_name):
            continue
        column = getattr(model, column_name)
        clause = column.asc() if order_def.get("ascending", True) else column.desc()
        if order_def.get("nullsFirst") is True:
            clause = clause.nullsfirst()
        elif order_def.get("nullsFirst") is False:
            clause = clause.nullslast()
        query = query.order_by(clause)
    return query


def _prepare_payload(model: type, payload: dict[str, Any], current_user: User, existing: Any | None) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for column in model.__table__.columns:
        name = column.name
        if name in {"id", "created_at", "updated_at", "tenant_id"}:
            continue
        if name not in payload:
            continue
        values[name] = _cast_column_value(column, payload.get(name))

    if hasattr(model, "tenant_id"):
        values["tenant_id"] = current_user.tenant_id

    if hasattr(model, "created_by") and not existing and "created_by" not in values:
        values["created_by"] = current_user.id
    if model is CrmNoticeHistory and not values.get("user_id"):
        values["user_id"] = current_user.id

    if model is CrmCatalogProduct:
        brand = values.get("brand") or getattr(existing, "brand", None)
        model_name = values.get("model") or getattr(existing, "model", None)
        specification = values.get("specification") or getattr(existing, "specification", None)
        if not values.get("name"):
            values["name"] = " ".join(part for part in [brand, model_name] if part) or getattr(existing, "name", None)
        if "description" not in values and specification:
            values["description"] = specification

    if model is CrmNotice:
        _apply_notice_business_rules(values, existing)

    return values


def _apply_notice_business_rules(values: dict[str, Any], existing: Any | None) -> None:
    phase = values.get("post_auction_phase")
    current_outcome = getattr(existing, "outcome", None)
    current_outcome_value = current_outcome.value if isinstance(current_outcome, enum.Enum) else current_outcome

    if phase in {CrmPostAuctionPhase.CONVERTED, CrmPostAuctionPhase.CONVERTED.value}:
        values["outcome"] = CrmNoticeOutcome.WON.value
        values["stage"] = CrmNoticeStage.RESULT.value
    elif phase in {CrmPostAuctionPhase.CLOSED, CrmPostAuctionPhase.CLOSED.value} and values.get("outcome", current_outcome_value) in {None, CrmNoticeOutcome.PENDING.value}:
        values["outcome"] = CrmNoticeOutcome.LOST.value
        values["stage"] = CrmNoticeStage.RESULT.value

    outcome = values.get("outcome")
    if outcome and outcome != CrmNoticeOutcome.PENDING.value:
        values.setdefault("stage", CrmNoticeStage.RESULT.value)


def _cast_column_value(column: Any, value: Any) -> Any:
    if value in ("", "none", "null"):
        value = None
    if value is None:
        return None

    column_type = column.type
    if isinstance(column_type, Integer):
        return int(value)
    if isinstance(column_type, Float):
        return float(value)
    if isinstance(column_type, Boolean):
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "yes", "on"}
    if isinstance(column_type, DateTime):
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if isinstance(column_type, Date):
        return date.fromisoformat(str(value)[:10])
    return value


def _require_role(current_user: User, allowed_roles: set[str]) -> None:
    if not allowed_roles:
        raise PermissionError("Operacao nao permitida para esta tabela.")
    if current_user.role not in allowed_roles:
        raise PermissionError("Permissao insuficiente para executar esta operacao.")


def _tenant_users_query(db: Session, current_user: User):
    return db.query(User).filter(User.tenant_id == current_user.tenant_id).order_by(User.full_name.asc(), User.email.asc())


def _list_virtual_table(
    db: Session,
    current_user: User,
    table_name: str,
    filters: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    limit: int | None,
) -> list[dict[str, Any]]:
    users = _tenant_users_query(db, current_user).all()
    if table_name == "profiles":
        rows = [
            {
                "id": str(user.id),
                "full_name": user.full_name,
                "email": user.email,
                "created_at": _json_value(user.created_at),
            }
            for user in users
        ]
    else:
        rows = [
            {
                "user_id": str(user.id),
                "role": MAIN_TO_CRM_ROLE.get(user.role, "viewer"),
            }
            for user in users
        ]

    rows = _filter_virtual_rows(rows, filters)
    rows = _order_virtual_rows(rows, orders)
    return rows[:limit] if limit is not None else rows


def _insert_virtual_table(db: Session, current_user: User, table_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if table_name != "user_roles":
        raise PermissionError("Insercao nao suportada para esta tabela virtual.")
    user_id = int(payload["user_id"])
    role = CRM_TO_MAIN_ROLE.get(payload.get("role"), "viewer")
    user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not user:
        raise LookupError("Usuario nao encontrado para atualizacao de papel.")
    user.role = role
    db.commit()
    db.refresh(user)
    return {"user_id": str(user.id), "role": MAIN_TO_CRM_ROLE.get(user.role, "viewer")}


def _update_virtual_table(
    db: Session,
    current_user: User,
    table_name: str,
    payload: dict[str, Any],
    filters: list[dict[str, Any]],
) -> dict[str, Any]:
    if table_name != "user_roles":
        raise PermissionError("Atualizacao nao suportada para esta tabela virtual.")
    filter_row = _first_filter_value(filters, "user_id")
    user_id = int(filter_row or payload.get("user_id"))
    role = CRM_TO_MAIN_ROLE.get(payload.get("role"), "viewer")
    user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not user:
        raise LookupError("Usuario nao encontrado para atualizacao de papel.")
    user.role = role
    db.commit()
    db.refresh(user)
    return {"user_id": str(user.id), "role": MAIN_TO_CRM_ROLE.get(user.role, "viewer")}


def _delete_virtual_table(db: Session, current_user: User, table_name: str, filters: list[dict[str, Any]]) -> None:
    if table_name != "user_roles":
        raise PermissionError("Remocao nao suportada para esta tabela virtual.")
    # O CRM faz delete + insert para trocar papel. Aqui o delete e um no-op
    # para evitar estado intermediario sem permissao.
    return None


def _first_filter_value(filters: list[dict[str, Any]], column_name: str) -> Any:
    for item in filters:
        if item.get("column") == column_name:
            return item.get("value")
    return None


def _filter_virtual_rows(rows: list[dict[str, Any]], filters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = rows
    for item in filters:
        column = item.get("column")
        op = item.get("op", "eq")
        value = item.get("value")
        if column not in {"id", "email", "full_name", "user_id", "role"}:
            continue
        if op == "eq":
            result = [row for row in result if row.get(column) == value]
        elif op == "neq":
            result = [row for row in result if row.get(column) != value]
        elif op == "in":
            values = set(value or [])
            result = [row for row in result if row.get(column) in values]
    return result


def _order_virtual_rows(rows: list[dict[str, Any]], orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = rows
    for item in reversed(orders):
        column = item.get("column")
        if column not in {"full_name", "email", "role", "user_id"}:
            continue
        ordered = sorted(
            ordered,
            key=lambda row: (row.get(column) or "").lower() if isinstance(row.get(column), str) else row.get(column),
            reverse=not item.get("ascending", True),
        )
    return ordered
