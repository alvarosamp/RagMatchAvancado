"""Dramatiq actors consumed by the dedicated job worker."""

from __future__ import annotations

import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from app.jobs.queue import (
    _executar_job_crm_notice_match,
    _executar_job_matching,
    _executar_job_upload,
)


broker = RedisBroker(url=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
dramatiq.set_broker(broker)


@dramatiq.actor(queue_name="edital-processing", max_retries=0, time_limit=60 * 60 * 1000)
def process_upload(job_id: str, pdf_path: str | None, filename: str, tenant_id: str, source_hash: str | None = None, analysis_only: bool = False, import_batch_id: int | None = None, source_path: str | None = None, crm_notice_id: str | None = None, object_key: str | None = None) -> None:
    _executar_job_upload(job_id, pdf_path, filename, tenant_id, source_hash, analysis_only, import_batch_id, source_path, crm_notice_id, object_key)


@dramatiq.actor(queue_name="matching", max_retries=0, time_limit=60 * 60 * 1000)
def process_matching(job_id: str, edital_id: int, tenant_id: str) -> None:
    _executar_job_matching(job_id, edital_id, tenant_id)


@dramatiq.actor(queue_name="matching", max_retries=0, time_limit=60 * 60 * 1000)
def process_crm_notice_match(job_id: str, notice_id: str, tenant_id: str, user_id: int) -> None:
    _executar_job_crm_notice_match(job_id, notice_id, tenant_id, user_id)
