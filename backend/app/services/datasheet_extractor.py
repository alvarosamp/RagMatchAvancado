"""
services/datasheet_extractor.py
────────────────────────────────
Extrai specs estruturadas de um datasheet (PDF de fabricante/concorrente) via
OCR (docling_parser.parse_pdf) + LLM, no MESMO vocabulário de campos usado no
catálogo próprio (data/Produtos/all_devices.json) — é isso que permite o
comparador de attribute_parsers.py funcionar sem uma camada de mapeamento
separada: pedimos pro LLM já devolver "Portas RJ45", "PoE", "Power Requirement
/ Tensão de Entrada" etc, em vez de inventar nomenclatura nova por fabricante.
"""

from __future__ import annotations

import json
import os
import re

import ollama
from json_repair import repair_json

from app.logs.config import logger
from app.pipeline.docling_parser import parse_pdf

_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
_ollama_client = ollama.Client(host=_OLLAMA_HOST)

# Nomes de campo já usados no catálogo próprio — ver attribute_parsers.classify_field,
# que faz match por substring nesses termos em português.
_KNOWN_FIELDS = [
    "Portas RJ45", "Uplinks", "PoE", "Portas PoE", "Budget PoE (W)",
    "Tipo de Gerenciamento", "Camada", "VLANs",
    "Power Requirement / Tensão de Entrada",
]

_SYSTEM_PROMPT = f"""Você é um especialista em extrair especificações técnicas de datasheets de \
equipamentos de rede (switches, access points, transceivers, módulos ópticos).

Leia o texto do datasheet e devolva APENAS um JSON válido no formato:
{{
  "model": "<modelo/part number do produto>",
  "manufacturer": "<fabricante>",
  "category": "<switch|access_point|transceiver|modulo_optico|outro>",
  "specs": {{ "<nome do campo>": "<valor>", ... }}
}}

Regras para os nomes de campo em "specs":
- Reutilize EXATAMENTE estes nomes quando o dado existir no datasheet: {", ".join(_KNOWN_FIELDS)}
- Para outros dados relevantes que não se encaixem nesses campos, crie um nome de campo em português, curto e descritivo.
- Valores booleanos (tem ou não tem o recurso) devem ser true/false.
- Não invente valor que não está no texto — se não encontrar, não inclua o campo.

Responda APENAS com o objeto JSON. Nada de texto antes, comentário depois, ou markdown (sem \`\`\`)."""


def _parse_json_loosely(raw_json: str) -> dict | None:
    """
    Tenta parsear o JSON como veio; se falhar, aplica correções comuns de
    modelos pequenos (vírgula sobrando antes de '}'/']', valor sem aspas,
    aspas assimétricas etc. via json_repair) antes de desistir.
    Retorna None se não der pra recuperar — o caller trata como "sem specs".
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

    try:
        repaired = repair_json(raw_json)
        parsed = json.loads(repaired)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def extract_specs_from_pdf(pdf_bytes: bytes, filename: str = "datasheet.pdf") -> dict:
    """
    OCR do PDF + LLM estrutura as specs no vocabulário do catálogo.

    Retorna {"model": str, "manufacturer": str, "category": str, "specs": dict, "raw_text": str}.
    Nunca lança exceção por falha do LLM — nesse caso volta com specs vazio
    (o caller decide se pede pro usuário preencher manualmente).
    """
    parsed = parse_pdf(pdf_bytes, filename=filename)
    text = parsed.full_text[:8000]  # datasheet é curto; limite generoso pro contexto do LLM

    result = {"model": "", "manufacturer": "", "category": "", "specs": {}, "raw_text": parsed.full_text}

    if not text.strip():
        logger.warning("[DatasheetExtractor] PDF sem texto extraivel: %s", filename)
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
                result["model"] = str(data.get("model") or "")
                result["manufacturer"] = str(data.get("manufacturer") or "")
                result["category"] = str(data.get("category") or "")
                result["specs"] = data.get("specs") or {}
        else:
            logger.warning("[DatasheetExtractor] Resposta do LLM sem JSON para %s: %s", filename, raw[:200])
    except Exception as exc:
        logger.error("[DatasheetExtractor] Falha ao extrair specs de %s: %s", filename, exc, exc_info=True)

    return result
