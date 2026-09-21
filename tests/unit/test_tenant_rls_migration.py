"""Regression checks for canonical tenant IDs and database-enforced isolation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_edital_and_job_models_use_numeric_tenant_foreign_keys():
    edital_models = (ROOT / "backend/app/db/models.py").read_text(encoding="utf-8")
    job_models = (ROOT / "backend/app/jobs/models.py").read_text(encoding="utf-8")

    assert 'tenant_id    = Column(Integer, ForeignKey("tenants.id")' in edital_models
    assert 'tenant_id = Column(Integer, ForeignKey("tenants.id")' in job_models
    assert 'ForeignKey("tenants.slug")' not in edital_models
    assert 'ForeignKey("tenants.slug")' not in job_models


def test_migration_validates_conversion_and_forces_rls():
    migration = (
        ROOT / "backend/alembic/versions/20260921_01_canonical_tenant_ids_and_rls.py"
    ).read_text(encoding="utf-8")

    assert "tenant_id_v2 = tenants.id" in migration
    assert "jsonb_set" in migration
    assert "_assert_complete" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "current_setting('app.current_tenant_id', true)" in migration


def test_authenticated_dependency_sets_rls_context():
    dependency = (ROOT / "backend/app/auth/dependencies.py").read_text(encoding="utf-8")

    assert "set_tenant_context(db, user.tenant_id)" in dependency
