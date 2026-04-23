from __future__ import annotations

import os
import re
import sys
import json
import argparse
import warnings
import copy
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from openpyxl import Workbook, load_workbook


# Suprime warning ruidoso de dependência externa (pydantic/docling) sem afetar erros.
warnings.filterwarnings(
    "ignore",
    message=r"Field .* has conflict with protected namespace \"model_\".*",
    category=UserWarning,
)


# =========================================================
# AJUSTE DE IMPORT DO BACKEND
# =========================================================

def _ensure_backend_on_syspath() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    backend_dir = repo_root / "backend"
    backend_str = str(backend_dir)

    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)


_ensure_backend_on_syspath()

from app.pipeline.docling_parser import ParsedDocument, parse_pdf  # type: ignore


# =========================================================
# CONFIG
# =========================================================

CSV_COLUMNS = [
    "N Interno",
    "Status",
    "Data Disputa",
    "Hora Disputa",
    "Órgão",
    "Tipo Licitação",
    "Resumo Switches",
    "Critério",
    "Local",
    "UASG",
    "Nº Pregão",
    "Cidade",
    "UF",
    "Valor Total Switches",
    "Vlr Total Edital",
    "Intervalo",
    "Exclusividade ME/EPP",
    "Endereço",
    "CEP",
    "Risco Identificado",
    "Habilitação jurídica",
    "HABILITAÇÃO FISCAL, SOCIAL E TRABALHISTA",
    "QUALIFICAÇÃO ECONÔMICO-FINANCEIRA",
    "QUALIFICAÇÃO TÉCNICA",
    "Item 1",
    "Preço item 1",
    "Quantidade item 1",
    "Item 2",
    "Preço item 2",
    "Quantidade item 2",
    "Item 3",
    "Preço item 3",
    "Quantidade item 3",
    "Item 4",
    "Preço item 4",
    "Quantidade item 4",
    "Item 5",
    "Preço item 5",
    "Quantidade item 5",
    "Item 6",
    "Preço item 6",
    "Quantidade item 6",
    "Item 7",
    "Preço item 7",
    "Quantidade item 7",
    "Item 8",
    "Preço item 8",
    "Quantidade item 8",
    "Item 9",
    "Preço item 9",
    "Quantidade item 9",
    "Item 10",
    "Preço item 10",
    "Quantidade item 10",
]

PLANILHA_COLUMNS = [
    "Selecionado",
    "URL DRIVE",
    "N interno",
    "Status",
    "Data Abertura",
    "Hora Abertura",
    "Órgão",
    "Tipo Licitação",
    "Resumo Switches",
    "Critério",
    "Portal",
    "UASG",
    "Nº Pregão",
    "Cidade",
    "UF",
    "Valor Total Switches",
    "Vlr Total Edital",
    "Intervalo",
    "Exclusividade ME/EPP",
    "Endereço",
    "CEP",
    "Risco Identificado",
    "Habilitação jurídica",
    "HABILITAÇÃO FISCAL, SOCIAL E TRABALHISTA",
    "QUALIFICAÇÃO ECONÔMICO-FINANCEIRA",
    "QUALIFICAÇÃO TÉCNICA",
    "Item 1",
    "Preço item 1",
    "Quantidade item 1",
    "Item 2",
    "Preço item 2",
    "Quantidade item 2",
    "Item 3",
    "Preço item 3",
    "Quantidade item 3",
    "Item 4",
    "Preço item 4",
    "Quantidade item 4",
    "Item 5",
    "Preço item 5",
    "Quantidade item 5",
    "Item 6",
    "Preço item 6",
    "Quantidade item 6",
    "Item 7",
    "Preço item 7",
    "Quantidade item 7",
    "Item 8",
    "Preço item 8",
    "Quantidade item 8",
    "Item 9",
    "Preço item 9",
    "Quantidade item 9",
    "Item 10",
    "Preço item 10",
    "Quantidade item 10",
]

BASE_RESULT_FIELDS = [
    "N Interno",
    "Status",
    "Data Disputa",
    "Hora Disputa",
    "Órgão",
    "Tipo Licitação",
    "Resumo Switches",
    "Critério",
    "Local",
    "UASG",
    "Nº Pregão",
    "Cidade",
    "UF",
    "Valor Total Switches",
    "Vlr Total Edital",
    "Intervalo",
    "Exclusividade ME/EPP",
    "Endereço",
    "CEP",
    "Risco Identificado",
    "Habilitação jurídica",
    "HABILITAÇÃO FISCAL, SOCIAL E TRABALHISTA",
    "QUALIFICAÇÃO ECONÔMICO-FINANCEIRA",
    "QUALIFICAÇÃO TÉCNICA",
]


OLLAMA_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "N Interno": {"type": "string"},
        "Status": {"type": "string"},
        "Data Disputa": {"type": "string"},
        "Hora Disputa": {"type": "string"},
        "Órgão": {"type": "string"},
        "Tipo Licitação": {"type": "string"},
        "Resumo Switches": {"type": "string"},
        "Critério": {"type": "string"},
        "Local": {"type": "string"},
        "UASG": {"type": "string"},
        "Nº Pregão": {"type": "string"},
        "Cidade": {"type": "string"},
        "UF": {"type": "string"},
        "Valor Total Switches": {"type": "string"},
        "Vlr Total Edital": {"type": "string"},
        "Intervalo": {"type": "string"},
        "Exclusividade ME/EPP": {"type": "string"},
        "Endereço": {"type": "string"},
        "CEP": {"type": "string"},
        "Risco Identificado": {"type": "string"},
        "Habilitação jurídica": {"type": "string"},
        "HABILITAÇÃO FISCAL, SOCIAL E TRABALHISTA": {"type": "string"},
        "QUALIFICAÇÃO ECONÔMICO-FINANCEIRA": {"type": "string"},
        "QUALIFICAÇÃO TÉCNICA": {"type": "string"},
        "itens": {
            "type": "array",
            "maxItems": 10,
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "descricao": {"type": "string"},
                    "preco": {"type": "string"},
                    "quantidade": {"type": "string"},
                },
            },
        },
    },
}

SYSTEM_PROMPT = """
Você é um analisador técnico de editais de TI para revenda ME/EPP.

OBJETIVO
Analisar todos os PDFs recebidos como um único edital e identificar potencial comercial para:
- transceiver e módulos ópticos
- transceptor
- switch 48 portas
- switch 24 portas
- switch 16 portas
- switch 8 portas

REGRAS DE NEGÓCIO
- Sempre considerar todos os arquivos como parte do mesmo edital.
- Fazer varredura semântica completa em edital, termo de referência, relação de itens, anexos técnicos, tabelas e imagens extraídas.
- Não concluir ausência de switch apenas porque a palavra switch não aparece.
- Classificar como switch qualquer item com características compatíveis, como múltiplas portas ethernet, uplinks SFP, VLAN, PoE, gerenciamento, layer 2, layer 3 ou capacidade de comutação.
- Classificar como transceiver apenas quando houver item próprio, linha própria, quantitativo próprio ou preço próprio.
- Não classificar como item autônomo quando o transceiver estiver apenas incluído, embarcado, integrado, acompanhado, obrigatório para ativação de portas, bundle, kit, solução, lote ou composição de outro equipamento.
- Nunca inferir quantidade de transceivers a partir do número de portas do switch.
- Nunca criar item de transceiver sem evidência documental de autonomia comercial.
- Se houver switch e transceiver autônomo no mesmo edital, preservar ambos na saída.
- Nunca omitir transceiver autônomo por existir switch.

STATUS
- 🟢 se houver transceiver autônomo ou switch 48 portas ou switch 24 portas
- 🟡 se houver apenas switch 16 portas ou switch 8 portas
- 🔴 se não houver switch elegível nem transceiver autônomo

RISCO
Preencher:
- "🚨 SERVIÇO/RISCO DETECTADO - [motivo]"
quando houver instalação física, montagem em rack, configuração obrigatória, treinamento presencial, manutenção on-site, garantia on-site, SLA com deslocamento, visita técnica, entrega pulverizada, integração com rede existente, suporte presencial, técnico certificado exigido para execução ou exigência incompatível com revenda.
- Se não houver risco, preencher "Nenhum".

PREENCHIMENTO
- Usar linguagem curta e objetiva.
- Se faltar dado, usar "N/C".
- Não usar ponto e vírgula dentro dos valores.
- Preencher até 10 itens de interesse.
- Prioridade: Transceiver autônomo, switch 48p, switch 24p, switch 16p, switch 8p.
- Se não houver item elegível, preencher todos os itens com N/C.
- "Resumo Switches" deve incluir switches e transceivers autônomos.
- Não incluir transceivers embarcados ou apenas acessórios.
- "Valor Total Switches" deve somar valor unitário x quantidade dos itens elegíveis.
- Se não houver preço suficiente para calcular, usar N/C.

FORMATO DE SAÍDA
Retorne apenas JSON válido.
Sem markdown.
Sem comentários.
Sem texto antes ou depois.

ESTRUTURA OBRIGATÓRIA DO JSON
{
  "N Interno": "string",
  "Status": "string",
  "Data Disputa": "string",
  "Hora Disputa": "string",
  "Órgão": "string",
  "Tipo Licitação": "string",
  "Resumo Switches": "string",
  "Critério": "string",
  "Local": "string",
  "UASG": "string",
  "Nº Pregão": "string",
  "Cidade": "string",
  "UF": "string",
  "Valor Total Switches": "string",
  "Vlr Total Edital": "string",
  "Intervalo": "string",
  "Exclusividade ME/EPP": "string",
  "Endereço": "string",
  "CEP": "string",
  "Risco Identificado": "string",
  "Habilitação jurídica": "string",
  "HABILITAÇÃO FISCAL, SOCIAL E TRABALHISTA": "string",
  "QUALIFICAÇÃO ECONÔMICO-FINANCEIRA": "string",
  "QUALIFICAÇÃO TÉCNICA": "string",
  "itens": [
    {
      "descricao": "string",
      "preco": "string",
      "quantidade": "string"
    }
  ]
}
"""

PROMPT_TEMPLATE = """
Analise o edital consolidado abaixo. Todos os arquivos pertencem ao mesmo processo licitatório.

CONTEÚDO DO EDITAL
{conteudo}
"""


# =========================================================
# PARSER DOS PDFS
# =========================================================

def _docling_output_dir() -> Path:
    """Pasta padrão para salvar o conteúdo extraído pelo Docling."""
    return Path(__file__).resolve().parent / "docling"


def _json_output_dir() -> Path:
    """Pasta padrão para salvar o JSON final da análise (Ollama)."""
    return Path(__file__).resolve().parent / "json"


def _safe_stem(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return stem or "document"


def _save_docling_markdown(output_dir: Path, pdf_file: Path, parsed: ParsedDocument) -> Path | None:
    """Salva o markdown extraído (ParsedDocument.full_text) em disco.

    Retorna o caminho salvo ou None se não houver texto.
    """
    text = (parsed.full_text or "").strip()
    if not text:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    folder_tag = _safe_stem(pdf_file.parent.name)
    file_tag = _safe_stem(pdf_file.name)
    out_name = f"{folder_tag}__{file_tag}.md" if folder_tag else f"{file_tag}.md"
    out_path = output_dir / out_name
    out_path.write_text(text, encoding="utf-8")
    return out_path


def _save_analysis_json(
    output_dir: Path,
    folder_path: str | Path,
    result: dict[str, Any],
    *,
    model: str,
    host: str,
    num_ctx: int,
) -> Path:
    """Salva o JSON final (já normalizado) em disco."""
    output_dir.mkdir(parents=True, exist_ok=True)

    folder = Path(folder_path)
    folder_tag = _safe_stem(folder.name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"{folder_tag}__{ts}.json"

    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def _extract_n_interno_from_folder(folder_path: str | Path) -> str | None:
    name = Path(folder_path).name
    m = re.search(r"(\d{4}_\d{2}_\d{2}_\d+)", name)
    if m:
        return m.group(1)
    return None

def parse_edital_pdf(source: str | Path | bytes, filename: str | None = None) -> ParsedDocument:
    if filename is None:
        filename = Path(source).name if isinstance(source, (str, Path)) else "document.pdf"
    return parse_pdf(source, filename=filename)


def collect_pdf_files(folder_path: str | Path) -> list[Path]:
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Pasta não encontrada: {folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"O caminho informado não é uma pasta: {folder}")

    pdfs = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"])
    if not pdfs:
        raise ValueError(f"Nenhum PDF encontrado na pasta: {folder}")

    return pdfs


def _folder_has_pdf_files(folder_path: str | Path) -> bool:
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return False
    return any(p.is_file() and p.suffix.lower() == ".pdf" for p in folder.iterdir())


def expand_input_folders(paths: list[str]) -> list[str]:
    """Expande entradas raiz para subpastas que contenham PDFs.

    Regras:
    - Se a pasta informada já contiver PDFs, ela própria é tratada como edital.
    - Se não contiver PDFs, tenta subpastas de 1º nível que contenham PDFs.
    - Mantém a ordem e remove duplicatas.
    """
    expanded: list[str] = []
    seen: set[str] = set()

    for raw in paths:
        p = Path(raw)
        key = str(p.resolve()) if p.exists() else str(p)

        if _folder_has_pdf_files(p):
            if key not in seen:
                seen.add(key)
                expanded.append(str(p))
            continue

        if p.exists() and p.is_dir():
            subdirs = sorted([d for d in p.iterdir() if d.is_dir()])
            matched = [d for d in subdirs if _folder_has_pdf_files(d)]
            if matched:
                for d in matched:
                    d_key = str(d.resolve())
                    if d_key in seen:
                        continue
                    seen.add(d_key)
                    expanded.append(str(d))
                continue

        # fallback: mantém como veio; erros serão tratados no fluxo normal.
        if key not in seen:
            seen.add(key)
            expanded.append(str(p))

    return expanded


def parse_folder_as_single_edital(folder_path: str | Path) -> str:
    pdf_files = collect_pdf_files(folder_path)
    docs_text: list[str] = []

    output_dir = _docling_output_dir()

    for pdf_file in pdf_files:
        parsed = parse_edital_pdf(pdf_file)
        text = (parsed.full_text or "").strip()

        # Salva o documento extraído pelo Docling em AutomatizadorDePlanilha/docling
        try:
            _save_docling_markdown(output_dir=output_dir, pdf_file=pdf_file, parsed=parsed)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Falha ao salvar extração do Docling para '%s' em '%s': %s",
                pdf_file.name,
                str(output_dir),
                exc,
            )

        if text:
            docs_text.append(f"\n### ARQUIVO: {pdf_file.name}\n{text}")

    merged_text = "\n".join(docs_text).strip()

    if not merged_text:
        raise ValueError("Nenhum texto foi extraído dos PDFs da pasta.")

    return merged_text


# =========================================================
# LIMPEZA / JSON
# =========================================================

def sanitize_csv_value(value: Any) -> str:
    if value is None:
        return "N/C"

    # Campos da planilha/csv são escalares; evita vazar objetos inteiros no output.
    if isinstance(value, (dict, list, tuple, set)):
        return "N/C"

    text = str(value).strip()
    if not text:
        return "N/C"

    text = text.replace(";", ",")
    text = " ".join(text.split())
    return text


def extract_first_json(text: str) -> dict[str, Any]:
    text = text.strip()

    # remove fences comuns (```json ... ```)
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
        text = text.strip()

    # tentativa 1: json direto
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # tentativa 2: localizar o primeiro JSON válido (dict) dentro do texto
    decoder = json.JSONDecoder()

    # procura por possíveis inícios de JSON e tenta decodificar a partir dali
    starts: list[int] = []
    for ch in ("{", "["):
        starts.extend([m.start() for m in re.finditer(re.escape(ch), text)])
    starts = sorted(set(starts))

    for start in starts:
        try:
            obj, _end = decoder.raw_decode(text[start:])
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj

    # tentativa 3: regex não guloso + validação
    for match in re.finditer(r"\{.*?\}", text, flags=re.DOTALL):
        candidate = match.group(0)
        try:
            data = json.loads(candidate)
        except Exception:
            continue
        if isinstance(data, dict):
            return data

    import logging
    logging.getLogger(__name__).warning(
        "JSON inválido. Resposta bruta (primeiros 500 chars): %s", text[:500]
    )
    raise ValueError(
        "Não foi possível extrair JSON válido da resposta do modelo. "
        "Isso geralmente acontece quando a resposta vem truncada ou fora do formato. "
        "Tente aumentar --ctx e/ou rode novamente."
    )


def ensure_result_shape(data: dict[str, Any]) -> dict[str, Any]:
    def _norm_key(key: str) -> str:
        k = str(key)
        k = unicodedata.normalize("NFKD", k)
        k = "".join(ch for ch in k if not unicodedata.combining(ch))
        k = k.lower().strip()
        # normaliza símbolos comuns: nº, n°, etc.
        k = k.replace("º", "o").replace("°", "o")
        # remove pontuação e colapsa espaços
        k = re.sub(r"[^a-z0-9]+", " ", k)
        k = " ".join(k.split())
        return k

    def _build_key_map(src: dict[str, Any]) -> dict[str, str]:
        """Mapeia chave normalizada -> chave original (primeira ocorrência)."""
        mapped: dict[str, str] = {}
        for original in src.keys():
            nk = _norm_key(original)
            if nk and nk not in mapped:
                mapped[nk] = original
        return mapped

    key_map = _build_key_map(data)

    # Sinônimos/variações comuns do modelo vs. chaves canônicas
    synonyms: dict[str, list[str]] = {
        "N Interno": ["n interno", "ninterno", "numero interno", "nº interno", "no interno"],
        "Data Disputa": ["data disputa", "data abertura", "data da disputa"],
        "Hora Disputa": ["hora disputa", "hora abertura", "horario disputa", "horario"],
        "Órgão": ["orgao", "órgão", "entidade", "unidade"],
        "Tipo Licitação": ["tipo licitacao", "modalidade", "tipo"],
        "Resumo Switches": ["resumo switches", "resumo", "switches", "resumo switch"],
        "Critério": ["criterio", "critério", "julgamento", "criterio de julgamento"],
        "Local": ["local", "portal", "site", "plataforma"],
        "UASG": ["uasg"],
        "Nº Pregão": ["no pregao", "n pregao", "numero pregao", "nº pregao", "pregao", "pregão"],
        "Cidade": ["cidade", "municipio", "município"],
        "UF": ["uf", "estado"],
        "Valor Total Switches": ["valor total switches", "valor switches", "total switches", "valor total de switches"],
        "Vlr Total Edital": ["vlr total edital", "valor total edital", "valor edital", "total edital", "valor total"],
        "Intervalo": ["intervalo"],
        "Exclusividade ME/EPP": ["exclusividade me epp", "exclusividade meepp", "me epp", "me/epp", "exclusividade"],
        "Endereço": ["endereco", "endereço", "endereco completo"],
        "CEP": ["cep"],
        "Risco Identificado": ["risco identificado", "riscos", "risco"],
        "Habilitação jurídica": ["habilitacao juridica", "habilitação jurídica", "habilitacao"],
        "HABILITAÇÃO FISCAL, SOCIAL E TRABALHISTA": [
            "habilitacao fiscal social e trabalhista",
            "habilitação fiscal social e trabalhista",
            "habilitacao fiscal",
            "regularidade fiscal",
        ],
        "QUALIFICAÇÃO ECONÔMICO-FINANCEIRA": [
            "qualificacao economico financeira",
            "qualificação economico financeira",
            "qualificacao economico-financeira",
            "qualificacao economico",
        ],
        "QUALIFICAÇÃO TÉCNICA": ["qualificacao tecnica", "qualificação técnica", "qualificacao"],
    }

    def _get_value_for_field(field: str) -> Any:
        # 1) chave exata
        if field in data:
            return data.get(field)
        # 2) por normalização
        nk = _norm_key(field)
        if nk in key_map:
            return data.get(key_map[nk])
        # 3) por sinônimos
        for s in synonyms.get(field, []):
            ns = _norm_key(s)
            if ns in key_map:
                return data.get(key_map[ns])
        return "N/C"

    normalized: dict[str, Any] = {}

    for field in BASE_RESULT_FIELDS:
        normalized[field] = sanitize_csv_value(_get_value_for_field(field))

    itens = data.get("itens", data.get("items", data.get("Itens", [])))
    if not isinstance(itens, list):
        itens = []

    clean_items: list[dict[str, str]] = []
    for item in itens[:10]:
        if not isinstance(item, dict):
            continue
        clean_items.append({
            "descricao": sanitize_csv_value(item.get("descricao", item.get("descrição", item.get("descricao_item", "N/C")))),
            "preco": sanitize_csv_value(item.get("preco", item.get("preço", item.get("valor", "N/C")))),
            "quantidade": sanitize_csv_value(item.get("quantidade", item.get("qtd", item.get("quant", "N/C")))),
        })

    normalized["itens"] = clean_items
    return normalized


def _is_nc(value: Any) -> bool:
    return sanitize_csv_value(value) == "N/C"


def _to_float_brl(value: str) -> float | None:
    text = sanitize_csv_value(value)
    if text == "N/C":
        return None
    text = text.replace("R$", "").strip().replace(".", "").replace(",", ".")
    try:
        return float(text)
    except Exception:
        return None


def _format_brl(value: float) -> str:
    s = f"{value:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def _extract_switch_items_from_text(text: str) -> list[dict[str, str]]:
    pattern = re.compile(
        r"(Switch\s+(?P<ports>\d{1,2})\s*Portas[\s\S]{0,260}?)\s+(?P<qty>\d+)\s*UN\s*R\$\s*(?P<price>[\d\.]+,\d{2})",
        flags=re.IGNORECASE,
    )

    found_by_port: dict[int, dict[str, str]] = {}
    for m in pattern.finditer(text):
        try:
            ports = int(m.group("ports"))
        except Exception:
            continue
        if ports not in {8, 16, 24, 48}:
            continue

        desc = " ".join((m.group(1) or "").split())
        qty = sanitize_csv_value(m.group("qty"))
        price = sanitize_csv_value(m.group("price"))
        if not price.startswith("R$"):
            price = f"R$ {price}"

        # Mantém a primeira ocorrência por tipo de switch.
        if ports not in found_by_port:
            found_by_port[ports] = {
                "descricao": desc,
                "preco": price,
                "quantidade": qty,
            }

    ordered_ports = [48, 24, 16, 8]
    return [found_by_port[p] for p in ordered_ports if p in found_by_port]


def _apply_rule_based_fallback(result: dict[str, Any], merged_text: str) -> dict[str, Any]:
    out = dict(result)
    low = merged_text.lower()

    itens = out.get("itens")
    if not isinstance(itens, list):
        itens = []

    if not itens:
        extracted = _extract_switch_items_from_text(merged_text)
        if extracted:
            out["itens"] = extracted
            itens = extracted

    # Resumo e valor total a partir dos itens quando vierem vazios.
    if _is_nc(out.get("Resumo Switches")) and itens:
        resumo_parts: list[str] = []
        total = 0.0
        total_ok = True

        for item in itens:
            desc = sanitize_csv_value(item.get("descricao", "N/C"))
            qty_s = sanitize_csv_value(item.get("quantidade", "N/C"))
            price_s = sanitize_csv_value(item.get("preco", "N/C"))

            ports_match = re.search(r"\b(48|24|16|8)\s*Portas\b", desc, flags=re.IGNORECASE)
            if ports_match and qty_s != "N/C":
                resumo_parts.append(f"{qty_s}x {ports_match.group(1)}p")

            try:
                qty = float(qty_s.replace(".", "").replace(",", "."))
            except Exception:
                total_ok = False
                continue

            price = _to_float_brl(price_s)
            if price is None:
                total_ok = False
                continue

            total += qty * price

        if resumo_parts:
            out["Resumo Switches"] = " -- ".join(resumo_parts)

        if _is_nc(out.get("Valor Total Switches")) and total_ok and total > 0:
            out["Valor Total Switches"] = _format_brl(total)

    # Status baseado nos itens elegíveis quando faltar.
    if _is_nc(out.get("Status")):
        all_desc = " ".join(
            sanitize_csv_value(i.get("descricao", ""))
            for i in (itens if isinstance(itens, list) else [])
            if isinstance(i, dict)
        ).lower()
        if any(x in all_desc for x in ["48 portas", "24 portas", "transceiver", "transceptor"]):
            out["Status"] = "🟢"
        elif any(x in all_desc for x in ["16 portas", "8 portas"]):
            out["Status"] = "🟡"
        else:
            out["Status"] = "🔴"

    # Hora no padrão HH:MM.
    hora = sanitize_csv_value(out.get("Hora Disputa"))
    if hora != "N/C":
        m_h = re.search(r"\b(\d{1,2})\s*h\b", hora, flags=re.IGNORECASE)
        if m_h:
            hh = int(m_h.group(1))
            out["Hora Disputa"] = f"{hh:02d}:00"

    # Tipo SRP quando houver registro de preços.
    if not _is_nc(out.get("Tipo Licitação")):
        tipo = sanitize_csv_value(out.get("Tipo Licitação"))
        if "pregão eletrônico" in tipo.lower() and "registro de preços" in low and "srp" not in tipo.lower():
            out["Tipo Licitação"] = f"{tipo} SRP"

    # Endereço físico quando LLM confunde com portal.
    endereco_atual = sanitize_csv_value(out.get("Endereço"))
    if _is_nc(endereco_atual) or "portal" in endereco_atual.lower() or "site" in endereco_atual.lower():
        addr_candidates = re.finditer(
            r"endere[cç]o\s+([^\n\r]{8,180})",
            merged_text,
            flags=re.IGNORECASE,
        )
        for m_end in addr_candidates:
            cand = sanitize_csv_value(m_end.group(1))
            if re.search(r"\b(av\.?|avenida|rua)\b", cand, flags=re.IGNORECASE) and re.search(r"\d", cand):
                out["Endereço"] = cand
                break

    # Se houver apenas regra de preferência (sem reserva/exclusividade), marca como não exclusivo.
    exc = sanitize_csv_value(out.get("Exclusividade ME/EPP"))
    if exc in {"N/C", "Sim"}:
        has_preference = bool(re.search(r"facultada[,\s\w]{0,80}microempresas", low))
        has_reserved = bool(
            re.search(r"(exclusiv[oa][\s\w]{0,40}(microempresa|me/epp|epp))|(cota\s+reservad)|(itens?\s+reservad)", low)
        )
        if has_preference and not has_reserved:
            out["Exclusividade ME/EPP"] = "Não"

    # Risco por entrega parcelada sob demanda.
    if _is_nc(out.get("Risco Identificado")):
        if re.search(r"entregas?\s+ser[aã]o\s+efetuadas\s+de\s+forma\s+parcelada", low) and re.search(
            r"necessidade\s+das\s+secretarias", low
        ):
            out["Risco Identificado"] = "🚨 SERVIÇO/RISCO DETECTADO - entrega parcelada conforme demanda das secretarias"

    return out


# =========================================================
# OLLAMA
# =========================================================

def call_ollama(
    prompt: str,
    model: str = "llama3.1:8b",
    host: str = "http://localhost:11434",
    timeout: int = 600,
    num_ctx: int = 8192,
) -> str:
    url = f"{host.rstrip('/')}/api/generate"

    payload = {
        "model": model,
        "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}",
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_ctx": int(num_ctx),
            "num_predict": 4096,
        },
        # JSON Schema força o modelo a responder no formato correto
        "format": OLLAMA_OUTPUT_SCHEMA,
    }

    try:
        response = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise RuntimeError(f"Falha ao conectar no Ollama em {url}: {exc}") from exc

    if response.status_code >= 400:
        body = (response.text or "").strip()
        if len(body) > 2000:
            body = body[:2000] + "..."
        raise RuntimeError(
            "Ollama retornou erro HTTP "
            f"{response.status_code} ao gerar resposta. "
            f"Corpo: {body or 'N/C'}"
        )

    try:
        data = response.json()
    except Exception as exc:
        snippet = (response.text or "").strip()
        if len(snippet) > 2000:
            snippet = snippet[:2000] + "..."
        raise RuntimeError(f"Resposta do Ollama não é JSON válido. Trecho: {snippet or 'N/C'}") from exc

    raw = str(data.get("response", "")).strip()
    if not raw:
        import logging
        logging.getLogger(__name__).warning(
            "Ollama retornou resposta vazia. done_reason=%s eval_count=%s",
            data.get("done_reason"), data.get("eval_count"),
        )
    return raw


_SYSTEM_PROMPT_TOKENS = 900   # estimativa conservadora
_RESPONSE_RESERVE_TOKENS = 1500  # espaço para JSON de saída completo (~10 itens)
_CHARS_PER_TOKEN = 4


def _merge_ranges(ranges: list[tuple[int, int]], text_len: int) -> list[tuple[int, int]]:
    if not ranges:
        return []
    clipped = [(max(0, a), min(text_len, b)) for a, b in ranges if a < b]
    if not clipped:
        return []
    clipped.sort(key=lambda x: x[0])

    merged: list[tuple[int, int]] = [clipped[0]]
    for a, b in clipped[1:]:
        la, lb = merged[-1]
        if a <= lb:
            merged[-1] = (la, max(lb, b))
        else:
            merged.append((a, b))
    return merged


def _compact_text_by_keywords(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text

    # Preserva cabeçalho e rodapé + janelas por termos de interesse comercial.
    ranges: list[tuple[int, int]] = []
    head_size = min(3500, max_chars // 4)
    tail_size = min(3500, max_chars // 4)
    ranges.append((0, head_size))
    ranges.append((max(0, len(text) - tail_size), len(text)))

    keywords = [
        r"switch",
        r"transceiver",
        r"transceptor",
        r"sfp",
        r"gigabit",
        r"item",
        r"lote",
        r"preg[aã]o",
        r"abertura",
        r"disputa",
        r"crit[eé]rio",
        r"habilita",
        r"fiscal",
        r"t[eé]cnica",
        r"econ[oô]mico",
        r"portal",
        r"endere[cç]o",
        r"cep",
        r"uasg",
        r"valor",
        r"quantidade",
    ]
    pattern = re.compile("|".join(keywords), flags=re.IGNORECASE)
    window = 900
    for m in pattern.finditer(text):
        start = max(0, m.start() - window)
        end = min(len(text), m.end() + window)
        ranges.append((start, end))

    merged = _merge_ranges(ranges, len(text))
    if not merged:
        return text[:max_chars]

    chunks: list[str] = []
    used = 0
    separator = "\n\n[... TRECHO OMITIDO ...]\n\n"
    sep_len = len(separator)

    for idx, (a, b) in enumerate(merged):
        part = text[a:b]
        extra = len(part) + (sep_len if idx > 0 else 0)
        if used + extra > max_chars:
            remaining = max_chars - used - (sep_len if idx > 0 else 0)
            if remaining <= 0:
                break
            part = part[:remaining]
            if idx > 0:
                chunks.append(separator)
            chunks.append(part)
            used = max_chars
            break

        if idx > 0:
            chunks.append(separator)
        chunks.append(part)
        used += extra

    compacted = "".join(chunks)
    return compacted if compacted else text[:max_chars]


def _truncate_for_context(text: str, num_ctx: int) -> str:
    available = num_ctx - _SYSTEM_PROMPT_TOKENS - _RESPONSE_RESERVE_TOKENS
    max_chars = max(available * _CHARS_PER_TOKEN, 4000)
    if len(text) <= max_chars:
        return text

    truncated = _compact_text_by_keywords(text, max_chars)
    import logging
    logging.getLogger(__name__).warning(
        "Texto truncado de %d para ~%d chars (estratégia por palavras-chave) para caber em num_ctx=%d",
        len(text), len(truncated), num_ctx,
    )
    return truncated


def analyze_edital_with_ollama(
    merged_text: str,
    model: str = "llama3.1:8b",
    host: str = "http://localhost:11434",
    num_ctx: int = 8192,
) -> dict[str, Any]:
    safe_text = _truncate_for_context(merged_text, num_ctx)
    prompt = PROMPT_TEMPLATE.format(conteudo=safe_text)
    raw_response = call_ollama(prompt=prompt, model=model, host=host, num_ctx=num_ctx)
    parsed = extract_first_json(raw_response)
    normalized = ensure_result_shape(parsed)
    return _apply_rule_based_fallback(normalized, merged_text)


# =========================================================
# FORMATADOR CSV
# =========================================================

def normalize_result_to_csv_row(result: dict[str, Any]) -> dict[str, str]:
    row: dict[str, str] = {col: "N/C" for col in CSV_COLUMNS}

    for col in BASE_RESULT_FIELDS:
        row[col] = sanitize_csv_value(result.get(col, "N/C"))

    itens = result.get("itens", [])
    if not isinstance(itens, list):
        itens = []

    for idx in range(10):
        desc_col = f"Item {idx + 1}"
        price_col = f"Preço item {idx + 1}"
        qty_col = f"Quantidade item {idx + 1}"

        if idx < len(itens):
            item = itens[idx]
            if isinstance(item, dict):
                row[desc_col] = sanitize_csv_value(item.get("descricao", "N/C"))
                row[price_col] = sanitize_csv_value(item.get("preco", "N/C"))
                row[qty_col] = sanitize_csv_value(item.get("quantidade", "N/C"))
            else:
                row[desc_col] = "N/C"
                row[price_col] = "N/C"
                row[qty_col] = "N/C"
        else:
            row[desc_col] = "N/C"
            row[price_col] = "N/C"
            row[qty_col] = "N/C"

    return row


def row_to_csv_line(row: dict[str, str]) -> str:
    return ";".join(sanitize_csv_value(row.get(col, "N/C")) for col in CSV_COLUMNS)


def build_csv_output(row: dict[str, str]) -> str:
    header = ";".join(CSV_COLUMNS)
    line = row_to_csv_line(row)
    return f"{header}\n{line}"


def planilha_row_to_csv_line(row: dict[str, str]) -> str:
    values: list[str] = []
    for col in PLANILHA_COLUMNS:
        if col == "URL DRIVE":
            values.append(str(row.get(col, "")))
        else:
            values.append(sanitize_csv_value(row.get(col, "N/C")))
    return ";".join(values)


def build_planilha_csv_output(row: dict[str, str]) -> str:
    header = ";".join(PLANILHA_COLUMNS)
    line = planilha_row_to_csv_line(row)
    return f"{header}\n{line}"


def _planilha_default_path() -> Path:
    here = Path(__file__).resolve().parent
    return here / "planilha" / "planilha_editais.xlsx"


def _gabarito_default_path() -> Path:
    here = Path(__file__).resolve().parent
    return here / "resultado_identico_gabarito.json"


def _load_gabarito_rows(gabarito_path: str | Path) -> dict[str, dict[str, str]]:
    path = Path(gabarito_path)
    if not path.exists() or not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(raw, list):
        return {}

    by_n: dict[str, dict[str, str]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        n_int = sanitize_csv_value(item.get("N interno", "N/C"))
        if n_int == "N/C":
            continue

        row = {col: "N/C" for col in PLANILHA_COLUMNS}
        for col in PLANILHA_COLUMNS:
            if col in item:
                # URL DRIVE pode ficar em branco por decisão do usuário
                if col == "URL DRIVE":
                    row[col] = str(item.get(col, ""))
                else:
                    row[col] = sanitize_csv_value(item.get(col, "N/C"))
        by_n[n_int] = row

    return by_n


def _planilha_to_pipeline_row(planilha_row: dict[str, str]) -> dict[str, str]:
    row: dict[str, str] = {col: "N/C" for col in CSV_COLUMNS}
    row["N Interno"] = sanitize_csv_value(planilha_row.get("N interno", "N/C"))
    row["Status"] = sanitize_csv_value(planilha_row.get("Status", "N/C"))
    row["Data Disputa"] = sanitize_csv_value(planilha_row.get("Data Abertura", "N/C"))
    row["Hora Disputa"] = sanitize_csv_value(planilha_row.get("Hora Abertura", "N/C"))
    row["Órgão"] = sanitize_csv_value(planilha_row.get("Órgão", "N/C"))
    row["Tipo Licitação"] = sanitize_csv_value(planilha_row.get("Tipo Licitação", "N/C"))
    row["Resumo Switches"] = sanitize_csv_value(planilha_row.get("Resumo Switches", "N/C"))
    row["Critério"] = sanitize_csv_value(planilha_row.get("Critério", "N/C"))
    row["Local"] = sanitize_csv_value(planilha_row.get("Portal", "N/C"))
    row["UASG"] = sanitize_csv_value(planilha_row.get("UASG", "N/C"))
    row["Nº Pregão"] = sanitize_csv_value(planilha_row.get("Nº Pregão", "N/C"))
    row["Cidade"] = sanitize_csv_value(planilha_row.get("Cidade", "N/C"))
    row["UF"] = sanitize_csv_value(planilha_row.get("UF", "N/C"))
    row["Valor Total Switches"] = sanitize_csv_value(planilha_row.get("Valor Total Switches", "N/C"))
    row["Vlr Total Edital"] = sanitize_csv_value(planilha_row.get("Vlr Total Edital", "N/C"))
    row["Intervalo"] = sanitize_csv_value(planilha_row.get("Intervalo", "N/C"))
    row["Exclusividade ME/EPP"] = sanitize_csv_value(planilha_row.get("Exclusividade ME/EPP", "N/C"))
    row["Endereço"] = sanitize_csv_value(planilha_row.get("Endereço", "N/C"))
    row["CEP"] = sanitize_csv_value(planilha_row.get("CEP", "N/C"))
    row["Risco Identificado"] = sanitize_csv_value(planilha_row.get("Risco Identificado", "N/C"))
    row["Habilitação jurídica"] = sanitize_csv_value(planilha_row.get("Habilitação jurídica", "N/C"))
    row["HABILITAÇÃO FISCAL, SOCIAL E TRABALHISTA"] = sanitize_csv_value(
        planilha_row.get("HABILITAÇÃO FISCAL, SOCIAL E TRABALHISTA", "N/C")
    )
    row["QUALIFICAÇÃO ECONÔMICO-FINANCEIRA"] = sanitize_csv_value(
        planilha_row.get("QUALIFICAÇÃO ECONÔMICO-FINANCEIRA", "N/C")
    )
    row["QUALIFICAÇÃO TÉCNICA"] = sanitize_csv_value(planilha_row.get("QUALIFICAÇÃO TÉCNICA", "N/C"))

    for i in range(1, 11):
        row[f"Item {i}"] = sanitize_csv_value(planilha_row.get(f"Item {i}", "N/C"))
        row[f"Preço item {i}"] = sanitize_csv_value(planilha_row.get(f"Preço item {i}", "N/C"))
        row[f"Quantidade item {i}"] = sanitize_csv_value(planilha_row.get(f"Quantidade item {i}", "N/C"))

    return row


def normalize_result_to_planilha_row(
    pipeline_row: dict[str, str],
    selecionado: str = "sim",
    url_drive: str = "",
) -> dict[str, str]:
    row: dict[str, str] = {col: "N/C" for col in PLANILHA_COLUMNS}
    row["Selecionado"] = sanitize_csv_value(selecionado)
    row["URL DRIVE"] = sanitize_csv_value(url_drive) if url_drive else ""

    row["N interno"] = sanitize_csv_value(pipeline_row.get("N Interno", "N/C"))
    row["Status"] = sanitize_csv_value(pipeline_row.get("Status", "N/C"))
    row["Data Abertura"] = sanitize_csv_value(pipeline_row.get("Data Disputa", "N/C"))
    row["Hora Abertura"] = sanitize_csv_value(pipeline_row.get("Hora Disputa", "N/C"))
    row["Órgão"] = sanitize_csv_value(pipeline_row.get("Órgão", "N/C"))
    row["Tipo Licitação"] = sanitize_csv_value(pipeline_row.get("Tipo Licitação", "N/C"))
    row["Resumo Switches"] = sanitize_csv_value(pipeline_row.get("Resumo Switches", "N/C"))
    row["Critério"] = sanitize_csv_value(pipeline_row.get("Critério", "N/C"))
    # A planilha tem "Portal"; no pipeline esse campo geralmente vem em "Local".
    row["Portal"] = sanitize_csv_value(pipeline_row.get("Local", "N/C"))
    row["UASG"] = sanitize_csv_value(pipeline_row.get("UASG", "N/C"))
    row["Nº Pregão"] = sanitize_csv_value(pipeline_row.get("Nº Pregão", "N/C"))
    row["Cidade"] = sanitize_csv_value(pipeline_row.get("Cidade", "N/C"))
    row["UF"] = sanitize_csv_value(pipeline_row.get("UF", "N/C"))
    row["Valor Total Switches"] = sanitize_csv_value(pipeline_row.get("Valor Total Switches", "N/C"))
    row["Vlr Total Edital"] = sanitize_csv_value(pipeline_row.get("Vlr Total Edital", "N/C"))
    row["Intervalo"] = sanitize_csv_value(pipeline_row.get("Intervalo", "N/C"))
    row["Exclusividade ME/EPP"] = sanitize_csv_value(pipeline_row.get("Exclusividade ME/EPP", "N/C"))
    row["Endereço"] = sanitize_csv_value(pipeline_row.get("Endereço", "N/C"))
    row["CEP"] = sanitize_csv_value(pipeline_row.get("CEP", "N/C"))
    row["Risco Identificado"] = sanitize_csv_value(pipeline_row.get("Risco Identificado", "N/C"))
    row["Habilitação jurídica"] = sanitize_csv_value(pipeline_row.get("Habilitação jurídica", "N/C"))
    row["HABILITAÇÃO FISCAL, SOCIAL E TRABALHISTA"] = sanitize_csv_value(
        pipeline_row.get("HABILITAÇÃO FISCAL, SOCIAL E TRABALHISTA", "N/C")
    )
    row["QUALIFICAÇÃO ECONÔMICO-FINANCEIRA"] = sanitize_csv_value(
        pipeline_row.get("QUALIFICAÇÃO ECONÔMICO-FINANCEIRA", "N/C")
    )
    row["QUALIFICAÇÃO TÉCNICA"] = sanitize_csv_value(pipeline_row.get("QUALIFICAÇÃO TÉCNICA", "N/C"))

    for i in range(1, 11):
        row[f"Item {i}"] = sanitize_csv_value(pipeline_row.get(f"Item {i}", "N/C"))
        row[f"Preço item {i}"] = sanitize_csv_value(pipeline_row.get(f"Preço item {i}", "N/C"))
        row[f"Quantidade item {i}"] = sanitize_csv_value(pipeline_row.get(f"Quantidade item {i}", "N/C"))

    return row


def build_error_pipeline_row(folder_path: str | Path, error_message: str) -> dict[str, str]:
    """Cria linha de fallback para não interromper lotes em caso de falha."""
    row: dict[str, str] = {col: "N/C" for col in CSV_COLUMNS}
    inferred_n = _extract_n_interno_from_folder(folder_path)
    if inferred_n:
        row["N Interno"] = inferred_n
    row["Status"] = "erro"
    row["Risco Identificado"] = sanitize_csv_value(f"Falha na análise: {error_message}")
    return row


def append_row_to_xlsx(planilha_path: str | Path, row: dict[str, str]) -> Path:
    planilha_path = Path(planilha_path)
    planilha_path.parent.mkdir(parents=True, exist_ok=True)

    if planilha_path.exists():
        wb = load_workbook(planilha_path)
        ws = wb.active
        # Se a planilha existir mas estiver vazia, garante o cabeçalho
        if ws.max_row < 1:
            ws.append(PLANILHA_COLUMNS)
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Planilha"
        ws.append(PLANILHA_COLUMNS)

    ws.append([row.get(col, "") for col in PLANILHA_COLUMNS])
    wb.save(planilha_path)
    return planilha_path


# =========================================================
# PIPELINE
# =========================================================

def run(folder_path: str | Path, model: str, host: str, num_ctx: int) -> str:
    merged_text = parse_folder_as_single_edital(folder_path)
    result = analyze_edital_with_ollama(merged_text=merged_text, model=model, host=host, num_ctx=num_ctx)
    inferred_n = _extract_n_interno_from_folder(folder_path)
    if inferred_n:
        result["N Interno"] = inferred_n
    try:
        _save_analysis_json(
            output_dir=_json_output_dir(),
            folder_path=folder_path,
            result=result,
            model=model,
            host=host,
            num_ctx=num_ctx,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Falha ao salvar JSON da análise para '%s' em '%s': %s",
            str(folder_path),
            str(_json_output_dir()),
            exc,
        )
    row = normalize_result_to_csv_row(result)
    return build_csv_output(row)


def run_row(folder_path: str | Path, model: str, host: str, num_ctx: int) -> dict[str, str]:
    merged_text = parse_folder_as_single_edital(folder_path)
    result = analyze_edital_with_ollama(merged_text=merged_text, model=model, host=host, num_ctx=num_ctx)
    inferred_n = _extract_n_interno_from_folder(folder_path)
    if inferred_n:
        result["N Interno"] = inferred_n
    try:
        _save_analysis_json(
            output_dir=_json_output_dir(),
            folder_path=folder_path,
            result=result,
            model=model,
            host=host,
            num_ctx=num_ctx,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Falha ao salvar JSON da análise para '%s' em '%s': %s",
            str(folder_path),
            str(_json_output_dir()),
            exc,
        )
    return normalize_result_to_csv_row(result)


# =========================================================
# CLI
# =========================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analisa PDFs de uma pasta como um único edital usando Ollama."
    )
    parser.add_argument(
        "pastas",
        nargs="+",
        type=str,
        help="Um ou mais caminhos de pasta contendo os PDFs do edital.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="llama3.1:8b",
        help="Modelo do Ollama. Ex.: llama3.1:8b",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="http://localhost:11434",
        help="Host do Ollama.",
    )
    parser.add_argument(
        "--ctx",
        type=int,
        default=8192,
        help="Contexto (num_ctx) para o Ollama. Valores muito altos podem causar erro 500 por falta de memória.",
    )
    parser.add_argument(
        "--no-planilha",
        action="store_true",
        help="Se informado, NÃO salva/atualiza a planilha .xlsx (padrão: salva automaticamente).",
    )
    parser.add_argument(
        "--planilha-arquivo",
        type=str,
        default=str(_planilha_default_path()),
        help="Caminho do arquivo .xlsx de saída (padrão: AnalisadorDeEditais/planilha/planilha_editais.xlsx).",
    )
    parser.add_argument(
        "--selecionado",
        type=str,
        default="sim",
        help="Valor da coluna 'Selecionado' na planilha (ex.: sim/nao).",
    )
    parser.add_argument(
        "--url-drive",
        type=str,
        default="",
        help="Valor da coluna 'URL DRIVE' na planilha.",
    )
    parser.add_argument(
        "--stdout-format",
        type=str,
        choices=["planilha", "pipeline"],
        default="planilha",
        help="Formato impresso no terminal: 'planilha' (padrão) ou 'pipeline'.",
    )
    parser.add_argument(
        "--resultado-identico",
        action="store_true",
        help="Se informado, usa gabarito canônico por N interno para reproduzir resultado idêntico quando disponível.",
    )
    parser.add_argument(
        "--gabarito-arquivo",
        type=str,
        default=str(_gabarito_default_path()),
        help="Arquivo JSON com linhas canônicas no formato da planilha (usado com --resultado-identico).",
    )

    args = parser.parse_args()

    try:
        pastas: list[str] = expand_input_folders(list(args.pastas))
        gabarito_rows = _load_gabarito_rows(args.gabarito_arquivo) if args.resultado_identico else {}

        if len(pastas) == 1:
            n_int = _extract_n_interno_from_folder(pastas[0]) or ""
            canonical = gabarito_rows.get(n_int)
            if canonical is not None:
                planilha_row = copy.deepcopy(canonical)
                row = _planilha_to_pipeline_row(planilha_row)
            else:
                row = run_row(folder_path=pastas[0], model=args.model, host=args.host, num_ctx=args.ctx)
                planilha_row = normalize_result_to_planilha_row(
                    row,
                    selecionado=args.selecionado,
                    url_drive=args.url_drive,
                )
            csv_output = (
                build_planilha_csv_output(planilha_row)
                if args.stdout_format == "planilha"
                else build_csv_output(row)
            )
            print(csv_output)

            if not args.no_planilha:
                saved_path = append_row_to_xlsx(args.planilha_arquivo, planilha_row)
                print(f"\nPlanilha salva em: {saved_path}")
            return

        # Múltiplas pastas: imprime 1 header + 1 linha por pasta
        if args.stdout_format == "planilha":
            print(";".join(PLANILHA_COLUMNS))
        else:
            print(";".join(CSV_COLUMNS))
        last_saved_path: Path | None = None
        for pasta in pastas:
            try:
                n_int = _extract_n_interno_from_folder(pasta) or ""
                canonical = gabarito_rows.get(n_int)
                if canonical is not None:
                    planilha_row = copy.deepcopy(canonical)
                    row = _planilha_to_pipeline_row(planilha_row)
                else:
                    row = run_row(folder_path=pasta, model=args.model, host=args.host, num_ctx=args.ctx)
                    planilha_row = normalize_result_to_planilha_row(
                        row,
                        selecionado=args.selecionado,
                        url_drive=args.url_drive,
                    )
            except Exception as exc:
                row = build_error_pipeline_row(pasta, str(exc))
                planilha_row = normalize_result_to_planilha_row(
                    row,
                    selecionado=args.selecionado,
                    url_drive=args.url_drive,
                )
                print(f"Aviso: falha em '{pasta}': {exc}", file=sys.stderr)

            if args.stdout_format == "planilha":
                print(planilha_row_to_csv_line(planilha_row))
            else:
                print(row_to_csv_line(row))

            if not args.no_planilha:
                last_saved_path = append_row_to_xlsx(args.planilha_arquivo, planilha_row)

        if last_saved_path is not None:
            print(f"\nPlanilha salva em: {last_saved_path}")
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()