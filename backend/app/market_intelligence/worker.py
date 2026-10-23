"""Durable, per-tenant job runner. Prefect schedules; this process claims jobs."""

import argparse
import logging
import os
import time
from datetime import timedelta

from sqlalchemy import or_, text

from .adapters import bling_record, normalized_record, pncp_record
from .connectors import BlingReader, ReadClient, ibge_index, pncp_records
from .crm_source import reconcile_crm
from .models import Checkpoint, ProductSupplier, SyncRun
from .repository import acquire_source_lock, now, scoped, store_raw, upsert

logger = logging.getLogger(__name__)


def source_should_transform(source):
    return os.getenv("MARKET_DBT_ENABLED", "false").lower() == "true" and source in {
        "crm",
        "bling",
        "pncp",
        "ibge",
    }


def run_source(db, tenant_id, run, session_factory):
    source, params = run.source, run.parameters or {}
    if not acquire_source_lock(db, tenant_id, source):
        raise RuntimeError("Fonte ocupada por outra carga.")
    if source == "crm":
        return reconcile_crm(db, tenant_id, run.id)
    if source == "models":
        from .training import train_task

        return train_task(db, tenant_id, params.get("task", "win_probability"))
    if source == "quality":
        from .monitoring import quality_snapshot

        return quality_snapshot(db, tenant_id)
    if source == "marts":
        from analytics.flows.pipeline import build_marts

        # dbt replaces shared views. Serialize DDL across every tenant, while
        # the tenant-specific core ingestion can continue independently.
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(hashtext('market-dbt-ddl'))"))

        build_marts(tenant_id)
        return {"dbt_status": "completed"}
    checkpoint = (
        scoped(db, Checkpoint, tenant_id)
        .filter_by(source=source, entity="all")
        .one_or_none()
    )
    today = now().date()
    start = params.get("date_from") or (
        (checkpoint.watermark.date() - timedelta(days=7)).isoformat()
        if checkpoint and checkpoint.watermark
        else (today - timedelta(days=30)).isoformat()
    )
    end = params.get("date_to") or today.isoformat()
    counts = {"records": 0, "raw_versions": 0}
    if source == "bling":
        from .config import bling_enabled

        if not bling_enabled():
            raise ValueError("Bling analítico ainda não habilitado.")
        # OAuth token renewal has its own transaction. It must never commit a
        # partially processed analytical snapshot.
        from app.db.session import set_tenant_context
        from app.integrations.bling.service import build_tenant_client

        with session_factory() as token_db:
            set_tenant_context(token_db, tenant_id)
            reader = BlingReader(build_tenant_client(token_db, tenant_id=tenant_id))
            resources = params.get("resources") or list(BlingReader.RESOURCES) + [
                "inventory"
            ]
            product_ids = []
            for resource in resources:
                if resource == "inventory":
                    if not product_ids:
                        from .models import Identity

                        product_ids = [
                            int(row.source_id)
                            for row in scoped(db, Identity, tenant_id)
                            .filter_by(source="bling", kind="product")
                            .all()
                            if row.source_id.isdigit()
                        ]
                    records = reader.stock(product_ids)
                elif resource in {"purchase", "sale", "proposal"}:
                    from .connectors import date_windows

                    def transactions(resource=resource):
                        for begin, finish in date_windows(start, end, days=365):
                            yield from reader.records(
                                resource,
                                {
                                    "dataInicial": begin.isoformat(),
                                    "dataFinal": finish.isoformat(),
                                },
                            )

                    records = transactions()
                else:
                    records = reader.records(resource)
                # Snapshot dims/relations are reconciled only for requested scope.
                if resource == "product_supplier":
                    scoped(db, ProductSupplier, tenant_id).filter_by(
                        source="bling"
                    ).update({ProductSupplier.active: False}, synchronize_session=False)
                for record in records:
                    record_id = str(
                        record.get("id") or (record.get("produto") or {}).get("id")
                    )
                    if record_id == "None":
                        raise ValueError("Registro Bling sem identidade.")
                    counts["raw_versions"] += store_raw(
                        db, tenant_id, run.id, source, resource, record_id, record
                    )
                    bling_record(db, tenant_id, resource, record)
                    if resource == "product":
                        product_ids.append(record["id"])
                    counts["records"] += 1
    elif source == "pncp":
        for entity, source_id, payload in pncp_records(
            ReadClient(), start, end, tuple(params.get("modalities") or [6])
        ):
            counts["raw_versions"] += store_raw(
                db, tenant_id, run.id, source, entity, source_id, payload
            )
            pncp_record(db, tenant_id, entity, source_id, payload)
            counts["records"] += 1
    elif source == "ibge":
        for record in ibge_index(
            ReadClient(),
            params.get("table", 1737),
            params.get("variable", 2266),
            start[:7].replace("-", ""),
            end[:7].replace("-", ""),
        ):
            counts["raw_versions"] += store_raw(
                db, tenant_id, run.id, source, "index", record["id"], record
            )
            normalized_record(
                db,
                tenant_id,
                source,
                "index",
                {
                    "id": record["id"],
                    "unit_price": record["value"],
                    "event_at": f"{record['month'][:4]}-{record['month'][4:6]}-01T00:00:00Z",
                    "attributes": record,
                },
            )
            counts["records"] += 1
    else:
        raise ValueError("Fonte desconhecida.")
    # A requested historical backfill must not skip the live watermark forward.
    watermark = run.started_at if not params.get("date_to") else None
    upsert(
        db,
        Checkpoint,
        tenant_id,
        {"source": source, "entity": "all"},
        {
            "watermark": watermark
            if watermark
            else checkpoint.watermark
            if checkpoint
            else None,
            "details": {"last_run": run.id, "period": [start, end]},
        },
    )
    return counts


def process_one(session_factory, tenant_id):
    from .config import enabled

    if not enabled():
        return False
    from app.db.session import set_tenant_context

    with session_factory() as db:
        set_tenant_context(db, tenant_id)
        run = (
            scoped(db, SyncRun, tenant_id)
            .filter(
                or_(
                    SyncRun.status == "queued",
                    (SyncRun.status == "running")
                    & (SyncRun.started_at < now() - timedelta(hours=4)),
                )
            )
            .order_by(SyncRun.created_at)
            .with_for_update(skip_locked=True)
            .first()
        )
        if not run:
            return False
        run_id = run.id
        run.status, run.started_at, run.error = "running", now(), None
        db.commit()
        try:
            # Hold the row for the complete transaction. Crash recovery cannot
            # claim a still-live job; expired rows are skipped while locked.
            run = (
                scoped(db, SyncRun, tenant_id)
                .filter_by(id=run_id)
                .with_for_update()
                .one()
            )
            run.counts = run_source(db, tenant_id, run, session_factory)
            run.status, run.finished_at = "completed", now()
            if source_should_transform(run.source):
                # Commit the source and durable follow-up together. dbt executes
                # in a later job, after this transaction becomes visible.
                existing = (
                    scoped(db, SyncRun, tenant_id)
                    .filter(
                        SyncRun.source == "marts",
                        SyncRun.status.in_(["queued", "running"]),
                    )
                    .first()
                )
                if not existing:
                    db.add(
                        SyncRun(
                            tenant_id=tenant_id,
                            source="marts",
                            parameters={"parent_run_id": run_id},
                        )
                    )
            db.commit()
        except Exception as error:  # noqa: BLE001 -- job boundary must persist failure after rollback
            db.rollback()
            run = scoped(db, SyncRun, tenant_id).filter_by(id=run_id).one()
            # Avoid source HTTP bodies and credentials in persisted errors.
            run.status, run.finished_at, run.error = (
                "failed",
                now(),
                f"{type(error).__name__}: carga revertida; consultar logs operacionais sem segredos.",
            )
            db.commit()
            logger.error("Data job %s failed (%s)", run_id, type(error).__name__)
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--tenant", type=int)
    args = parser.parse_args()
    from app.db.session import SessionLocal

    with SessionLocal() as validation_db:
        if validation_db.get_bind().dialect.name == "postgresql":
            role = validation_db.execute(
                text(
                    "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"
                )
            ).one()
            if role.rolsuper or role.rolbypassrls:
                raise SystemExit("worker-data exige conta sem SUPERUSER/BYPASSRLS.")

    tenants = (
        [args.tenant]
        if args.tenant
        else [
            int(value)
            for value in os.getenv("MARKET_TENANT_IDS", "").split(",")
            if value.strip()
        ]
    )
    if not tenants or any(value <= 0 for value in tenants):
        raise SystemExit("Configure MARKET_TENANT_IDS com os tenants autorizados.")
    logging.basicConfig(level=logging.INFO)
    while True:
        busy = sum(bool(process_one(SessionLocal, tenant)) for tenant in tenants) > 0
        if args.once:
            return
        if not busy:
            time.sleep(5)


if __name__ == "__main__":
    main()
