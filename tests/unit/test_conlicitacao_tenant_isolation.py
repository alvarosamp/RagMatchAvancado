from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_tender_tables_have_tenant_constraints_and_rls():
    migration = (
        ROOT / "backend/alembic/versions/20260926_01_conlicitacao_tenders.py"
    ).read_text(encoding="utf-8")

    assert '"tenant_id", "provider", "external_id"' in migration
    assert '"tenant_id", "provider", "external_filter_id"' in migration
    assert '_enable_rls("tenders")' in migration
    assert '_enable_rls("tender_sync_checkpoints")' in migration
    assert "current_setting('app.current_tenant_id', true)" in migration
    assert "WITH CHECK (tenant_id" in migration


def test_tender_endpoints_apply_explicit_tenant_filter():
    router = (
        ROOT / "backend/app/integrations/conlicitacao/router.py"
    ).read_text(encoding="utf-8")

    assert "Tender.tenant_id == current_user.tenant_id" in router
