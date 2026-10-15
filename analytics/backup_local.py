"""Rehearse consistent backup/restore only on the isolated fictitious Docker DB.

This is a local acceptance tool, not a production backup policy.
"""

import argparse
import hashlib
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = [
    "docker",
    "compose",
    "-p",
    "ragmatch-market-test",
    "-f",
    str(ROOT / "docker-compose.analytics.test.yaml"),
    "exec",
    "-T",
    "db",
]
URL = "postgresql://postgres:database-local-test-only@127.0.0.1:65441/market_local_test"
TABLES = (
    "raw.records",
    "raw.checkpoints",
    "core.entities",
    "core.identities",
    "core.facts",
    "core.feedback",
    "core.identity_reviews",
    "core.brand_aliases",
    "core.product_suppliers",
    "core.procurement_requests",
    "core.supplier_quotes",
    "raw.sync_runs",
    "mart.model_runs",
)


def snapshot(connection):
    result = {}
    for table in TABLES:
        # Names are code constants; no user SQL or identifier interpolation.
        result[table] = [
            list(row)
            for row in connection.execute(
                text(
                    f"SELECT tenant_id, count(*) FROM {table} GROUP BY tenant_id ORDER BY tenant_id"
                )
            )
        ]
    result["values"] = [
        list(row)
        for row in connection.execute(
            text(
                "SELECT tenant_id, kind, count(*), coalesce(sum(total_value),0)::text FROM core.facts WHERE active GROUP BY tenant_id,kind ORDER BY tenant_id,kind"
            )
        )
    ]
    return result


def rehearse(destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    identifier = uuid.uuid4().hex[:12]
    archive = destination / f"market-local-{identifier}.dump"
    restored_name = f"market_restore_{identifier}_test"
    engine = create_engine(URL)
    try:
        with engine.connect().execution_options(
            isolation_level="REPEATABLE READ"
        ) as db:
            db.execute(text("SET TRANSACTION READ ONLY"))
            assert db.scalar(text("SELECT current_database()")) == "market_local_test"
            assert (
                db.scalar(
                    text(
                    "SELECT count(*) FROM public.tenants WHERE slug NOT IN ('demo-market-1', 'demo-market-2')"
                    )
                )
                == 0
            ), "Refusing a database with non-demo tenants"
            before = snapshot(db)
            exported = db.scalar(text("SELECT pg_export_snapshot()"))
            with archive.open("xb") as output:
                subprocess.run(
                    COMPOSE
                    + [
                        "pg_dump",
                        "-U",
                        "postgres",
                        "-d",
                        "market_local_test",
                        "--format=custom",
                        "--no-owner",
                        "--no-acl",
                        "--snapshot",
                        exported,
                    ],
                    stdout=output,
                    check=True,
                )
        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "market_local_test",
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "snapshot": before,
            "roles": "not included; provision separately",
        }
        subprocess.run(
            COMPOSE + ["createdb", "-U", "postgres", restored_name], check=True
        )
        try:
            with archive.open("rb") as source:
                subprocess.run(
                    COMPOSE
                    + [
                        "pg_restore",
                        "-U",
                        "postgres",
                        "-d",
                        restored_name,
                        "--exit-on-error",
                        "--no-owner",
                        "--no-acl",
                    ],
                    stdin=source,
                    check=True,
                )
            restored = create_engine(URL.rsplit("/", 1)[0] + "/" + restored_name)
            try:
                with restored.begin() as db:
                    assert snapshot(db) == before, "Backup values/counts mismatch"
                    assert (
                        db.scalar(text("SELECT version_num FROM alembic_version"))
                        == "20261009_02"
                    )
                    assert (
                        db.scalar(
                            text(
                                "SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('raw','core','mart') AND c.relkind='r'"
                            )
                        )
                        is True
                    )
                    # ACLs are intentionally provisioned separately after restore.
                    db.execute(
                        text(
                            "GRANT USAGE ON SCHEMA core TO market_test_runtime; GRANT SELECT ON core.facts TO market_test_runtime"
                        )
                    )
                    db.execute(text("SET LOCAL ROLE market_test_runtime"))
                    assert db.scalar(text("SELECT count(*) FROM core.facts")) == 0
                    for tenant in (1, 2):
                        db.execute(
                            text(
                                "SELECT set_config('app.current_tenant_id', :tenant, true)"
                            ),
                            {"tenant": str(tenant)},
                        )
                        assert set(
                            db.execute(
                                text("SELECT DISTINCT tenant_id FROM core.facts")
                            ).scalars()
                        ) == {tenant}
                manifest["restore_verified"] = True
                manifest["rls_verified"] = True
            finally:
                restored.dispose()
        finally:
            # Only the unique database created by this invocation is removed.
            assert restored_name.startswith(
                "market_restore_"
            ) and restored_name.endswith("_test")
            subprocess.run(
                COMPOSE + ["dropdb", "-U", "postgres", restored_name], check=True
            )
        archive.with_suffix(".json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        print(
            f"Backup, independent restore, migration and two-tenant RLS passed: {archive}"
        )
        return manifest
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "analytics/.validation/backups"
    )
    args = parser.parse_args()
    rehearse(args.output)


if __name__ == "__main__":
    main()
