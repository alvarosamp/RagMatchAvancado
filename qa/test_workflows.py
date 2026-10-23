import json

import pytest


@pytest.fixture
def notice(api, unique):
    response = api.post("/crm/query/notices/insert", json={"values": {"number": f"FLOW-{unique}", "title": "QA ciclo comercial", "auction_date": "2026-12-31T10:00:00"}})
    assert response.status_code == 200, response.text
    return response.json()["data"][0]


def reread(api, notice):
    return api.get("/crm/query/notices", params={"filters": json.dumps([{"column": "id", "op": "eq", "value": notice["id"]}])}).json()["data"][0]


def test_suspend_and_resume_creates_new_session_and_audit_history(api, notice):
    path = f"/crm/notices/{notice['id']}"
    assert api.post(path + "/suspend", json={"reason": "QA recurso"}).status_code == 200
    response = api.post(path + "/resume", json={"reason": "QA retomada", "scheduled_at": "2026-12-31T13:00:00Z"})
    assert response.status_code == 200, response.text
    saved = reread(api, notice)
    assert len(saved["notice_sessions"]) == 2
    assert saved["auction_date"].startswith("2026-12-31T10:00:00")
    history = api.get("/crm/query/notice_history", params={"filters": json.dumps([{"column": "notice_id", "op": "eq", "value": notice["id"]}])}).json()["data"]
    assert any("suspenso" in row["action"] for row in history)
    assert any("retomado" in row["action"] for row in history)


@pytest.mark.parametrize("operation,payload", [
    ("suspend", {}), ("resume", {"reason": "QA"}),
    ("resume", {"reason": "QA", "scheduled_at": "invalid"}),
    ("reopen", {}), ("close", {"outcome": "invalid"}),
])
def test_invalid_workflow_transition_cannot_mutate_record(api, notice, operation, payload):
    before = reread(api, notice)
    response = api.post(f"/crm/notices/{notice['id']}/{operation}", json=payload)
    assert response.status_code in {400, 409, 422}, response.text
    after = reread(api, notice)
    assert after["stage"] == before["stage"] and after["outcome"] == before["outcome"]


def test_cancel_reopen_and_wrong_stage_close_are_enforced(api, notice):
    path = f"/crm/notices/{notice['id']}"
    assert api.post(path+"/close", json={"outcome": "won", "reason": "QA"}).status_code == 409
    response = api.post(path+"/close", json={"outcome": "cancelled", "reason": "QA cancelamento"})
    assert response.status_code == 200, response.text
    assert reread(api, notice)["outcome"] == "cancelled"
    response = api.post(path+"/reopen", json={"reason": "QA reabertura"})
    assert response.status_code == 200, response.text
    saved = reread(api, notice)
    assert saved["outcome"] == "pending" and saved["post_auction_phase"] == "homologation"


@pytest.mark.parametrize("operation", ["advance", "suspend", "resume", "close", "reopen"])
def test_foreign_tenant_cannot_mutate_workflow(api, seed, operation):
    foreign = seed["tenants"]["beta"]["notice_id"]
    response = api.post(f"/crm/notices/{foreign}/{operation}", json={"reason": "QA", "scheduled_at": "2026-12-31T10:00:00", "outcome": "cancelled"})
    assert response.status_code == 404, response.text


def test_calendar_exports_real_notice_as_valid_ics(api, seed):
    notice_id = seed["tenants"]["alpha"]["notice_id"]
    response = api.get(f"/crm/notices/{notice_id}/calendar.ics")
    assert response.status_code == 200, response.text
    assert "text/calendar" in response.headers["Content-Type"]
    assert "BEGIN:VCALENDAR" in response.text and "BEGIN:VEVENT" in response.text
    assert "QA-alpha-001" in response.text


def test_match_report_csv_download_has_header_and_attachment(api):
    response = api.get("/crm/matches/attached-products/report.csv")
    assert response.status_code == 200, response.text
    assert "text/csv" in response.headers["Content-Type"]
    assert "attachment" in response.headers["Content-Disposition"]
    assert len(response.content) > 10
