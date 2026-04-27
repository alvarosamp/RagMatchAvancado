"""
Configuração global do pytest.

O conftest.py é carregado automaticamente pelo pytest antes de qualquer teste.
Aqui fazemos duas coisas:
  1. Adicionamos o diretório 'backend/' ao sys.path — permite importar
     módulos como 'from app.core.ml_config import get_ml_config'
  2. Mockamos dependências externas pesadas (MLflow, Ollama, Docling)
     para que testes unitários rodem sem infraestrutura real.

CONCEITO MLOPS: testes unitários NUNCA devem precisar de serviços externos.
Use mocks para isolar a lógica do código das dependências de infraestrutura.
"""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

# ── Caminho do backend ────────────────────────────────────────────────────────
BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


def _stub(name: str, **attrs) -> ModuleType:
    """Cria um módulo-stub leve para substituir dependências pesadas."""
    m = ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


# ── Mocks de infra (carregados antes de qualquer import de app.*) ─────────────
for mod_name in [
    "docling", "docling.document_converter", "docling.datamodel",
    "docling.datamodel.base_models", "docling.datamodel.document",
    "ollama", "pgvector", "pgvector.sqlalchemy",
    "evidently", "evidently.report", "evidently.metric_preset",
    "evidently.metrics",
    "reportlab", "reportlab.lib", "reportlab.platypus",
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.ext",
    "sqlalchemy.ext.declarative",
]:
    sys.modules.setdefault(mod_name, MagicMock())

# mlflow precisa de um stub com atributos específicos usados no tracker
_mlflow_stub = _stub(
    "mlflow",
    set_tracking_uri=MagicMock(),
    set_experiment=MagicMock(),
    start_run=MagicMock(),
    log_params=MagicMock(),
    log_metrics=MagicMock(),
    log_artifact=MagicMock(),
    register_model=MagicMock(),
    search_runs=MagicMock(),
)
_mlflow_stub.tracking = MagicMock()
sys.modules.setdefault("mlflow", _mlflow_stub)
