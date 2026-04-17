from __future__ import annotations

import json
import logging
import re
import hashlib
import time
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Union

import os
import ollama

# Import opcional do módulo shared (persistência). O pacote `Pncp/apiPncp`
# contém um `shared` que não está no PYTHONPATH por padrão em alguns runners;
# quem usar persistência deve ajustar o PYTHONPATH ou fornecer um stub.
try:
    from shared import db  # comente se não quiser persistência aqui
except Exception:
    db = None

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# Configuração
# ──────────────────────────────────────────

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MAX_CHARS_POR_CHUNK = int(os.environ.get("MAX_CHARS_POR_CHUNK", "10000"))
TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.0"))
NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "4096"))

# ──────────────────────────────────────────
# Tipos de saída
# ──────────────────────────────────────────

@dataclass
class ItemAta:
    """Representa um item extraído da ata pelo LLM."""
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
    """Resultado completo da análise de uma ata."""
    id_pncp: str | None = None
    numero_ata: str | None = None
    orgao: str | None = None
    data_assinatura: str | None = None
    vigencia: str | None = None
    objeto: str | None = None
    itens: list[ItemAta] = field(default_factory=list)
    tokens_usados: int = 0
    aviso: str | None = None


# ──────────────────────────────────────────
# Prompt ajustado
# ──────────────────────────────────────────

SYSTEM_PROMPT = """\
Você é um especialista em licitações públicas brasileiras e Atas de Registro de Preços (ARP).

Sua tarefa é extrair APENAS os ITENS reais da ata.

ATENÇÃO:
- O texto pode conter cláusulas jurídicas, penalidades, vigência, reajuste, sanções, cabeçalhos, rodapés e outros trechos administrativos.
- Você deve FILTRAR e IGNORAR tudo que NÃO for item contratável.

DEFINIÇÃO DE ITEM VÁLIDO:
Considere item apenas registros que representem produto, equipamento, material, lote de fornecimento ou serviço contratável.
Um item válido normalmente contém pelo menos um dos seguintes elementos:
- descrição de produto/serviço
- quantidade
- unidade
- valor unitário
- valor total
- fornecedor
- especificações técnicas

IGNORE COMPLETAMENTE:
- cláusulas legais (ex.: "7. NEGOCIAÇÃO DE PREÇOS", "DAS SANÇÕES", "DA VIGÊNCIA")
- artigos de lei
- cabeçalhos institucionais
- rodapés
- textos administrativos
- condições de participação
- penalidades, recursos, reajustes, cancelamento, vigência, adesão
- qualquer trecho que não seja claramente um item

REGRAS DE EXTRAÇÃO:
- Extraia TODOS os itens válidos, mesmo incompletos.
- NÃO invente dados.
- Use null quando o campo não estiver presente ou não for confiável.
- Preserve o texto original do item em raw_descricao.
- Limpe a descrição removendo prefixos como "LOTE 1:", "ITEM 3:", quando eles não fizerem parte do nome do produto.
- Se houver vários fornecedores, associe o fornecedor correto a cada item quando isso estiver explícito.

REGRAS DE VALORES:
- Use número float com ponto decimal.
- Remova símbolos como R$.
- Remova separador de milhar.
- Se não for possível confiar no valor, use null.

REGRAS DE ESPECIFICAÇÕES:
- Preencha especificacoes apenas com características técnicas realmente presentes no texto.
- Exemplos: portas, velocidade, PoE, padrão IEEE, tensão, capacidade, dimensão, cor, tamanho, voltagem, categoria do cabo.
- Não invente especificações genéricas.

RETORNE APENAS UM OBJETO JSON VÁLIDO.
Não inclua markdown.
Não inclua comentários.
Não inclua texto antes ou depois do JSON.

Schema obrigatório:
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
      "quantidade": número inteiro ou null,
      "unidade": "string ou null",
      "valor_unitario": número float ou null,
      "valor_total": número float ou null,
      "fornecedor": "string ou null",
      "cnpj_fornecedor": "string ou null",
      "especificacoes": ["lista de strings"],
      "observacoes": "string ou null"
    }
  ]
}
"""

USER_TEMPLATE = "Analise a ata abaixo e extraia SOMENTE os itens válidos no formato JSON exigido.\n\n{texto}"

USER_TEMPLATE_ITEM = (
    "Analise o bloco de texto abaixo e retorne APENAS um OBJETO JSON representando UM ITEM VÁLIDO.\n"
    "Se o bloco não for um item real contratável, retorne um objeto com todos os campos null e raw_descricao com o texto original.\n"
    "Nunca invente dados. Inclua sempre raw_descricao.\n"
    "Use exatamente este formato de objeto:\n"
    "{\"numero_item\": null, \"descricao\": null, \"raw_descricao\": null, \"tipo\": null, \"marca\": null, \"modelo\": null, \"quantidade\": null, \"unidade\": null, \"valor_unitario\": null, \"valor_total\": null, \"fornecedor\": null, \"cnpj_fornecedor\": null, \"especificacoes\": [], \"observacoes\": null}\n\n"
    "Bloco:\n{texto_item}"
)


# Cliente Ollama (singleton)
_client: ollama.Client | None = None


def _get_client() -> ollama.Client:
    global _client
    if _client is None:
        _client = ollama.Client(host=OLLAMA_HOST)
        logger.info("[LLM] Ollama conectado em %s | modelo: %s", OLLAMA_HOST, OLLAMA_MODEL)
    return _client


def _repair_json_with_ollama(resposta_raw: str) -> str:
    """Pede ao Ollama para consertar uma saída JSON inválida."""
    client = _get_client()
    repairs_dir = Path(__file__).resolve().parent / "results_llm_repairs"
    repairs_dir.mkdir(parents=True, exist_ok=True)

    system = (
        "Você corrige JSON malformado. "
        "Retorne APENAS JSON válido e nada mais. "
        "Se algo estiver truncado ou incerto, use null."
    )

    user = "Conserte somente este JSON:\n\n" + resposta_raw

    resp = client.chat(
        model=OLLAMA_MODEL,
        format="json",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        options={"temperature": 0.0, "num_predict": NUM_PREDICT},
    )

    repaired = None
    try:
        repaired = resp["message"]["content"].strip()
    except Exception:
        repaired = json.dumps(resp, ensure_ascii=False)

    ts = int(time.time())
    fname = repairs_dir / f"repair_{ts}.txt"
    try:
        fname.write_text(repaired, encoding="utf-8")
    except Exception:
        logger.exception("Falha ao salvar repair log")

    return repaired


# ──────────────────────────────────────────
# Chunking
# ──────────────────────────────────────────

def _dividir_em_chunks(texto: str, max_chars: int = MAX_CHARS_POR_CHUNK) -> list[str]:
    """Divide o texto em blocos respeitando quebras de parágrafo."""
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


def _split_into_item_blocks(texto: str) -> list[str]:
    """Tenta dividir o texto em blocos por item usando heurísticas."""
    pattern = re.compile(r"(?im)^(?:item\s+\d+|\d{1,4}\s*[\.\-\)]\s+)")
    matches = list(pattern.finditer(texto))
    if len(matches) < 3:
        return []

    starts = [m.start() for m in matches]
    blocks: list[str] = []
    for i, s in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(texto)
        block = texto[s:end].strip()
        if block:
            blocks.append(block)

    return blocks


# ──────────────────────────────────────────
# Limpeza / normalização
# ──────────────────────────────────────────

def _normalize_text_for_dedupe(s: str) -> str:
    if not s:
        return ""

    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9\s]", " ", s)

    stopwords = {
        "de", "da", "do", "das", "dos", "para", "com",
        "item", "lote", "registro", "ata", "contrato", "processo"
    }
    tokens = [t for t in s.split() if t not in stopwords]
    s = " ".join(tokens)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _is_lote_prefix(s: str) -> str | None:
    if not s:
        return None
    cleaned = re.sub(r"(?i)^\s*(?:lote|item)\s*\d+[:\-\)]\s*", "", s).strip()
    return cleaned


def _looks_like_juridical_text(texto: str) -> bool:
    if not texto:
        return True
    t = _normalize_text_for_dedupe(texto)
    juridicos = [
        "negociacao precos", "sancoes", "vigencia", "cancelamento",
        "reajuste", "penalidade", "recurso", "adesao", "lei 14133",
        "orgao gerenciador", "cadastro reserva", "administracao publica"
    ]
    return any(j in t for j in juridicos)


def _clean_item_dict(d: dict) -> dict:
    allowed = {
        "numero_item", "descricao", "tipo", "marca", "modelo", "quantidade",
        "unidade", "valor_unitario", "valor_total", "fornecedor", "cnpj_fornecedor",
        "especificacoes", "observacoes", "raw_descricao"
    }
    new = {k: d.get(k) for k in allowed}

    if not new.get("raw_descricao") and new.get("descricao"):
        new["raw_descricao"] = new["descricao"]

    for key in ("raw_descricao", "descricao"):
        if new.get(key):
            new[key] = _is_lote_prefix(str(new[key]))

    if isinstance(new.get("especificacoes"), list):
        new["especificacoes"] = [str(x).strip() for x in new["especificacoes"] if str(x).strip()]
    else:
        new["especificacoes"] = []

    return new


def _dedupe_items(items: list[dict]) -> list[dict]:
    grupos: dict[str, dict] = {}

    for d in items:
        desc_ref = d.get("raw_descricao") or d.get("descricao") or ""
        chave = _normalize_text_for_dedupe(desc_ref)
        if not chave:
            continue

        fornecedor = _normalize_text_for_dedupe(str(d.get("fornecedor") or ""))
        valor = str(d.get("valor_unitario") or "")
        chave_full = f"{chave}|{fornecedor}|{valor}"
        key_hash = hashlib.sha1(chave_full.encode("utf-8")).hexdigest()

        if key_hash not in grupos:
            grupos[key_hash] = d.copy()
            continue

        existente = grupos[key_hash]

        q1 = _int(existente.get("quantidade"))
        q2 = _int(d.get("quantidade"))
        if q1 is not None and q2 is not None:
            existente["quantidade"] = q1 + q2
        elif q1 is None and q2 is not None:
            existente["quantidade"] = q2

        v1 = _float(existente.get("valor_total"))
        v2 = _float(d.get("valor_total"))
        if v1 is not None and v2 is not None:
            existente["valor_total"] = round(v1 + v2, 2)
        elif v1 is None and v2 is not None:
            existente["valor_total"] = v2

        if len(str(d.get("descricao") or "")) > len(str(existente.get("descricao") or "")):
            existente["descricao"] = d.get("descricao")

        specs = list(existente.get("especificacoes") or [])
        for spec in d.get("especificacoes") or []:
            if spec not in specs:
                specs.append(spec)
        existente["especificacoes"] = specs

    return list(grupos.values())


def _filter_invalid_items(items: list[dict]) -> list[dict]:
    out: list[dict] = []
    for d in items:
        desc = d.get("descricao") or d.get("raw_descricao") or ""
        if _looks_like_juridical_text(desc):
            continue

        tem_conteudo = any([
            d.get("descricao"), d.get("raw_descricao"), d.get("quantidade"),
            d.get("valor_unitario"), d.get("valor_total"), d.get("fornecedor")
        ])
        if not tem_conteudo:
            continue

        out.append(d)
    return out


def _extract_id_pncp(texto: str) -> str | None:
    if not texto:
        return None
    m = re.search(r"(\d{1,6}/\d{4})", texto)
    if m:
        return m.group(1)
    m = re.search(r"N[º°]?\s*(\d{1,6})(?:[\-/](\d{2,4}))?", texto, flags=re.IGNORECASE)
    if m:
        return "/".join(filter(None, m.groups()))
    m = re.search(r"Ata\s*[-:]?\s*(\d{1,6})", texto, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return None


# ──────────────────────────────────────────
# Chamada ao LLM
# ──────────────────────────────────────────

def _chamar_llm(texto_chunk: str) -> tuple[dict, int]:
    client = _get_client()

    response = client.chat(
        model=OLLAMA_MODEL,
        format="json",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(texto=texto_chunk)},
        ],
        options={
            "temperature": TEMPERATURE,
            "num_predict": NUM_PREDICT,
        },
    )

    resposta_raw: str = response["message"]["content"].strip()
    resposta_raw = re.sub(r"^```(?:json)?\s*", "", resposta_raw)
    resposta_raw = re.sub(r"\s*```$", "", resposta_raw)

    try:
        dados = json.loads(resposta_raw)
    except json.JSONDecodeError as e:
        logger.error("[LLM] JSON inválido: %s | preview: %s", e, resposta_raw[:300])
        try:
            reparado = _repair_json_with_ollama(resposta_raw)
            dados = json.loads(reparado)
            logger.info("[LLM] Reparo automático por Ollama bem-sucedido")
        except Exception as repair_exc:
            logger.exception("[LLM] Falha ao chamar reparo automático: %s", repair_exc)
            raise ValueError(f"LLM retornou JSON inválido: {e}") from e

    tokens = response.get("eval_count", 0) + response.get("prompt_eval_count", 0)
    return dados, tokens


def _chamar_llm_item(texto_item: str) -> tuple[dict, int]:
    client = _get_client()

    response = client.chat(
        model=OLLAMA_MODEL,
        format="json",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE_ITEM.format(texto_item=texto_item)},
        ],
        options={
            "temperature": TEMPERATURE,
            "num_predict": NUM_PREDICT,
        },
    )

    resposta_raw: str = response["message"]["content"].strip()
    resposta_raw = re.sub(r"^```(?:json)?\s*", "", resposta_raw)
    resposta_raw = re.sub(r"\s*```$", "", resposta_raw)

    try:
        dados = json.loads(resposta_raw)
    except json.JSONDecodeError as e:
        logger.error("[LLM] JSON inválido (item): %s | preview: %s", e, resposta_raw[:300])
        try:
            reparado = _repair_json_with_ollama(resposta_raw)
            dados = json.loads(reparado)
            logger.info("[LLM] Reparo automático por Ollama (item) bem-sucedido")
        except Exception as repair_exc:
            logger.exception("[LLM] Falha ao chamar reparo automático (item): %s", repair_exc)
            raise ValueError(f"LLM retornou JSON inválido para item: {e}") from e

    tokens = response.get("eval_count", 0) + response.get("prompt_eval_count", 0)
    return dados, tokens


def _mesclar_chunks(resultados: list[dict]) -> dict:
    if not resultados:
        return {}
    base = resultados[0].copy()
    todos_itens: list[dict] = list(base.get("itens") or [])
    for r in resultados[1:]:
        todos_itens.extend(r.get("itens") or [])
    base["itens"] = todos_itens
    return base


# ──────────────────────────────────────────
# Conversão dict → dataclasses
# ──────────────────────────────────────────

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


def _int(v) -> int | None:
    try:
        if v is None or v == "":
            return None
        return int(float(str(v).replace(",", ".")))
    except (ValueError, TypeError):
        return None


def _float(v) -> float | None:
    try:
        if v is None or v == "":
            return None
        s = str(v).strip().replace("R$", "").replace(" ", "")
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
        return float(s)
    except (ValueError, TypeError):
        return None


# ──────────────────────────────────────────
# Função principal
# ──────────────────────────────────────────

def analisar_ata(
    texto: str,
    id_pncp: str | None = None,
    persistir: bool = False,
) -> ResultadoAnalise:
    """
    Analisa o texto (markdown/txt) de uma ata usando Ollama.
    """
    if not texto or not texto.strip():
        logger.warning("[LLM] Texto vazio para %s", id_pncp)
        return ResultadoAnalise(id_pncp=id_pncp, aviso="texto vazio")

    guessed_id = _extract_id_pncp(texto)
    if not id_pncp and guessed_id:
        id_pncp = guessed_id

    label = id_pncp or "ata"

    try:
        md_dir = Path(__file__).resolve().parent / "textos_md"
        md_dir.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", label or f"ata_{int(time.time())}")
        out_path = md_dir / f"{stem}.md"
        out_path.write_text(texto, encoding="utf-8")
        logger.info("[LLM] Texto salvo em: %s", out_path)
    except Exception as e:
        logger.warning("Falha ao salvar md: %s", e)

    logger.info("[LLM] Iniciando: %s (%s chars)", label, len(texto))

    item_blocks = _split_into_item_blocks(texto)
    total_tokens = 0
    aviso = None

    if item_blocks:
        logger.info("[LLM] Detectados %s blocos de item — usando item-mode", len(item_blocks))
        chunks = _dividir_em_chunks(texto)
        try:
            meta_dados, meta_tokens = _chamar_llm(chunks[0])
            total_tokens += meta_tokens
        except Exception as e:
            logger.warning("[LLM] Falha ao extrair metadados: %s", e)
            meta_dados = {}

        itens_raw: list[dict] = []
        for idx, block in enumerate(item_blocks, 1):
            logger.info("[LLM] Item-mode: processando item %s/%s (%s chars)", idx, len(item_blocks), len(block))
            try:
                item_d, item_tokens = _chamar_llm_item(block)
                itens_raw.append(item_d)
                total_tokens += item_tokens
            except Exception as e:
                logger.error("[LLM] Erro ao processar item %s: %s", idx, e)
                numero_guess = None
                m = re.match(r"(?i)^(?:item\s*)?(\d{1,4})", block.strip())
                if m:
                    numero_guess = m.group(1)
                itens_raw.append({
                    "numero_item": numero_guess,
                    "descricao": None,
                    "raw_descricao": block,
                    "tipo": None,
                    "marca": None,
                    "modelo": None,
                    "quantidade": None,
                    "unidade": None,
                    "valor_unitario": None,
                    "valor_total": None,
                    "fornecedor": None,
                    "cnpj_fornecedor": None,
                    "especificacoes": [],
                    "observacoes": None,
                })

        dados = meta_dados or {}
        itens_clean = [_clean_item_dict(d) for d in itens_raw]
        itens_clean = _filter_invalid_items(itens_clean)
        itens_clean = _dedupe_items(itens_clean)
        dados["itens"] = itens_clean
        itens = [_para_item(d) for d in (dados.get("itens") or [])]
    else:
        chunks = _dividir_em_chunks(texto)
        aviso = f"texto dividido em {len(chunks)} chunks" if len(chunks) > 1 else None

        resultados_raw: list[dict] = []
        for i, chunk in enumerate(chunks, 1):
            logger.info("[LLM] Chunk %s/%s (%s chars)", i, len(chunks), len(chunk))
            try:
                dados_chunk, tokens = _chamar_llm(chunk)
                resultados_raw.append(dados_chunk)
                total_tokens += tokens
            except Exception as e:
                logger.error("[LLM] Erro chunk %s/%s de %s: %s", i, len(chunks), label, e)
                if i == 1:
                    return ResultadoAnalise(id_pncp=id_pncp, aviso=f"erro LLM: {e}")
                aviso = (aviso or "") + f" | erro chunk {i}: {e}"

        dados = _mesclar_chunks(resultados_raw)
        itens_clean = [_clean_item_dict(d) for d in (dados.get("itens") or [])]
        itens_clean = _filter_invalid_items(itens_clean)
        itens_clean = _dedupe_items(itens_clean)
        dados["itens"] = itens_clean
        itens = [_para_item(d) for d in (dados.get("itens") or [])]

    resultado = ResultadoAnalise(
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

    logger.info("[LLM] Concluído %s: %s itens | %s tokens", label, len(itens), total_tokens)

    if persistir and id_pncp:
        _persistir(id_pncp, resultado)

    return resultado


# ──────────────────────────────────────────
# Persistência
# ──────────────────────────────────────────

def _persistir(id_pncp: str, resultado: ResultadoAnalise) -> None:
    if db is None:
        logger.info("[LLM] Persistência desabilitada (shared.db não disponível) — pulando persistência para %s", id_pncp)
        return
    try:
        for item in resultado.itens:
            db.inserir_item_ata(id_pncp, {
                "id_pncp": id_pncp,
                "numero_item": item.numero_item,
                "descricao_llm": item.descricao,
                "tipo": item.tipo,
                "marca_extraida": item.marca,
                "modelo_extraido": item.modelo,
                "quantidade": item.quantidade,
                "unidade": item.unidade,
                "valor_unitario": item.valor_unitario,
                "valor_total": item.valor_total,
                "fornecedor": item.fornecedor,
                "cnpj_fornecedor": item.cnpj_fornecedor,
                "especificacoes": json.dumps(item.especificacoes, ensure_ascii=False),
                "observacoes": item.observacoes,
                "status_llm": "ok",
            })
        db.atualizar_status(id_pncp, "llm", "ok")
        logger.info("[LLM] %s itens persistidos — %s", len(resultado.itens), id_pncp)
    except Exception as e:
        logger.error("[LLM] Erro ao persistir %s: %s", id_pncp, e)
        try:
            db.atualizar_status(id_pncp, "llm", "erro_persistencia")
        except Exception:
            logger.exception("Falha ao atualizar status de persistência")


# ──────────────────────────────────────────
# Exportação (dataclass → dict / JSON)
# ──────────────────────────────────────────

def resultado_para_dict(resultado: ResultadoAnalise) -> dict:
    return asdict(resultado)


def resultado_para_json(resultado: ResultadoAnalise, indent: int = 2) -> str:
    return json.dumps(resultado_para_dict(resultado), ensure_ascii=False, indent=indent)


# ──────────────────────────────────────────
# Wrapper para pipeline_atas.py
# ──────────────────────────────────────────

def analisar_texto_ata_extraido(
    texto_ocr: str,
    id_pncp: str,
    nome_arquivo: str = "",
) -> ResultadoAnalise | None:
    if not texto_ocr or not texto_ocr.strip():
        logger.warning("[LLM] Texto vazio — %s / %s", id_pncp, nome_arquivo)
        return None
    try:
        return analisar_ata(texto_ocr, id_pncp=id_pncp)
    except Exception as e:
        logger.error("[LLM] Falha em %s (%s): %s", nome_arquivo, id_pncp, e)
        return None


# ──────────────────────────────────────────
# CLI
# ──────────────────────────────────────────

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
        print("Uso: python pipelinellm_prompt_ajustado.py <arquivo.md> [id_pncp]")
        raise SystemExit(1)

    resultado = run_arquivo(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(resultado_para_json(resultado))
