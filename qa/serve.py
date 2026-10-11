"""Bootstrap only the disposable QA database, then run the real app with coverage."""

import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from datetime import datetime, timedelta


def bootstrap():
    admin_url = os.environ["QA_ADMIN_DATABASE_URL"]
    if admin_url.rsplit("/", 1)[-1] != "ragmatch_quality":
        raise RuntimeError("QA refuses to modify any database except ragmatch_quality")
    env = {**os.environ, "DATABASE_URL": admin_url}
    subprocess.run([sys.executable, "scripts/migrate_database.py"], env=env, check=True)
    subprocess.run([sys.executable, "scripts/provision_app_role.py"], env=env, check=True)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.auth.models import Tenant, User
    from app.auth.security import hash_password
    from app.crm.models import CrmNotice, CrmOrgan, CrmPortal, CrmNoticeProduct
    from app.db.models import Edital, Requirement
    from app.jobs.models import Job, JobStatus, JobType
    # Import all mappers before the first ORM operation.
    from app.main import app  # noqa: F401

    password = "Quality-Test-Only-2026!"
    seed = {"password": password, "tenants": {}}
    with Session(create_engine(admin_url)) as db:
        hashed = hash_password(password)
        for slug in ("alpha", "beta", "empty"):
            tenant = db.query(Tenant).filter_by(slug=f"qa-{slug}").first()
            if tenant:
                raise RuntimeError("QA database is not fresh; run compose down before testing")
            tenant = Tenant(slug=f"qa-{slug}", name=f"Empresa QA {slug.title()}")
            db.add(tenant)
            db.flush()
            record = {"id": tenant.id, "users": {}}
            for role in ("admin", "editor", "viewer"):
                user = User(tenant_id=tenant.id, email=f"{slug}-{role}@example.com",
                            hashed_password=hashed, full_name=f"QA {slug} {role}", role=role,
                            cpf="52998224725", phone="11999998888")
                db.add(user)
                db.flush()
                record["users"][role] = {"id": user.id, "email": user.email}
            if slug != "empty":
                organ = CrmOrgan(tenant_id=tenant.id, name=f"Prefeitura QA {slug}", city="São Paulo", state="SP")
                portal = CrmPortal(tenant_id=tenant.id, name=f"Portal QA {slug}")
                db.add_all([organ, portal])
                db.flush()
                notice = CrmNotice(tenant_id=tenant.id, number=f"QA-{slug}-001",
                                   title=f"Compra QA {slug} – Switch 48 portas",
                                   organ_id=organ.id, portal_id=portal.id,
                                   auction_date=datetime.now()+timedelta(days=7))
                db.add(notice)
                db.flush()
                db.add(CrmNoticeProduct(tenant_id=tenant.id, notice_id=notice.id,
                                       description="Switch QA 48 portas", quantity=3, reference_price=100))
                edital = Edital(tenant_id=tenant.id, filename=f"edital-qa-{slug}.pdf")
                db.add(edital)
                db.flush()
                db.add(Requirement(edital_id=edital.id, attribute="ports", raw_value="48 portas", parsed_value="48"))
                record.update(notice_id=notice.id, edital_id=edital.id, organ_id=organ.id, portal_id=portal.id)
                record["jobs"] = {}
                for state in JobStatus:
                    job = Job(id=str(uuid.uuid4()), tenant_id=tenant.id, user_id=record["users"]["admin"]["id"],
                              job_type=JobType.UPLOAD_EDITAL, status=state,
                              progress=1 if state == JobStatus.DONE else 0,
                              payload={"filename": "qa.pdf"},
                              result={"edital_id": edital.id} if state == JobStatus.DONE else None,
                              error_message="Erro QA controlado" if state == JobStatus.FAILED else None)
                    db.add(job)
                    db.flush()
                    record["jobs"][state.value] = job.id
            seed["tenants"][slug] = record
        db.commit()
    report_dir = Path(os.environ["QA_REPORT_DIR"])
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "seed.json").write_text(json.dumps(seed), encoding="utf-8")


if __name__ == "__main__":
    bootstrap()
    os.environ["COVERAGE_FILE"] = "/reports/.coverage.functional"
    os.execv(sys.executable, [sys.executable, "-m", "coverage", "run", "--source=app",
                            "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])
