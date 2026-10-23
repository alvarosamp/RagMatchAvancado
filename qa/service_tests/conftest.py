"""Service tests use actual libraries and transactions in the disposable database."""
import os
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.main  # noqa: F401 -- register all production ORM mappings


@pytest.fixture
def unique():
    # This suite also runs directly inside the production dependency image,
    # independently of the host's HTTP/browser conftest.
    return uuid.uuid4().hex[:12]


@pytest.fixture
def db():
    url = os.environ["QA_ADMIN_DATABASE_URL"]
    assert url.rsplit("/", 1)[-1] == "ragmatch_quality"
    engine = create_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
    engine.dispose()


@pytest.fixture
def context(db):
    from app.auth.models import Tenant, User
    tenant = db.query(Tenant).filter_by(slug="qa-alpha").one()
    user = db.query(User).filter_by(email="alpha-admin@example.com").one()
    return SimpleNamespace(tenant=tenant, user=user)
