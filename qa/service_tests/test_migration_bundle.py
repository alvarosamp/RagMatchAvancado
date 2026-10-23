import json
from datetime import datetime, timezone

from openpyxl import load_workbook
import pytest
from sqlalchemy import create_engine, text

from app.services import migration_bundle as bundle


@pytest.fixture
def audit_database(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users(id integer,name text,hashed_password text)"))
        connection.execute(text("INSERT INTO users VALUES(1,'QA user','secret-hash-must-not-be-exported')"))
        connection.execute(text("CREATE TABLE crm_notices(id integer,title text)"))
        connection.execute(text("INSERT INTO crm_notices VALUES(1,'QA notice')"))
    monkeypatch.setattr(bundle, "engine", engine)
    yield engine
    engine.dispose()


def fake_dump(command, **kwargs):
    from pathlib import Path
    if command[0] == "pg_dump":
        assert "--no-owner" in command and "--no-privileges" in command
        Path(command[command.index("--file")+1]).write_bytes(b"PGDMP synthetic test archive")
    else:
        assert command[0] == "pg_restore" and "--clean" in command and "--if-exists" in command


def test_bundle_inventory_redacts_credentials_and_audit_excludes_passwords(audit_database, monkeypatch, tmp_path):
    monkeypatch.setattr(bundle.subprocess, "run", fake_dump)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://qa:private@localhost/ragmatch_quality")
    monkeypatch.setenv("MIGRATION_FILE_ROOTS", str(tmp_path / "documents") + "," + str(tmp_path / "missing"))
    documents = tmp_path / "documents"
    documents.mkdir()
    (documents / "qa.txt").write_text("QA bytes")
    (documents / "backups").mkdir()
    (documents / "backups/private.txt").write_text("excluded")
    manifest = bundle.create_bundle(tmp_path / "bundle")
    assert "private" not in manifest["database_url_redacted"]
    assert manifest["table_counts"] == {"crm_notices": 1, "users": 1}
    assert manifest["copied_file_count"] == 1
    assert bundle.validate_bundle(tmp_path / "bundle", compare_database=True)["database_matches"]
    workbook = load_workbook(tmp_path / "bundle/auditoria.xlsx")
    assert "hashed_password" not in [cell.value for row in workbook["users"] for cell in row]
    assert "secret-hash-must-not-be-exported" not in str(list(workbook["users"].values))
    (tmp_path / "bundle/files/documents/qa.txt").write_text("tampered")
    report = bundle.validate_bundle(tmp_path / "bundle")
    assert not report["valid"] and "Hash divergente" in report["failures"][0]
    with pytest.raises(ValueError, match="Pacote invalido"):
        bundle.restore_bundle(tmp_path / "bundle", confirm_restore=True)


def test_bundle_missing_files_and_schema_versions_are_rejected(audit_database, monkeypatch, tmp_path):
    monkeypatch.setattr(bundle.subprocess, "run", fake_dump)
    monkeypatch.setenv("DATABASE_URL", "postgresql://qa@localhost/ragmatch_quality")
    with pytest.raises(ValueError, match="manifest"):
        bundle.validate_bundle(tmp_path)
    manifest = bundle.create_bundle(tmp_path / "bundle", include_files=False)
    manifest["bundle_version"] = 999
    (tmp_path / "bundle/manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Versao"):
        bundle.validate_bundle(tmp_path / "bundle")
    manifest["bundle_version"] = 1
    (tmp_path / "bundle/manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "bundle/database.dump").unlink()
    with pytest.raises(ValueError, match="database.dump"):
        bundle.validate_bundle(tmp_path / "bundle")
    with pytest.raises(ValueError, match="destino nao esta vazio"):
        bundle.create_bundle(tmp_path / "bundle")
    with pytest.raises(ValueError, match="bloqueada"):
        bundle.restore_bundle(tmp_path, confirm_restore=False)


def test_restore_uses_verified_archive_and_checks_restored_counts(audit_database, monkeypatch, tmp_path):
    monkeypatch.setattr(bundle.subprocess, "run", fake_dump)
    monkeypatch.setenv("DATABASE_URL", "postgresql://qa@localhost/ragmatch_quality")
    bundle.create_bundle(tmp_path / "bundle", include_files=False)
    assert bundle.restore_bundle(tmp_path / "bundle", confirm_restore=True, restore_files=False) == {
        "restored_files": 0, "restored_objects": 0, "database_matches": True}
    with audit_database.begin() as connection:
        connection.execute(text("INSERT INTO users VALUES(2,'New user','private')"))
    assert not bundle.validate_bundle(tmp_path / "bundle", compare_database=True)["database_matches"]


def test_object_storage_bundle_round_trip_uses_exact_keys_and_bytes(monkeypatch, tmp_path):
    from app.services import object_storage
    monkeypatch.setattr(bundle, "object_storage_enabled", lambda: True)
    monkeypatch.setattr(object_storage, "list_objects", lambda: [{"key": "tenant_1/qa.pdf"}])
    monkeypatch.setattr(bundle, "get_bytes", lambda key: b"QA object")
    writes = {}
    monkeypatch.setattr(bundle, "put_bytes", lambda key, data, **kwargs: writes.update({key: data}))
    assert bundle._export_object_storage(tmp_path / "objects") == ["tenant_1/qa.pdf"]
    assert bundle._restore_object_storage(tmp_path / "objects") == 1
    assert writes == {"tenant_1/qa.pdf": b"QA object"}
    assert bundle._restore_file_roots(tmp_path / "missing") == 0


def test_audit_preserves_json_and_timezone_without_excel_type_errors():
    assert bundle._xlsx_value({"QA": [1, 2]}) == '{"QA": [1, 2]}'
    assert bundle._xlsx_value(datetime(2026, 1, 1, tzinfo=timezone.utc)).tzinfo is None
    assert bundle._pg_cli_url("postgresql+psycopg2://qa/db") == "postgresql://qa/db"
