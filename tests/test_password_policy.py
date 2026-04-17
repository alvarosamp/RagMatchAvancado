import pytest

import importlib.util
from pathlib import Path
import sys

# Carrega o arquivo por caminho para não executar __init__.py do pacote auth
# (que puxa dependencies e outros módulos) e não depender de PYTHONPATH.
_POLICY_PATH = Path(__file__).resolve().parents[1] / 'backend' / 'app' / 'auth' / 'password_policy.py'
_spec = importlib.util.spec_from_file_location('password_policy', _POLICY_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

validate_password = _mod.validate_password


@pytest.mark.parametrize(
    "password, ok",
    [
        ("Aa1!aaaa", True),
        ("Aa1!aa", False),           # < 8
        ("aa1!aaaa", False),         # sem maiúscula
        ("AA1!AAAA", False),         # sem minúscula
        ("Aa!aaaaa", False),         # sem número
        ("Aa1aaaaa", False),         # sem símbolo
    ],
)
def test_password_policy(password, ok):
    res = validate_password(password)
    assert res.ok is ok
    if not ok:
        assert len(res.errors) >= 1
