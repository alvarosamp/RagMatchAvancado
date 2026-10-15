"""Exercise the real session endpoints and PostgreSQL revocation state."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from jose import jwt
import pytest
from conftest import Api

ACCESS = os.getenv('AUTH_COOKIE_NAME', 'access_token')
REFRESH = os.getenv('AUTH_REFRESH_COOKIE_NAME', ACCESS + '_refresh')
HEADERS = {'X-Session-Refresh': '1'}


def login(client, seed, remember=False, email='alpha-admin@example.com'):
    result = client.post('/auth/login', json={'email': email, 'password': seed['password'], 'remember_me': remember})
    assert result.status_code == 200, result.text
    return result


@pytest.mark.parametrize('remember', [False, True])
def test_cookie_policy_and_absolute_deadline(anonymous, seed, admin_db, remember):
    result = login(anonymous, seed, remember)
    cookies = result.raw.headers.getlist('Set-Cookie')
    assert len(cookies) == 2
    for cookie in cookies:
        assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie
        assert ('Max-Age=' in cookie) == remember
    claims = jwt.get_unverified_claims(anonymous.session.cookies[REFRESH])
    remaining = claims['exp'] - datetime.now(timezone.utc).timestamp()
    expected = (int(os.getenv('AUTH_REMEMBER_DAYS', '30')) * 86400 if remember else int(os.getenv('AUTH_SESSION_HOURS', '12')) * 3600)
    assert expected - 10 <= remaining <= expected
    assert anonymous.post('/auth/refresh', headers=HEADERS).status_code == 200
    assert jwt.get_unverified_claims(anonymous.session.cookies[REFRESH])['exp'] == claims['exp']
    assert result.headers['Cache-Control'] == 'no-store'
    assert result.json()['access_token'] == ''


def test_expired_access_can_be_renewed_without_password(anonymous, seed):
    login(anonymous, seed)
    claims = jwt.get_unverified_claims(anonymous.session.cookies[ACCESS])
    claims['exp'] = datetime.now(timezone.utc) - timedelta(seconds=5)
    expired = jwt.encode(claims, 'quality-only-signing-key-never-use-in-production', algorithm='HS256')
    visitor = Api({ACCESS: expired, REFRESH: anonymous.session.cookies[REFRESH]})
    assert visitor.get('/auth/me').status_code == 401
    assert visitor.post('/auth/refresh', headers=HEADERS).status_code == 200
    assert visitor.get('/auth/me').status_code == 200


def test_logout_revokes_both_copied_tokens(anonymous, seed):
    login(anonymous, seed, True)
    copied = Api(anonymous.session.cookies.copy())
    assert anonymous.post('/auth/logout').status_code == 200
    assert ACCESS not in anonymous.session.cookies and REFRESH not in anonymous.session.cookies
    assert copied.get('/auth/me').status_code == 401
    assert copied.post('/auth/refresh', headers=HEADERS).status_code == 401


def test_rotation_grace_and_replay_revocation(anonymous, seed, admin_db):
    login(anonymous, seed)
    copied = Api(anonymous.session.cookies.copy())
    before = anonymous.session.cookies[REFRESH]
    sid = jwt.get_unverified_claims(before)['sid']
    assert anonymous.post('/auth/refresh', headers=HEADERS).status_code == 200
    after = anonymous.session.cookies[REFRESH]
    assert after != before
    assert copied.post('/auth/refresh', headers=HEADERS).status_code == 200
    assert copied.session.cookies[REFRESH] == after
    # Simulate time passage only in this disposable session; no waiting needed.
    with admin_db.cursor() as cursor:
        cursor.execute("UPDATE auth_sessions SET rotated_at=now()-interval '20 seconds' WHERE id=%s", (sid,))
    admin_db.commit()
    stale = Api({REFRESH: before})
    assert stale.post('/auth/refresh', headers=HEADERS).status_code == 401
    assert anonymous.get('/auth/me').status_code == 401


def test_concurrent_refresh_issues_same_generation(anonymous, seed):
    login(anonymous, seed)
    cookies = anonymous.session.cookies.copy()
    def run(_):
        client = Api(cookies)
        response = client.post('/auth/refresh', headers=HEADERS)
        return response.status_code, client.session.cookies[REFRESH]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert all(status == 200 for status, _ in results)
    assert results[0][1] == results[1][1]


def test_expired_session_cannot_renew_or_use_access(anonymous, seed, admin_db):
    login(anonymous, seed)
    sid = jwt.get_unverified_claims(anonymous.session.cookies[REFRESH])['sid']
    with admin_db.cursor() as cursor:
        cursor.execute("UPDATE auth_sessions SET expires_at=now()-interval '1 second' WHERE id=%s", (sid,))
    admin_db.commit()
    assert anonymous.post('/auth/refresh', headers=HEADERS).status_code == 401
    assert anonymous.get('/auth/me').status_code == 401


def test_refresh_purpose_csrf_and_invalid_token(anonymous, seed):
    login(anonymous, seed)
    assert anonymous.post('/auth/refresh').status_code == 403
    assert anonymous.post('/auth/refresh', headers={**HEADERS, 'Origin': 'https://untrusted.example'}).status_code == 403
    token = anonymous.session.cookies[REFRESH]
    assert anonymous.get('/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code == 401
    assert Api({REFRESH: 'broken'}).post('/auth/refresh', headers=HEADERS).status_code == 401
    assert Api().post('/auth/refresh', headers=HEADERS).status_code == 401


@pytest.mark.parametrize('entity', ['users', 'tenants', 'auth_version'])
def test_disabled_user_tenant_or_changed_auth_version_cannot_renew(anonymous, seed, admin_db, entity):
    login(anonymous, seed, email='beta-editor@example.com')
    user_id = seed['tenants']['beta']['users']['editor']['id']
    tenant_id = seed['tenants']['beta']['id']
    sql = ('UPDATE users SET auth_version=auth_version+%s WHERE id=%s' if entity == 'auth_version'
           else f'UPDATE {entity} SET is_active=%s WHERE id=%s')
    identifier = tenant_id if entity == 'tenants' else user_id
    try:
        with admin_db.cursor() as cursor:
            cursor.execute(sql, (1 if entity == 'auth_version' else False, identifier))
        admin_db.commit()
        assert anonymous.post('/auth/refresh', headers=HEADERS).status_code == 401
    finally:
        with admin_db.cursor() as cursor:
            cursor.execute(sql, (-1 if entity == 'auth_version' else True, identifier))
        admin_db.commit()


def test_password_change_revokes_refresh_on_other_device(anonymous, seed, unique):
    login(anonymous, seed)
    email = f'session-{unique}@example.com'
    created = anonymous.post('/auth/users', json={'email': email, 'password': seed['password'],
        'full_name': 'Conta sintética para teste de sessão', 'cpf': '52998224725', 'phone': '11999998888', 'role': 'editor'})
    assert created.status_code == 201, created.text
    first, other = Api(), Api()
    login(first, seed, email=email)
    login(other, seed, email=email)
    result = first.post('/auth/password/change', json={'current_password': seed['password'], 'new_password': 'Another-Quality-2026!'})
    assert result.status_code == 200, result.text
    assert REFRESH not in first.session.cookies
    assert other.get('/auth/me').status_code == 401
    assert other.post('/auth/refresh', headers=HEADERS).status_code == 401
