from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from app.services.analysis_normalizer import normalize_brand_direction

SCHEMA_NAME = "tor.match-item"
SCHEMA_VERSION = "1.0.0"


def build_crm_notice_match_export(notice: Any, products: list[Any]) -> dict[str, Any]:
    """Build one Match JSON per edital, containing every edital item."""
    edital_products = [
        product
        for product in products
        if not _mapping(product.raw_payload).get("kit_component")
    ]
    item_exports = [build_crm_match_item_export(notice, product) for product in edital_products]
    if not item_exports:
        raise ValueError("O edital nao possui itens para exportar.")

    first = item_exports[0]
    return {
        "metadados_exportacao": {
            **first["metadados_exportacao"],
            "schema": "tor.match-edital",
            "schema_version": SCHEMA_VERSION,
            "finalidade": "match_dos_itens_do_edital_com_catalogo_lpu",
        },
        "processo": first["processo"],
        "resumo": {
            "quantidade_itens": len(item_exports),
            "quantidade_total": sum(
                float(exported["item"].get("quantidade") or 0) for exported in item_exports
            ),
        },
        "itens": [
            {
                key: value
                for key, value in exported.items()
                if key not in {"metadados_exportacao", "processo"}
            }
            for exported in item_exports
        ],
    }


def match_notice_filename(payload: dict[str, Any]) -> str:
    process_id = _mapping(payload.get("processo")).get("processo_id") or "edital"
    return f"match_edital_{_slug(process_id)}.json"


def build_crm_match_item_export(notice: Any, product: Any) -> dict[str, Any]:
    """Adapt a CRM notice item to the same contract used by analysis items."""
    raw = _mapping(product.raw_payload)
    portal = getattr(notice, "portal", None)
    organ = getattr(notice, "organ", None)
    document = SimpleNamespace(
        id=notice.analysis_document_id or notice.id,
        business_key=notice.tor_id or notice.number,
        source_name=_first(raw, "arquivo", "source_name", "documento_principal"),
        source_path=_first(raw, "source_path", "caminho_origem"),
        result={
            "n_interno": notice.tor_id or notice.number,
            "edital": {
                "numero_pregao": notice.bid_number or notice.number,
                "tipo_licitacao": notice.modality,
                "orgao": getattr(organ, "name", None),
                "uasg": notice.uasg,
                "local": getattr(portal, "name", None),
                "url_origem": getattr(portal, "url", None),
                "data_disputa": notice.auction_date,
            },
            "documentacao": [],
        },
    )
    item = SimpleNamespace(
        id=product.id,
        item_number=product.item_number,
        categoria=product.category,
        lote_grupo=product.lot,
        quantity=product.quantity,
        unit=product.unit,
        description=product.description,
        unit_value=product.reference_price,
        total_value=product.reference_total_price,
        garantia=product.warranty,
        prazo_entrega=product.delivery_deadline,
        exclusividade_me_epp_item=product.exclusive_epp_label
        or product.is_exclusive_epp,
        brand=None,
        model=product.brand_direction_model,
        has_direcionamento_marca=product.brand_direction_exists,
        direcionamento_marca_tipo=product.brand_direction_type,
        direcionamento_marca_justificativa=product.brand_direction_justification,
        caracteristicas_tecnicas=product.technical_characteristics,
        caracteristicas_bi=product.bi_features,
        raw_payload=raw,
    )
    return build_match_item_export(document, item)


def build_match_item_export(document: Any, item: Any) -> dict[str, Any]:
    """Build the stable, auditable contract consumed by the Match agent."""
    result = _mapping(document.result)
    stored_item = _mapping(item.raw_payload)
    raw_item = _mapping(stored_item.get("_raw_input")) or stored_item
    edital = _mapping(result.get("edital"))
    direction_value = stored_item.get("direcionamento_marca")
    if direction_value is None:
        direction_value = raw_item.get("direcionamento_marca")
    direction = _mapping(direction_value)
    if not direction and _value(direction_value) is not None:
        direction = normalize_brand_direction(direction_value)
    bi = _without_nc(
        _mapping(item.caracteristicas_bi) or _mapping(stored_item.get("caracteristicas_bi"))
    )
    category = _value(item.categoria) or _value(stored_item.get("categoria"))
    origin = _origin(document, item, raw_item)

    requirements = _atomic_requirements(
        raw_item, bi, origin, item.item_number,
        allow_bi_fallback=result.get("schema_version") != "8.0",
    )
    divergences = _document_divergences(raw_item, bi)

    return {
        "metadados_exportacao": {
            "schema": SCHEMA_NAME,
            "schema_version": SCHEMA_VERSION,
            "gerado_em": datetime.now(timezone.utc).isoformat(),
            "idioma": "pt-BR",
            "finalidade": "match_com_catalogo_lpu",
            "principios": [
                "raw_preservado",
                "campos_ausentes_nao_sao_requisitos",
                "requisitos_rastreaveis",
            ],
        },
        "processo": {
            "processo_id": _value(result.get("n_interno")) or _value(document.business_key),
            "numero": _first(edital, "numero_pregao", "numero_licitacao"),
            "modalidade": _first(edital, "tipo_licitacao", "modalidade"),
            "orgao": _value(edital.get("orgao")),
            "uasg": _value(edital.get("uasg")),
            "portal": _first(edital, "local", "portal"),
            "url_origem": _first(edital, "url_origem", "url"),
            "data_sessao": _value(edital.get("data_disputa")),
            "hora_sessao": _value(edital.get("hora_disputa")),
            "documento_principal": _value(document.source_name),
            "caminho_origem": _value(document.source_path),
            "revisao_documento": _first(result, "revisao_documento", "versao_documento"),
        },
        "item": {
            "id_interno": item.id,
            "numero": _value(item.item_number),
            "lote": _value(item.lote_grupo),
            "codigo": _first(raw_item, "codigo", "codigo_item", "codigo_material"),
            "categoria": category,
            "subcategoria": _first(raw_item, "subcategoria", "tipo"),
            "quantidade": item.quantity,
            "unidade_fornecimento": _value(item.unit),
            "descricao_original": _value(item.description),
            "descricao_resumida": _first(raw_item, "descricao_resumida", "resumo"),
            "preco_referencia_unitario": item.unit_value,
            "preco_referencia_total": item.total_value,
            "minimo_unitario": _first(raw_item, "minimo_unitario", "quantidade_minima"),
            "garantia_original": _value(item.garantia),
            "prazo_entrega_original": _value(item.prazo_entrega),
            "exclusivo_epp": _boolean_or_none(item.exclusividade_me_epp_item),
            "item_em_disputa": _boolean_or_none(raw_item.get("item_em_disputa")),
        },
        "raw": {
            "descricao_original": _value(item.description),
            "caracteristicas_tecnicas_original": _value(item.caracteristicas_tecnicas),
            "garantia_original": _value(item.garantia),
            "prazo_entrega_original": _value(item.prazo_entrega),
            "direcionamento_original": direction or None,
            "payload_original": raw_item,
        },
        "direcionamento_marca": {
            "existe": bool(direction.get("existe") or item.has_direcionamento_marca),
            "fabricante": _first(direction, "fabricante", "marca") or _value(item.brand),
            "modelo": _value(direction.get("modelo")) or _value(item.model),
            "sku": _first(direction, "sku", "codigo"),
            "tipo": _value(direction.get("tipo")) or _value(item.direcionamento_marca_tipo),
            "equivalente_aceito": _boolean_or_none(direction.get("equivalente_aceito")),
            "texto_original": _first(direction, "texto_original", "marca_modelo"),
            "justificativa": _value(direction.get("justificativa"))
            or _value(item.direcionamento_marca_justificativa),
        },
        "requisitos_atomicos": requirements,
        "requisitos_gerais_aplicaveis": raw_item.get("requisitos_gerais_aplicaveis") or [],
        "conflitos_documentais": _mapping(result.get("auditoria")).get("conflitos_documentais") or [],
        "normalized": {
            "categoria": category,
            "caracteristicas_bi": bi,
            "categoria_especifica": _category_payload(category, bi, raw_item),
        },
        "obrigacoes_gerais": _general_obligations(result, raw_item, item),
        "divergencias_documentais": divergences,
    }


def match_item_filename(document: Any, item: Any) -> str:
    process = _slug(_mapping(document.result).get("n_interno") or document.business_key or document.id)
    number = _slug(item.item_number or item.id)
    return f"match_{process}_item_{number}.json"


def _atomic_requirements(
    raw_item: dict[str, Any],
    bi: dict[str, Any],
    origin: dict[str, Any],
    item_number: Any,
    allow_bi_fallback: bool = True,
) -> list[dict[str, Any]]:
    supplied = raw_item.get("requisitos_atomicos") or raw_item.get("requisitos_tecnicos")
    if isinstance(supplied, list) and supplied:
        return [
            _normalize_requirement(
                value,
                index,
                _requirement_origin(raw_item, value, origin),
                item_number,
            )
            for index, value in enumerate(supplied, start=1)
            if isinstance(value, (dict, str))
        ]

    if not allow_bi_fallback:
        return []

    requirements: list[dict[str, Any]] = []
    for field, value in _flatten_features(bi).items():
        requirements.append(
            {
                "id": _requirement_id(item_number, len(requirements) + 1),
                "texto_original": None,
                "campo_normalizado": field,
                "operador": "=",
                "valor": value,
                "unidade": None,
                "operador_logico": "E",
                "obrigatorio": True,
                "origem": origin,
                "derivado_de": "caracteristicas_bi",
            }
        )

    technical = _value(raw_item.get("caracteristicas_tecnicas"))
    if technical:
        requirements.append(
            {
                "id": _requirement_id(item_number, len(requirements) + 1),
                "texto_original": technical,
                "campo_normalizado": "caracteristicas_tecnicas",
                "operador": "contem_requisitos",
                "valor": technical,
                "unidade": None,
                "operador_logico": "E",
                "obrigatorio": True,
                "origem": origin,
                "derivado_de": "texto_original_nao_atomizado",
            }
        )
    return requirements


def _normalize_requirement(
    requirement: dict[str, Any] | str,
    index: int,
    default_origin: dict[str, Any],
    item_number: Any,
) -> dict[str, Any]:
    payload = requirement if isinstance(requirement, dict) else {"texto_original": requirement}
    direct_evidences = payload.get("evidencias") if isinstance(payload.get("evidencias"), list) else []
    source = _mapping(payload.get("origem") or payload.get("fonte")) or (
        {**default_origin, **direct_evidences[0]} if direct_evidences and isinstance(direct_evidences[0], dict)
        else default_origin
    )
    return {
        "id": _value(payload.get("id")) or _requirement_id(item_number, index),
        "texto_original": _first(payload, "texto_original", "texto", "trecho"),
        "campo_normalizado": _first(payload, "campo_normalizado", "campo", "atributo"),
        "sujeito": _value(payload.get("sujeito")),
        "escopo": _value(payload.get("escopo") or payload.get("condicao")),
        "operador": _value(payload.get("operador")) or "=",
        "valor": payload.get("valor"),
        "unidade": _value(payload.get("unidade")),
        "alternativas": payload.get("alternativas"),
        "valores": payload.get("valores"),
        "operador_logico": _value(payload.get("logica") or payload.get("operador_logico")) or "E",
        "grupo_logico": _value(payload.get("grupo_logico")),
        "evidencias": direct_evidences,
        "obrigatorio": payload.get("obrigatorio") is not False,
        "origem": source,
        "derivado_de": _value(payload.get("derivado_de")) or "extracao_original",
    }


def _general_obligations(result: dict[str, Any], raw_item: dict[str, Any], item: Any) -> dict[str, Any]:
    supplied = _mapping(raw_item.get("obrigacoes_gerais"))
    documentation = result.get("documentacao") if isinstance(result.get("documentacao"), list) else []
    document_names = [
        _value(entry.get("documento"))
        for entry in documentation
        if isinstance(entry, dict) and _value(entry.get("documento"))
    ]
    delivery_days, delivery_kind = _parse_days(item.prazo_entrega)
    warranty_months = _parse_months(item.garantia)
    return {
        "prazo_entrega_dias": supplied.get("prazo_entrega_dias", delivery_days),
        "prazo_entrega_tipo": supplied.get("prazo_entrega_tipo", delivery_kind),
        "marco_inicio_prazo": _value(supplied.get("marco_inicio_prazo")),
        "garantia_meses": supplied.get("garantia_meses", warranty_months),
        "garantia_texto": _value(supplied.get("garantia_texto")) or _value(item.garantia),
        "suporte_on_site": _boolean_or_none(supplied.get("suporte_on_site")),
        "instalacao": _boolean_or_none(supplied.get("instalacao")),
        "configuracao": _boolean_or_none(supplied.get("configuracao")),
        "treinamento": _boolean_or_none(supplied.get("treinamento")),
        "produto_novo": _boolean_or_none(supplied.get("produto_novo")),
        "embalagem_original": _boolean_or_none(supplied.get("embalagem_original")),
        "manuais_inclusos": _boolean_or_none(supplied.get("manuais_inclusos")),
        "acessorios_inclusos": supplied.get("acessorios_inclusos") or [],
        "amostra_exigida": _boolean_or_none(supplied.get("amostra_exigida")),
        "datasheet_exigido": _boolean_or_none(supplied.get("datasheet_exigido")),
        "certificados_exigidos": supplied.get("certificados_exigidos") or [],
        "documentos_exigidos": document_names,
    }


def _category_payload(category: str | None, bi: dict[str, Any], raw_item: dict[str, Any]) -> dict[str, Any]:
    folded = _fold(category)
    explicit = _mapping(raw_item.get("normalized"))
    flat_bi = _flatten_features(bi)
    if "switch" in folded:
        return {
            "tipo": "switch",
            "portas_acesso_qtd": _integer(_feature(flat_bi, "portas_acesso_rj45_qtd", "quantidade_portas")),
            "portas_acesso": _feature(flat_bi, "velocidades_porta", "portas_acesso"),
            "gerenciavel": _managed_value(_feature(flat_bi, "gerenciamento_local", "gerenciamento")),
            "poe": _poe_value(_feature(flat_bi, "poe_padroes", "alimentacao_poe")),
            "poe_padrao": _feature(flat_bi, "poe_padroes", "alimentacao_poe"),
            "uplinks": _feature(flat_bi, "uplinks_formatos", "uplinks"),
            "camada": _feature(flat_bi, "protocolos_roteamento", "camada"),
            **explicit,
        }
    if "access point" in folded or folded == "ap":
        return {
            "tipo": "access_point",
            "wifi_standard": _feature(flat_bi, "padroes_ieee", "tecnologia_wifi"),
            "alimentacao": _feature(flat_bi, "poe_padroes", "alimentacao"),
            "ambiente": _feature(flat_bi, "ambiente_uso", "ambiente"),
            **explicit,
        }
    if "transceiver" in folded or "modulo optico" in folded or "modulo otico" in folded:
        return {
            "tipo": "transceiver",
            "form_factor": _feature(flat_bi, "form_factor", "formato"),
            "speed": _feature(flat_bi, "velocidade_nominal_gbps", "velocidade"),
            "media_type": _feature(flat_bi, "tipo_fibra", "tipo_meio"),
            "distance": _feature(flat_bi, "alcance_m", "alcance"),
            **explicit,
        }
    return {"tipo": _value(category), **explicit}


def _document_divergences(raw_item: dict[str, Any], bi: dict[str, Any]) -> list[dict[str, Any]]:
    supplied = raw_item.get("divergencias_documentais")
    divergences = [entry for entry in supplied if isinstance(entry, dict)] if isinstance(supplied, list) else []
    candidates = []
    for field, value in (
        ("caracteristicas_bi.gerenciamento", bi.get("gerenciamento")),
        ("gerenciamento", raw_item.get("gerenciamento")),
        ("normalized.gerenciamento", _mapping(raw_item.get("normalized")).get("gerenciamento")),
    ):
        canonical = _managed_value(value)
        if canonical is not None:
            candidates.append((field, canonical, value))
    if len({value for _, value, _ in candidates}) > 1:
        divergences.append(
            {
                "id": f"D{len(divergences) + 1:02d}",
                "tipo": "CONFLITO_ENTRE_CAMPOS",
                "campo": "gerenciamento",
                "fontes": [
                    {"campo": field, "valor": original} for field, _, original in candidates
                ],
                "status": "NAO_RESOLVIDO",
            }
        )
    return divergences


def _origin(document: Any, item: Any, raw_item: dict[str, Any]) -> dict[str, Any]:
    supplied = _mapping(raw_item.get("origem") or raw_item.get("fonte"))
    return {
        "documento_id": supplied.get("documento_id") or document.id,
        "arquivo": supplied.get("arquivo") or _value(document.source_name),
        "pagina": supplied.get("pagina") or raw_item.get("pagina"),
        "secao": supplied.get("secao") or raw_item.get("secao"),
        "item": supplied.get("item") or _value(item.item_number),
        "trecho": supplied.get("trecho") or _value(item.description),
        "url": supplied.get("url"),
    }


def _without_nc(values: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, dict):
            nested = _without_nc(value)
            if nested:
                cleaned[key] = nested
        elif _value(value) is not None:
            cleaned[key] = value
    return cleaned


def _flatten_features(values: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in values.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flattened.update(_flatten_features(value, path))
        elif _value(value) is not None:
            flattened[path] = value
    return flattened


def _feature(values: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in values:
            return values[name]
        suffix = f".{name}"
        for path, value in values.items():
            if path.endswith(suffix):
                return value
    return None


def _requirement_origin(
    raw_item: dict[str, Any], requirement: dict[str, Any] | str, default: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(requirement, dict):
        return default
    direct_evidences = requirement.get("evidencias")
    if isinstance(direct_evidences, list) and direct_evidences and isinstance(direct_evidences[0], dict):
        return {**default, **direct_evidences[0]}
    supplied = _mapping(requirement.get("origem") or requirement.get("fonte"))
    if supplied:
        return supplied
    field = _value(requirement.get("campo") or requirement.get("campo_normalizado"))
    evidences = _mapping(raw_item.get("evidencias"))
    if field:
        for path, entries in evidences.items():
            if (
                (path == field or path.endswith(f".{field}"))
                and isinstance(entries, list)
                and entries
                and isinstance(entries[0], dict)
            ):
                return {**default, **entries[0]}
    return default


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if _fold(cleaned) in {"", "-", "n/c", "nao consta", "nao informado"}:
            return None
        return cleaned
    return value


def _first(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = _value(payload.get(key))
        if value is not None:
            return value
    return None


def _boolean_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    folded = _fold(value)
    if folded in {"sim", "true", "1", "exclusivo", "exclusiva"}:
        return True
    if folded in {"nao", "false", "0"}:
        return False
    return None


def _managed_value(value: Any) -> bool | None:
    folded = _fold(value)
    if not folded:
        return None
    if "nao gerenci" in folded:
        return False
    if "gerenci" in folded:
        return True
    return _boolean_or_none(value)


def _poe_value(value: Any) -> bool | None:
    folded = _fold(value)
    if not folded:
        return None
    if "nao poe" in folded or "sem poe" in folded:
        return False
    if "poe" in folded:
        return True
    return _boolean_or_none(value)


def _integer(value: Any) -> int | None:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else None


def _parse_days(value: Any) -> tuple[int | None, str | None]:
    text = _value(value)
    if not text:
        return None, None
    match = re.search(r"(\d+)\s*dias?", str(text), re.IGNORECASE)
    kind = "uteis" if "ute" in _fold(text) else "corridos" if "corrido" in _fold(text) else None
    return (int(match.group(1)) if match else None), kind


def _parse_months(value: Any) -> int | None:
    text = _value(value)
    if not text:
        return None
    months = re.search(r"(\d+)\s*mes", _fold(text))
    if months:
        return int(months.group(1))
    years = re.search(r"(\d+)\s*ano", _fold(text))
    return int(years.group(1)) * 12 if years else None


def _requirement_id(item_number: Any, index: int) -> str:
    item_token = re.sub(r"\W+", "", str(item_number or "ITEM")) or "ITEM"
    return f"R{item_token}.{index:02d}"


def _slug(value: Any) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "sem-id")).strip("-").lower()
    return slug or "sem-id"


def _fold(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    text = "".join(
        char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", text).casefold()
