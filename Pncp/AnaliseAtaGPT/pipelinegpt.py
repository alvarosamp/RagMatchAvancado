from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Union

from dotenv import load_dotenv
from openai import OpenAI

# carrega .env
load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4")
MAX_CHARS_POR_CHUNK = 10_000

# =========================
# DATACLASSES
# =========================

@dataclass
class ItemAta:
    numero_item: str | None = None
    descricao: str | None = None
    tipo: str | None = None
    marca: str | None = None
    modelo: str | None = None
    quantidade: int | None = None
    unidade: str | None = None
    valor_unitario: float | None = None
    valor_total: float | None = None
    fornecedor: str | None = None
    cnpj_fornecedor: str | None = None
    especificacoes: list[str] = field(default_factory=list)
    observacoes: str | None = None
    raw_descricao: str | None = None


@dataclass
class ResultadoAnalise:
    id_pncp: str | None = None
    numero_ata: str | None = None
    orgao: str | None = None
    data_assinatura: str | None = None
    vigencia: str | None = None
    objeto: str | None = None
    itens: list[ItemAta] = field(default_factory=list)
    tokens_usados: int = 0
    aviso: str | None = None


# =========================
# PROMPT AJUSTADO
# =========================

SYSTEM_PROMPT = """Você é um especialista em licitações públicas brasileiras e Atas de Registro de Preços (ARP).

Sua tarefa é extrair APENAS os ITENS reais da ata.

IMPORTANTE:
- Ignore cláusulas jurídicas, penalidades, reajustes, artigos de lei, cabeçalhos e rodapés.
- Considere item válido apenas quando representar produto, equipamento ou serviço contratável.
- Não invente dados.
- Se um campo não existir com confiança, use null.
- Preserve o texto original em raw_descricao.
- Limpe prefixos como "ITEM 1", "LOTE 2", se aparecerem no início da descrição.

Retorne APENAS JSON válido com este formato:
{
  "numero_ata": "string ou null",
  "orgao": "string ou null",
  "data_assinatura": "string ou null",
  "vigencia": "string ou null",
  "objeto": "string ou null",
  "itens": [
    {
      "numero_item": "string ou null",
      "descricao": "string ou null",
      "raw_descricao": "string ou null",
      "tipo": "string ou null",
      "marca": "string ou null",
      "modelo": "string ou null",
      "quantidade": number ou null,
      "unidade": "string ou null",
      "valor_unitario": number ou null,
      "valor_total": number ou null,
      "fornecedor": "string ou null",
      "cnpj_fornecedor": "string ou null",
      "especificacoes": ["lista"],
      "observacoes": "string ou null"
    }
  ]
}
"""

USER_TEMPLATE = "Analise a ata abaixo e extraia somente os itens válidos:\n\n{texto}"


# =========================
# CLIENTE OPENAI
# =========================

_client: OpenAI | None = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
        logger.info(f"[LLM] OpenAI inicializado | modelo: {OPENAI_MODEL}")
    return _client


# =========================
# HELPERS
# =========================

def _int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _float(v) -> float | None:
    try:
        return float(str(v).replace(",", ".")) if v is not None else None
    except (ValueError, TypeError):
        return None


def _normalize_text_for_dedupe(s: str) -> str:
    if not s:
        return ""

    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9\s]", " ", s)

    stopwords = {
        "de", "da", "do", "para", "com",
        "item", "lote", "registro",
        "ata", "contrato", "processo"
    }
    tokens = [t for t in s.split() if t not in stopwords]
    s = " ".join(tokens)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _dedupe_items(items: list[dict]) -> list[dict]:
    grupos: dict[str, dict] = {}

    for d in items:
        chave = _normalize_text_for_dedupe(
            d.get("raw_descricao") or d.get("descricao") or ""
        )
        if not chave:
            continue

        if chave not in grupos:
            grupos[chave] = d.copy()
        else:
            existente = grupos[chave]

            if existente.get("quantidade") is not None and d.get("quantidade") is not None:
                existente["quantidade"] += d["quantidade"]

            if existente.get("valor_total") is not None and d.get("valor_total") is not None:
                existente["valor_total"] += d["valor_total"]

            if len(str(d.get("descricao") or "")) > len(str(existente.get("descricao") or "")):
                existente["descricao"] = d.get("descricao")

            if not existente.get("raw_descricao") and d.get("raw_descricao"):
                existente["raw_descricao"] = d["raw_descricao"]

    return list(grupos.values())


def _dividir_em_chunks(texto: str, max_chars: int = MAX_CHARS_POR_CHUNK) -> list[str]:
    if len(texto) <= max_chars:
        return [texto]

    chunks: list[str] = []
    while texto:
        if len(texto) <= max_chars:
            chunks.append(texto)
            break
        corte = texto.rfind("\n", 0, max_chars)
        if corte == -1:
            corte = max_chars
        chunks.append(texto[:corte].strip())
        texto = texto[corte:].strip()

    return chunks


def _para_item(d: dict) -> ItemAta:
    return ItemAta(
        numero_item=d.get("numero_item"),
        descricao=d.get("descricao"),
        tipo=d.get("tipo"),
        marca=d.get("marca"),
        modelo=d.get("modelo"),
        quantidade=_int(d.get("quantidade")),
        unidade=d.get("unidade"),
        valor_unitario=_float(d.get("valor_unitario")),
        valor_total=_float(d.get("valor_total")),
        fornecedor=d.get("fornecedor"),
        cnpj_fornecedor=d.get("cnpj_fornecedor"),
        especificacoes=d.get("especificacoes") or [],
        observacoes=d.get("observacoes"),
        raw_descricao=d.get("raw_descricao"),
    )


def _mesclar_chunks(resultados: list[dict]) -> dict:
    if not resultados:
        return {}
    base = resultados[0].copy()
    todos_itens = list(base.get("itens") or [])
    for r in resultados[1:]:
        todos_itens.extend(r.get("itens") or [])
    base["itens"] = todos_itens
    return base


# =========================
# CHAMADA AO GPT
# =========================

def _chamar_gpt_json(texto_chunk: str) -> tuple[dict, int]:
    client = _get_client()

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(texto=texto_chunk)},
        ],
        text={
            "format": {
                "type": "json_object"
            }
        }
    )

    raw = response.output_text.strip()

    try:
        dados = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"[GPT] JSON inválido: {e} | preview: {raw[:400]}")
        raise ValueError(f"Resposta inválida em JSON: {e}") from e

    usage = getattr(response, "usage", None)
    total_tokens = 0
    if usage:
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        total_tokens = input_tokens + output_tokens

    return dados, total_tokens


# =========================
# FUNÇÃO PRINCIPAL
# =========================

def analisar_ata(
    texto: str,
    id_pncp: str | None = None,
) -> ResultadoAnalise:
    if not texto or not texto.strip():
        return ResultadoAnalise(id_pncp=id_pncp, aviso="texto vazio")

    label = id_pncp or "ata"
    logger.info(f"[GPT] Iniciando análise: {label}")

    chunks = _dividir_em_chunks(texto)
    aviso = f"texto dividido em {len(chunks)} chunks" if len(chunks) > 1 else None

    resultados_raw: list[dict] = []
    total_tokens = 0

    for i, chunk in enumerate(chunks, 1):
        logger.info(f"[GPT] Chunk {i}/{len(chunks)}")
        dados, tokens = _chamar_gpt_json(chunk)
        resultados_raw.append(dados)
        total_tokens += tokens

    dados = _mesclar_chunks(resultados_raw)

    itens_clean = _dedupe_items(dados.get("itens") or [])
    itens = [_para_item(d) for d in itens_clean]

    return ResultadoAnalise(
        id_pncp=id_pncp,
        numero_ata=dados.get("numero_ata"),
        orgao=dados.get("orgao"),
        data_assinatura=dados.get("data_assinatura"),
        vigencia=dados.get("vigencia"),
        objeto=dados.get("objeto"),
        itens=itens,
        tokens_usados=total_tokens,
        aviso=aviso,
    )


# =========================
# EXPORTAÇÃO
# =========================

def resultado_para_dict(resultado: ResultadoAnalise) -> dict:
    return asdict(resultado)


def resultado_para_json(resultado: ResultadoAnalise, indent: int = 2) -> str:
    return json.dumps(resultado_para_dict(resultado), ensure_ascii=False, indent=indent)


# =========================
# WRAPPER PARA O PIPELINE
# =========================

def analisar_texto_ata_extraido(
    texto_ocr: str,
    id_pncp: str,
    nome_arquivo: str = "",
) -> ResultadoAnalise | None:
    if not texto_ocr or not texto_ocr.strip():
        logger.warning(f"[GPT] Texto vazio — {id_pncp} / {nome_arquivo}")
        return None
    try:
        return analisar_ata(texto_ocr, id_pncp=id_pncp)
    except Exception as e:
        logger.error(f"[GPT] Falha em {nome_arquivo} ({id_pncp}): {e}")
        return None


# =========================
# CLI
# =========================

def run_arquivo(caminho: Union[str, Path], id_pncp: str | None = None) -> ResultadoAnalise:
    caminho = Path(caminho)
    texto = caminho.read_text(encoding="utf-8")
    return analisar_ata(texto, id_pncp=id_pncp or caminho.stem)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if len(sys.argv) < 2:
        print("Uso: python pipelinellm_openai.py <arquivo.md> [id_pncp]")
        raise SystemExit(1)

    resultado = run_arquivo(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(resultado_para_json(resultado))