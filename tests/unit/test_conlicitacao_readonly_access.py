from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _router_source() -> str:
    return (
        ROOT / "backend/app/integrations/conlicitacao/router.py"
    ).read_text(encoding="utf-8")


def test_readonly_diagnostics_does_not_require_tenant_allowlist():
    source = _router_source()
    diagnostics_block = source.split(
        "async def conlicitacao_diagnostics(", 1
    )[1].split(
        "@router.post(\"/integrations/conlicitacao/monitoring/start\")", 1
    )[0]

    assert "_ensure_conlicitacao_configured()" in diagnostics_block
    assert "_ensure_conlicitacao_access(current_user)" not in diagnostics_block


def test_write_operations_keep_tenant_authorization():
    source = _router_source()

    assert "def _ensure_conlicitacao_access(current_user: User)" in source
    assert (
        "current_user.tenant_id not in settings.conlicitacao_sync_tenant_ids"
        in source
    )
    assert source.count("_ensure_conlicitacao_access(current_user)") >= 2


def test_status_exposes_readonly_availability_separately():
    source = _router_source()

    assert '"read_only_available": configured' in source
    assert '"authorized": authorized' in source
