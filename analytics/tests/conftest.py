"""Real dependencies. Never inherits tests/conftest.py's SQLAlchemy mocks."""

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault(
    "DATABASE_URL", "postgresql://test:test@127.0.0.1:65432/market_test"
)
os.environ.setdefault("SECRET_KEY", "market-analytics-isolated-test-secret-only")


@pytest.fixture
def db():
    from app.market_intelligence.models import WarehouseBase

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def attach(connection, _):
        for name in ["raw", "core", "mart"]:
            connection.execute(f"ATTACH DATABASE ':memory:' AS {name}")

    WarehouseBase.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
        session.rollback()
    engine.dispose()
