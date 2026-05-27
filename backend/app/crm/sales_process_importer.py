from __future__ import annotations

import hashlib
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from app.auth.models import Tenant, User
from app.auth.security import hash_password
from app.crm.models import CrmNotice, CrmNoticeProduct, CrmOrgan, CrmPortal
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.crm_notice_sync import sync_notice_from_product, sync_notice_relationships


PRIMARY_EMAIL = "alvaroscareli@gmail.com"
FALLBACK_EMAIL = "vish88@outlook.com"
DEFAULT_PASSWORD = "Elainema157!"
DEFAULT_TENANT_SLUG = "tor-tec"
DEFAULT_TENANT_NAME = "Tor Tec"
DEFAULT_USER_NAME = "Tor Tec"


@dataclass
class ImportContext:
    tenant: Tenant
    user: User


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def optional_text(value: Any) -> str | None:
    text = normalize_text(value)
    return text or None


def normalize_key_part(value: Any) -> str:
    text = normalize_text(value)
    return " ".join(text.lower().split())


def canonical_header(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    ascii_text = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    cleaned = [char if char.isalnum() else "_" for char in ascii_text]
    return "_".join(part for part in "".join(cleaned).split("_") if part)


def parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(".", "").replace(",", ".")
    if not text or text == "-":
        return None
    return float(text)


def parse_bool(value: Any) -> bool | None:
    text = normalize_key_part(value)
    if not text:
        return None
    if text in {"sim", "s", "yes", "true", "1"}:
        return True
    if text in {"nao", "n", "false", "0"}:
        return False
    return None


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    text = normalize_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def parse_item_number(value: Any, fallback_index: int) -> str:
    if isinstance(value, (datetime, date)):
        return str(value.day)
    text = normalize_text(value)
    if not text or text == "-":
        return str(fallback_index)
    if text.endswith(".0"):
        try:
            return str(int(float(text)))
        except ValueError:
            return text
    return text


def build_tor_id(prefix: str, import_key: str) -> str:
    digest = hashlib.sha1(import_key.encode("utf-8")).hexdigest()[:8].upper()
    return f"TOR-{prefix}-{digest}"


def ensure_context(db) -> ImportContext:
    primary_user = db.query(User).filter(User.email == PRIMARY_EMAIL).first()
    if primary_user:
        return ImportContext(tenant=primary_user.tenant, user=primary_user)

    fallback_user = db.query(User).filter(User.email == FALLBACK_EMAIL).first()
    if fallback_user:
        tenant = fallback_user.tenant
        primary_user = User(
            email=PRIMARY_EMAIL,
            full_name=DEFAULT_USER_NAME,
            hashed_password=hash_password(DEFAULT_PASSWORD),
            role="admin",
            tenant_id=tenant.id,
        )
        db.add(primary_user)
        db.flush()
        return ImportContext(tenant=tenant, user=primary_user)

    tenant = db.query(Tenant).filter(Tenant.slug == DEFAULT_TENANT_SLUG).first()
    if tenant is None:
        tenant = Tenant(slug=DEFAULT_TENANT_SLUG, name=DEFAULT_TENANT_NAME)
        db.add(tenant)
        db.flush()

    primary_user = User(
        email=PRIMARY_EMAIL,
        full_name=DEFAULT_USER_NAME,
        hashed_password=hash_password(DEFAULT_PASSWORD),
        role="admin",
        tenant_id=tenant.id,
    )
    db.add(primary_user)
    db.flush()
    return ImportContext(tenant=tenant, user=primary_user)


def ensure_portal(db, tenant_id: int, name: str | None, url: str | None = None, created_by: int | None = None) -> CrmPortal | None:
    portal_name = optional_text(name)
    if not portal_name:
        return None
    portal = (
        db.query(CrmPortal)
        .filter(CrmPortal.tenant_id == tenant_id, CrmPortal.name == portal_name)
        .first()
    )
    if portal is None:
        portal = CrmPortal(
            tenant_id=tenant_id,
            name=portal_name,
            url=optional_text(url),
            created_by=created_by,
        )
        db.add(portal)
        db.flush()
    elif not portal.url and url:
        portal.url = optional_text(url)
    return portal


def ensure_organ(
    db,
    tenant_id: int,
    name: str | None,
    city: str | None = None,
    state: str | None = None,
    created_by: int | None = None,
) -> CrmOrgan | None:
    organ_name = optional_text(name)
    if not organ_name:
        return None
    organ = (
        db.query(CrmOrgan)
        .filter(CrmOrgan.tenant_id == tenant_id, CrmOrgan.name == organ_name)
        .first()
    )
    if organ is None:
        organ = CrmOrgan(
            tenant_id=tenant_id,
            name=organ_name,
            city=optional_text(city),
            state=optional_text(state),
            created_by=created_by,
        )
        db.add(organ)
        db.flush()
    else:
        if not organ.city and city:
            organ.city = optional_text(city)
        if not organ.state and state:
            organ.state = optional_text(state)
    return organ


def read_sheet_rows(path: Path, sheet_name: str) -> list[dict[str, Any]]:
    workbook = load_workbook(path, data_only=True)
    sheet = workbook[sheet_name]
    rows = list(sheet.iter_rows(values_only=True))
    headers = [canonical_header(value) for value in rows[0]]
    parsed_rows: list[dict[str, Any]] = []
    for raw_row in rows[1:]:
        if not any(value not in (None, "") for value in raw_row):
            continue
        row = {headers[index]: raw_row[index] for index in range(len(headers)) if headers[index]}
        parsed_rows.append(row)
    return parsed_rows


def group_sheet_rows(sheet_name: str, rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if sheet_name == "Processos ganhos":
            key_parts = [
                sheet_name,
                normalize_key_part(row.get("data_da_sessao")),
                normalize_key_part(row.get("orgao")),
                normalize_key_part(row.get("link_pasta_processo")),
                normalize_key_part(row.get("proposta")),
            ]
        else:
            key_parts = [
                sheet_name,
                normalize_key_part(row.get("data_da_sessao")),
                normalize_key_part(row.get("portal")),
                normalize_key_part(row.get("orgao")),
            ]
        groups["|".join(key_parts)].append(row)
    return groups


def upsert_notice_from_group(db, context: ImportContext, import_key: str, rows: list[dict[str, Any]], sheet_name: str) -> CrmNotice:
    first = rows[0]
    prefix = "GAN" if sheet_name == "Processos ganhos" else "MON"
    tor_id = build_tor_id(prefix, import_key)
    auction_date = parse_datetime(first.get("data_da_sessao"))

    if sheet_name == "Processos ganhos":
        municipality = optional_text(first.get("endereco"))
        state = optional_text(first.get("uf"))
        organ = ensure_organ(
            db,
            context.tenant.id,
            first.get("orgao"),
            city=municipality,
            state=state,
            created_by=context.user.id,
        )
        notice_fields = {
            "number": tor_id,
            "tor_id": tor_id,
            "municipality_name": municipality,
            "title": None,
            "organ_id": organ.id if organ else None,
            "portal_id": None,
            "auction_date": auction_date,
            "drive_link": optional_text(first.get("link_pasta_processo")),
            "proposal_link": optional_text(first.get("proposta")),
            "supplier_proposal_link": optional_text(first.get("proposta_fornecedor")),
            "address": municipality,
            "state": state,
            "sales_status": optional_text(first.get("situacao")) or "ganho",
            "owner_id": context.user.id,
            "created_by": context.user.id,
            "import_key": import_key,
            "stage": "result",
            "outcome": "won",
            "company_position": "ganho",
        }
    else:
        organ = ensure_organ(
            db,
            context.tenant.id,
            first.get("orgao"),
            created_by=context.user.id,
        )
        portal = ensure_portal(
            db,
            context.tenant.id,
            first.get("portal"),
            created_by=context.user.id,
        )
        notice_fields = {
            "number": tor_id,
            "tor_id": tor_id,
            "municipality_name": None,
            "title": None,
            "organ_id": organ.id if organ else None,
            "portal_id": portal.id if portal else None,
            "auction_date": auction_date,
            "drive_link": None,
            "proposal_link": None,
            "supplier_proposal_link": None,
            "address": None,
            "state": None,
            "sales_status": optional_text(first.get("status")) or "monitoramento",
            "owner_id": context.user.id,
            "created_by": context.user.id,
            "import_key": import_key,
            "stage": "auction",
            "outcome": "pending",
            "company_position": optional_text(first.get("posicao_tor")),
        }

    notice = (
        db.query(CrmNotice)
        .filter(CrmNotice.tenant_id == context.tenant.id, CrmNotice.import_key == import_key)
        .first()
    )
    if notice is None:
        notice = CrmNotice(tenant_id=context.tenant.id, **notice_fields)
        db.add(notice)
        db.flush()
    else:
        for field_name, value in notice_fields.items():
            if value is not None or getattr(notice, field_name) is None:
                setattr(notice, field_name, value)

    sync_notice_relationships(db, notice, created_by=context.user.id)
    return notice


def upsert_group_products(db, context: ImportContext, notice: CrmNotice, rows: list[dict[str, Any]], sheet_name: str) -> int:
    imported = 0
    for index, row in enumerate(rows, start=1):
        if sheet_name == "Processos ganhos":
            item_number = parse_item_number(row.get("item"), index)
            product_code = optional_text(row.get("codigo_do_produto"))
            description = optional_text(row.get("descricao")) or product_code or f"Produto do item {item_number}"
            lot = optional_text(row.get("lote"))
            quantity = parse_float(row.get("quantidade")) or 1.0
            cost = parse_float(row.get("custo_unitario_c_ipi")) or parse_float(row.get("custo_unitario_s_ipi"))
            reference_price = parse_float(row.get("preco_minimo_unitario"))
            reference_total = parse_float(row.get("preco_minimo_total"))
            unit_price = None
            notes = optional_text(row.get("observacao"))
            exclusive_epp = parse_bool(row.get("exclusivo_epp"))
        else:
            item_number = str(index)
            product_code = optional_text(row.get("part_number_do_produto"))
            description = optional_text(row.get("descricao_do_produto")) or product_code or f"Produto monitorado {index}"
            lot = None
            quantity = parse_float(row.get("quantidade")) or 1.0
            cost = parse_float(row.get("custo"))
            reference_price = parse_float(row.get("preco"))
            reference_total = parse_float(row.get("preco_minimo_total"))
            unit_price = parse_float(row.get("preco"))
            notes = optional_text(row.get("status"))
            exclusive_epp = None

        product = (
            db.query(CrmNoticeProduct)
            .filter(CrmNoticeProduct.notice_id == notice.id, CrmNoticeProduct.item_number == item_number)
            .first()
        )
        if product is None:
            product = CrmNoticeProduct(
                tenant_id=context.tenant.id,
                notice_id=notice.id,
                item_number=item_number,
                sort_order=index - 1,
                description=description,
                quantity=quantity,
            )
            db.add(product)
            db.flush()

        product.description = description
        product.lot = lot
        product.product_code = product_code
        product.is_exclusive_epp = exclusive_epp
        product.quantity = quantity
        product.cost = cost
        product.unit_price = unit_price
        product.reference_price = reference_price
        product.reference_total_price = reference_total
        product.notes = notes
        product.sort_order = index - 1

        sync_notice_from_product(db, product, created_by=context.user.id)
        imported += 1

    return imported


def build_import_context_for_user(user: User) -> ImportContext:
    tenant = user.tenant
    if tenant is None:
        raise ValueError("Usuario importador sem tenant associado.")
    return ImportContext(tenant=tenant, user=user)


def run_import(path: Path, *, context_override: ImportContext | None = None) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Planilha nao encontrada em {path}")

    db = SessionLocal()
    try:
        init_db(db)
        context = context_override or ensure_context(db)
        sheet_names = ["Processos ganhos", "Processos - Monitoramento"]
        total_notices = 0
        total_products = 0

        for sheet_name in sheet_names:
            rows = read_sheet_rows(path, sheet_name)
            for import_key, group_rows in group_sheet_rows(sheet_name, rows).items():
                notice = upsert_notice_from_group(db, context, import_key, group_rows, sheet_name)
                total_notices += 1
                total_products += upsert_group_products(db, context, notice, group_rows, sheet_name)

        db.commit()
        summary = {
            "tenant": context.tenant.slug,
            "user": context.user.email,
            "grupos_processados": total_notices,
            "itens_processados": total_products,
        }
        print("Importacao concluida:", summary)
        return summary
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
