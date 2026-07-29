from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

from requests import RequestException
from sqlalchemy.orm import Session

from app.db.models import PncpRadarItem
from app.db.session import SessionLocal
from app.logs.config import logger
from app.services.pncp_client import list_purchase_items, search_publications


DEFAULT_DAILY_SEARCHES = [
    "switch switches poe sfp gbic",
    "access point wifi wireless",
    "roteador router firewall",
    "rede redes cabeamento fibra transceiver rack",
]


def daily_search_terms() -> list[str]:
    raw = os.getenv("PNCP_RADAR_DAILY_TERMS")
    if not raw:
        return DEFAULT_DAILY_SEARCHES
    terms = [chunk.strip() for chunk in raw.split("|") if chunk.strip()]
    return terms or DEFAULT_DAILY_SEARCHES


def get_cached_notices(
    db: Session,
    *,
    limit: int = 200,
    text_filter: str | None = None,
) -> list[dict[str, Any]]:
    query = (
        db.query(PncpRadarItem)
        .filter(PncpRadarItem.status == "active")
        .order_by(PncpRadarItem.last_seen_at.desc())
        .limit(max(1, min(limit, 500)))
    )
    rows = query.all()
    items = [dict(row.notice or {}) for row in rows]
    if text_filter:
        needles = [term.lower() for term in text_filter.replace(",", " ").split() if len(term) >= 3]
        if needles:
            items = [
                item
                for item in items
                if any(needle in _notice_text(item) for needle in needles)
            ]
    return items


def refresh_pncp_radar_cache(
    db: Session,
    *,
    searches: list[str] | None = None,
    max_pages: int | None = None,
    tamanho_pagina: int | None = None,
    propostas_abertas: bool = True,
) -> dict[str, Any]:
    searches = searches or daily_search_terms()
    max_pages = max_pages or int(os.getenv("PNCP_RADAR_DAILY_MAX_PAGES", "4"))
    tamanho_pagina = tamanho_pagina or int(os.getenv("PNCP_RADAR_DAILY_PAGE_SIZE", "50"))
    seen: set[str] = set()
    fetched = 0
    upserted = 0
    errors: list[str] = []

    for terms in searches:
        try:
            payload = search_publications(
                texto=terms,
                modalidade="Pregao Eletronico",
                pagina=1,
                tamanho_pagina=tamanho_pagina,
                max_pages=max_pages,
                propostas_abertas=propostas_abertas,
            )
        except RequestException as exc:
            logger.warning("[RadarCache] Falha ao consultar PNCP para '%s': %s", terms, exc)
            errors.append(f"{terms}: {exc}")
            continue

        for item in payload.get("items") or []:
            id_pncp = str(item.get("id_pncp") or item.get("numero_controle") or "").strip()
            if not id_pncp or id_pncp in seen:
                continue
            seen.add(id_pncp)
            fetched += 1
            item = enrich_notice_for_engineering(item)
            row = db.query(PncpRadarItem).filter(PncpRadarItem.id_pncp == id_pncp).first()
            if row is None:
                row = PncpRadarItem(
                    id_pncp=id_pncp,
                    notice=item,
                    search_terms=terms,
                    status="active",
                )
                db.add(row)
            else:
                row.notice = item
                row.search_terms = terms
                row.status = "active"
                row.last_seen_at = datetime.now(timezone.utc)
            upserted += 1

    db.commit()
    latest = latest_cache_update(db)
    return {
        "ok": not errors,
        "fetched": fetched,
        "upserted": upserted,
        "searches": searches,
        "errors": errors,
        "last_update": latest.isoformat() if latest else None,
    }


def latest_cache_update(db: Session) -> datetime | None:
    row = (
        db.query(PncpRadarItem)
        .filter(PncpRadarItem.status == "active")
        .order_by(PncpRadarItem.last_seen_at.desc())
        .first()
    )
    return row.last_seen_at if row else None


def enrich_notice_for_engineering(item: dict[str, Any]) -> dict[str, Any]:
    id_pncp = str(item.get("id_pncp") or item.get("numero_controle") or "").strip()
    items: list[dict[str, Any]] = []
    item_error = None
    if id_pncp:
        try:
            items = list_purchase_items(id_pncp)
        except Exception as exc:
            item_error = str(exc)
            logger.info("[RadarCache] Itens PNCP indisponiveis para %s: %s", id_pncp, exc)

    relevant_items = _relevant_items(items)
    summary = _engineering_summary(item, relevant_items, item_error=item_error)
    return {
        **item,
        "radar_items": relevant_items,
        "radar_items_count": len(items),
        "engineering_summary": summary,
        "items_error": item_error,
    }


def start_daily_radar_refresh() -> None:
    if os.getenv("PNCP_RADAR_AUTO_REFRESH", "1").lower() not in {"1", "true", "yes", "sim"}:
        logger.info("[RadarCache] Rotina diaria desativada por PNCP_RADAR_AUTO_REFRESH.")
        return

    interval_seconds = int(os.getenv("PNCP_RADAR_REFRESH_INTERVAL_SECONDS", str(24 * 60 * 60)))
    initial_delay = int(os.getenv("PNCP_RADAR_INITIAL_DELAY_SECONDS", "25"))

    def _loop() -> None:
        time.sleep(max(0, initial_delay))
        while True:
            db = SessionLocal()
            try:
                logger.info("[RadarCache] Iniciando captura diaria PNCP.")
                summary = refresh_pncp_radar_cache(db)
                logger.info("[RadarCache] Captura concluida: %s", summary)
            except Exception as exc:
                logger.warning("[RadarCache] Captura diaria falhou: %s", exc, exc_info=True)
            finally:
                db.close()
            time.sleep(max(300, interval_seconds))

    threading.Thread(target=_loop, daemon=True, name="pncp-radar-daily-refresh").start()


def _notice_text(item: dict[str, Any]) -> str:
    parts = [
        item.get("objeto"),
        item.get("titulo"),
        item.get("modalidade"),
        " ".join(str(row.get("descricao") or "") for row in item.get("radar_items") or []),
        (item.get("orgao_entidade") or {}).get("nome_razao_social"),
        (item.get("unidade_orgao") or {}).get("municipio"),
    ]
    return " ".join(str(part).lower() for part in parts if part)


def _relevant_items(items: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    scored = []
    for row in items:
        text = str(row.get("descricao") or "").lower()
        score = _item_fit_score(text)
        if score <= 0:
            continue
        scored.append((score, row))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [_compact_item(row, score) for score, row in scored[:limit]]


def _compact_item(row: dict[str, Any], score: int) -> dict[str, Any]:
    return {
        "numero_item": row.get("numero_item"),
        "descricao": _clip(row.get("descricao"), 220),
        "quantidade": row.get("quantidade"),
        "unidade": row.get("unidade"),
        "valor_unitario": row.get("valor_unitario"),
        "valor_total": row.get("valor_total"),
        "criterio_julgamento": row.get("criterio_julgamento"),
        "beneficio": row.get("beneficio"),
        "fit_score": score,
        "matched_terms": _matched_terms(str(row.get("descricao") or "").lower()),
    }


def _engineering_summary(
    notice: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    item_error: str | None,
) -> dict[str, Any]:
    best_score = max((int(row.get("fit_score") or 0) for row in items), default=0)
    has_switch = any("switch" in (row.get("matched_terms") or []) for row in items)
    has_ap = any("access point" in (row.get("matched_terms") or []) or "wifi" in (row.get("matched_terms") or []) for row in items)
    has_security = any(term in {"firewall", "roteador"} for row in items for term in (row.get("matched_terms") or []))
    estimated = _coerce_float(notice.get("valor_total_estimado"))

    if best_score >= 70:
        verdict = "vale_entrar"
        label = "Vale entrar"
    elif best_score >= 40:
        verdict = "avaliar"
        label = "Avaliar engenharia"
    else:
        verdict = "baixo_fit"
        label = "Baixo fit"

    reasons = []
    if has_switch:
        reasons.append("itens de switch/rede")
    if has_ap:
        reasons.append("itens wireless/access point")
    if has_security:
        reasons.append("firewall/roteador")
    if estimated:
        reasons.append(f"valor estimado {_money(estimated)}")
    if not items and item_error:
        reasons.append("itens ainda nao disponiveis no PNCP")
    if not reasons:
        reasons.append("sem item tecnico forte identificado")

    return {
        "verdict": verdict,
        "label": label,
        "fit_score": best_score,
        "headline": "; ".join(reasons[:3]),
        "items_considered": len(items),
    }


def _item_fit_score(text: str) -> int:
    terms = _matched_terms(text)
    score = len(terms) * 18
    if any(term in terms for term in ("switch", "access point", "firewall", "roteador")):
        score += 28
    if any(term in terms for term in ("poe", "sfp", "wifi", "vlan", "fibra")):
        score += 12
    return min(100, score)


def _matched_terms(text: str) -> list[str]:
    mapping = {
        "switch": ("switch", "switches"),
        "access point": ("access point", "ap wireless"),
        "wifi": ("wifi", "wi-fi", "wireless"),
        "firewall": ("firewall",),
        "roteador": ("roteador", "router"),
        "poe": ("poe",),
        "sfp": ("sfp", "gbic", "transceiver"),
        "vlan": ("vlan",),
        "fibra": ("fibra", "optica", "óptica"),
        "rack": ("rack",),
    }
    return [label for label, needles in mapping.items() if any(needle in text for needle in needles)]


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _money(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _clip(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else f"{text[: limit - 3]}..."
