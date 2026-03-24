from __future__ import annotations
import sys
import logging
import importlib
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from pathlib import Path
import pandas as pd

warnings.filterwarnings(
    "ignore",
    message=r"Field .* has conflict with protected namespace \"model_\".",
    category=UserWarning,
)

# Garante que o pacote backend/app esteja disponível para importar a config de logs.
ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
	sys.path.insert(0, str(BACKEND_DIR))

importlib.import_module("app.logs.config")

logger = logging.getLogger(__name__)
from shared.pnpc_client import PNCPId, build_session
from shared import db


def _get_pipeline_api():
    return importlib.import_module("pipeline.pipeline_api")


def _get_pipeline_atas():
    return importlib.import_module("pipeline.pipeline_atas")

# Configurações de paralelismo

# Quantos IDs processam AO MESMO TEMPO (cada um usa 2 threads: API + Ata)
# Com 5 IDs simultâneos → até 10 threads ativas
# Aumente com cautela: mais IDs = mais chamadas ao PNCP = risco de rate limit
MAX_IDS_SIMULTANEOS = 5

# Total de workers no pool (deve ser >= MAX_IDS_SIMULTANEOS * 2)
MAX_WORKERS = 12

def carregar_planilha(caminho: str) -> list[PNCPId]:
    """
    Lê a planilha e retorna lista de PNCPId válidos.
    Aceita .xlsx, .xls e .csv
    """
    path = Path(caminho)
    if not path.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {caminho}")

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, dtype=str)
    else:
        df = pd.read_excel(path, dtype=str)

    # tenta encontrar a coluna de ID PNCP automaticamente
    possiveis = ["ID PNCP", "id_pncp", "IDPNCP", "id pncp", "ID_PNCP"]
    coluna = next((c for c in possiveis if c in df.columns), None)

    if coluna is None:
        print(f"\nColunas disponíveis: {list(df.columns)}")
        coluna = input("Nome exato da coluna com o ID PNCP: ").strip()

    ids_raw = df[coluna].fillna("").astype(str).str.strip().tolist()
    ids = [PNCPId.parse(raw) for raw in ids_raw]
    ids_validos = [pid for pid in ids if pid is not None]

    total = len(ids_raw)
    invalidos = total - len(ids_validos)
    print(f"\n  IDs encontrados  : {total}")
    print(f"  IDs válidos      : {len(ids_validos)}")
    if invalidos > 0:
        print(f"  IDs inválidos    : {invalidos} (ignorados)")

    return ids_validos

#Registrando no bacno
def registrar_ids(ids: list[PNCPId]) -> None:
    """Garante que todos os IDs existam no banco antes de processar."""
    for pid in ids:
        db.upsert_licitacao(str(pid), pid.cnpj, pid.ano, pid.sequencial)
        

#Tentativa do worker: Processando um id paralelo (API + ata)
def _processar_id_completo(
    pid: PNCPId,
    executor: ThreadPoolExecutor,
) -> dict:
    """
    Para cada ID, submete API e Ata como duas futures paralelas
    em um executor dedicado de tarefas e aguarda ambas terminarem.
    """
    pipeline_api = _get_pipeline_api()
    pipeline_atas = _get_pipeline_atas()

    session_api = build_session()   # cada thread tem sua própria sessão HTTP
    session_ata = build_session()

    future_api = executor.submit(pipeline_api.processar_id, pid, session_api)
    future_ata = executor.submit(pipeline_atas.processar_id, pid, session_ata)

    status_api = "erro"
    status_ata = "erro"

    try:
        status_api = future_api.result(timeout=300)  # 5 min timeout por ID
    except TimeoutError:
        status_api = "timeout"
        logger.error(f"[{pid}] Pipeline API falhou: Timeout após 300s")
    except Exception as e:
        logger.error(f"[{pid}] Pipeline API falhou: {type(e).__name__}: {e}", exc_info=True)

    try:
        status_ata = future_ata.result(timeout=600)  # 10 min (OCR é mais lento)
    except TimeoutError:
        status_ata = "timeout"
        logger.error(f"[{pid}] Pipeline Ata falhou: Timeout após 600s")
    except Exception as e:
        logger.error(f"[{pid}] Pipeline Ata falhou: {type(e).__name__}: {e}", exc_info=True)

    return {
        "id_pncp": str(pid),
        "status_api": status_api,
        "status_ata": status_ata,
    }
        
#Exportando relatorio
def exportar_relatorio() -> None:
    dados = db.relatorio_final()
    if not dados:
        print("  Nenhum dado para exportar.")
        return

    df = pd.DataFrame(dados)
    caminho = Path("relatorio_final.xlsx")
    df.to_excel(caminho, index=False)
    print(f"\n  Relatório exportado: {caminho}  ({len(df)} linhas)")

    # resumo rápido no terminal
    print(f"\n  Resumo:")
    print(f"    IDs únicos   : {df['id_pncp'].nunique()}")
    print(f"    Itens API    : {df['descricao_api'].notna().sum()}")
    print(f"    PDFs com OCR : {df['descricao_ocr'].notna().sum()}")

def _cabecalho():
    print("\n" + "=" * 52)
    print("  PNCP Pipeline — Sistema de Licitações")
    print("=" * 52)


def _menu_principal() -> str:
    print("\n  1. Rodar ambos pipelines em paralelo (recomendado)")
    print("  2. Somente Pipeline API (itens + preços)")
    print("  3. Somente Pipeline Atas (download + OCR)")
    print("  4. Exportar relatório final (XLSX)")
    print("  5. Sair")
    return input("\n  Escolha: ").strip()


def main():
    _cabecalho()

    db.init_db()
    print("  Banco inicializado (WAL mode ativo)")

    while True:
        opcao = _menu_principal()

        if opcao == "5":
            print("\n  Até logo.\n")
            break

        if opcao == "4":
            exportar_relatorio()
            continue

        if opcao not in ("1", "2", "3"):
            print("  Opção inválida.")
            continue

        # solicita planilha
        caminho = input("\n  Caminho da planilha (.xlsx ou .csv): ").strip().strip('"')

        try:
            ids = carregar_planilha(caminho)
        except FileNotFoundError as e:
            print(f"\n  Erro: {e}")
            continue

        if not ids:
            print("  Nenhum ID válido encontrado na planilha.")
            continue

        registrar_ids(ids)

        # ── Opção 1: ambos em paralelo ──────────────────────────
        if opcao == "1":
            print(f"\n  Iniciando processamento paralelo de {len(ids)} IDs")
            print(f"  Máximo simultâneo: {MAX_IDS_SIMULTANEOS} IDs ({MAX_IDS_SIMULTANEOS * 2} threads)")
            print(f"  Cada ID: API + Ata rodando ao mesmo tempo\n")

            resultados = []

            # Evita deadlock: executor de IDs separado do executor de tarefas API/Ata.
            with ThreadPoolExecutor(max_workers=MAX_IDS_SIMULTANEOS) as id_executor, ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {
                    id_executor.submit(_processar_id_completo, pid, executor): pid
                    for pid in ids
                }

                concluidos = 0
                for future in as_completed(futures):
                    pid = futures[future]
                    concluidos += 1
                    try:
                        resultado = future.result()
                        resultados.append(resultado)
                        print(
                            f"  [{concluidos}/{len(ids)}] {pid} — "
                            f"API: {resultado['status_api']} | "
                            f"Ata: {resultado['status_ata']}"
                        )
                    except Exception as e:
                        logger.error(f"Erro inesperado em {pid}: {type(e).__name__}: {e}", exc_info=True)
                        print(f"  [{concluidos}/{len(ids)}] {pid} — ERRO: {e}")

            # resumo
            ok_api = sum(1 for r in resultados if r["status_api"] == "ok")
            ok_ata = sum(1 for r in resultados if r["status_ata"] in ("ok", "sem_atas"))
            print(f"\n  Concluído!")
            print(f"  API: {ok_api}/{len(ids)} com itens salvos")
            print(f"  Ata: {ok_ata}/{len(ids)} processados")

        # ── Opção 2: somente API ────────────────────────────────
        elif opcao == "2":
            pipeline_api = _get_pipeline_api()
            print(f"\n  Rodando Pipeline API para {len(ids)} IDs...\n")
            session = build_session()
            for i, pid in enumerate(ids, 1):
                status = pipeline_api.processar_id(pid, session)
                print(f"  [{i}/{len(ids)}] {pid} — {status}")

        # ── Opção 3: somente Atas ───────────────────────────────
        elif opcao == "3":
            pipeline_atas = _get_pipeline_atas()
            print(f"\n  Rodando Pipeline Atas para {len(ids)} IDs...\n")
            session = build_session()
            for i, pid in enumerate(ids, 1):
                status = pipeline_atas.processar_id(pid, session)
                print(f"  [{i}/{len(ids)}] {pid} — {status}")


if __name__ == "__main__":
    main()