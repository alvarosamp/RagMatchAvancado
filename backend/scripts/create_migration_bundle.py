from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.migration_bundle import create_bundle


parser = argparse.ArgumentParser(description="Gera backup completo e auditavel para migracao de servidor.")
parser.add_argument("--output", required=True, help="Diretorio vazio onde o pacote sera criado.")
parser.add_argument("--database-only", action="store_true", help="Nao copia volumes de arquivos ou objetos.")
args = parser.parse_args()

print(json.dumps(create_bundle(Path(args.output), include_files=not args.database_only), ensure_ascii=False, indent=2))
