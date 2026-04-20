# CONCEITO: Como funciona a fila de jobs?
#
# Hoje usamos BackgroundTasks do FastAPI:
#   - Zero infra extra (não precisa de Redis, RabbitMQ, etc.)
#   - Roda no mesmo processo da API, em thread separada
#   - Perfeito para desenvolvimento e cargas moderadas
#
# Quando escalar (futuro):
#   - Trocar por Celery + Redis: workers independentes, retry avançado
#   - Ou ativar Prefect: já está preparado no pipeline_worker.py
#   - A interface (JobQueue) não muda — só a implementação interna
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
import tempfile 
import os 
from datetime import datetime, timezone
from typing import Optional
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.jobs.models import Job, JobStatus, JobType
from app.logs.config import logger


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
        tmp_dir = "/data/tmp_uploads"
        os.makedirs(tmp_dir, exist_ok=True)

        job_id   = str(uuid.uuid4())
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
            },
        )
        db.add(job)
        db.commit()

        logger.info(f"[JobQueue] Job criado | id={job_id[:8]}... | arquivo={filename} | tenant={tenant_id}")

        # Agenda execução em background
        # O FastAPI vai chamar essa função DEPOIS de retornar a resposta HTTP
        background_tasks.add_task(
            _executar_job_upload,
            job_id    = job_id,
            pdf_path  = pdf_path,
            filename  = filename,
            tenant_id = tenant_id,
        )

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

        background_tasks.add_task(
            _executar_job_matching,
            job_id    = job_id,
            edital_id = edital_id,
            tenant_id = tenant_id,
        )

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
    pdf_path:  str,
    filename:  str,
    tenant_id: str,
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
        _update_job(db, job_id, status=JobStatus.RUNNING, progress=0.05,
                    started_at=datetime.now(timezone.utc))
        logger.info(f"[Worker] Iniciando upload | job={job_id[:8]}... | arquivo={filename}")

        # ── Etapa 1: OCR + Parse (Docling) ────────────────────────────────────
        # Docling é o passo mais pesado — pode demorar 1-3 minutos em PDFs grandes
        from app.pipeline.docling_parser import parse_pdf
        _update_job(db, job_id, progress=0.10)

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        parsed_doc = parse_pdf(pdf_bytes, filename=filename)
        _update_job(db, job_id, progress=0.40)
        logger.info(f"[Worker] OCR concluído | job={job_id[:8]}... | chars={len(parsed_doc.full_text)}")

        # ── Etapa 2: Salva Edital + Chunking ──────────────────────────────────
        from app.db.models import Edital
        from app.pipeline.chunker import chunk_document

        edital = Edital(
            filename  = filename,
            full_text = parsed_doc.full_text,
            tenant_id = tenant_id,
        )
        db.add(edital)
        db.flush()  # gera edital.id

        chunks = chunk_document(parsed_doc)
        _update_job(db, job_id, progress=0.60)
        logger.info(f"[Worker] Chunking concluído | job={job_id[:8]}... | chunks={len(chunks)}")

        # ── Etapa 3: Embeddings + pgvector ────────────────────────────────────
        # Segunda etapa mais pesada — chama o Ollama para cada chunk
        from app.vector.pgvector_store import save_chunks
        _update_job(db, job_id, progress=0.65)

        saved = save_chunks(db, edital, chunks)
        _update_job(db, job_id, progress=0.90)
        logger.info(f"[Worker] Embeddings salvos | job={job_id[:8]}... | n={saved}")

        # ── Etapa 4: Commit + cleanup ─────────────────────────────────────────
        db.commit()
        db.refresh(edital)

        # Remove PDF temporário (já processado, não precisa mais)
        try:
            os.remove(pdf_path)
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
            },
        )
        logger.info(f"[Worker] Job concluído | job={job_id[:8]}... | edital={edital.id}")

    except Exception as e:
        # Qualquer erro: marca como FAILED e salva a mensagem
        logger.error(f"[Worker] Job falhou | job={job_id[:8]}... | erro={e}", exc_info=True)
        _update_job(
            db, job_id,
            status        = JobStatus.FAILED,
            finished_at   = datetime.now(timezone.utc),
            error_message = str(e),
        )

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
        _update_job(db, job_id, status=JobStatus.RUNNING, progress=0.05,
                    started_at=datetime.now(timezone.utc))
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

        # ── Executa matching (parte mais pesada) ──────────────────────────────
        # match_all_products já integra o MLOps internamente
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

    except Exception as e:
        logger.error(f"[Worker] Job matching falhou | job={job_id[:8]}... | erro={e}", exc_info=True)
        _update_job(
            db, job_id,
            status        = JobStatus.FAILED,
            finished_at   = datetime.now(timezone.utc),
            error_message = str(e),
        )

    finally:
        db.close()


# =============================================================================
# Helper interno
# =============================================================================

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