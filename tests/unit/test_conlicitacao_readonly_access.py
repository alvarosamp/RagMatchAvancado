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
        '@router.get("/integrations/conlicitacao/opportunities/{external_id}/preview")', 1
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
    assert '"manual_import_authorized": manual_import_authorized' in source


def test_preview_is_read_only_but_import_keeps_tenant_authorization():
    source = _router_source()
    preview_block = source.split(
        "async def preview_conlicitacao_opportunity(", 1
    )[1].split(
        '@router.post("/integrations/conlicitacao/opportunities/{external_id}/import")', 1
    )[0]
    import_block = source.split(
        "async def import_conlicitacao_opportunity(", 1
    )[1].split(
        '@router.post("/integrations/conlicitacao/monitoring/start")', 1
    )[0]

    assert "_ensure_conlicitacao_configured()" in preview_block
    assert "_ensure_conlicitacao_access(current_user)" not in preview_block
    assert "_ensure_conlicitacao_manual_import_access(current_user)" in import_block
    assert "TenderRepository(db, current_user.tenant_id)" in import_block


def test_manual_import_uses_explicit_admin_email_allowlist():
    source = _router_source()

    assert "settings.conlicitacao_manual_import_admin_emails" in source
    assert "(current_user.email or \"\").strip().casefold()" in source
