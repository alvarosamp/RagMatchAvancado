import hashlib
from datetime import datetime, timedelta, timezone

from jose import jwt
import pytest

from conftest import Api


def test_login_issues_httponly_cookie_without_exposing_token(anonymous, seed):
    response = anonymous.post("/auth/login", json={"email": "alpha-admin@example.com", "password": seed["password"]})
    assert response.status_code == 200, response.text
    assert response.json()["access_token"] == ""
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert anonymous.get("/auth/me").json()["email"] == "alpha-admin@example.com"
    assert "hashed_password" not in anonymous.get("/auth/me").text
    assert anonymous.post("/auth/logout").status_code == 200
    assert anonymous.get("/auth/me").status_code == 401


@pytest.mark.parametrize("credentials", [
    {"email": "missing@example.com", "password": "wrong"},
    {"email": "alpha-admin@example.com", "password": "wrong"},
])
def test_login_does_not_disclose_account_existence(anonymous, credentials):
    response = anonymous.post("/auth/login", json=credentials)
    assert response.status_code == 401
    assert response.json()["detail"] == "Email ou senha incorretos."


@pytest.mark.parametrize("payload", [{}, {"email": "bad-email", "password": "x"}, {"email": "alpha-admin@example.com"}])
def test_login_rejects_invalid_input(anonymous, payload):
    assert anonymous.post("/auth/login", json=payload).status_code == 422


def test_login_account_rate_limit_is_enforced_by_real_redis(anonymous, unique):
    payload = {"email": f"qa-rate-{unique}@example.com", "password": "wrong"}
    for _ in range(10):
        assert anonymous.post("/auth/login", json=payload).status_code == 401
    assert anonymous.post("/auth/login", json=payload).status_code == 429


@pytest.mark.parametrize("token", ["invalid", "a.b.c", "", "null"])
def test_invalid_bearer_token_returns_401(anonymous, token):
    assert anonymous.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("claims", [
    {"user_id": "invalid"}, {"user_id": {}}, {"auth_version": "invalid"},
    {"user_id": True}, {"user_id": 0}, {"user_id": -1}, {"user_id": 1.5},
    {"auth_version": 999}, {"user_id": 99999999},
    {"exp": datetime.now(timezone.utc)-timedelta(days=1)},
])
def test_signed_but_invalid_claims_fail_closed(anonymous, seed, claims):
    payload = {"sub": "alpha-admin@example.com", "user_id": seed["tenants"]["alpha"]["users"]["admin"]["id"],
               "auth_version": 0, "exp": datetime.now(timezone.utc)+timedelta(minutes=5), **claims}
    token = jwt.encode(payload, "quality-only-signing-key-never-use-in-production", algorithm="HS256")
    response = anonymous.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401, response.text


def test_legacy_email_only_jwt_still_authenticates_existing_user(anonymous):
    token = jwt.encode({"sub": "alpha-admin@example.com", "auth_version": 0,
                        "exp": datetime.now(timezone.utc)+timedelta(minutes=5)},
                       "quality-only-signing-key-never-use-in-production", algorithm="HS256")
    response = anonymous.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200 and response.json()["email"] == "alpha-admin@example.com"


@pytest.mark.parametrize("entity", ["user", "tenant"])
def test_existing_session_cannot_access_deactivated_account_or_company(clients, admin_db, seed, entity):
    user = seed["tenants"]["beta"]["users"]["editor"]
    table, identifier = ("users", user["id"]) if entity == "user" else ("tenants", seed["tenants"]["beta"]["id"])
    from psycopg2 import sql
    query = sql.SQL("UPDATE {} SET is_active=%s WHERE id=%s").format(sql.Identifier(table))
    with admin_db.cursor() as cursor:
        cursor.execute(query, (False, identifier))
    admin_db.commit()
    try:
        for path in ("/auth/me", "/crm/dashboard-data", "/documents/files"):
            assert clients("beta", "editor").get(path).status_code == 403
    finally:
        with admin_db.cursor() as cursor:
            cursor.execute(query, (True, identifier))
        admin_db.commit()


@pytest.mark.parametrize("role", ["editor", "viewer"])
@pytest.mark.parametrize("path", ["/auth/users", "/auth/tenant/ai-features"])
def test_non_admin_cannot_access_admin_endpoints(clients, role, path):
    assert clients(role=role).get(path).status_code == 403


@pytest.fixture
def new_user(api, unique, seed):
    payload = {"email": f"qa-{unique}@example.com", "password": seed["password"],
               "full_name": "QA Novo Usuário", "cpf": "529.982.247-25", "phone": "(11) 99999-8888", "role": "viewer"}
    response = api.post("/auth/users", json=payload)
    assert response.status_code == 201, response.text
    return {**payload, **response.json()}


def test_admin_creates_user_and_duplicate_is_conflict(api, new_user, seed, admin_db):
    assert new_user["tenant"]["slug"] == "qa-alpha"
    assert new_user["cpf"] == "52998224725"
    assert "hashed_password" not in new_user
    payload = {key: new_user[key] for key in ("email", "password", "full_name", "cpf", "phone", "role")}
    assert api.post("/auth/users", json=payload).status_code == 409
    with admin_db.cursor() as cursor:
        cursor.execute("SELECT hashed_password, tenant_id FROM users WHERE id=%s", (new_user["id"],))
        hashed, tenant_id = cursor.fetchone()
        assert hashed.startswith("$2") and hashed != seed["password"]
        assert tenant_id == seed["tenants"]["alpha"]["id"]


@pytest.mark.parametrize("field,value", [("email", "invalid"), ("password", "short"), ("full_name", " "), ("cpf", "11111111111"), ("phone", "12"), ("role", "root")])
def test_user_creation_validation_is_field_specific(api, seed, unique, field, value):
    payload = {"email": f"{unique}@example.com", "password": seed["password"], "full_name": "QA", "cpf": "52998224725", "phone": "11999998888", "role": "viewer", field: value}
    assert api.post("/auth/users", json=payload).status_code == 422


def test_password_change_revokes_previous_sessions_and_persists_hash(api, new_user, seed, admin_db):
    client = Api()
    assert client.post("/auth/login", json={"email": new_user["email"], "password": seed["password"]}).status_code == 200
    old_cookie = dict(client.session.cookies)
    assert client.post("/auth/password/change", json={"current_password": "wrong", "new_password": "Another-Quality-2026!"}).status_code == 400
    assert client.post("/auth/password/change", json={"current_password": seed["password"], "new_password": seed["password"]}).status_code == 400
    assert client.post("/auth/password/change", json={"current_password": seed["password"], "new_password": "Another-Quality-2026!"}).status_code == 200
    assert Api(old_cookie).get("/auth/me").status_code == 401
    assert client.post("/auth/login", json={"email": new_user["email"], "password": seed["password"]}).status_code == 401
    assert client.post("/auth/login", json={"email": new_user["email"], "password": "Another-Quality-2026!"}).status_code == 200
    with admin_db.cursor() as cursor:
        cursor.execute("SELECT auth_version FROM users WHERE id=%s", (new_user["id"],))
        assert cursor.fetchone()[0] == 1


def test_last_admin_cannot_be_demoted(api, seed):
    user_id = seed["tenants"]["alpha"]["users"]["admin"]["id"]
    assert api.patch(f"/auth/users/{user_id}/role", json={"role": "viewer"}).status_code == 409


def test_role_change_is_audited_and_foreign_user_is_404(api, new_user, seed, admin_db):
    response = api.patch(f"/auth/users/{new_user['id']}/role", json={"role": "editor"})
    assert response.status_code == 200 and response.json()["role"] == "editor"
    foreign = seed["tenants"]["beta"]["users"]["viewer"]["id"]
    assert api.patch(f"/auth/users/{foreign}/role", json={"role": "admin"}).status_code == 404
    with admin_db.cursor() as cursor:
        cursor.execute("SELECT previous_role,new_role FROM user_role_audit WHERE target_user_id=%s", (new_user["id"],))
        assert cursor.fetchall() == [("viewer", "editor")]


@pytest.mark.parametrize("state", ["valid", "expired", "used", "missing"])
def test_password_reset_is_expiring_single_use_and_atomic(anonymous, new_user, admin_db, unique, state):
    token = f"quality-reset-{unique}"
    if state != "missing":
        with admin_db.cursor() as cursor:
            cursor.execute("INSERT INTO password_reset_tokens(user_id,token_hash,expires_at,used_at) VALUES (%s,%s,%s,%s)",
                           (new_user["id"], hashlib.sha256(token.encode()).hexdigest(),
                            datetime.now(timezone.utc)+timedelta(hours=-1 if state == "expired" else 1),
                            datetime.now(timezone.utc) if state == "used" else None))
        admin_db.commit()
    response = anonymous.post("/auth/password/reset/confirm", json={"token": token, "new_password": "Reset-Quality-2026!"})
    assert response.status_code == (200 if state == "valid" else 400), response.text
    if state == "valid":
        assert anonymous.post("/auth/password/reset/confirm", json={"token": token, "new_password": "Other-Quality-2026!"}).status_code == 400
        assert anonymous.post("/auth/login", json={"email": new_user["email"], "password": "Reset-Quality-2026!"}).status_code == 200


def test_public_registration_disabled_in_production(anonymous, seed):
    payload = {"tenant_slug": "qa-register", "tenant_name": "QA", "email": "registration@example.com",
               "password": seed["password"], "full_name": "QA", "cpf": "52998224725", "phone": "11999998888"}
    assert anonymous.post("/auth/register", json=payload).status_code == 403


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
def test_cross_origin_writes_are_rejected_before_database_access(api, method):
    response = api.request(method, "/crm/query/organs", json={"values": {}}, headers={"Origin": "https://evil.example.com"})
    assert response.status_code == 403


def test_untrusted_host_is_rejected(anonymous):
    assert anonymous.get("/health", headers={"Host": "evil.example.com"}).status_code == 400


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_production_does_not_expose_api_documentation(anonymous, path):
    assert anonymous.get(path).status_code == 404
