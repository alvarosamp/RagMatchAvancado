"""Fresh operational snapshot must be stamped before analytical upgrade."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def migration_runner(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "market_bootstrap_test",
        Path(__file__).resolve().parents[2] / "backend/scripts/migrate_database.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    monkeypatch.setattr(module, "Config", lambda _: "config")
    monkeypatch.setattr(
        module,
        "require_explicit_empty_database_bootstrap",
        lambda: calls.append("authorize"),
    )
    monkeypatch.setattr(
        module, "_bootstrap_empty_database", lambda _: calls.append("snapshot")
    )
    monkeypatch.setattr(module.command, "upgrade", lambda *_: calls.append("upgrade"))
    return module, calls


def configure(module, monkeypatch, head, tables):
    monkeypatch.setattr(
        module, "inspect", lambda _: SimpleNamespace(get_table_names=lambda **_: tables)
    )
    monkeypatch.setattr(
        module.ScriptDirectory,
        "from_config",
        lambda _: SimpleNamespace(get_current_head=lambda: head),
    )


def test_fresh_database_applies_analytical_upgrade_after_snapshot(
    migration_runner, monkeypatch
):
    module, calls = migration_runner
    configure(module, monkeypatch, "20261009_01", [])
    module.main()
    assert calls == ["authorize", "snapshot", "upgrade"]


def test_fresh_database_rejects_unvalidated_future_head(migration_runner, monkeypatch):
    module, calls = migration_runner
    configure(module, monkeypatch, "future_unknown", [])
    with pytest.raises(RuntimeError, match="Atualize e valide"):
        module.main()
    assert calls == ["authorize"]


def test_existing_database_only_runs_migrations(migration_runner, monkeypatch):
    module, calls = migration_runner
    configure(module, monkeypatch, "20261009_01", ["tenants"])
    module.main()
    assert calls == ["upgrade"]
