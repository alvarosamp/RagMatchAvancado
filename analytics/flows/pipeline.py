import argparse
import os
import subprocess
import time
from pathlib import Path

from prefect import flow, task


@task(retries=3, retry_delay_seconds=[5, 20, 60])
def enqueue(tenant_id: int, source: str = "crm", parameters: dict | None = None):
    from app.db.session import SessionLocal, set_tenant_context
    from app.market_intelligence.config import enabled
    from app.market_intelligence.queue import enqueue_run

    if not enabled():
        return None
    with SessionLocal() as db:
        set_tenant_context(db, int(tenant_id))
        run = enqueue_run(db, tenant_id, {**(parameters or {}), "source": source})
        result = run.id
        db.commit()
        return result


@flow(name="market-intelligence-enqueue", log_prints=False)
def pipeline(tenant_id: int, source: str = "crm", parameters: dict | None = None):
    return enqueue(tenant_id, source, parameters)


@flow(name="market-intelligence-dbt")
def build_marts(tenant_id: int):
    environment = {
        **os.environ,
        "MARKET_TENANT_ID": str(int(tenant_id)),
        "PGOPTIONS": f"-c app.current_tenant_id={int(tenant_id)}",
    }
    project = Path(__file__).resolve().parents[1] / "dbt"
    subprocess.run(
        [
            os.getenv("MARKET_DBT_BIN", "dbt"),
            "build",
            "--project-dir",
            str(project),
            "--profiles-dir",
            str(project),
            "--target-path",
            f"/tmp/market-dbt-{int(tenant_id)}/target",
            "--log-path",
            f"/tmp/market-dbt-{int(tenant_id)}/logs",
        ],
        env=environment,
        check=True,
        timeout=1800,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule", action="store_true")
    parser.add_argument("--tenant", type=int)
    parser.add_argument("--source", default="crm")
    parser.add_argument("--dbt", action="store_true")
    args = parser.parse_args()
    if not args.schedule:
        if not args.tenant or args.tenant <= 0:
            raise SystemExit("--tenant is required.")
        return (
            build_marts(args.tenant) if args.dbt else pipeline(args.tenant, args.source)
        )
    tenants = [
        int(t) for t in os.getenv("MARKET_TENANT_IDS", "").split(",") if t.strip()
    ]
    sources = [
        s.strip()
        for s in os.getenv("MARKET_SCHEDULE_SOURCES", "crm").split(",")
        if s.strip()
    ]
    if not tenants:
        raise SystemExit("MARKET_TENANT_IDS required.")
    interval = max(60, int(os.getenv("MARKET_SCHEDULE_SECONDS", "3600")))
    while True:
        for tenant in tenants:
            for source in sources:
                pipeline(tenant, source)
        time.sleep(interval)


if __name__ == "__main__":
    main()
