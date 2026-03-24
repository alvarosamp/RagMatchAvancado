"""
Pipeline 1: baixa PDFs de atas e extrai descrição do item via OCR (Docling).

Responsabilidades:
  - Buscar atas da contratação via API
  - Baixar cada documento PDF
  - Rodar OCR com Docling
  - Extrair marca e modelo do texto extraído via regex
  - Persistir no banco via shared/db.py
"""

from __future__ import annotations

import re
import time
import logging
import importlib
from pathlib import Path

import requests

from shared.pnpc_client import (
    PNCPId, build_session,
    buscar_atas, buscar_documentos_ata,
    url_download_documento, download_arquivo,
)
from shared import db

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# Configurações
# ──────────────────────────────────────────

PASTA_ATAS   = Path("atas_baixadas")
DELAY_DOWNLOAD = 1.5   # segundos entre downloads (respeita rate limit)
KEYWORD_PRODUTO = "switch"  # mantém igual ao pipeline_api.py

# Prioriza parser central do backend. Se indisponível, usa fallback local com pypdf.
try:
    parse_pdf_docling = importlib.import_module("app.pipeline.docling_parser").parse_pdf
    DOCLING_DISPONIVEL = True
except Exception:
    parse_pdf_docling = None
    DOCLING_DISPONIVEL = False
    logger.warning("Docling não encontrado. Usando fallback sem OCR (texto nativo do PDF).")


# ──────────────────────────────────────────
# OCR
# ──────────────────────────────────────────

def extrair_texto_pdf(caminho: Path) -> str:
    """Extrai texto do PDF. Usa Docling se disponível, senão texto nativo."""
    if not caminho.exists():
        return ""

    if DOCLING_DISPONIVEL and parse_pdf_docling is not None:
        try:
            parsed = parse_pdf_docling(caminho, filename=caminho.name)
            return parsed.full_text
        except Exception as e:
            logger.warning(f"Docling falhou em {caminho.name}: {e}. Tentando fallback.")

    # fallback: texto nativo (sem OCR para PDFs escaneados)
    try:
        import pypdf
        reader = pypdf.PdfReader(str(caminho))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception as e:
        logger.error(f"Fallback pypdf falhou em {caminho.name}: {e}")
        return ""


# ──────────────────────────────────────────
# Extração de marca/modelo do texto OCR
# ──────────────────────────────────────────

_RE_MARCA = re.compile(
    r"\b(cisco|intelbras|mikrotik|huawei|hp|hpe|dell|d-link|tp-link|juniper|aruba|extreme|allied)\b",
    re.IGNORECASE,
)
_RE_MODELO = re.compile(r"\b([A-Z]{1,5}[-\s]?\d{3,6}[A-Z0-9\-]*)\b")


def extrair_marca_modelo(texto: str) -> tuple[str | None, str | None]:
    marca = _RE_MARCA.search(texto)
    modelo = _RE_MODELO.search(texto)
    return (
        marca.group(0).title() if marca else None,
        modelo.group(0) if modelo else None,
    )


# ──────────────────────────────────────────
# Utilitários
# ──────────────────────────────────────────

def _sanitize(name: str, max_len: int = 150) -> str:
    name = re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", str(name).strip())
    name = re.sub(r"\s+", " ", name).strip()
    return name[:max_len] or "sem_nome"


def _inferir_extensao(doc: dict) -> str:
    ext = (doc.get("extensao") or doc.get("tipoArquivo") or "pdf")
    return str(ext).strip().lower().replace(".", "")


# ──────────────────────────────────────────
# Pipeline principal
# ──────────────────────────────────────────

def processar_id(pid: PNCPId, session: requests.Session) -> str:
    """
    Processa um ID PNCP:
    1. Busca atas da contratação
    2. Baixa cada documento PDF
    3. Extrai texto via OCR
    4. Salva no banco

    Retorna status: 'ok' | 'sem_atas' | 'erro'
    """
    logger.info(f"[ATA] Iniciando: {pid}")
    pasta_id = PASTA_ATAS / _sanitize(str(pid))

    try:
        atas = buscar_atas(session, pid)
    except Exception as e:
        logger.error(f"[ATA] Erro ao buscar atas {pid}: {e}")
        db.atualizar_status(str(pid), "ata", "erro")
        return "erro"

    if not atas:
        logger.info(f"[ATA] Sem atas: {pid}")
        db.atualizar_status(str(pid), "ata", "sem_atas")
        return "sem_atas"

    arquivos_salvos = 0

    for ata in atas:
        seq_ata = ata.get("sequencialAta") or ata.get("numeroSequencialAta") or 1

        try:
            documentos = buscar_documentos_ata(session, pid, int(seq_ata))
        except Exception as e:
            logger.warning(f"[ATA] Erro documentos ata {seq_ata} de {pid}: {e}")
            _registrar_erro(str(pid), seq_ata, None, "erro_consulta_documentos", str(e))
            continue

        if not documentos:
            _registrar_erro(str(pid), seq_ata, None, "ata_sem_documentos", "Sem documentos listados")
            continue

        for seq_doc, doc in enumerate(documentos, start=1):
            seq_doc_real = doc.get("sequencialDocumento") or doc.get("id") or seq_doc
            extensao = _inferir_extensao(doc)
            nome_arquivo = f"ata_{seq_ata}_doc_{seq_doc_real}.{extensao}"
            caminho = pasta_id / nome_arquivo

            url = url_download_documento(pid, int(seq_ata), int(seq_doc_real))

            try:
                download_arquivo(session, url, caminho)
                logger.info(f"[ATA] Baixado: {nome_arquivo}")
            except Exception as e:
                logger.error(f"[ATA] Erro download {nome_arquivo}: {e}")
                _registrar_erro(str(pid), seq_ata, seq_doc_real, "erro_download", str(e), nome_arquivo, str(caminho))
                time.sleep(DELAY_DOWNLOAD)
                continue

            # OCR
            texto_ocr = ""
            status_ocr = "ok"
            marca = modelo = None

            if extensao == "pdf":
                try:
                    texto_ocr = extrair_texto_pdf(caminho)
                    if KEYWORD_PRODUTO.lower() in texto_ocr.lower():
                        marca, modelo = extrair_marca_modelo(texto_ocr)
                except Exception as e:
                    logger.warning(f"[ATA] Erro OCR {nome_arquivo}: {e}")
                    status_ocr = "erro_ocr"

            db.inserir_item_ata(str(pid), {
                "id_pncp": str(pid),
                "sequencial_ata": seq_ata,
                "sequencial_doc": seq_doc_real,
                "nome_arquivo": nome_arquivo,
                "caminho_pdf": str(caminho),
                "status_download": "baixado",
                "descricao_ocr": texto_ocr[:5000] if texto_ocr else None,  # limita tamanho
                "marca_extraida": marca,
                "modelo_extraido": modelo,
                "status_ocr": status_ocr,
                "mensagem_erro": None,
            })

            arquivos_salvos += 1
            time.sleep(DELAY_DOWNLOAD)

    status = "ok" if arquivos_salvos > 0 else "sem_documentos"
    db.atualizar_status(str(pid), "ata", status)
    logger.info(f"[ATA] Concluído {pid}: {arquivos_salvos} arquivos ({status})")
    return status


def _registrar_erro(id_pncp, seq_ata, seq_doc, status, mensagem, nome=None, caminho=None):
    db.inserir_item_ata(id_pncp, {
        "id_pncp": id_pncp,
        "sequencial_ata": seq_ata,
        "sequencial_doc": seq_doc,
        "nome_arquivo": nome,
        "caminho_pdf": caminho,
        "status_download": status,
        "descricao_ocr": None,
        "marca_extraida": None,
        "modelo_extraido": None,
        "status_ocr": "n/a",
        "mensagem_erro": mensagem,
    })


def run(ids: list[PNCPId]) -> None:
    """Ponto de entrada para o menu. Processa lista de IDs sequencialmente."""
    session = build_session()
    for pid in ids:
        processar_id(pid, session)