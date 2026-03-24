"""
Pipeline 2: consulta a API do PNCP para cada ID e salva itens + resultados no banco.

Responsabilidades:
  - Buscar itens da contratação
  - Buscar resultado de cada item (vencedor + preço homologado)
  - Classificar se o item é o produto-alvo (regex + Ollama opcional)
  - Persistir no banco via shared/db.py
"""

from __future__ import annotations

import re
import time
import json
import logging
from pathlib import Path

import requests

from shared.pnpc_client import PNCPId, build_session, buscar_itens, buscar_resultado_item
from shared import db

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# Configurações
# ──────────────────────────────────────────

PAUSA_ENTRE_ITENS = 0.5   # segundos entre chamadas de resultado (evita rate limit)
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"
OLLAMA_ATIVO = False  # mude para True quando Ollama estiver rodando

# Palavra-chave do produto que você está pesquisando
# Altere conforme o produto: "switch", "nobreak", "servidor", etc.
KEYWORD_PRODUTO = "switch"


# ──────────────────────────────────────────
# Classificação Regex (algoritmo 1 — determinístico)
# ──────────────────────────────────────────

_RE_PRODUTO_PRINCIPAL = re.compile(
    r"\b" + re.escape(KEYWORD_PRODUTO) + r"\b",
    re.IGNORECASE,
)
_RE_ACESSORIO = re.compile(
    r"\b(cabo|rack|patch|suporte|fonte|módulo|sfp|gbic|transceiver)\b",
    re.IGNORECASE,
)
_RE_MARCA = re.compile(
    r"\b(cisco|intelbras|mikrotik|huawei|hp|hpe|dell|d-link|tp-link|juniper|aruba|extreme|allied)\b",
    re.IGNORECASE,
)
_RE_MODELO = re.compile(
    r"\b([A-Z]{1,5}[-\s]?\d{3,6}[A-Z0-9\-]*)\b"
)


def classificar_regex(descricao: str) -> dict:
    """Retorna dict com principal, marca e modelo extraídos via regex."""
    if not descricao:
        return {"principal": False, "marca": None, "modelo": None}

    tem_produto = bool(_RE_PRODUTO_PRINCIPAL.search(descricao))
    tem_acessorio = bool(_RE_ACESSORIO.search(descricao))

    marca_match = _RE_MARCA.search(descricao)
    modelo_match = _RE_MODELO.search(descricao)

    return {
        "principal": tem_produto and not tem_acessorio,
        "marca": marca_match.group(0).title() if marca_match else None,
        "modelo": modelo_match.group(0) if modelo_match else None,
    }


# ──────────────────────────────────────────
# Classificação Ollama (algoritmo 2 — LLM local)
# ──────────────────────────────────────────

def classificar_ollama(descricao: str) -> dict:
    """Chama o Ollama local para classificar e extrair marca/modelo."""
    prompt = f"""Analise esta descrição de item de licitação pública brasileira:

"{descricao}"

Responda SOMENTE com JSON válido, sem explicações:
{{
  "principal": true/false,   // true se o item principal é um {KEYWORD_PRODUTO}
  "marca": "string ou null", // marca do equipamento
  "modelo": "string ou null" // modelo do equipamento
}}"""

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=30,
        )
        resp.raise_for_status()
        texto = resp.json().get("response", "")
        # extrai JSON da resposta
        match = re.search(r"\{.*?\}", texto, re.DOTALL)
        if match:
            dados = json.loads(match.group(0))
            return {
                "principal": bool(dados.get("principal")),
                "marca": dados.get("marca"),
                "modelo": dados.get("modelo"),
            }
    except Exception as e:
        logger.warning(f"Ollama falhou: {e}")

    return {"principal": None, "marca": None, "modelo": None}


# ──────────────────────────────────────────
# Pipeline principal
# ──────────────────────────────────────────

def processar_id(pid: PNCPId, session: requests.Session) -> str:
    """
    Processa um ID PNCP completo:
    1. Busca itens da contratação
    2. Para cada item que contém a keyword: busca resultado + classifica
    3. Salva no banco

    Retorna o status final: 'ok' | 'sem_itens' | 'erro'
    """
    logger.info(f"[API] Iniciando: {pid}")

    try:
        itens = buscar_itens(session, pid)
    except Exception as e:
        logger.error(f"[API] Erro ao buscar itens {pid}: {e}")
        db.atualizar_status(str(pid), "api", "erro")
        return "erro"

    if not itens:
        logger.info(f"[API] Sem itens: {pid}")
        db.atualizar_status(str(pid), "api", "sem_itens")
        return "sem_itens"

    itens_salvos = 0

    for item in itens:
        descricao = str(item.get("descricao") or item.get("descricaoItem") or "")

        # filtra apenas itens com a keyword
        if KEYWORD_PRODUTO.lower() not in descricao.lower():
            continue

        numero_item = item.get("numeroItem") or item.get("numero") or 0

        # busca resultado (vencedor + preço)
        try:
            resultados = buscar_resultado_item(session, pid, numero_item)
            resultado = resultados[0] if resultados else {}
        except Exception as e:
            logger.warning(f"[API] Erro resultado item {numero_item} de {pid}: {e}")
            resultado = {}

        time.sleep(PAUSA_ENTRE_ITENS)

        # classifica
        regex = classificar_regex(descricao)
        ollama = classificar_ollama(descricao) if OLLAMA_ATIVO else {"principal": None, "marca": None, "modelo": None}

        # monta registro
        registro = {
            "id_pncp": str(pid),
            "numero_item": numero_item,
            "descricao": descricao,
            "quantidade": item.get("quantidade"),
            "unidade_medida": item.get("unidadeMedida"),
            "valor_estimado": item.get("valorUnitarioEstimado"),
            "valor_homologado": resultado.get("valorUnitario"),
            "valor_total_homolog": resultado.get("valorTotal"),
            "nome_vencedor": resultado.get("nomeRazaoSocialFornecedor"),
            "cnpj_vencedor": resultado.get("cnpjFornecedor"),
            "porte_vencedor": resultado.get("porteFornecedor"),
            "data_resultado": resultado.get("dataResultado"),
            "situacao_item": item.get("situacaoCompraItem"),
            "srp": 1 if item.get("temResultado") else 0,
            "principal_regex": 1 if regex["principal"] else 0,
            "marca_regex": regex["marca"],
            "modelo_regex": regex["modelo"],
            "principal_ollama": 1 if ollama["principal"] else (0 if ollama["principal"] is False else None),
            "marca_ollama": ollama["marca"],
            "modelo_ollama": ollama["modelo"],
        }

        try:
            db.inserir_item_api(str(pid), registro)
            itens_salvos += 1
        except Exception as e:
            logger.error(f"[API] Erro ao salvar item {numero_item} de {pid}: {e}")

    status = "ok" if itens_salvos > 0 else "sem_keyword"
    db.atualizar_status(str(pid), "api", status)
    logger.info(f"[API] Concluído {pid}: {itens_salvos} itens salvos ({status})")
    return status


def run(ids: list[PNCPId]) -> None:
    """Ponto de entrada para o menu. Processa lista de IDs sequencialmente."""
    session = build_session()
    for pid in ids:
        processar_id(pid, session)