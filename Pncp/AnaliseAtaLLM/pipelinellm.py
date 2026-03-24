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
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Union

import ollama

from shared import db  # comente se não quiser persistência aqui

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# Configuração
# ──────────────────────────────────────────

OLLAMA_MODEL        = "phi3"               # troque pelo modelo que você tem puxado
OLLAMA_HOST         = "http://localhost:11434"  # padrão do Ollama
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

    label = id_pncp or "ata"
    logger.info(f"[LLM] Iniciando: {label} ({len(texto)} chars)")

    chunks = _dividir_em_chunks(texto)
    aviso = f"texto dividido em {len(chunks)} chunks" if len(chunks) > 1 else None

    resultados_raw: list[dict] = []
    total_tokens = 0

    for i, chunk in enumerate(chunks, 1):
        logger.info(f"[LLM] Chunk {i}/{len(chunks)} ({len(chunk)} chars)")
        try:
            dados, tokens = _chamar_llm(chunk)
            resultados_raw.append(dados)
            total_tokens += tokens
        except Exception as e:
            logger.error(f"[LLM] Erro chunk {i}/{len(chunks)} de {label}: {e}")
            if i == 1:
                return ResultadoAnalise(id_pncp=id_pncp, aviso=f"erro LLM: {e}")
            aviso = (aviso or "") + f" | erro chunk {i}: {e}"

    dados = _mesclar_chunks(resultados_raw)
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
        db.atualizar_status(id_pncp, "llm", "erro_persistencia")



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