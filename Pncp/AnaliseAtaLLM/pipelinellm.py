"""
pipeline/pipelinellm.py
────────────────────────
Recebe o texto extraído (markdown/txt) de uma ata de registro de preços
e usa um LLM local via Ollama para extrair os itens de forma estruturada.

Responsabilidades:
  - Receber texto markdown/txt de uma ata (saída do docling_parser)
  - Enviar ao Ollama com format="json" (JSON mode nativo)
  - Parsear e validar o JSON retornado
  - Retornar ResultadoAnalise (dataclass) + exportação JSON
  - Persistir no banco via shared/db.py (opcional)

Dependências:
  pip install ollama

Uso rápido (CLI):
  python pipelinellm.py ata_extraida.md [id_pncp]

Uso no código:
  from app.pipeline.pipelinellm import analisar_ata, resultado_para_json
  resultado = analisar_ata(texto, id_pncp="123")
  print(resultado_para_json(resultado))
"""

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

import os

# Modelo default otimizado para baixa latência em CPU; pode ser sobrescrito via
# variável de ambiente OLLAMA_MODEL. Recomendado: 'llama3.2:1b' para baixa
# latência. Se preferir outro, exporte OLLAMA_MODEL antes de rodar.
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")  # padrão do Ollama
MAX_CHARS_POR_CHUNK = 10_000                   

# ──────────────────────────────────────────
# Tipos de saída
# ──────────────────────────────────────────

@dataclass
class ItemAta:
    """Representa um item extraído da ata pelo LLM."""
    numero_item: str | None      = None   # ex: "1", "Item 3"
    descricao: str | None        = None   # descrição completa
    tipo: str | None             = None   # Switch, Roteador, Firewall, AP, etc.
    marca: str | None            = None   # ex: "Cisco", "Intelbras"
    modelo: str | None           = None   # ex: "SG350-28"
    quantidade: int | None       = None   # quantidade registrada
    unidade: str | None          = None   # "unidade", "conjunto", "kit"
    valor_unitario: float | None = None   # valor unitário (R$)
    valor_total: float | None    = None   # valor total do item (R$)
    fornecedor: str | None       = None   # razão social da empresa vencedora
    cnpj_fornecedor: str | None  = None   # CNPJ formatado
    especificacoes: list[str]    = field(default_factory=list)  # specs técnicas
    observacoes: str | None      = None
    raw_descricao: str | None    = None  # texto original do item como apareceu na ata


@dataclass
class ResultadoAnalise:
    """Resultado completo da análise de uma ata."""
    id_pncp: str | None          = None
    numero_ata: str | None       = None
    orgao: str | None            = None
    data_assinatura: str | None  = None   # DD/MM/AAAA
    vigencia: str | None         = None
    objeto: str | None           = None   # objeto geral da ata
    itens: list[ItemAta]         = field(default_factory=list)
    tokens_usados: int           = 0
    aviso: str | None            = None   # ex: "texto dividido em 2 chunks"


# ──────────────────────────────────────────
# Prompt
# ──────────────────────────────────────────

SYSTEM_PROMPT = """\
Você é um especialista em licitações públicas brasileiras e Atas de Registro de Preços (ARPs).

Sua tarefa é extrair todas as informações relevantes do texto da ata fornecida.

Responda APENAS com um objeto JSON válido seguindo exatamente o schema abaixo.
Não inclua texto fora do JSON. Não use blocos de código (sem ```).

Schema obrigatório:
{
  "numero_ata": "string ou null",
  "orgao": "string ou null",
  "data_assinatura": "DD/MM/AAAA ou null",
  "vigencia": "string descritiva ou null",
  "objeto": "descrição do objeto geral da ata ou null",
  "itens": [
    {
      "numero_item": "string ou null",
      "descricao": "descrição completa do item ou null",
      "tipo": "categoria (Switch, Roteador, Firewall, Access Point, Servidor,Bateria, transceiver etc.) ou null",
      "marca": "string ou null",
      "modelo": "modelo exato ou null",
      "quantidade": número inteiro ou null,
      "unidade": "unidade, conjunto, kit, etc. ou null",
      "valor_unitario": número float ou null,
      "valor_total": número float ou null,
      "fornecedor": "razão social da empresa ou null",
      "cnpj_fornecedor": "CNPJ formatado ou null",
      "especificacoes": ["lista de especificações técnicas"],
      "observacoes": "observações adicionais ou null"
    }
  ]
}

Regras:
- Extraia TODOS os itens presentes, mesmo os incompletos.
- Valores monetários: use ponto como decimal (ex: 1250.50), sem R$ ou pontos de milhar.
- Campos ausentes no texto: use null, nunca invente dados.
- especificacoes: inclua portas, velocidade, padrão IEEE, certificações, tensão, etc.
- Se houver vários fornecedores, registre o correto para cada item.\
"""

USER_TEMPLATE = "Analise a ata abaixo e extraia todas as informações:\n\n{texto}"

# Template for per-item extraction: model should return a single item object
USER_TEMPLATE_ITEM = (
    "Analise o bloco de texto do ITEM abaixo e retorne APENAS um OBJETO JSON com as chaves do schema de um item:\n"
    "Inclua também o campo 'raw_descricao' com o texto original do item (sem alterações).\n"
    "Se não tiver certeza de algum campo, use null. Responda somente com o JSON.\n"
    "{texto_item}"
)



# Cliente Ollama (singleton)


_client: ollama.Client | None = None


def _get_client() -> ollama.Client:
    global _client
    if _client is None:
        _client = ollama.Client(host=OLLAMA_HOST)
        logger.info(f"[LLM] Ollama conectado em {OLLAMA_HOST} | modelo: {OLLAMA_MODEL}")
    return _client



# Chunking


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
    """Tenta dividir o texto em blocos por item usando heurísticas.

    Retorna uma lista de strings, cada uma contendo o texto de um item (incluindo
    sua linha de cabeçalho). Se não encontrar marcadores claros, retorna [] para
    indicar que a estratégia falhou e o código deve usar chunking normal.
    """
    # Procura linhas que iniciam itens: exemplos comuns
    # - "Item 1" ou "ITEM 1"
    # - "1. " ou "1 - " ou "1) " no início de linha
    # fix character class ordering and escape hyphen to avoid invalid range
    pattern = re.compile(r"(?im)^(?:item\s+\d+|\d{1,4}\s*[\.\-\)]\s+)")
    matches = list(pattern.finditer(texto))
    if len(matches) < 3:
        # pouquíssimos hits → não arriscamos a dividir por item
        return []

    starts = [m.start() for m in matches]
    blocks: list[str] = []
    for i, s in enumerate(starts):
        end = starts[i+1] if i+1 < len(starts) else len(texto)
        block = texto[s:end].strip()
        if block:
            blocks.append(block)

    return blocks


def _normalize_text_for_dedupe(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9\s]", "", s)
    return s.strip()


def _is_lote_prefix(s: str) -> str | None:
    """Remove lote prefixes like 'LOTE 1:' at start of description and return cleaned string."""
    if not s:
        return None
    cleaned = re.sub(r"(?i)^\s*lote\s*\d+[:\-\)]\s*", "", s).strip()
    return cleaned


def _clean_item_dict(d: dict) -> dict:
    """Keep only allowed keys and clean descricao from lote headers."""
    allowed = {
        "numero_item", "descricao", "tipo", "marca", "modelo", "quantidade",
        "unidade", "valor_unitario", "valor_total", "fornecedor", "cnpj_fornecedor",
        "especificacoes", "observacoes", "raw_descricao"
    }
    new = {k: d.get(k) for k in allowed}
    # If raw_descricao missing, try to preserve descricao
    if not new.get("raw_descricao") and new.get("descricao"):
        new["raw_descricao"] = new["descricao"]

    # Clean lote prefixes from raw_descricao and descricao
    for key in ("raw_descricao", "descricao"):
        if new.get(key):
            cleaned = _is_lote_prefix(str(new[key]))
            if cleaned is not None:
                new[key] = cleaned

    return new


def _dedupe_items(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for d in items:
        key = _normalize_text_for_dedupe(d.get("raw_descricao") or d.get("descricao") or "")
        # also include fornecedor and valor for stronger signal
        key += "|" + str(d.get("fornecedor") or "")
        key += "|" + str(d.get("valor_unitario") or "")
        h = hashlib.sha1(key.encode("utf-8")).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        out.append(d)
    return out


def _extract_id_pncp(texto: str) -> str | None:
    """Heuristically extract an identifier for the ata from the text.
    Tries common patterns like 'Nº 1234/2025', '1234/2025', or 'Ata 1234'.
    """
    if not texto:
        return None
    # common PNCP-like: 4-6 digits / 4 digits
    m = re.search(r"(\d{1,6}/\d{4})", texto)
    if m:
        return m.group(1)
    # N° or Nº forms
    m = re.search(r"N\°\s*(\d{1,6})[\-/]?(\d{2,4})?", texto, flags=re.IGNORECASE)
    if m:
        return "/".join(filter(None, m.groups()))
    # 'Ata - 1432' like patterns
    m = re.search(r"Ata\s*[-:]?\s*(\d{1,6})", texto, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return None



# Chamada ao LLM


def _chamar_llm(texto_chunk: str) -> tuple[dict, int]:
    """
    Envia um chunk ao Ollama com JSON mode ativado.
    Retorna (dict_parsed, tokens_usados).
    """
    client = _get_client()

    response = client.chat(
        model=OLLAMA_MODEL,
        format="json",          # JSON mode nativo do Ollama — garante saída estruturada
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": USER_TEMPLATE.format(texto=texto_chunk)},
        ],
        options={
            "temperature": 0.0,  # determinístico para extração de dados
            "num_predict": 4096,
        },
    )

    resposta_raw: str = response["message"]["content"].strip()

    # Remove blocos de código caso o modelo os inclua mesmo com format="json"
    resposta_raw = re.sub(r"^```(?:json)?\s*", "", resposta_raw)
    resposta_raw = re.sub(r"\s*```$", "", resposta_raw)

    try:
        dados = json.loads(resposta_raw)
    except json.JSONDecodeError as e:
        logger.error(f"[LLM] JSON inválido: {e} | preview: {resposta_raw[:300]}")
        raise ValueError(f"LLM retornou JSON inválido: {e}") from e

    # Ollama reporta tokens em eval_count (output) e prompt_eval_count (input)
    tokens = response.get("eval_count", 0) + response.get("prompt_eval_count", 0)

    return dados, tokens


def _chamar_llm_item(texto_item: str) -> tuple[dict, int]:
    """Envia um bloco de ITEM para o LLM e retorna um dicionário representando
    o item extraído e o número estimado de tokens usados.
    Em caso de falha de parse, a função lança ValueError.
    """
    client = _get_client()

    response = client.chat(
        model=OLLAMA_MODEL,
        format="json",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": USER_TEMPLATE_ITEM.format(texto_item=texto_item)},
        ],
        options={
            "temperature": 0.0,
            "num_predict": 4096,
        },
    )

    resposta_raw: str = response["message"]["content"].strip()
    resposta_raw = re.sub(r"^```(?:json)?\s*", "", resposta_raw)
    resposta_raw = re.sub(r"\s*```$", "", resposta_raw)

    try:
        dados = json.loads(resposta_raw)
    except json.JSONDecodeError as e:
        logger.error(f"[LLM] JSON inválido (item): {e} | preview: {resposta_raw[:300]}")
        raise ValueError(f"LLM retornou JSON inválido para item: {e}") from e

    tokens = response.get("eval_count", 0) + response.get("prompt_eval_count", 0)
    return dados, tokens


def _mesclar_chunks(resultados: list[dict]) -> dict:
    """Mescla resultados de múltiplos chunks: metadados do primeiro, itens de todos."""
    if not resultados:
        return {}
    base = resultados[0].copy()
    todos_itens: list[dict] = list(base.get("itens") or [])
    for r in resultados[1:]:
        todos_itens.extend(r.get("itens") or [])
    base["itens"] = todos_itens
    return base



# Conversão dict → dataclasses


def _para_item(d: dict) -> ItemAta:
    return ItemAta(
        numero_item     = d.get("numero_item"),
        descricao       = d.get("descricao"),
        tipo            = d.get("tipo"),
        marca           = d.get("marca"),
        modelo          = d.get("modelo"),
        quantidade      = _int(d.get("quantidade")),
        unidade         = d.get("unidade"),
        valor_unitario  = _float(d.get("valor_unitario")),
        valor_total     = _float(d.get("valor_total")),
        fornecedor      = d.get("fornecedor"),
        cnpj_fornecedor = d.get("cnpj_fornecedor"),
        especificacoes  = d.get("especificacoes") or [],
        observacoes     = d.get("observacoes"),
        raw_descricao   = d.get("raw_descricao"),
    )


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



# Função principal


def analisar_ata(
    texto: str,
    id_pncp: str | None = None,
    persistir: bool = False,
) -> ResultadoAnalise:
    """
    Analisa o texto (markdown/txt) de uma ata usando Llama via Ollama.

    Args:
        texto:     Texto extraído da ata (saída do docling_parser ou similar).
        id_pncp:   Identificador PNCP (para log e persistência).
        persistir: Se True, salva os itens no banco via shared/db.py.

    Returns:
        ResultadoAnalise com todos os itens extraídos.
    """
    if not texto or not texto.strip():
        logger.warning(f"[LLM] Texto vazio para {id_pncp}")
        return ResultadoAnalise(id_pncp=id_pncp, aviso="texto vazio")

    # attempt to find an id inside the text if not provided
    guessed_id = _extract_id_pncp(texto)
    if not id_pncp and guessed_id:
        id_pncp = guessed_id

    label = id_pncp or "ata"

    # Save the raw text as markdown for traceability
    try:
        md_dir = Path(os.path.expanduser("/Users/alvarosamp/Documents/Projetos/RagMatchAvan-ado/Pncp/AnaliseAtaLLM/textos_md"))
        md_dir.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", label or f"ata_{int(time.time())}")
        out_path = md_dir / f"{stem}.md"
        out_path.write_text(texto, encoding="utf-8")
        logger.info(f"[LLM] Texto salvo em: {out_path}")
    except Exception as e:
        logger.warning(f"Falha ao salvar md: {e}")
    logger.info(f"[LLM] Iniciando: {label} ({len(texto)} chars)")

    # Heuristic: if the document looks like it contains many item headers, prefer
    # item-based extraction to avoid chunk boundaries splitting descriptions.
    item_blocks = _split_into_item_blocks(texto)
    total_tokens = 0
    aviso = None

    if item_blocks:
        logger.info(f"[LLM] Detectados {len(item_blocks)} blocos de item — usando item-mode")
        # Try to extract document-level metadata from the first chunk (fast)
        chunks = _dividir_em_chunks(texto)
        try:
            meta_dados, meta_tokens = _chamar_llm(chunks[0])
            total_tokens += meta_tokens
        except Exception as e:
            logger.warning(f"[LLM] Falha ao extrair metadados: {e}")
            meta_dados = {}

        itens_raw: list[dict] = []
        for idx, block in enumerate(item_blocks, 1):
            logger.info(f"[LLM] Item-mode: processando item {idx}/{len(item_blocks)} ({len(block)} chars)")
            try:
                item_d, item_tokens = _chamar_llm_item(block)
                itens_raw.append(item_d)
                total_tokens += item_tokens
            except Exception as e:
                logger.error(f"[LLM] Erro ao processar item {idx}: {e}")
                # Fallback conservador: keep the raw block as descricao
                numero_guess = None
                m = re.match(r"(?i)^(?:item\s*)?(\d{1,4})", block.strip())
                if m:
                    numero_guess = m.group(1)
                itens_raw.append({
                    "numero_item": numero_guess,
                    "descricao": block,
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
        # clean and dedupe item dicts
        itens_clean = [_clean_item_dict(d) for d in itens_raw]
        itens_clean = _dedupe_items(itens_clean)
        dados["itens"] = itens_clean
        itens = [_para_item(d) for d in (dados.get("itens") or [])]
    else:
        chunks = _dividir_em_chunks(texto)
        aviso = f"texto dividido em {len(chunks)} chunks" if len(chunks) > 1 else None

        resultados_raw: list[dict] = []
        for i, chunk in enumerate(chunks, 1):
            logger.info(f"[LLM] Chunk {i}/{len(chunks)} ({len(chunk)} chars)")
            try:
                dados_chunk, tokens = _chamar_llm(chunk)
                resultados_raw.append(dados_chunk)
                total_tokens += tokens
            except Exception as e:
                logger.error(f"[LLM] Erro chunk {i}/{len(chunks)} de {label}: {e}")
                if i == 1:
                    return ResultadoAnalise(id_pncp=id_pncp, aviso=f"erro LLM: {e}")
                aviso = (aviso or "") + f" | erro chunk {i}: {e}"

        dados = _mesclar_chunks(resultados_raw)
        # clean and dedupe
        itens_clean = [_clean_item_dict(d) for d in (dados.get("itens") or [])]
        itens_clean = _dedupe_items(itens_clean)
        dados["itens"] = itens_clean
        itens = [_para_item(d) for d in (dados.get("itens") or [])]

    resultado = ResultadoAnalise(
        id_pncp         = id_pncp,
        numero_ata      = dados.get("numero_ata"),
        orgao           = dados.get("orgao"),
        data_assinatura = dados.get("data_assinatura"),
        vigencia        = dados.get("vigencia"),
        objeto          = dados.get("objeto"),
        itens           = itens,
        tokens_usados   = total_tokens,
        aviso           = aviso,
    )

    logger.info(f"[LLM] Concluído {label}: {len(itens)} itens | {total_tokens} tokens")

    if persistir and id_pncp:
        _persistir(id_pncp, resultado)

    return resultado



# Persistência


def _persistir(id_pncp: str, resultado: ResultadoAnalise) -> None:
    if db is None:
        logger.info(f"[LLM] Persistência desabilitada (shared.db não disponível) — pulando persistência para {id_pncp}")
        return
    try:
        for item in resultado.itens:
            db.inserir_item_ata(id_pncp, {
                "id_pncp":          id_pncp,
                "numero_item":      item.numero_item,
                "descricao_llm":    item.descricao,
                "tipo":             item.tipo,
                "marca_extraida":   item.marca,
                "modelo_extraido":  item.modelo,
                "quantidade":       item.quantidade,
                "unidade":          item.unidade,
                "valor_unitario":   item.valor_unitario,
                "valor_total":      item.valor_total,
                "fornecedor":       item.fornecedor,
                "cnpj_fornecedor":  item.cnpj_fornecedor,
                "especificacoes":   json.dumps(item.especificacoes, ensure_ascii=False),
                "observacoes":      item.observacoes,
                "status_llm":       "ok",
            })
        db.atualizar_status(id_pncp, "llm", "ok")
        logger.info(f"[LLM] {len(resultado.itens)} itens persistidos — {id_pncp}")
    except Exception as e:
        logger.error(f"[LLM] Erro ao persistir {id_pncp}: {e}")
        try:
            db.atualizar_status(id_pncp, "llm", "erro_persistencia")
        except Exception:
            logger.exception("Falha ao atualizar status de persistência")



# Exportação (dataclass → dict / JSON)


def resultado_para_dict(resultado: ResultadoAnalise) -> dict:
    """Converte ResultadoAnalise para dict serializável (inclui todos os itens)."""
    return asdict(resultado)


def resultado_para_json(resultado: ResultadoAnalise, indent: int = 2) -> str:
    """Serializa ResultadoAnalise para string JSON formatada."""
    return json.dumps(resultado_para_dict(resultado), ensure_ascii=False, indent=indent)



# Wrapper para pipeline_atas.py

def analisar_texto_ata_extraido(
    texto_ocr: str,
    id_pncp: str,
    nome_arquivo: str = "",
) -> ResultadoAnalise | None:
    """
    Wrapper direto para uso dentro do pipeline_atas.py.
    Substitui o extrair_marca_modelo() por análise completa via LLM.

    Exemplo de uso em pipeline_atas.py (dentro do loop, após extrair_texto_pdf):

        from app.pipeline.pipelinellm import analisar_texto_ata_extraido, resultado_para_json

        resultado_llm = analisar_texto_ata_extraido(texto_ocr, str(pid), nome_arquivo)
        if resultado_llm:
            logger.info(resultado_para_json(resultado_llm))
    """
    if not texto_ocr or not texto_ocr.strip():
        logger.warning(f"[LLM] Texto vazio — {id_pncp} / {nome_arquivo}")
        return None
    try:
        return analisar_ata(texto_ocr, id_pncp=id_pncp)
    except Exception as e:
        logger.error(f"[LLM] Falha em {nome_arquivo} ({id_pncp}): {e}")
        return None



# CLI


def run_arquivo(caminho: Union[str, Path], id_pncp: str | None = None) -> ResultadoAnalise:
    """Lê um .md ou .txt e analisa. Útil para testes manuais."""
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
        print("Uso: python pipelinellm.py <arquivo.md> [id_pncp]")
        sys.exit(1)

    resultado = run_arquivo(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(resultado_para_json(resultado))