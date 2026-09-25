"""The email monitor must never query CRM notices without tenant context."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock, patch

MODULE_PATH = Path(__file__).resolve().parents[2] / "backend/app/services/email_monitor.py"
SPEC = importlib.util.spec_from_file_location("email_monitor_under_test", MODULE_PATH)
email_monitor = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
session_stub = ModuleType("app.db.session")
session_stub.SessionLocal = MagicMock()
session_stub.set_tenant_context = MagicMock()
with patch.dict(sys.modules, {"app.db.session": session_stub}):
    SPEC.loader.exec_module(email_monitor)


class FakeImap:
    stored: ClassVar[list[tuple[bytes, str, str]]] = []
    fetched_with: ClassVar[list[str]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def select(self, _):
        return "OK", []

    def search(self, *_):
        return "OK", [b"1"]

    def fetch(self, _, query):
        self.fetched_with.append(query)
        return "OK", [(b"RFC822", b"Subject: Pregao 123\r\n\r\nResultado")]

    def store(self, message_id, operation, flag):
        self.stored.append((message_id, operation, flag))
        return "OK", []


def _configure(monkeypatch):
    FakeImap.stored = []
    FakeImap.fetched_with = []
    monkeypatch.setenv("EMAIL_MONITOR_IMAP_HOST", "imap.example.test")
    monkeypatch.setenv("EMAIL_MONITOR_USER", "monitor@example.test")
    monkeypatch.setenv("EMAIL_MONITOR_PASSWORD", "secret")
    monkeypatch.setattr(email_monitor, "_connect_imap", FakeImap)


def test_manual_monitor_only_uses_authenticated_tenant(monkeypatch):
    _configure(monkeypatch)
    db = MagicMock()
    db.info = {"tenant_id": 101}
    notice = SimpleNamespace(tenant_id=101)
    contexts = []
    monkeypatch.setattr(email_monitor, "set_tenant_context", lambda _, tenant_id: contexts.append(tenant_id))
    monkeypatch.setattr(email_monitor, "_load_candidate_notices", lambda _: [notice])
    monkeypatch.setattr(email_monitor, "_match_message_to_notice", lambda *_: notice)
    monkeypatch.setattr(email_monitor, "_record_message", lambda *_: None)

    result = email_monitor.run_email_monitor_once(db)

    assert result == {"configured": True, "processed": 1, "matched": 1}
    assert contexts == [101]
    db.query.assert_not_called()
    db.commit.assert_called_once()
    assert FakeImap.fetched_with == ["(BODY.PEEK[])"]
    assert FakeImap.stored == []


def test_scheduler_sets_context_before_each_tenant_query(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(email_monitor, "Tenant", SimpleNamespace(is_active=SimpleNamespace(is_=lambda _: True)))
    db = MagicMock()
    db.info = {}
    db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(id=101), SimpleNamespace(id=102)]
    queried_under = []
    recorded_under = []

    def set_context(_, tenant_id):
        db.info["tenant_id"] = tenant_id

    def load_notices(_):
        queried_under.append(db.info["tenant_id"])
        return [SimpleNamespace(tenant_id=db.info["tenant_id"])]

    def record(_, notice, msg):
        recorded_under.append((db.info["tenant_id"], notice.tenant_id))

    monkeypatch.setattr(email_monitor, "set_tenant_context", set_context)
    monkeypatch.setattr(email_monitor, "_load_candidate_notices", load_notices)
    monkeypatch.setattr(email_monitor, "_match_message_to_notice", lambda _, __, notices: notices[0])
    monkeypatch.setattr(email_monitor, "_record_message", record)

    result = email_monitor.run_email_monitor_once(db)

    assert result == {"configured": True, "processed": 1, "matched": 2}
    assert queried_under == [101, 102]
    assert recorded_under == [(101, 101), (102, 102)]
    assert db.commit.call_count == 2
    assert FakeImap.stored == [(b"1", "+FLAGS", "\\Seen")]


def test_scheduler_does_not_consume_messages_without_active_tenants(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(email_monitor, "Tenant", SimpleNamespace(is_active=SimpleNamespace(is_=lambda _: True)))
    db = MagicMock()
    db.info = {}
    db.query.return_value.filter.return_value.all.return_value = []

    result = email_monitor.run_email_monitor_once(db)

    assert result["processed"] == 1
    assert FakeImap.stored == []
