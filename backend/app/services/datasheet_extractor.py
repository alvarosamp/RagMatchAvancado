"""
services/datasheet_extractor.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Extrai specs estruturadas de um datasheet (PDF de fabricante/concorrente) via
OCR (docling_parser.parse_pdf) + LLM, no MESMO vocabulÃ¡rio de campos usado no
catÃ¡logo prÃ³prio (data/Produtos/all_devices.json) â€” Ã© isso que permite o
comparador de attribute_parsers.py funcionar sem uma camada de mapeamento
separada: pedimos pro LLM jÃ¡ devolver "Portas RJ45", "PoE", "Power Requirement
/ TensÃ£o de Entrada" etc, em vez de inventar nomenclatura nova por fabricante.
"""

from __future__ import annotations

import json
import os
import re

import ollama

try:
    from json_repair import repair_json
except ImportError:
    repair_json = None

from app.logs.config import logger
from app.pipeline.docling_parser import parse_pdf

_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
_ollama_client = ollama.Client(host=_OLLAMA_HOST)

# Nomes de campo jÃ¡ usados no catÃ¡logo prÃ³prio â€” ver attribute_parsers.classify_field,
# que faz match por substring nesses termos em portuguÃªs.
_KNOWN_FIELDS = [
    "Portas RJ45", "Uplinks", "PoE", "Portas PoE", "Budget PoE (W)",
    "Tipo de Gerenciamento", "Camada", "VLANs",
    "Power Requirement / TensÃ£o de Entrada",
]

_SYSTEM_PROMPT = f"""VocÃª Ã© um especialista em extrair especificaÃ§Ãµes tÃ©cnicas de datasheets de \
equipamentos de rede (switches, access points, transceivers, mÃ³dulos Ã³pticos).

Leia o texto do datasheet e devolva APENAS um JSON vÃ¡lido no formato:
{{
  "model": "<modelo/part number do produto>",
  "manufacturer": "<fabricante>",
  "category": "<switch|access_point|transceiver|modulo_optico|outro>",
  "specs": {{ "<nome do campo>": "<valor>", ... }}
}}

Regras para os nomes de campo em "specs":
- Reutilize EXATAMENTE estes nomes quando o dado existir no datasheet: {", ".join(_KNOWN_FIELDS)}
- Para outros dados relevantes que nÃ£o se encaixem nesses campos, crie um nome de campo em portuguÃªs, curto e descritivo.
- Valores booleanos (tem ou nÃ£o tem o recurso) devem ser true/false.
- NÃ£o invente valor que nÃ£o estÃ¡ no texto â€” se nÃ£o encontrar, nÃ£o inclua o campo.

Responda APENAS com o objeto JSON. Nada de texto antes, comentÃ¡rio depois, ou markdown (sem \`\`\`)."""


def _parse_json_loosely(raw_json: str) -> dict | None:
    """
    Tenta parsear o JSON como veio; se falhar, aplica correÃ§Ãµes comuns de
    modelos pequenos (vÃ­rgula sobrando antes de '}'/']', valor sem aspas,
    aspas assimÃ©tricas etc. via json_repair) antes de desistir.
    Retorna None se nÃ£o der pra recuperar â€” o caller trata como "sem specs".
    """
    try:
        return json.loads(raw_json)
    except json.JSONDecodeError:
        pass

    no_trailing_commas = re.sub(r",\s*([}\]])", r"\1", raw_json)
    try:
        return json.loads(no_trailing_commas)
    except json.JSONDecodeError:
        pass

    if repair_json is not None:
        try:
            repaired = repair_json(raw_json)
            parsed = json.loads(repaired)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def extract_specs_from_pdf(pdf_bytes: bytes, filename: str = "datasheet.pdf") -> dict:
    """
    OCR do PDF + LLM estrutura as specs no vocabulÃ¡rio do catÃ¡logo.

    Retorna {"model": str, "manufacturer": str, "category": str, "specs": dict, "raw_text": str}.
    Nunca lanÃ§a exceÃ§Ã£o por falha do LLM â€” nesse caso volta com specs vazio
    (o caller decide se pede pro usuÃ¡rio preencher manualmente).
    """
    parsed = parse_pdf(pdf_bytes, filename=filename)
    text = parsed.full_text[:8000]  # datasheet Ã© curto; limite generoso pro contexto do LLM

    result = {"model": "", "manufacturer": "", "category": "", "specs": {}, "raw_text": parsed.full_text}

    if not text.strip():
        logger.warning("[DatasheetExtractor] PDF sem texto extraivel: %s", filename)
        return result

    heuristic = _extract_specs_heuristic(parsed.full_text, filename)
    for key, value in heuristic.items():
        if value:
            result[key] = value

    use_llm = os.environ.get("DATASHEET_EXTRACTOR_USE_LLM", "1").lower() not in {"0", "false", "no", "off"}
    if not use_llm or _heuristic_quality(result) == "boa":
        return result

    try:
        response = _ollama_client.chat(
            model=_OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Texto do datasheet ({filename}):\n\n{text}"},
            ],
            options={"temperature": 0.1},
        )
        raw = response["message"]["content"].strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = _parse_json_loosely(match.group())
            if data is None:
                logger.warning("[DatasheetExtractor] JSON malformado do LLM para %s: %s", filename, match.group()[:300])
            else:
                result = _merge_llm_extraction(result, data, parsed.full_text)
        else:
            logger.warning("[DatasheetExtractor] Resposta do LLM sem JSON para %s: %s", filename, raw[:200])
    except Exception as exc:
        logger.error("[DatasheetExtractor] Falha ao extrair specs de %s: %s", filename, exc, exc_info=True)

    return result


def _extract_specs_heuristic(text: str, filename: str) -> dict:
    normalized = " ".join((text or "").split())
    folded = normalized.lower()
    model = _first_match(normalized, r"\b([A-Z]{2,}[A-Z0-9]{4,})\b") or os.path.splitext(filename)[0]

    specs: dict[str, str] = {}
    is_ap = any(term in folded for term in ("access point", "wi-fi", "wifi", "802.11", "802 11"))
    is_optical = any(term in folded for term in ("sfp", "transceptor", "transceiver", "fibra", "monomodo", "multimodo"))
    is_switch = not is_optical and any(term in folded for term in ("switch", "porta rj", "portas rj", "vlan", "poe"))

    if is_ap:
        if wifi := _first_match(normalized, r"\b(Wi-?Fi\s*(?:5|6E?|7)|802\.11[a-z]+)\b"):
            specs["Tecnologia Wi-Fi"] = wifi
        if re.search(r"\bPoE\+?\+?\b", normalized, re.I):
            specs["PoE"] = _first_match(normalized, r"\b(PoE\+?\+?)\b") or "PoE"
        if re.search(r"\bindoor\b", normalized, re.I):
            specs["Ambiente"] = "Indoor"
        elif re.search(r"\boutdoor\b", normalized, re.I):
            specs["Ambiente"] = "Outdoor"
        return {"model": model, "manufacturer": "", "category": "access_point", "specs": specs}

    if is_switch:
        if ports := _first_match(normalized, r"(\d+)\s*(?:portas?|x)\s*(?:RJ-?45|10/100/1000|Gigabit)?"):
            specs["Portas RJ45"] = ports
        if re.search(r"\bPoE\+?\+?\b", normalized, re.I):
            specs["PoE"] = _first_match(normalized, r"\b(PoE\+?\+?)\b") or "PoE"
        if uplinks := _first_match(normalized, r"(\d+\s*(?:x\s*)?SFP\+?(?:\s*\d+G)?)"):
            specs["Uplinks"] = uplinks
        return {"model": model, "manufacturer": "", "category": "switch", "specs": specs}

    if not is_optical:
        return {"model": model, "manufacturer": "", "category": "", "specs": {}}

    if re.search(r"\bSFP\+?\b", normalized, re.I):
        specs["Formato"] = _first_match(normalized, r"\b(SFP\+?)\b") or "SFP"
    if speed := _first_match(normalized, r"(\d+(?:[,.]\d+)?)\s*G\s*b\s*/?\s*s"):
        specs["Velocidade"] = f"{speed.replace('.', ',')} Gbps"
    if reach := _first_match(normalized, r"(?<![A-Z0-9])(\d+(?:[,.]\d+)?)\s+k\s*m\b"):
        specs["Alcance"] = f"{reach.replace('.', ',')} km"
    if wavelength := _first_match(normalized, r"Tx\s*(\d{3,4})\s*nm\s*/\s*Rx\s*(\d{3,4})\s*nm"):
        specs["Comprimento de onda"] = f"Tx {wavelength[0]} nm / Rx {wavelength[1]} nm"
    if "monomodo" in folded or "smf" in folded:
        specs["Tipo de meio"] = "Fibra monomodo"
    elif "multimodo" in folded or "mmf" in folded:
        specs["Tipo de meio"] = "Fibra multimodo"
    if temperature := _first_match(normalized, r"Temperatura de opera[Ã§c][aÃ£]o[^:]*:\s*([^\.]*?[+-]?\d+\s*Â?°?\s*C\s*a\s*\+?\d+\s*Â?°?\s*C)"):
        specs["Temperatura de operaÃ§Ã£o"] = temperature.strip()
    if voltage := _first_match(normalized, r"\+?\s*(3[,.]3)\s*V"):
        specs["Power Requirement / TensÃ£o de Entrada"] = f"{voltage.replace('.', ',')} V"

    return {
        "model": model,
        "manufacturer": "",
        "category": "transceiver",
        "specs": specs,
    }


def _heuristic_quality(result: dict) -> str:
    specs = result.get("specs") or {}
    if result.get("category") and len(specs) >= 3:
        return "boa"
    if result.get("category") and specs:
        return "parcial"
    return "fraca"


def _merge_llm_extraction(current: dict, llm_data: dict, source_text: str) -> dict:
    merged = dict(current)
    folded_source = source_text.lower()

    llm_model = str(llm_data.get("model") or "").strip()
    if llm_model and llm_model.lower() in folded_source:
        merged["model"] = llm_model

    llm_manufacturer = str(llm_data.get("manufacturer") or "").strip()
    if llm_manufacturer and llm_manufacturer.lower() in folded_source:
        merged["manufacturer"] = llm_manufacturer

    llm_category = _canonical_datasheet_category(llm_data.get("category"))
    current_category = _canonical_datasheet_category(merged.get("category"))
    if llm_category and (not current_category or llm_category == current_category):
        merged["category"] = llm_category

    specs = dict(merged.get("specs") or {})
    llm_specs = llm_data.get("specs") if isinstance(llm_data.get("specs"), dict) else {}
    for key, value in llm_specs.items():
        if value not in ("", None, [], {}):
            specs.setdefault(str(key), value)
    merged["specs"] = specs
    return merged


def _canonical_datasheet_category(value) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"access_point", "ap"}:
        return "access_point"
    if text in {"transceiver", "modulo_optico", "modulo_otico"}:
        return "transceiver"
    if text == "switch":
        return "switch"
    return text


def _first_match(text: str, pattern: str):
    match = re.search(pattern, text, re.I)
    if not match:
        return ""
    if len(match.groups()) > 1:
        return match.groups()
    return match.group(1).strip()

