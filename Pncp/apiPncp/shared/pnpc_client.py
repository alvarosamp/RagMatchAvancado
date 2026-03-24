"""
─────────────────────
Cliente HTTP unificado para a API do PNCP.
Centraliza: parse de ID, sessão com retry, e todas as chamadas de endpoint.

Regra de ouro: NENHUM outro arquivo deve fazer requests.get() direto.
"""
from __future__ import annotations
 
import re
import time
import logging
from dataclasses import dataclass
from typing import Optional
 
import requests
 
logger = logging.getLogger(__name__)
 
BASE_API = "https://pncp.gov.br/api/pncp/v1"
 
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; PNCP-pipeline/1.0)",
}
 
# ──────────────────────────────────────────
# Parse do ID PNCP
# ──────────────────────────────────────────
 
_PATTERN_ID = re.compile(r"^(\d{14})-(\d+)-(\d+)/(\d{4})$")
 
 
@dataclass(frozen=True)
class PNCPId:
    raw: str
    cnpj: str
    tipo: int        # normalmente 1
    sequencial: int
    ano: int
 
    @classmethod
    def parse(cls, raw: str) -> Optional["PNCPId"]:
        """
        Converte '14226731000164-1-000018/2025' → PNCPId.
        Retorna None se o formato for inválido.
        """
        if not raw or str(raw).strip().lower() in ("nan", "none", ""):
            return None
        texto = str(raw).strip()
        m = _PATTERN_ID.match(texto)
        if not m:
            return None
        return cls(
            raw=texto,
            cnpj=m.group(1),
            tipo=int(m.group(2)),
            sequencial=int(m.group(3)),
            ano=int(m.group(4)),
        )
 
    def __str__(self) -> str:
        return self.raw
 
 
# ──────────────────────────────────────────
# Sessão HTTP com retry automático
# ──────────────────────────────────────────
 
def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session
 
 
def _get_json(
    session: requests.Session,
    url: str,
    timeout: int = 30,
    max_tentativas: int = 5,
    espera_base: float = 2.0,
) -> Optional[dict | list]:
    """
    GET com retry exponencial e tratamento de 429.
    Retorna None em vez de lançar exceção para 204/404.
    """
    for tentativa in range(1, max_tentativas + 1):
        try:
            resp = session.get(url, timeout=timeout)
 
            if resp.status_code in (204, 404):
                logger.debug(f"[{resp.status_code}] {url}")
                return None
 
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                espera = float(retry_after) if retry_after and retry_after.isdigit() else espera_base * tentativa
                logger.warning(f"Rate limit (429). Aguardando {espera:.1f}s... URL: {url}")
                time.sleep(espera)
                continue
 
            resp.raise_for_status()
 
            if not resp.text.strip():
                return None
 
            return resp.json()
 
        except requests.RequestException as e:
            if tentativa < max_tentativas:
                espera = espera_base * tentativa
                logger.warning(f"Erro tentativa {tentativa}/{max_tentativas}: {e}. Nova tentativa em {espera:.1f}s")
                time.sleep(espera)
            else:
                logger.error(f"Falhou após {max_tentativas} tentativas: {url} — {e}")
                raise
 
    return None
 
 
# ──────────────────────────────────────────
# Endpoints da API PNCP
# ──────────────────────────────────────────
 
def buscar_itens(session: requests.Session, pid: PNCPId) -> list[dict]:
    """Retorna lista de itens da contratação."""
    url = f"{BASE_API}/orgaos/{pid.cnpj}/compras/{pid.ano}/{pid.sequencial}/itens"
    dados = _get_json(session, url)
    if isinstance(dados, list):
        return dados
    if isinstance(dados, dict):
        return dados.get("data", dados.get("itens", []))
    return []
 
 
def buscar_resultado_item(session: requests.Session, pid: PNCPId, numero_item: int) -> list[dict]:
    """Retorna resultado (vencedor + preço) de um item."""
    url = f"{BASE_API}/orgaos/{pid.cnpj}/compras/{pid.ano}/{pid.sequencial}/itens/{numero_item}/resultados"
    dados = _get_json(session, url)
    return dados if isinstance(dados, list) else []
 
 
def buscar_atas(session: requests.Session, pid: PNCPId) -> list[dict]:
    """Retorna lista de atas de registro de preço da contratação."""
    url = f"{BASE_API}/orgaos/{pid.cnpj}/compras/{pid.ano}/{pid.sequencial}/atas"
    dados = _get_json(session, url)
    if isinstance(dados, list):
        return dados
    if isinstance(dados, dict):
        for key in ("data", "dados", "atas", "resultado"):
            if isinstance(dados.get(key), list):
                return dados[key]
    return []
 
 
def buscar_documentos_ata(
    session: requests.Session,
    pid: PNCPId,
    sequencial_ata: int,
) -> list[dict]:
    """Retorna lista de documentos de uma ata específica."""
    url = (
        f"{BASE_API}/orgaos/{pid.cnpj}/compras/{pid.ano}/"
        f"{pid.sequencial}/atas/{sequencial_ata}/arquivos"
    )
    dados = _get_json(session, url)
    if isinstance(dados, list):
        return dados
    if isinstance(dados, dict):
        for key in ("data", "arquivos", "documentos"):
            if isinstance(dados.get(key), list):
                return dados[key]
    return []
 
 
def url_download_documento(pid: PNCPId, sequencial_ata: int, sequencial_doc: int) -> str:
    return (
        f"{BASE_API}/orgaos/{pid.cnpj}/compras/{pid.ano}/"
        f"{pid.sequencial}/atas/{sequencial_ata}/arquivos/{sequencial_doc}"
    )
 
 
def download_arquivo(
    session: requests.Session,
    url: str,
    destino,
    timeout: int = 60,
    max_tentativas: int = 5,
    espera_base: float = 2.0,
) -> None:
    """Download de arquivo binário com retry."""
    destino.parent.mkdir(parents=True, exist_ok=True)
 
    for tentativa in range(1, max_tentativas + 1):
        try:
            with session.get(url, stream=True, timeout=timeout) as resp:
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    espera = float(retry_after) if retry_after and retry_after.isdigit() else espera_base * tentativa
                    logger.warning(f"Rate limit no download. Aguardando {espera:.1f}s")
                    time.sleep(espera)
                    continue
                resp.raise_for_status()
                with open(destino, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=128 * 1024):
                        if chunk:
                            f.write(chunk)
                return
        except requests.RequestException as e:
            if tentativa < max_tentativas:
                espera = espera_base * tentativa
                logger.warning(f"Erro download tentativa {tentativa}/{max_tentativas}: {e}")
                time.sleep(espera)
            else:
                raise