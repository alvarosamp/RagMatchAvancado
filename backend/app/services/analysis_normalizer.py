from __future__ import annotations

import copy
import re
import unicodedata
from typing import Any


NC = "N/C"

SWITCH_BI_DEFAULTS = {
    "quantidade_portas": NC,
    "portas_acesso": NC,
    "gerenciamento": NC,
    "alimentacao_poe": NC,
    "uplinks": NC,
    "camada": NC,
}

AP_BI_DEFAULTS = {
    "tecnologia_wifi": NC,
    "alimentacao": NC,
    "ambiente": NC,
}

OPTICAL_BI_DEFAULTS = {
    "formato": NC,
    "velocidade": NC,
    "tipo_meio": NC,
    "alcance": NC,
}

CATEGORY_ALIASES = {
    "switch": "Switch",
    "access point": "Access Point",
    "ap": "Access Point",
    "transceiver": "Transceiver",
    "modulo optico": "Modulo optico",
    "modulo otico": "Modulo optico",
    "módulo óptico": "Modulo optico",
    "módulo ótico": "Modulo optico",
    "outro": "Outro",
    "outros": "Outros",
}

PORTAL_ALIASES = {
    "bll": "BLL",
    "bolsa de licitacoes": "BLL",
    "bolsa de licitacoes e leiloes": "BLL",
    "bnc": "BNC",
    "compras gov": "Compras.gov.br",
    "compras.gov.br": "Compras.gov.br",
    "comprasnet": "Compras.gov.br",
    "pcp": "PCP",
    "pncp": "PNCP",
}

ALLOWED_BI_VALUES = {
    "quantidade_portas": [
        "5 Portas",
        "8 Portas",
        "10 Portas",
        "12 Portas",
        "16 Portas",
        "24 Portas",
        "48 Portas",
        "96 Portas",
        "Modular",
        "Outros",
        NC,
    ],
    "portas_acesso": [
        "Fast Ethernet (10/100)",
        "Gigabit (10/100/1000)",
        "MultiGig 2.5G",
        "MultiGig 5G",
        "10 Gigabit",
        "25 Gigabit",
        "40 Gigabit",
        "100 Gigabit",
        NC,
    ],
    "gerenciamento": ["Gerenciavel", "Nao Gerenciavel", NC],
    "alimentacao_poe": ["Nao PoE", "PoE", "PoE+", "PoE++", NC],
    "uplinks": [
        "Sem Uplink",
        "2 SFP 1G",
        "4 SFP 1G",
        "8 SFP 1G",
        "2 SFP+ 10G",
        "4 SFP+ 10G",
        "8 SFP+ 10G",
        "2 SFP28 25G",
        "4 SFP28 25G",
        "2 QSFP+ 40G",
        "4 QSFP+ 40G",
        "2 QSFP28 100G",
        "4 QSFP28 100G",
        "Outros",
        NC,
    ],
    "camada": ["Sem Camada", "L2", "L2+", "L3 Lite", "L3", "L3 Full", NC],
    "tecnologia_wifi": ["Wi-Fi 5", "Wi-Fi 6", "Wi-Fi 6E", "Wi-Fi 7", "Outro", NC],
    "alimentacao": ["Fonte", "PoE", "PoE+", "PoE++", NC],
    "ambiente": ["Indoor", "Outdoor", NC],
    "formato": ["SFP", "SFP+", "QSFP+", "QSFP28", "Outro", NC],
    "velocidade": ["1G", "10G", "25G", "40G", "100G", "Outro", NC],
    "tipo_meio": ["Monomodo", "Multimodo", "RJ45", "BiDi", "Outro", NC],
    "alcance": ["100m", "300m", "550m", "2km", "10km", "20km", "40km", "80km", "Outro", NC],
}


def normalize_analysis_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return a v7.4-friendly analysis payload ready for DB and CRM."""
    normalized = copy.deepcopy(result or {})
    normalized["schema_version"] = _text(normalized.get("schema_version"), "7.4")
    normalized["n_interno"] = _text(normalized.get("n_interno"))

    controle = _dict(normalized.get("controle"))
    controle["versao_analisador"] = _text(controle.get("versao_analisador"))
    controle["data_processamento"] = _text(controle.get("data_processamento"))
    normalized["controle"] = controle

    edital = _dict(normalized.get("edital"))
    for key in (
        "selecionado",
        "status",
        "data_disputa",
        "orgao",
        "tipo_licitacao",
        "resumo_itens",
        "criterio",
        "uasg",
        "numero_pregao",
        "cidade",
        "uf",
        "valor_total_itens",
        "valor_total_edital",
        "intervalo",
        "exclusividade_me_epp",
        "validade_proposta",
        "momento_entrega_documentacao_habilitacao",
        "endereco",
        "cep",
    ):
        edital[key] = _text(edital.get(key))
    if not _meaningful(edital.get("resumo_itens")):
        edital["resumo_itens"] = _text(edital.get("resumo_switches"))
    if not _meaningful(edital.get("valor_total_itens")):
        edital["valor_total_itens"] = _text(edital.get("valor_total_switches"))
    edital["hora_disputa"] = _normalize_time(edital.get("hora_disputa"))
    edital["local"] = _normalize_portal(edital.get("local"))
    normalized["edital"] = edital

    riscos = _dict(normalized.get("riscos"))
    riscos["risco_identificado"] = _text(riscos.get("risco_identificado"), "Nenhum")
    for group_name in ("risco_operacional", "risco_documental"):
        group = _dict(riscos.get(group_name))
        group["existe"] = bool(group.get("existe"))
        group["motivos"] = _list(group.get("motivos"))
        riscos[group_name] = group
    normalized["riscos"] = riscos

    normalized["documentacao"] = _list(normalized.get("documentacao"))
    normalized["declaracoes"] = _list(normalized.get("declaracoes"))
    normalized["auditoria"] = _normalize_auditoria(normalized.get("auditoria"))

    source_items = normalized.get("itens_elegiveis") or normalized.get("itens") or []
    normalized["itens_elegiveis"] = [_normalize_item(item) for item in _list(source_items)]
    return normalized


def _normalize_item(item: Any) -> dict[str, Any]:
    payload = _dict(item)
    categoria = _normalize_category(payload.get("categoria") or payload.get("tipo") or payload.get("item_type"))
    aliases = {
        "lote_grupo": ("lote_grupo", "lote", "grupo"),
        "numero_item_edital": ("numero_item_edital", "numero_item", "item", "numero"),
        "descricao_original": ("descricao_original", "descricao", "descricao_item", "raw_descricao"),
        "preco_unitario": ("preco_unitario", "valor_unitario", "preco_minimo"),
        "quantidade": ("quantidade", "qtd"),
        "valor_total_item": ("valor_total_item", "valor_total", "total"),
        "garantia": ("garantia",),
        "prazo_entrega": ("prazo_entrega", "prazo_de_entrega", "entrega"),
        "exclusividade_me_epp_item": ("exclusividade_me_epp_item", "exclusividade_item"),
        "risco_associado": ("risco_associado", "risco"),
    }
    for key, source_keys in aliases.items():
        payload[key] = _text(_first(payload, *source_keys))
    payload["categoria"] = categoria

    direcionamento = _dict(payload.get("direcionamento_marca"))
    direcionamento["existe"] = bool(direcionamento.get("existe"))
    direcionamento["marca_modelo"] = _text(direcionamento.get("marca_modelo"))
    direcionamento["tipo"] = _text(direcionamento.get("tipo"))
    direcionamento["justificativa"] = _text(direcionamento.get("justificativa"))
    payload["direcionamento_marca"] = direcionamento
    payload["caracteristicas_bi"] = _normalize_bi_features(
        categoria,
        _dict(payload.get("caracteristicas_bi")),
    )
    return payload


def _normalize_bi_features(categoria: str, features: dict[str, Any]) -> dict[str, Any]:
    defaults = {}
    if categoria == "Switch":
        defaults = SWITCH_BI_DEFAULTS
    elif categoria == "Access Point":
        defaults = AP_BI_DEFAULTS
    elif categoria in ("Transceiver", "Modulo optico"):
        defaults = OPTICAL_BI_DEFAULTS

    normalized = {key: _canonical_bi_value(key, value) for key, value in features.items()}
    for key, default_value in defaults.items():
        normalized[key] = _canonical_bi_value(key, normalized.get(key, default_value))
    return normalized


def _normalize_auditoria(value: Any) -> dict[str, Any]:
    auditoria = _dict(value)
    for key in (
        "modo_analise",
        "status_conferido",
        "motivo_status",
        "confianca_geral",
        "observacoes",
    ):
        auditoria[key] = _text(auditoria.get(key))
    for key in (
        "documentacao_extraida",
        "fontes_consultadas",
        "anti_falso_negativo_aplicado",
        "teste_autonomia_aplicado_internamente",
        "dupla_checagem_status_vermelho",
    ):
        auditoria[key] = bool(auditoria.get(key))
    return auditoria


def _canonical_bi_value(field: str, value: Any) -> str:
    text = _text(value)
    if text == NC:
        return NC
    allowed = ALLOWED_BI_VALUES.get(field)
    if not allowed:
        return text
    folded = _fold(text)
    for option in allowed:
        if _fold(option) == folded:
            return option
    if folded == "outro":
        return "Outro" if "Outro" in allowed else text
    if folded == "outros":
        return "Outros" if "Outros" in allowed else text
    return text


def _normalize_category(value: Any) -> str:
    text = _text(value)
    if text == NC:
        return NC
    return CATEGORY_ALIASES.get(_fold(text), text)


def _normalize_portal(value: Any) -> str:
    text = _text(value)
    if text == NC:
        return NC
    folded = _fold(re.sub(r"^https?://", "", text).split("/")[0])
    for alias, canonical in PORTAL_ALIASES.items():
        if alias in folded:
            return canonical
    return text


def _normalize_time(value: Any) -> str:
    text = _text(value)
    if text == NC:
        return NC
    match = re.search(r"(\d{1,2})\s*(?::|h|H)\s*(\d{2})", text)
    if match:
        hour = max(0, min(23, int(match.group(1))))
        minute = max(0, min(59, int(match.group(2))))
        return f"{hour:02d}:{minute:02d}"
    match = re.fullmatch(r"\d{1,2}", text)
    if match:
        hour = max(0, min(23, int(text)))
        return f"{hour:02d}:00"
    return text


def _text(value: Any, default: str = NC) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else default
    return str(value).strip() or default


def _meaningful(value: Any) -> bool:
    return value is not None and str(value).strip() not in ("", "-", NC, "n/c")


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _first(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _fold(value: Any) -> str:
    text = str(value).strip()
    text = "".join(
        char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", text).casefold()
