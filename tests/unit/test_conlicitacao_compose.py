from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _service(compose: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)",
        compose,
    )
    assert match is not None
    return match.group(1)


def test_conlicitacao_worker_receives_tenant_allowlist_in_all_environments():
    for filename in ("docker-compose.yaml", "docker-compose.prod.yaml"):
        compose = (ROOT / filename).read_text(encoding="utf-8")
        worker = _service(compose, "worker-conlicitacao")

        assert "CONLICITACAO_ENABLED" in worker
        assert "CONLICITACAO_TOKEN" in worker
        assert "CONLICITACAO_TENANT_IDS" in worker


def test_production_api_receives_lookup_and_manual_import_settings():
    compose = (ROOT / "docker-compose.prod.yaml").read_text(encoding="utf-8")
    api = _service(compose, "api")

    assert "CONLICITACAO_LOOKUP_MAX_BULLETINS" in api
    assert "CONLICITACAO_ALLOWED_ADMIN_EMAILS" in api
