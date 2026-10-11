"""Real HTTP, PostgreSQL and browser fixtures; no application dependency mocks."""

import json
import os
from pathlib import Path
import uuid

import psycopg2
import pytest
import requests


ROOT = Path(__file__).resolve().parents[1]
API_URL = os.getenv("QA_API_URL", "http://127.0.0.1:18089")
WEB_URL = os.getenv("QA_WEB_URL", "http://127.0.0.1:13089")
ADMIN_URL = os.getenv("QA_ADMIN_URL", "postgresql://postgres:quality-admin-only@127.0.0.1:18439/ragmatch_quality")
RUNTIME_URL = os.getenv("QA_RUNTIME_URL", "postgresql://ragmatch_quality:quality-runtime-only@127.0.0.1:18439/ragmatch_quality")


class Api:
    def __init__(self, cookies=None):
        self.session = requests.Session()
        # Independent simulated visitors retain the real rate-limit enforcement.
        self.session.headers["X-Forwarded-For"] = "10." + ".".join(str(value) for value in uuid.uuid4().bytes[:3])
        if cookies:
            self.session.cookies.update(cookies)

    def request(self, method, path, **kwargs):
        return self.session.request(method, API_URL + path, timeout=15, **kwargs)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def patch(self, path, **kwargs):
        return self.request("PATCH", path, **kwargs)


@pytest.fixture(scope="session")
def seed():
    path = ROOT / "test-results/functional/seed.json"
    if not path.exists():
        pytest.fail("QA stack is not running: start qa/compose.yaml before this suite")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def identities(seed):
    result = {}
    for tenant in seed["tenants"]:
        for role, user in seed["tenants"][tenant]["users"].items():
            client = Api()
            response = client.post("/auth/login", json={"email": user["email"], "password": seed["password"]})
            assert response.status_code == 200, response.text
            result[tenant, role] = dict(client.session.cookies)
            client.session.close()
    return result


@pytest.fixture
def clients(identities):
    opened = []

    def create(tenant="alpha", role="admin"):
        client = Api(identities[tenant, role])
        opened.append(client)
        return client

    yield create
    for client in opened:
        client.session.close()


@pytest.fixture
def api(clients):
    return clients()


@pytest.fixture
def anonymous():
    client = Api()
    yield client
    client.session.close()


@pytest.fixture
def admin_db():
    if ADMIN_URL.rsplit("/", 1)[-1] != "ragmatch_quality":
        pytest.fail("Refusing QA queries against a non-QA database")
    with psycopg2.connect(ADMIN_URL) as connection:
        yield connection


@pytest.fixture
def runtime_db():
    if RUNTIME_URL.rsplit("/", 1)[-1] != "ragmatch_quality":
        pytest.fail("Refusing QA queries against a non-QA database")
    with psycopg2.connect(RUNTIME_URL) as connection:
        yield connection


@pytest.fixture
def unique():
    return uuid.uuid4().hex[:12]


@pytest.fixture
def authenticated_page(page, identities):
    page.context.add_cookies([{"name": "access_token", "value": identities["alpha", "admin"]["access_token"], "url": WEB_URL}])
    return page
