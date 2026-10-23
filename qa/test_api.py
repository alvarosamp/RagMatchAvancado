"""Contracts exercised through HTTP against the production app and real DB."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest


READ_ROUTES = [
    "/auth/me", "/auth/users", "/auth/tenant/ai-features", "/crm/auth/user",
    "/crm/dashboard-data", "/crm/dashboard-summary", "/crm/summary", "/crm/notices",
    "/crm/fulfillment", "/crm/suspended-notices", "/crm/notices/reopen-recovery",
    "/crm/email-monitor/status", "/editais/", "/jobs/", "/ops/summary",
    "/reports/executive", "/analytics/overview", "/analytics/produtos",
    "/analytics/requisitos", "/analytics/evolucao", "/analytics/distribuicao",
    "/analysis/dashboard", "/analysis/editais-listagem", "/documents/files",
    "/documents/templates", "/documents/signers", "/documents/signature-requests",
    "/documents/signature-alert", "/integrations/bling/status",
    *[f"/crm/market-intelligence/{path}" for path in (
        "diagnostic", "capabilities", "report", "facts", "entities", "sync-runs",
        "operations", "identity-reviews", "aliases", "model-runs", "procurement",
        "supplier-presentations",
    )],
]
CRM_TABLES = ["organs", "portals", "catalog_products", "notices", "notice_products",
              "notice_documents", "notice_sessions", "notice_item_results", "notice_history",
              "notice_competitors", "checklist_templates", "checklist_template_items",
              "notice_product_matches", "post_auction_transitions", "profiles", "user_roles"]


@pytest.mark.parametrize("path", READ_ROUTES)
def test_authenticated_read_contract_returns_json_not_server_error(api, path):
    response = api.get(path)
    assert response.status_code == 200, f"{path}: {response.text}"
    assert isinstance(response.json(), (dict, list))
    assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("path", READ_ROUTES)
def test_protected_api_requires_authentication(anonymous, path):
    response = anonymous.get(path)
    assert response.status_code == 401, f"{path}: {response.text}"
    assert "Bearer" in response.headers["WWW-Authenticate"]


@pytest.mark.parametrize("table", CRM_TABLES)
def test_crm_queries_return_only_current_tenant(api, table, seed):
    response = api.get(f"/crm/query/{table}")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert isinstance(data, list)
    for row in data:
        if "tenant_id" in row:
            assert row["tenant_id"] == seed["tenants"]["alpha"]["id"]
    assert "QA-beta-001" not in response.text
    assert "beta-admin@example.com" not in response.text


@pytest.mark.parametrize("tenant", ["alpha", "beta", "empty"])
def test_dashboard_data_matches_seed_and_never_invents_missing_data(clients, seed, tenant):
    response = clients(tenant).get("/crm/dashboard-data")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["tenant_name"] == f"Empresa QA {tenant.title()}"
    assert data["errors"] == []
    expected = seed["tenants"][tenant].get("notice_id")
    if expected:
        assert expected in [row["id"] for row in data["notices"]]
        assert data["analyzed_points"] == 1
        assert data["products"][0]["quantity"] == 3
    else:
        assert data["notices"] == []
        assert data["analyzed_points"] == 0


@pytest.mark.parametrize("status", ["pending", "running", "done", "failed"])
def test_job_lifecycle_data_and_filters(api, seed, status):
    job_id = seed["tenants"]["alpha"]["jobs"][status]
    response = api.get(f"/jobs/{job_id}")
    assert response.status_code == 200, response.text
    job = response.json()
    assert job["status"] == status
    if status == "done":
        assert job["progress"] == 1
        assert job["result"]["edital_id"] == seed["tenants"]["alpha"]["edital_id"]
    if status == "failed":
        assert job["error_message"] == "Erro QA controlado"
    response = api.get("/jobs/", params={"status": status})
    assert response.status_code == 200
    assert all(row["status"] == status for row in response.json())


@pytest.mark.parametrize("resource", ["jobs", "editais"])
def test_foreign_tenant_resources_are_not_disclosed(api, seed, resource):
    foreign_id = seed["tenants"]["beta"]["jobs"]["done"] if resource == "jobs" else seed["tenants"]["beta"]["edital_id"]
    response = api.get(f"/{resource}/{foreign_id}" + ("/results" if resource == "editais" else ""))
    assert response.status_code == 404, response.text


@pytest.mark.parametrize("table,payload", [
    ("organs", {"name": "OrgÃƒÂ£o CRUD QA", "city": "SÃƒÂ£o Paulo", "state": "SP"}),
    ("portals", {"name": "Portal CRUD QA", "url": "https://example.com"}),
    ("catalog_products", {"name": "Produto CRUD QA", "cost": 100, "tax_percent": 10, "margin_percent": 20}),
    ("notices", {"number": "CRUD", "title": "AquisiÃƒÂ§ÃƒÂ£o CRUD QA", "auction_date": "2026-12-31T10:00:00"}),
])
def test_crud_persists_updates_and_deletes_with_tenant_ownership(api, clients, seed, unique, table, payload):
    payload = dict(payload)
    payload["name" if "name" in payload else "number"] += unique
    payload["tenant_id"] = seed["tenants"]["beta"]["id"]
    response = api.post(f"/crm/query/{table}/insert", json={"values": payload})
    assert response.status_code == 200, response.text
    row = response.json()["data"][0]
    assert row["tenant_id"] == seed["tenants"]["alpha"]["id"]
    filters = [{"op": "eq", "column": "id", "value": row["id"]}]
    assert clients("beta").get(f"/crm/query/{table}", params={"filters": json.dumps(filters)}).json()["data"] == []
    field = "title" if table == "notices" else "name"
    updated = api.patch(f"/crm/query/{table}", json={"values": {field: "Atualizado QA"}, "filters": filters})
    assert updated.status_code == 200, updated.text
    reread = api.get(f"/crm/query/{table}", params={"filters": json.dumps(filters)}).json()["data"]
    assert reread[0][field] == "Atualizado QA"
    blocked = clients("beta").patch(f"/crm/query/{table}", json={"values": {field: "Ataque QA"}, "filters": filters})
    assert blocked.status_code == 200 and blocked.json()["data"] == []
    deleted = api.request("DELETE", f"/crm/query/{table}", json={"filters": filters})
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] == 1
    assert api.get(f"/crm/query/{table}", params={"filters": json.dumps(filters)}).json()["data"] == []


@pytest.mark.parametrize("table", ["organs", "portals", "catalog_products", "notices"])
@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
def test_viewer_cannot_write_any_crm_resource(clients, table, method):
    suffix = "/insert" if method == "POST" else ""
    response = clients(role="viewer").request(method, f"/crm/query/{table}{suffix}", json={"values": {"name": "Forbidden"}, "filters": []})
    assert response.status_code == 403, response.text


def test_duplicate_notice_returns_conflict_and_next_query_still_works(api, seed):
    response = api.post("/crm/query/notices/insert", json={"values": {"number": "QA-alpha-001", "title": "Duplicate"}})
    assert response.status_code == 409, response.text
    assert api.get("/crm/dashboard-data").json()["errors"] == []


@pytest.mark.parametrize("params", [
    {"limit": 1}, {"head": "true"},
    {"filters": json.dumps([{"op": "in", "column": "name", "value": ["Prefeitura QA alpha"]}])},
    {"orders": json.dumps([{"column": "name", "ascending": False}])},
])
def test_query_pagination_count_filter_and_order(api, params):
    response = api.get("/crm/query/organs", params=params)
    assert response.status_code == 200, response.text
    if params.get("head"):
        assert response.json()["data"] is None and response.json()["count"] >= 1
    else:
        assert len(response.json()["data"]) >= 1
        if "limit" in params:
            assert len(response.json()["data"]) == 1


@pytest.mark.parametrize("params", [{"filters": "{"}, {"orders": "{"}, {"limit": 0}])
def test_malformed_query_is_client_error(api, params):
    response = api.get("/crm/query/notices", params=params)
    assert response.status_code in {400, 422}, response.text


def test_unknown_table_returns_404(api):
    assert api.get("/crm/query/pg_authid").status_code == 404


def test_dashboard_partial_database_failure_is_explicit_and_other_sections_recover(api, admin_db):
    # Actual PostgreSQL permission failure must be contained by a savepoint.
    with admin_db.cursor() as cursor:
        cursor.execute("REVOKE SELECT ON crm_notice_documents FROM ragmatch_quality")
    admin_db.commit()
    try:
        response = api.get("/crm/dashboard-data")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["errors"] == ["documents"]
        assert data["pending_documents"] is None
        assert data["notices"] and data["products"]
        assert data["analyzed_points"] >= 1
    finally:
        with admin_db.cursor() as cursor:
            cursor.execute("GRANT SELECT ON crm_notice_documents TO ragmatch_quality")
        admin_db.commit()
    assert api.get("/crm/dashboard-data").json()["errors"] == []


def test_parallel_reads_bootstrap_only_one_default_checklist(clients, seed, admin_db):
    def read(_):
        client = clients("empty")
        response = client.get("/crm/query/checklist_templates")
        assert response.status_code == 200, response.text
        return [row["id"] for row in response.json()["data"] if row["is_default"]]
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(read, range(5)))
    assert all(len(rows) == 1 for rows in results)
    assert len({rows[0] for rows in results}) == 1
    with admin_db.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM crm_checklist_templates WHERE tenant_id=%s AND is_default", (seed["tenants"]["empty"]["id"],))
        assert cursor.fetchone()[0] == 1
