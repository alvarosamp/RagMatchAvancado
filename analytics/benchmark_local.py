"""Exercise representative analytics queries with transaction-only fictitious rows."""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from app.market_intelligence.models import Fact
from app.market_intelligence.service import report
from sqlalchemy import create_engine, insert, text
from sqlalchemy.orm import Session

URL = "postgresql://market_test_runtime:runtime-local-test-only@127.0.0.1:65441/market_local_test"


def set_tenant_context(db, tenant):
    db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
        {"tenant": str(tenant)},
    )


def benchmark(count=5000):
    if not 100 <= count <= 20000:
        raise ValueError("Use 100–20000 temporary rows.")
    engine = create_engine(URL)
    moment = datetime.now(timezone.utc)
    category = "Validação temporária de desempenho"
    try:
        with Session(engine) as db:
            assert db.scalar(text("SELECT current_database()")) == "market_local_test"
            assert not db.scalar(
                text(
                    "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user"
                )
            )
            set_tenant_context(db, 1)
            before = db.query(Fact).count()
            db.execute(
                insert(Fact),
                [
                    {
                        "tenant_id": 1,
                        "source": "crm",
                        "kind": "demand",
                        "source_id": f"benchmark-{i}",
                        "category": category,
                        "description": "Fixture temporária",
                        "unit": "UN",
                        "currency": "BRL",
                        "quantity": 1,
                        "total_value": 10,
                        "reference_price": 10,
                        "coverage": "unassessed",
                        "event_at": moment,
                        "available_at": moment,
                        "active": True,
                        "attributes": {},
                    }
                    for i in range(count)
                ],
            )
            timings = []
            for _ in range(5):
                started = time.perf_counter()
                payload = report(db, 1, category=category)
                encoded = json.dumps(payload, default=str)
                timings.append(time.perf_counter() - started)
                assert payload["summary"]["internal_demand_items"] == count
                assert payload["summary"]["reference_value"] == count * 10
            db.rollback()
            set_tenant_context(db, 1)
            assert db.query(Fact).count() == before, (
                "Temporary facts were not rolled back"
            )
            result = {
                "rows": count,
                "runs": len(timings),
                "p50_seconds": median(timings),
                "max_seconds": max(timings),
                "serialized_bytes": len(encoded.encode()),
                "scope": "PostgreSQL queries + analytics + JSON; excludes HTTP/browser",
                "transaction_rolled_back": True,
                "created_at": moment.isoformat(),
            }
            destination = Path(__file__).resolve().parent / ".validation/benchmark.json"
            destination.parent.mkdir(exist_ok=True)
            destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False))
            return result
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=5000)
    benchmark(parser.parse_args().rows)


if __name__ == "__main__":
    main()
