from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.crm.sales_process_importer import run_import  # noqa: E402


def main() -> None:
    workbook_path = (
        Path(sys.argv[1]).expanduser()
        if len(sys.argv) > 1
        else Path(r"C:\Users\vish8\Downloads\PLANILHA DE PROCESSOS DE VENDAS TOR.xlsx")
    )
    summary = run_import(workbook_path)
    print(summary)


if __name__ == "__main__":
    main()
