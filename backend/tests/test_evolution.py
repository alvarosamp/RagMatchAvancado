"""Real SQLite + HTTP tests; run separately from root tests' SQLAlchemy stubs.

PYTHONPATH=backend pytest backend/tests/test_evolution.py -q
"""
import os
from datetime import timedelta
from unittest.mock import Mock

os.environ.setdefault("DATABASE_URL", "sqlite:////private/tmp/ragmatch-whatsapp-test-unused.db")
os.environ.setdefault("SECRET_KEY", "whatsapp-test-secret-only")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.jobs.models  # Register User/Tenant relationships.
from app.auth.models import Tenant, User
from app.crm.models import CrmNotice
from app.db.models import Base
from app.integrations.evolution import client, service
from app.integrations.evolution.models import WhatsAppContact, WhatsAppDelivery
from app.integrations.evolution import router as routes


@pytest.fixture
def setup(monkeypatch):
    for key, value in {
        "EVOLUTION_ENABLED": "1", "EVOLUTION_BASE_URL": "http://evolution:8080",
        "EVOLUTION_API_KEY": "test-api-key", "EVOLUTION_INSTANCE": "test",
        "EVOLUTION_WEBHOOK_SECRET": "test-webhook-secret", "EVOLUTION_BOT_PHONE": "5511999990000",
        "EVOLUTION_DIGEST_HOUR": "0",
    }.items():
        monkeypatch.setenv(key, value)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    tables = [Tenant.__table__, User.__table__, CrmNotice.__table__,
              WhatsAppContact.__table__, WhatsAppDelivery.__table__]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as db:
        db.add_all([Tenant(id=1, name="Empresa A"), Tenant(id=2, name="Empresa B")])
        db.flush()
        db.add_all([User(id=1, tenant_id=1, email="a@test", hashed_password="x"),
                    User(id=2, tenant_id=2, email="b@test", hashed_password="x")])
        db.add_all([CrmNotice(id="a", tenant_id=1, number="A-001", title="Edital da A"),
                    CrmNotice(id="b", tenant_id=2, number="B-SECRET", title="Dado da B"),
                    CrmNotice(id="c", tenant_id=1, number="A-002", title="Sessão futura",
                              auction_date=service.utcnow().astimezone(service.LOCAL_TZ).replace(tzinfo=None) + timedelta(days=1))])
        db.commit()
        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[routes.get_db] = lambda: db
        app.dependency_overrides[routes.get_current_user] = lambda: db.get(User, 1)
        sender = Mock()
        monkeypatch.setattr(service, "send_text", sender)
        monkeypatch.setattr(routes, "send_text", sender)
        with TestClient(app) as http:
            yield db, http, sender
    engine.dispose()


def event(text="RESUMO", phone="5511999991111", id="m1", **changes):
    payload = {"event": "messages.upsert", "instance": "test", "data": {
        "key": {"remoteJid": f"{phone}@s.whatsapp.net", "fromMe": False, "id": id},
        "message": {"conversation": text}, "messageTimestamp": int(service.utcnow().timestamp()),
    }}
    payload.update(changes)
    return payload


def post(http, payload):
    return http.post("/integrations/whatsapp/webhook", json=payload,
                     headers={"x-webhook-secret": "test-webhook-secret"})


def bind(db, http):
    link = http.post("/integrations/whatsapp/link").json()
    assert link["url"].startswith("https://wa.me/5511999990000?")
    assert post(http, event(link["message"])).json()["status"] == "processed"
    contact = db.get(WhatsAppContact, 1)
    contact.last_request_at = None
    db.commit()
    return contact


def test_link_commands_and_tenant_isolation(setup):
    db, http, sender = setup
    bind(db, http)
    assert http.get("/integrations/whatsapp/me").json()["linked"] is True
    for index, text in enumerate(["RESUMO", "EDITAIS", "PRAZOS"]):
        assert post(http, event(text, id=f"query{index}")).json()["status"] == "processed"
        answer = sender.call_args.args[1]
        assert "Empresa A" in answer
        assert "Empresa B" not in answer and "B-SECRET" not in answer
        db.get(WhatsAppContact, 1).last_request_at = None
        db.commit()
    assert "A-002" in sender.call_args.args[1]


def test_forged_unknown_group_self_stale_and_wrong_instance_events(setup):
    db, http, sender = setup
    bind(db, http)
    sender.reset_mock()
    assert http.post("/integrations/whatsapp/webhook", json=event()).status_code == 401
    payloads = [event(phone="5511999992222"), event(instance="other"), event(event="messages.set")]
    for field, value in [("remoteJid", "123@g.us"), ("remoteJid", "123@lid"), ("fromMe", True)]:
        payload = event()
        payload["data"]["key"][field] = value
        payloads.append(payload)
    stale = event()
    stale["data"]["messageTimestamp"] = 1
    payloads.append(stale)
    for payload in payloads:
        assert post(http, payload).json()["status"] == "ignored"
    sender.assert_not_called()


def test_link_token_expiry_one_time_and_replacement(setup):
    db, http, sender = setup
    old = http.post("/integrations/whatsapp/link").json()["message"]
    new = http.post("/integrations/whatsapp/link").json()["message"]
    assert post(http, event(old)).json()["status"] == "ignored"
    db.get(WhatsAppContact, 1).token_expires_at = service.utcnow() - timedelta(seconds=1)
    db.commit()
    assert post(http, event(new)).json()["status"] == "ignored"
    bind(db, http)
    assert db.get(WhatsAppContact, 1).token_hash is None


def test_lid_requires_explicit_alternate_phone_and_malformed_event_is_ignored(setup):
    db, http, sender = setup
    bind(db, http)
    payload = event(id="lid")
    payload["data"]["key"].update(remoteJid="123456789@lid", remoteJidAlt="5511999991111@s.whatsapp.net")
    assert post(http, payload).json()["status"] == "processed"
    group = event(id="group")
    group["data"]["key"].update(remoteJid="123@g.us", remoteJidAlt="5511999991111@s.whatsapp.net")
    assert post(http, group).json()["status"] == "ignored"
    assert post(http, event(event=123)).json()["status"] == "ignored"


def test_duplicate_events_and_daily_opt_in(setup):
    db, http, sender = setup
    contact = bind(db, http)
    sender.reset_mock()
    assert service.send_daily_summaries(db) == 0
    assert http.patch("/integrations/whatsapp/me", json={"notifications_enabled": True}).status_code == 200
    assert service.send_daily_summaries(db) == 1
    assert service.send_daily_summaries(db) == 0
    assert sender.call_count == 1
    sender.reset_mock()
    assert post(http, event("EDITAIS", id="unique")).json()["status"] == "processed"
    contact.last_request_at = None
    db.commit()
    assert post(http, event("EDITAIS", id="unique")).json()["status"] == "duplicate"
    assert sender.call_count == 1
    assert post(http, event("PARAR", id="stop")).json()["status"] == "processed"
    assert not contact.notifications_enabled


@pytest.mark.parametrize("revocation", ["user", "tenant", "password", "move"])
def test_revoked_accounts_cannot_consult_or_receive_notifications(setup, revocation):
    db, http, sender = setup
    contact = bind(db, http)
    contact.notifications_enabled = True
    user = db.get(User, 1)
    if revocation == "user": user.is_active = False
    elif revocation == "tenant": user.tenant.is_active = False
    elif revocation == "password": user.auth_version += 1
    else: user.tenant_id = 2
    db.commit()
    sender.reset_mock()
    assert post(http, event(id="revoked")).json()["status"] == "ignored"
    assert service.send_daily_summaries(db) == 0
    sender.assert_not_called()


def test_network_failure_is_not_retried_and_unlink_revokes(setup):
    db, http, sender = setup
    contact = bind(db, http)
    sender.side_effect = client.EvolutionUnavailable("unavailable")
    assert post(http, event(id="failure")).json()["status"] == "send_failed"
    contact.last_request_at = None
    db.commit()
    assert post(http, event(id="failure")).json()["status"] == "duplicate"
    assert http.delete("/integrations/whatsapp/me").status_code == 200
    assert post(http, event(id="after-unlink")).json()["status"] == "ignored"


def test_disabled_integration_and_test_rate_limit(setup, monkeypatch):
    db, http, sender = setup
    bind(db, http)
    assert http.post("/integrations/whatsapp/test").status_code == 200
    assert http.post("/integrations/whatsapp/test").status_code == 429
    monkeypatch.setenv("EVOLUTION_ENABLED", "0")
    assert http.post("/integrations/whatsapp/link").status_code == 503
    assert post(http, event()).status_code == 503


def test_client_contract_and_secret_redaction(setup, monkeypatch):
    import httpx
    captured = []
    real_client = httpx.Client
    def handler(request):
        captured.append(request)
        return httpx.Response(201, json={"key": {"id": "out"}})
    monkeypatch.setattr(client.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    client.send_text("5511999991111", "Teste")
    assert captured[0].url.path == "/message/sendText/test"
    assert captured[0].headers["apikey"] == "test-api-key"
    assert b'"text":"Teste"' in captured[0].content
    def failed(request):
        return httpx.Response(500, text="secret upstream response")
    monkeypatch.setattr(client.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(failed), **kwargs))
    with pytest.raises(client.EvolutionUnavailable, match="Não foi possível") as exc:
        client.send_text("5511999991111", "Teste")
    assert "secret" not in str(exc.value)


def test_migration_creates_and_removes_identity_tables():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect

    path = Path(__file__).parents[1] / "alembic/versions/20261028_01_whatsapp.py"
    spec = importlib.util.spec_from_file_location("whatsapp_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        Base.metadata.create_all(connection, tables=[Tenant.__table__, User.__table__])
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert {"whatsapp_contacts", "whatsapp_deliveries"}.issubset(inspect(connection).get_table_names())
            columns = {c["name"] for c in inspect(connection).get_columns("whatsapp_contacts")}
            assert columns == set(WhatsAppContact.__table__.columns.keys())
            migration.downgrade()
            assert "whatsapp_contacts" not in inspect(connection).get_table_names()
    engine.dispose()
