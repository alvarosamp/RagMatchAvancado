"""Shared transactional queue semantics for HTTP requests and scheduled flows."""

from sqlalchemy import func

from .models import SyncRun
from .repository import acquire_source_lock, scoped
from .schemas import SyncRequest


def enqueue_run(db, tenant_id, parameters):
    from .config import bling_enabled

    request = SyncRequest.model_validate(parameters)
    source = request.source
    if source == "bling" and not bling_enabled():
        raise ValueError(
            "Integração Bling planejada; habilite somente após configurar e homologar a conta."
        )
    if not acquire_source_lock(db, tenant_id, "enqueue:" + source):
        raise RuntimeError("Outra solicitação de carga está sendo registrada.")
    pending = scoped(db, SyncRun, tenant_id).filter(
        SyncRun.source == source, SyncRun.status.in_(["queued", "running"])
    )
    if source == "models":
        pending = pending.filter(
            func.coalesce(SyncRun.parameters["task"].as_string(), "win_probability")
            == request.task
        )
    run = pending.first()
    if run is None:
        run = SyncRun(
            tenant_id=tenant_id,
            source=source,
            parameters=request.model_dump(mode="json"),
        )
        db.add(run)
        db.flush()
    return run
