"""Dramatiq actors consumed by the dedicated job worker."""

from __future__ import annotations

import asyncio
import json
import os
import uuid

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from app.jobs.queue import (
    _executar_job_crm_notice_match,
    _executar_job_matching,
    _executar_job_upload,
)
from app.logs.config import logger

broker = RedisBroker(url=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
dramatiq.set_broker(broker)


@dramatiq.actor(queue_name="edital-processing", max_retries=0, time_limit=60 * 60 * 1000)
def process_upload(job_id: str, pdf_path: str | None, filename: str, tenant_id: int, source_hash: str | None = None, analysis_only: bool = False, import_batch_id: int | None = None, source_path: str | None = None, crm_notice_id: str | None = None, object_key: str | None = None) -> None:
    _executar_job_upload(job_id, pdf_path, filename, tenant_id, source_hash, analysis_only, import_batch_id, source_path, crm_notice_id, object_key)


@dramatiq.actor(queue_name="matching", max_retries=0, time_limit=60 * 60 * 1000)
def process_matching(job_id: str, edital_id: int, tenant_id: int) -> None:
    _executar_job_matching(job_id, edital_id, tenant_id)


@dramatiq.actor(queue_name="ai-inference", max_retries=0, time_limit=60 * 60 * 1000)
def process_crm_notice_match(job_id: str, notice_id: str, tenant_id: int, user_id: int) -> None:
    _executar_job_crm_notice_match(job_id, notice_id, tenant_id, user_id)


@dramatiq.actor(
    queue_name="conlicitacao-sync",
    max_retries=2,
    min_backoff=30_000,
    max_backoff=300_000,
    time_limit=15 * 60 * 1000,
)
def process_conlicitacao_sync(tenant_id: int, correlation_id: str | None = None) -> None:
    """Synchronize bulletins outside the FastAPI process."""
    from app.core.config import settings
    from app.db.session import SessionLocal, set_tenant_context
    from app.integrations.conlicitacao.client import ConlicitacaoClient
    from app.integrations.conlicitacao.service import ConlicitacaoService
    from app.integrations.tenders.repository import TenderRepository

    if not settings.conlicitacao_enabled:
        logger.info('[ConLicitacao] {"event":"sync_skipped","reason":"disabled"}')
        return
    if tenant_id not in settings.conlicitacao_sync_tenant_ids:
        logger.warning(
            '[ConLicitacao] {"event":"sync_skipped","reason":"tenant_not_authorized","tenant_id":%s}',
            tenant_id,
        )
        return
    correlation_id = correlation_id or str(uuid.uuid4())
    db = SessionLocal()
    try:
        normalized_tenant_id = set_tenant_context(db, tenant_id)

        async def _run() -> dict:
            async with ConlicitacaoClient() as client:
                service = ConlicitacaoService(
                    client,
                    TenderRepository(db, normalized_tenant_id),
                    max_pages=settings.conlicitacao_sync_max_pages,
                )
                result = await service.sync(
                    normalized_tenant_id, correlation_id=correlation_id
                )
                return result.model_dump()

        summary = asyncio.run(_run())
        logger.info(
            "%s",
            json.dumps(
                {
                    "event": "sync_completed",
                    "provider": "conlicitacao",
                    "correlation_id": correlation_id,
                    **summary,
                },
                ensure_ascii=False,
            ),
        )
    except Exception:
        db.rollback()
        logger.exception(
            '[ConLicitacao] {"event":"sync_failed","correlation_id":"%s","tenant_id":%s}',
            correlation_id,
            tenant_id,
        )
        raise
    finally:
        db.close()
