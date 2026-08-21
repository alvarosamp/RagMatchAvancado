# CONCEITO: Como funciona a fila de jobs?
#
# Os jobs sao persistidos no PostgreSQL e enviados ao worker via Redis/Dramatiq.
# A API apenas cria o registro e publica a mensagem; OCR, embeddings e LLM nao
# concorrem mais com os requests HTTP.
#
# FLUXO:
#   1. POST /editais/upload chega
#   2. JobQueue.criar_job() salva Job(status=PENDING) no banco
#   3. FastAPI retorna {"job_id": "abc"} imediatamente (< 100ms)
#   4. BackgroundTasks executa _executar_job() em background
#   5. _executar_job() atualiza status: PENDING → RUNNING → DONE/FAILED
#   6. Cliente consulta GET /jobs/abc/status até receber "done"
#
# VOCABULÁRIO MLOps:
#   - BackgroundTasks: mecanismo do FastAPI para rodar funções após a resposta
#   - Worker:          processo/thread que consome e executa jobs da fila
#   - Idempotência:    rodar o mesmo job duas vezes produz o mesmo resultado
#   - Dead letter:     job que falhou N vezes e foi descartado
#

import uuid
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.auth.models import User
from app.jobs.models import Job, JobStatus, JobType
from app.logs.config import logger


class JobCancelledError(Exception):
    """Raised when a running job is cancelled externally."""
    pass


def _claim_job(db: Session, job_id: str) -> bool:
    """Atomically claim a pending job so duplicate broker messages are harmless."""
    job = db.get(Job, job_id)
    if job is None or job.status != JobStatus.PENDING:
        return False

    payload = dict(job.payload or {})
    payload["attempts"] = int(payload.get("attempts", 0)) + 1
    job.payload = payload
    job.status = JobStatus.RUNNING
    job.progress = 0.05
    job.started_at = datetime.now(timezone.utc)
    job.finished_at = None
    job.error_message = None
    db.commit()
    return True


def _enqueue_job(db: Session, job: Job, *, delay_ms: int = 0) -> None:
    """Persist the delivery metadata and publish a job to the Redis broker."""
    payload = dict(job.payload or {})
    payload["last_enqueued_at"] = datetime.now(timezone.utc).isoformat()
    job.payload = payload
    db.commit()

    from app.jobs.tasks import process_crm_notice_match, process_matching, process_upload

    if job.job_type == JobType.UPLOAD_EDITAL:
        actor = process_upload
        args = (
            job.id, payload.get("pdf_path"), payload["filename"], payload["tenant_id"],
            payload.get("source_hash"), bool(payload.get("analysis_only", False)),
            payload.get("import_batch_id"), payload.get("source_path"), payload.get("crm_notice_id"),
            payload.get("object_key"),
        )
    elif job.job_type == JobType.RUN_MATCHING:
        actor = process_matching
        args = (job.id, payload["edital_id"], payload["tenant_id"])
    elif job.job_type == JobType.CRM_NOTICE_MATCH:
        actor = process_crm_notice_match
        args = (job.id, payload["notice_id"], payload["tenant_id"], job.user_id)
    else:
        raise ValueError(f"Tipo de job sem dispatcher: {job.job_type}")

    if delay_ms:
        actor.send_with_options(args=args, delay=delay_ms)
    else:
        actor.send(*args)


def _retry_or_fail(db: Session, job_id: str, error: Exception) -> bool:
    """Retry transient failures with backoff, preserving the visible job record."""
    job = db.get(Job, job_id)
    if job is None:
        return True

    payload = dict(job.payload or {})
    attempts = int(payload.get("attempts", 1))
    max_attempts = max(1, int(os.getenv("JOB_MAX_ATTEMPTS", "3")))
    if attempts >= max_attempts:
        _update_job(
            db, job_id, status=JobStatus.FAILED,
            finished_at=datetime.now(timezone.utc), error_message=str(error),
        )
        return True

    delay_ms = min(300_000, 30_000 * (2 ** max(0, attempts - 1)))
    job.status = JobStatus.PENDING
    job.progress = 0.0
    job.started_at = None
    job.error_message = f"Tentativa {attempts}/{max_attempts} falhou: {error}"
    db.commit()
    logger.warning("[Worker] Reenfileirando job=%s em %ss", job_id[:8], delay_ms // 1000)
    _enqueue_job(db, job, delay_ms=delay_ms)
    return False


def recover_interrupted_jobs(db: Session) -> dict[str, int]:
    """Requeue pending work and recover work left running after a worker crash."""
    now = datetime.now(timezone.utc)
    pending_after = max(30, int(os.getenv("JOB_PENDING_REQUEUE_SECONDS", "60")))
    stale_after = max(300, int(os.getenv("JOB_STALE_TIMEOUT_SECONDS", "7200")))
    max_attempts = max(1, int(os.getenv("JOB_MAX_ATTEMPTS", "3")))
    summary = {"pending_requeued": 0, "stale_requeued": 0, "stale_failed": 0}

    jobs = db.query(Job).filter(Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING])).all()
    for job in jobs:
        payload = dict(job.payload or {})
        attempts = int(payload.get("attempts", 0))
        if job.status == JobStatus.PENDING:
            last_enqueued = _parse_timestamp(payload.get("last_enqueued_at")) or job.created_at
            if last_enqueued and _as_utc(last_enqueued) <= now - timedelta(seconds=pending_after):
                _enqueue_job(db, job)
                summary["pending_requeued"] += 1
        elif job.started_at and _as_utc(job.started_at) <= now - timedelta(seconds=stale_after):
            if attempts >= max_attempts:
                _update_job(
                    db, job.id, status=JobStatus.FAILED, finished_at=now,
                    error_message="Job interrompido: excedeu o limite de tentativas de recuperacao.",
                )
                summary["stale_failed"] += 1
            else:
                job.status = JobStatus.PENDING
                job.progress = 0.0
                job.started_at = None
                job.error_message = "Job recuperado apos interrupcao do worker."
                db.commit()
                _enqueue_job(db, job)
                summary["stale_requeued"] += 1
    return summary


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _remove_local_upload(pdf_path: str | None) -> None:
    if not pdf_path:
        return
    try:
        os.remove(pdf_path)
    except OSError:
        pass


def _remove_object_upload(object_key: str | None) -> None:
    if object_key:
        from app.services.object_storage import delete
        delete(object_key)


def _is_cancelled(db: Session, job_id: str) -> bool:
    """Check if a job was cancelled externally (bypasses identity map cache)."""
    row = db.execute(
        select(Job.status, Job.error_message).where(Job.id == job_id)
    ).first()
    return (
        row is not None
        and row.status == JobStatus.FAILED
        and row.error_message == "Cancelado pelo usuário"
    )


class JobQueue:
    """
    Interface para criar e executar jobs assíncronos.

    Uso no router:
        queue = JobQueue()
        job_id = queue.criar_job_upload(
            background_tasks = background_tasks,
            pdf_bytes        = pdf_bytes,
            filename         = file.filename,
            tenant_id        = current_user.tenant.slug,
            user_id          = current_user.id,
        )
        return {"job_id": job_id}
    """

    def criar_job_upload(
        self,
        background_tasks: BackgroundTasks,
        pdf_bytes:        bytes,
        filename:         str,
        tenant_id:        str,
        user_id:          int,
        db:               Session,
        source_hash:      str | None = None,
        analysis_only:    bool = False,
        import_batch_id:  int | None = None,
        source_path:      str | None = None,
        crm_notice_id:    str | None = None,
    ) -> str:
        """
        Cria um job de upload+processamento de edital.

        Salva o PDF em arquivo temporário, cria o Job no banco
        e agenda a execução em background.

        Args:
            background_tasks: injeção do FastAPI para rodar em background
            pdf_bytes:        conteúdo binário do PDF
            filename:         nome original do arquivo
            tenant_id:        slug do tenant
            user_id:          ID do usuário que fez o upload
            db:               sessão do banco (para criar o Job)

        Returns:
            job_id (UUID string) para o cliente consultar o status
        """
        # Salva o PDF em arquivo temporário persistente
        # (não podemos usar NamedTemporaryFile com delete=True porque
        # o background task roda depois que o request termina)
        job_id   = str(uuid.uuid4())
        object_key = None
        pdf_path = None
        from app.services.object_storage import object_storage_enabled, put_upload

        if object_storage_enabled():
            object_key = put_upload(tenant_id, job_id, filename, pdf_bytes)
        else:
            tmp_dir = "/data/tmp_uploads"
            os.makedirs(tmp_dir, exist_ok=True)
            pdf_path = os.path.join(tmp_dir, f"{job_id}.pdf")
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)

        # Cria o Job no banco com status PENDING
        job = Job(
            id        = job_id,
            job_type  = JobType.UPLOAD_EDITAL,
            status    = JobStatus.PENDING,
            tenant_id = tenant_id,
            user_id   = user_id,
            # payload = dados de entrada que o worker vai precisar
            payload   = {
                "pdf_path": pdf_path,
                "filename": filename,
                "tenant_id": tenant_id,
                "source_hash": source_hash,
                "analysis_only": analysis_only,
                "import_batch_id": import_batch_id,
                "source_path": source_path,
                "crm_notice_id": crm_notice_id,
                "object_key": object_key,
            },
        )
        db.add(job)
        db.commit()

        logger.info(f"[JobQueue] Job criado | id={job_id[:8]}... | arquivo={filename} | tenant={tenant_id}")

        _enqueue_job(db, job)

        return job_id

    def criar_job_matching(
        self,
        background_tasks: BackgroundTasks,
        edital_id:        int,
        tenant_id:        str,
        user_id:          int,
        db:               Session,
    ) -> str:
        """
        Cria um job de matching para um edital já processado.

        Args:
            background_tasks: injeção do FastAPI
            edital_id:        ID do edital a fazer matching
            tenant_id:        slug do tenant
            user_id:          ID do usuário que disparou
            db:               sessão do banco

        Returns:
            job_id (UUID string)
        """
        job_id = str(uuid.uuid4())

        job = Job(
            id        = job_id,
            job_type  = JobType.RUN_MATCHING,
            status    = JobStatus.PENDING,
            tenant_id = tenant_id,
            user_id   = user_id,
            payload   = {
                "edital_id": edital_id,
                "tenant_id": tenant_id,
            },
        )
        db.add(job)
        db.commit()

        logger.info(f"[JobQueue] Job matching criado | id={job_id[:8]}... | edital={edital_id}")

        _enqueue_job(db, job)

        return job_id

    def criar_job_crm_notice_match(
        self,
        background_tasks: BackgroundTasks,
        notice_id:         str,
        tenant_id:         str,
        user_id:           int,
        db:                Session,
        notice_product_id: str | None = None,
        category: str | None = None,
        use_llm: bool = True,
    ) -> str:
        """
        Cria um job assíncrono de match do CRM (catalogo x itens do edital).
        """
        job_id = str(uuid.uuid4())

        job = Job(
            id=job_id,
            job_type=JobType.CRM_NOTICE_MATCH,
            status=JobStatus.PENDING,
            tenant_id=tenant_id,
            user_id=user_id,
            payload={
                "notice_id": notice_id,
                "tenant_id": tenant_id,
                "notice_product_id": notice_product_id,
                "category": category,
                "use_llm": use_llm,
            },
        )
        db.add(job)
        db.commit()

        logger.info(f"[JobQueue] Job CRM match criado | id={job_id[:8]}... | notice={notice_id}")

        _enqueue_job(db, job)

        return job_id


# =============================================================================
# Handlers de execução (rodam em background)
# =============================================================================
# Cada função abaixo:
#   1. Abre sua própria sessão de banco (a sessão do request já fechou)
#   2. Atualiza o status do Job em cada etapa
#   3. Loga progresso (visível no GET /jobs/{id}/status)
#   4. Nunca lança exceção para cima (captura tudo e marca como FAILED)
# =============================================================================

def _executar_job_upload(
    job_id:    str,
    pdf_path:  str | None,
    filename:  str,
    tenant_id: str,
    source_hash: str | None = None,
    analysis_only: bool = False,
    import_batch_id: int | None = None,
    source_path: str | None = None,
    crm_notice_id: str | None = None,
    object_key: str | None = None,
) -> None:
    """
    Handler do job de upload — roda em background thread.

    Etapas:
        1. OCR + parse com Docling         (progress: 0.1 → 0.4)
        2. Chunking semântico              (progress: 0.4 → 0.6)
        3. Embeddings + salva no pgvector  (progress: 0.6 → 0.9)
        4. Commit final + limpa PDF temp   (progress: 0.9 → 1.0)
    """
    # Cada handler abre sua própria sessão de banco.
    # A sessão do request original já foi fechada quando chegamos aqui.
    db = SessionLocal()

    try:
        # ── Marca como RUNNING ────────────────────────────────────────────────
        if not _claim_job(db, job_id):
            return
        logger.info(f"[Worker] Iniciando upload | job={job_id[:8]}... | arquivo={filename}")

        # ── Etapa 1: OCR + Parse (Docling) ────────────────────────────────────
        # Docling é o passo mais pesado — pode demorar 1-3 minutos em PDFs grandes
        from app.pipeline.docling_parser import parse_pdf
        _update_job(db, job_id, progress=0.10)

        if object_key:
            from app.services.object_storage import get_bytes
            pdf_bytes = get_bytes(object_key)
        elif pdf_path:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
        else:
            raise ValueError("Job de upload sem origem de arquivo.")

        parsed_doc = parse_pdf(pdf_bytes, filename=filename)
        _update_job(db, job_id, progress=0.40)
        logger.info(f"[Worker] OCR concluído | job={job_id[:8]}... | chars={len(parsed_doc.full_text)}")

        if _is_cancelled(db, job_id):
            raise JobCancelledError()

        # ── Etapa 2: Salva Edital + Chunking ──────────────────────────────────
        from app.db.models import Edital
        from app.services.document_identity import edital_business_key_from_text, is_unidentified_pdf_text
        from app.pipeline.chunker import chunk_document

        business_key = edital_business_key_from_text(parsed_doc.full_text, filename)
        if is_unidentified_pdf_text(parsed_doc.full_text, filename):
            raise ValueError(
                "Documento nao identificado. O PDF nao possui texto suficiente ou dados de edital reconheciveis."
            )

        duplicate = (
            db.query(Edital)
            .filter(
                Edital.tenant_id == tenant_id,
                Edital.business_key == business_key,
            )
            .first()
        )
        if duplicate is not None:
            decision_payload = _try_generate_decision_intelligence(
                db,
                crm_notice_id=crm_notice_id,
                edital=duplicate,
                user_id=None,
            )
            _remove_local_upload(pdf_path)
            _remove_object_upload(object_key)
            _update_job(
                db, job_id,
                status      = JobStatus.DONE,
                progress    = 1.0,
                finished_at = datetime.now(timezone.utc),
                result      = {
                    "edital_id": duplicate.id,
                    "filename": filename,
                    "duplicate": True,
                    "analysis_only": analysis_only,
                    "import_batch_id": import_batch_id,
                    "crm_notice_id": crm_notice_id,
                    "decision_intelligence": decision_payload,
                    "message": "Documento ja cadastrado. Este arquivo nao foi reprocessado.",
                },
            )
            logger.info("[Worker] Documento duplicado ignorado | job=%s | edital=%s", job_id[:8], duplicate.id)
            return

        edital = Edital(
            filename  = filename,
            source_hash = source_hash,
            business_key = business_key,
            status = "done",
            full_text = parsed_doc.full_text,
            tenant_id = tenant_id,
            import_batch_id = import_batch_id,
            source_path = source_path,
            storage_key = object_key,
            analysis_only = analysis_only,
        )
        db.add(edital)
        db.flush()  # gera edital.id

        chunks = chunk_document(parsed_doc)
        _update_job(db, job_id, progress=0.60)
        logger.info(f"[Worker] Chunking concluído | job={job_id[:8]}... | chunks={len(chunks)}")

        if _is_cancelled(db, job_id):
            raise JobCancelledError()

        # ── Etapa 3: Embeddings + pgvector ────────────────────────────────────
        from app.vector.pgvector_store import save_chunks
        _update_job(db, job_id, progress=0.65)

        saved = save_chunks(db, edital, chunks)
        _update_job(db, job_id, progress=0.90)

        if _is_cancelled(db, job_id):
            raise JobCancelledError()
        logger.info(f"[Worker] Embeddings salvos | job={job_id[:8]}... | n={saved}")

        # ── Etapa 4: Commit + cleanup ─────────────────────────────────────────
        db.commit()
        db.refresh(edital)
        decision_payload = _try_generate_decision_intelligence(
            db,
            crm_notice_id=crm_notice_id,
            edital=edital,
            user_id=None,
        )

        # Remove PDF temporário (já processado, não precisa mais)
        try:
            _remove_local_upload(pdf_path)
        except OSError:
            pass  # não crítico

        # Marca como DONE com o resultado
        _update_job(
            db, job_id,
            status      = JobStatus.DONE,
            progress    = 1.0,
            finished_at = datetime.now(timezone.utc),
            result      = {
                "edital_id": edital.id,
                "filename":  filename,
                "n_chunks":  saved,
                "analysis_only": analysis_only,
                "import_batch_id": import_batch_id,
                "crm_notice_id": crm_notice_id,
                "decision_intelligence": decision_payload,
            },
        )
        logger.info(f"[Worker] Job concluído | job={job_id[:8]}... | edital={edital.id}")

    except JobCancelledError:
        logger.info(f"[Worker] Job cancelado pelo usuário | job={job_id[:8]}...")
        _remove_local_upload(pdf_path)
        _remove_object_upload(object_key)

    except Exception as e:
        logger.error(f"[Worker] Job falhou | job={job_id[:8]}... | erro={e}", exc_info=True)
        if _retry_or_fail(db, job_id, e):
            _remove_local_upload(pdf_path)
            _remove_object_upload(object_key)

    finally:
        db.close()


def _executar_job_matching(
    job_id:    str,
    edital_id: int,
    tenant_id: str,
) -> None:
    """
    Handler do job de matching — roda em background thread.

    Etapas:
        1. Carrega edital + requisitos + produtos    (progress: 0.1)
        2. Executa match_all_products() com MLOps   (progress: 0.1 → 0.95)
        3. Salva resultado                           (progress: 1.0)
    """
    db = SessionLocal()

    try:
        if not _claim_job(db, job_id):
            return
        logger.info(f"[Worker] Iniciando matching | job={job_id[:8]}... | edital={edital_id}")

        # ── Carrega dados ─────────────────────────────────────────────────────
        from app.db.models import Edital, Product
        from app.services.matching_engine import match_all_products

        edital = db.get(Edital, edital_id)
        if not edital:
            raise ValueError(f"Edital {edital_id} não encontrado")

        requirements = edital.requirements
        if not requirements:
            raise ValueError(f"Edital {edital_id} não possui requisitos")

        products = db.query(Product).filter(Product.category == "switch").all()
        if not products:
            raise ValueError("Nenhum produto no catálogo")

        _update_job(db, job_id, progress=0.10)
        logger.info(
            f"[Worker] Matching | job={job_id[:8]}... | "
            f"{len(products)} produtos × {len(requirements)} requisitos"
        )

        if _is_cancelled(db, job_id):
            raise JobCancelledError()

        # ── Executa matching (parte mais pesada) ──────────────────────────────
        reports = match_all_products(
            db,
            products,
            requirements,
            edital_id = edital_id,
            tenant_id = tenant_id,
        )
        _update_job(db, job_id, progress=0.95)

        # ── Marca como DONE ───────────────────────────────────────────────────
        _update_job(
            db, job_id,
            status      = JobStatus.DONE,
            progress    = 1.0,
            finished_at = datetime.now(timezone.utc),
            result      = {
                "edital_id":      edital_id,
                "total_produtos": len(reports),
                "melhor_modelo":  reports[0].product_model if reports else None,
                "melhor_score":   reports[0].overall_score if reports else None,
            },
        )
        logger.info(
            f"[Worker] Matching concluído | job={job_id[:8]}... | "
            f"melhor={reports[0].product_model if reports else 'N/A'}"
        )

    except JobCancelledError:
        logger.info(f"[Worker] Job matching cancelado pelo usuário | job={job_id[:8]}...")

    except Exception as e:
        logger.error(f"[Worker] Job matching falhou | job={job_id[:8]}... | erro={e}", exc_info=True)
        _retry_or_fail(db, job_id, e)

    finally:
        db.close()


def _executar_job_crm_notice_match(
    job_id: str,
    notice_id: str,
    tenant_id: str,
    user_id: int,
) -> None:
    """
    Handler do job de match do CRM — roda em background thread.

    Etapas:
        1. Carrega o edital CRM e o catálogo          (progress: 0.1)
        2. Executa o match catalogo x itens           (progress: 0.1 → 0.95)
        3. Salva o resumo do match                    (progress: 1.0)
    """
    db = SessionLocal()

    try:
        if not _claim_job(db, job_id):
            return
        logger.info(f"[Worker] Iniciando CRM match | job={job_id[:8]}... | notice={notice_id}")

        if _is_cancelled(db, job_id):
            raise JobCancelledError()

        from app.crm.models import CrmNotice
        from app.services.crm_item_matcher import run_notice_item_match

        notice = db.get(CrmNotice, notice_id)
        user = db.get(User, user_id)
        if not notice:
            raise ValueError(f"Edital CRM {notice_id} nao encontrado")
        if not user:
            raise ValueError(f"Usuario {user_id} nao encontrado para executar o match CRM")

        _update_job(db, job_id, progress=0.10)

        if _is_cancelled(db, job_id):
            raise JobCancelledError()

        job = db.get(Job, job_id)
        use_llm = True
        notice_product_id = None
        category = None
        if job is not None:
            use_llm = bool((job.payload or {}).get("use_llm", True))
            notice_product_id = (job.payload or {}).get("notice_product_id")
            category = (job.payload or {}).get("category")

        payload = run_notice_item_match(
            db,
            user,
            notice_id,
            use_llm=use_llm,
            notice_product_id=notice_product_id,
            category=category,
        )
        summary = payload.get("summary") or {}

        _update_job(
            db,
            job_id,
            status=JobStatus.DONE,
            progress=1.0,
            finished_at=datetime.now(timezone.utc),
            result={
                "notice_id": notice_id,
                "notice_number": notice.tor_id or notice.number,
                "overall_score": summary.get("overall_score"),
                "coverage_ratio": summary.get("coverage_ratio"),
                "strong_items": summary.get("strong_items"),
                "possible_items": summary.get("possible_items"),
                "weak_items": summary.get("weak_items"),
                "unmatched_items": summary.get("unmatched_items"),
                "label": summary.get("label"),
            },
        )
        logger.info(
            f"[Worker] CRM match concluido | job={job_id[:8]}... | notice={notice_id} | "
            f"score={summary.get('overall_score')}"
        )

    except JobCancelledError:
        logger.info(f"[Worker] Job CRM match cancelado | job={job_id[:8]}...")

    except Exception as e:
        logger.error(f"[Worker] Job CRM match falhou | job={job_id[:8]}... | erro={e}", exc_info=True)
        _retry_or_fail(db, job_id, e)

    finally:
        db.close()


# =============================================================================
# Helper interno
# =============================================================================

def _try_generate_decision_intelligence(
    db: Session,
    *,
    crm_notice_id: str | None,
    edital,
    user_id: int | None,
) -> dict | None:
    if not crm_notice_id:
        return None
    try:
        from app.services.decision_intelligence import persist_notice_decision_intelligence

        return persist_notice_decision_intelligence(
            db,
            notice_id=crm_notice_id,
            edital=edital,
            user_id=user_id,
        )
    except Exception as exc:
        logger.warning(
            "[Worker] Falha ao gerar parecer IA | notice=%s | erro=%s",
            crm_notice_id,
            exc,
            exc_info=True,
        )
        return {"error": str(exc)}

def _update_job(
    db:            Session,
    job_id:        str,
    status:        Optional[JobStatus] = None,
    progress:      Optional[float]     = None,
    result:        Optional[dict]      = None,
    error_message: Optional[str]       = None,
    started_at:    Optional[datetime]  = None,
    finished_at:   Optional[datetime]  = None,
) -> None:
    """
    Atualiza os campos do Job no banco.

    Centraliza os updates para não repetir o padrão
    get → setar campo → commit em todo o código.
    """
    job = db.get(Job, job_id)
    if not job:
        logger.error(f"[Worker] Job não encontrado para update: {job_id}")
        return

    if status        is not None: job.status        = status
    if progress      is not None: job.progress      = round(progress, 2)
    if result        is not None: job.result        = result
    if error_message is not None: job.error_message = error_message
    if started_at    is not None: job.started_at    = started_at
    if finished_at   is not None: job.finished_at   = finished_at

    db.commit()
