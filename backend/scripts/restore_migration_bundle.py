from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.migration_bundle import restore_bundle, validate_bundle


parser = argparse.ArgumentParser(description="Valida ou restaura um pacote de migracao.")
parser.add_argument("--bundle", required=True, help="Diretorio do pacote de migracao.")
parser.add_argument("--mode", choices=("validate", "restore"), default="validate")
parser.add_argument("--confirm-restore", action="store_true", help="Obrigatorio para sobrescrever o banco de destino.")
parser.add_argument("--skip-files", action="store_true", help="Restaura somente o banco PostgreSQL.")
args = parser.parse_args()

if args.mode == "validate":
    result = validate_bundle(Path(args.bundle))
else:
    result = restore_bundle(Path(args.bundle), confirm_restore=args.confirm_restore, restore_files=not args.skip_files)
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
