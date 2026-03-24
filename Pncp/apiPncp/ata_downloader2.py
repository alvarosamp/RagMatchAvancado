import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests


BASE_API = "https://pncp.gov.br/api/pncp/v1"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; PNCP-atas-downloader/2.0)"
}


# =========================
# CONFIGURAÇÕES PRINCIPAIS
# =========================
CAMINHO_PLANILHA = r"C:\Users\Luiz\Documents\Asimov Academy\Projetos\baixador_editais\base para 1000 atas\_Processados\[Projeto 1000 atas] - 401 a 500_processado.xlsx"
COLUNA_ID_PNCP = "ID PNCP"
COLUNA_N_ATA = "N Ata"
PASTA_SAIDA = Path("atas_baixadas")
CAMINHO_RELATORIO = PASTA_SAIDA / f"relatorio - {Path(CAMINHO_PLANILHA).stem}.csv"
DELAY_ENTRE_DOWNLOADS = 2.0



# =========================
# FUNÇÕES UTILITÁRIAS
# =========================

def obter_pasta_raiz_saida(caminho_planilha: str, pasta_base: Path) -> Path:
    nome_planilha = Path(caminho_planilha).stem
    nome_planilha = sanitize_filename(nome_planilha)
    return pasta_base / nome_planilha

def sanitize_filename(name: str, max_len: int = 180) -> str:
    """
    Remove caracteres inválidos para nomes de arquivos/pastas no Windows.
    """
    if name is None:
        return "sem_nome"

    name = str(name).strip()
    if not name:
        return "sem_nome"

    name = re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()

    return name[:max_len]


def parse_id_contratacao_pncp(id_contratacao: str) -> Tuple[str, int, int]:
    """
    Converte um ID PNCP no padrão:
    99999999999999-1-999999/9999

    Retorna:
    - cnpj
    - ano_compra
    - sequencial_compra
    """
    if not isinstance(id_contratacao, str):
        raise ValueError("ID PNCP precisa ser string.")

    texto = id_contratacao.strip()
    padrao = r"^(\d{14})-1-(\d{1,6})/(\d{4})$"
    match = re.match(padrao, texto)

    if not match:
        raise ValueError(f"ID PNCP inválido: {id_contratacao}")

    cnpj = match.group(1)
    sequencial_compra = int(match.group(2))
    ano_compra = int(match.group(3))

    return cnpj, ano_compra, sequencial_compra


def ensure_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def get_json(
    session: requests.Session,
    url: str,
    timeout: int = 30,
    tentativas: int = 5,
    espera_base: float = 2.0
) -> Optional[dict]:
    ultimo_erro = None

    for tentativa in range(1, tentativas + 1):
        try:
            resp = session.get(url, timeout=timeout)

            if resp.status_code in (204, 404):
                return None

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")

                if retry_after and retry_after.isdigit():
                    espera = float(retry_after)
                else:
                    espera = espera_base * tentativa

                print(f"429 recebido. Aguardando {espera:.1f}s antes de tentar novamente...")
                time.sleep(espera)
                continue

            resp.raise_for_status()

            if not resp.text.strip():
                return None

            return resp.json()

        except requests.RequestException as e:
            ultimo_erro = e

            if tentativa < tentativas:
                espera = espera_base * tentativa
                print(f"Erro na tentativa {tentativa}/{tentativas}: {e}. Nova tentativa em {espera:.1f}s...")
                time.sleep(espera)
            else:
                raise ultimo_erro

    return None


def download_file(
    session: requests.Session,
    url: str,
    destination,
    timeout: int = 60,
    tentativas: int = 5,
    espera_base: float = 2.0
) -> None:
    ultimo_erro = None

    for tentativa in range(1, tentativas + 1):
        try:
            with session.get(url, stream=True, timeout=timeout) as resp:
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")

                    if retry_after and retry_after.isdigit():
                        espera = float(retry_after)
                    else:
                        espera = espera_base * tentativa

                    print(f"429 no download. Aguardando {espera:.1f}s antes de tentar novamente...")
                    time.sleep(espera)
                    continue

                resp.raise_for_status()
                destination.parent.mkdir(parents=True, exist_ok=True)

                with open(destination, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 128):
                        if chunk:
                            f.write(chunk)
                return

        except requests.RequestException as e:
            ultimo_erro = e

            if tentativa < tentativas:
                espera = espera_base * tentativa
                print(f"Erro no download, tentativa {tentativa}/{tentativas}: {e}. Nova tentativa em {espera:.1f}s...")
                time.sleep(espera)
            else:
                raise ultimo_erro


def extract_ata_list(payload: Optional[dict]) -> List[dict]:
    """
    Lida com possíveis variações no formato da resposta.
    """
    if not payload:
        return []

    if isinstance(payload, list):
        return payload

    for key in ["data", "dados", "items", "atas", "resultado"]:
        value = payload.get(key)
        if isinstance(value, list):
            return value

    if payload.get("sequencialAta") is not None:
        return [payload]

    return []


def extract_document_list(payload: Optional[dict]) -> List[dict]:
    """
    Lida com possíveis variações no formato da resposta.
    """
    if not payload:
        return []

    if isinstance(payload, list):
        return payload

    for key in ["data", "dados", "items", "arquivos", "documentos", "resultado"]:
        value = payload.get(key)
        if isinstance(value, list):
            return value

    return []


def infer_document_filename(doc: dict, seq_doc: int) -> str:

    """
    Tenta descobrir um nome apropriado para o arquivo.
    """
    possible_names = [
        doc.get("titulo"),
        doc.get("nomeArquivo"),
        doc.get("nome"),
        doc.get("descricao"),
        doc.get("arquivo"),
    ]
    base_name = next((x for x in possible_names if x), f"documento_{seq_doc}")

    ext = (
        doc.get("extensao")
        or doc.get("tipoArquivo")
        or ""
    )
    ext = str(ext).strip().lower().replace(".", "")

    filename = sanitize_filename(base_name)

    if ext and not filename.lower().endswith(f".{ext}"):
        filename = f"{filename}.{ext}"

    return filename

def montar_nome_arquivo_ata(n_ata: str, indice_arquivo: int, extensao: str) -> str:
    n_ata_limpo = sanitize_filename(str(n_ata))
    extensao = extensao.lower().replace(".", "").strip()

    if not extensao:
        extensao = "pdf"

    return f"Ata#{n_ata_limpo}_{indice_arquivo}.{extensao}"

# =========================
# CHAMADAS AO PNCP
# =========================
def get_atas(session: requests.Session, cnpj: str, ano_compra: int, sequencial_compra: int) -> List[dict]:
    url = f"{BASE_API}/orgaos/{cnpj}/compras/{ano_compra}/{sequencial_compra}/atas"
    payload = get_json(session, url)
    return extract_ata_list(payload)


def get_documentos_ata(
    session: requests.Session,
    cnpj: str,
    ano_compra: int,
    sequencial_compra: int,
    sequencial_ata: int
) -> List[dict]:
    url = (
        f"{BASE_API}/orgaos/{cnpj}/compras/{ano_compra}/"
        f"{sequencial_compra}/atas/{sequencial_ata}/arquivos"
    )
    payload = get_json(session, url)
    return extract_document_list(payload)


# =========================
# PROCESSAMENTO DA PLANILHA
# =========================
def carregar_linhas_planilha(caminho_planilha: str) -> pd.DataFrame:
    path = Path(caminho_planilha)

    if not path.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {caminho_planilha}")

    if path.suffix.lower() == ".csv":
        # Se sua planilha vier do ConLicitação em CSV com ;
        df = pd.read_csv(path, sep=";", dtype=str)
    elif path.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(path, dtype=str)
    else:
        raise ValueError("Formato não suportado. Use CSV, XLSX ou XLS.")

    df.columns = [str(col).strip() for col in df.columns]

    colunas_obrigatorias = [COLUNA_ID_PNCP, COLUNA_N_ATA]
    faltantes = [c for c in colunas_obrigatorias if c not in df.columns]

    if faltantes:
        raise ValueError(
            f"Colunas obrigatórias não encontradas: {faltantes}. "
            f"Colunas disponíveis: {list(df.columns)}"
        )

    return df


# =========================
# PROCESSAMENTO DE UMA LINHA
# =========================
def infer_document_extension(doc: dict) -> str:
    possible_exts = [
        doc.get("extensao"),
        doc.get("tipoArquivo"),
    ]

    for ext in possible_exts:
        if ext:
            ext = str(ext).strip().lower().replace(".", "")
            if ext:
                return ext

    return "pdf"

def baixar_atas_de_uma_linha(
    session: requests.Session,
    id_pncp: str,
    n_ata: str,
    pasta_saida: Path,
    delay_segundos: float = 1.5
) -> List[Dict]:
    logs = []

    try:
        cnpj, ano_compra, sequencial_compra = parse_id_contratacao_pncp(id_pncp)
    except Exception as e:
        logs.append({
            "id_pncp": id_pncp,
            "n_ata": n_ata,
            "status": "id_invalido",
            "mensagem": str(e),
            "indice_ata": None,
            "sequencial_ata": None,
            "sequencial_documento": None,
            "arquivo": None,
            "caminho": None,
        })
        return logs

    try:
        atas = get_atas(session, cnpj, ano_compra, sequencial_compra)
    except Exception as e:
        logs.append({
            "id_pncp": id_pncp,
            "n_ata": n_ata,
            "status": "erro_consulta_atas",
            "mensagem": str(e),
            "indice_ata": None,
            "sequencial_ata": None,
            "sequencial_documento": None,
            "arquivo": None,
            "caminho": None,
        })
        return logs

    if not atas:
        logs.append({
            "id_pncp": id_pncp,
            "n_ata": n_ata,
            "status": "sem_atas",
            "mensagem": "Nenhuma ata encontrada para esta contratação.",
            "indice_ata": None,
            "sequencial_ata": None,
            "sequencial_documento": None,
            "arquivo": None,
            "caminho": None,
        })
        return logs

    nome_pasta_ata = f"Ata#{sanitize_filename(str(n_ata))}"
    pasta_ata = pasta_saida / nome_pasta_ata
    pasta_ata.mkdir(parents=True, exist_ok=True)

    indice_global_arquivo = 1

    for indice_ata, ata in enumerate(atas, start=1):
        sequencial_ata = ata.get("sequencialAta") or ata.get("numeroSequencialAta") or indice_ata

        try:
            documentos = get_documentos_ata(
                session=session,
                cnpj=cnpj,
                ano_compra=ano_compra,
                sequencial_compra=sequencial_compra,
                sequencial_ata=int(sequencial_ata)
            )
        except Exception as e:
            logs.append({
                "id_pncp": id_pncp,
                "n_ata": n_ata,
                "status": "erro_consulta_documentos",
                "mensagem": str(e),
                "indice_ata": indice_ata,
                "sequencial_ata": sequencial_ata,
                "sequencial_documento": None,
                "arquivo": None,
                "caminho": str(pasta_ata),
            })
            continue

        if not documentos:
            logs.append({
                "id_pncp": id_pncp,
                "n_ata": n_ata,
                "status": "ata_sem_documentos",
                "mensagem": "Ata encontrada, mas sem documentos listados.",
                "indice_ata": indice_ata,
                "sequencial_ata": sequencial_ata,
                "sequencial_documento": None,
                "arquivo": None,
                "caminho": str(pasta_ata),
            })
            continue

        for seq_local_doc, doc in enumerate(documentos, start=1):
            sequencial_documento = (
                doc.get("sequencialDocumento")
                or doc.get("sequencialArquivo")
                or doc.get("id")
                or seq_local_doc
            )

            extensao = infer_document_extension(doc)
            nome_arquivo = montar_nome_arquivo_ata(
                n_ata=n_ata,
                indice_arquivo=indice_global_arquivo,
                extensao=extensao
            )

            caminho_arquivo = pasta_ata / nome_arquivo

            url_download = (
                f"{BASE_API}/orgaos/{cnpj}/compras/{ano_compra}/"
                f"{sequencial_compra}/atas/{int(sequencial_ata)}/arquivos/{int(sequencial_documento)}"
            )

            try:
                download_file(session, url_download, caminho_arquivo)
                logs.append({
                    "id_pncp": id_pncp,
                    "n_ata": n_ata,
                    "status": "baixado",
                    "mensagem": "Arquivo baixado com sucesso.",
                    "indice_ata": indice_ata,
                    "sequencial_ata": sequencial_ata,
                    "sequencial_documento": sequencial_documento,
                    "arquivo": nome_arquivo,
                    "caminho": str(caminho_arquivo),
                })
                indice_global_arquivo += 1
            except Exception as e:
                logs.append({
                    "id_pncp": id_pncp,
                    "n_ata": n_ata,
                    "status": "erro_download",
                    "mensagem": str(e),
                    "indice_ata": indice_ata,
                    "sequencial_ata": sequencial_ata,
                    "sequencial_documento": sequencial_documento,
                    "arquivo": nome_arquivo,
                    "caminho": str(caminho_arquivo),
                })

            time.sleep(delay_segundos)

    return logs

def salvar_relatorio(logs: List[Dict], caminho_saida: Path) -> None:
    df = pd.DataFrame(logs)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(caminho_saida, index=False, encoding="utf-8-sig")

def determinar_status_final(logs: List[Dict]) -> str:
    """
    Regras:
    - Baixado: encontrou ata e baixou ao menos 1 arquivo
    - Sem ata: não encontrou ata
    - Falhou no processo: qualquer outro caso com erro ou sem download útil
    """
    if not logs:
        return "Falhou no processo"

    statuses = [log.get("status", "") for log in logs]

    if "baixado" in statuses:
        return "Baixado"

    if "sem_atas" in statuses:
        return "Sem ata"

    if "ata_sem_documentos" in statuses:
        return "Ata sem documentos"

    return "Falhou no processo"

def salvar_planilha_atualizada(df: pd.DataFrame, caminho_planilha: str) -> None:
    path = Path(caminho_planilha)

    if path.suffix.lower() == ".csv":
        df.to_csv(path, sep=";", index=False, encoding="utf-8-sig")
    elif path.suffix.lower() in [".xlsx", ".xls"]:
        df.to_excel(path, index=False)
    else:
        raise ValueError("Formato não suportado para salvar a planilha.")
    
def main():
    df = carregar_linhas_planilha(CAMINHO_PLANILHA)

    # normaliza colunas usadas
    df[COLUNA_ID_PNCP] = df[COLUNA_ID_PNCP].fillna("").astype(str).str.strip()
    df[COLUNA_N_ATA] = df[COLUNA_N_ATA].fillna("").astype(str).str.strip()
    df["Status"] = df["Status"].fillna("").astype(str)

    # apenas linhas com ID PNCP preenchido serão processadas
    df_processar = df[df[COLUNA_ID_PNCP] != ""].copy()

    pasta_saida_final = obter_pasta_raiz_saida(CAMINHO_PLANILHA, PASTA_SAIDA)
    caminho_relatorio_final = pasta_saida_final / "relatorio_downloads.csv"

    print(f"Total de linhas com ID PNCP: {len(df_processar)}")
    print(f"Pasta de saída: {pasta_saida_final}")

    session = ensure_session()
    todos_logs = []

    for i, (idx_original, row) in enumerate(df_processar.iterrows(), start=1):
        id_pncp = str(row[COLUNA_ID_PNCP]).strip()
        n_ata = str(row[COLUNA_N_ATA]).strip()

        print(f"[{i}/{len(df_processar)}] Processando ID PNCP={id_pncp} | N Ata={n_ata}")

        try:
            logs = baixar_atas_de_uma_linha(
                session=session,
                id_pncp=id_pncp,
                n_ata=n_ata,
                pasta_saida=pasta_saida_final,
                delay_segundos=DELAY_ENTRE_DOWNLOADS
            )
            todos_logs.extend(logs)

            status_final = determinar_status_final(logs)
            df.at[idx_original, "Status"] = status_final

        except Exception as e:
            df.at[idx_original, "Status"] = "Falhou no processo"

            todos_logs.append({
                "id_pncp": id_pncp,
                "n_ata": n_ata,
                "status": "falha_inesperada",
                "mensagem": str(e),
                "indice_ata": None,
                "sequencial_ata": None,
                "sequencial_documento": None,
                "arquivo": None,
                "caminho": None,
            })

    salvar_relatorio(todos_logs, caminho_relatorio_final)
    salvar_planilha_atualizada(df, CAMINHO_PLANILHA)

    print(f"Concluído. Relatório salvo em: {caminho_relatorio_final}")
    print(f"Planilha atualizada com status em: {CAMINHO_PLANILHA}")

if __name__ == "__main__":
    main()