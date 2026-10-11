"""Run ORM compatibility checks inside the same production dependency image."""
import importlib
import os

import app.main  # noqa: F401 -- register production model mappings
from sqlalchemy import text

from app.auth import security
from app.db.session import SessionLocal, set_tenant_context


with SessionLocal() as db:
    tenant_id = set_tenant_context(db, "qa-alpha")
    assert db.execute(text("SELECT DISTINCT tenant_id FROM crm_notices")).scalars().all() == [tenant_id]
    db.commit()
    assert db.execute(text("SELECT DISTINCT tenant_id FROM crm_notices")).scalars().all() == [tenant_id]
    db.rollback()
    assert db.execute(text("SELECT DISTINCT tenant_id FROM crm_notices")).scalars().all() == [tenant_id]
    try:
        set_tenant_context(db, "qa-missing-tenant")
    except ValueError:
        pass
    else:
        raise AssertionError("Unknown legacy tenant slug must be rejected")

original = os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES")
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "invalid"
importlib.reload(security)
assert security.ACCESS_TOKEN_EXPIRE_MINUTES == 60
token = security.create_access_token("qa@example.com", "qa-alpha", "viewer", 1)
assert security.decode_access_token(token)["user_id"] == 1
if original is None:
    os.environ.pop("ACCESS_TOKEN_EXPIRE_MINUTES")
else:
    os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = original
print("ORM tenant context survives commit and rollback; legacy slugs and JWT configuration validated")
