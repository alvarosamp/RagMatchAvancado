# CONCEITO: Por que precisamos de uma tabela de Jobs?
#
# Sem job tracking:
#   Cliente faz POST /upload → espera 5 minutos → talvez receba timeout
#   Se a API cair no meio, o cliente nunca sabe o que aconteceu.
#
# Com job tracking:
#   Cliente faz POST /upload → recebe job_id imediatamente
#   Cliente consulta GET /jobs/{id}/status a cada X segundos
#   Quando status="done", busca o resultado
#
# A tabela Job é o "painel de controle" de tudo que está rodando.
# Cada linha é um job com estado, progresso, e resultado ou erro.
#
# VOCABULÁRIO MLOps:
#   - Job:      unidade de trabalho assíncrono (ex: processar um PDF)
#   - Status:   estado atual do job (pending → running → done/failed)
#   - Payload:  dados de entrada do job (path do PDF, tenant_id, etc.)
#   - Result:   dados de saída (edital_id criado, número de chunks, etc.)
#   - Retry:    número de tentativas em caso de falha
#
# =============================================================================

import enum
from sqlachemy import Column, DateTime, Enum, Float, Integer, JSON, String, Text
from sqlalchemy.sql import func
from app.db.models import Base

class JobStatus(str, enum.Enum):
    '''
    Estados possiveis de um job

    A transição de estados é sempre linear (sem volta):
        Pending -> Running -> Done
                           -> Failed
    
    '''
    PENDING = "pending"   # job criado, aguardando worker pegar
    RUNNING = "running"   # worker está executando agora
    DONE = "done"      # concluído com sucesso
    FAILED = "failed"    # falhou (ver campo error_message)

class JobType(str, enum.Enum):
    '''
    Tipos de job suportados. Cada tipo tem seu próprio handler no queue.py
    '''
    UPLOAD_EDITAL = "upload_edital"   # OCR + chunk + embed
    RUN_MATCHING  = "run_matching"    # matching de produtos

class Job(Base):
    """
    Representa um job assíncrono no banco de dados.

    Campos:
        id:            UUID gerado pelo Python (não auto-increment)
                       Usamos string UUID para não expor sequência numérica
        job_type:      qual pipeline vai rodar (upload ou matching)
        status:        estado atual (pending/running/done/failed)
        progress:      percentual de progresso 0.0-1.0 (para barra de progresso)
        tenant_id:     slug do tenant dono do job (isolamento multi-tenant)
        user_id:       quem criou o job
        payload:       JSON com dados de entrada (ex: path do PDF)
        result:        JSON com dados de saída (ex: edital_id, n_chunks)
        error_message: mensagem de erro se status=failed
        created_at:    quando o job foi criado
        started_at:    quando o worker começou a executar
        finished_at:   quando terminou (sucesso ou falha)
    """
    __tablename__ = 'jobs'
    id = Column(String, primary_key = True, index = True)
    job_type = Column(Enum(JobType), nullable = False)
    status = Column(Enum(JobStatus), nullable = False, defaut= JobStatus.PENDING, index = True)
    progress = Column(Float, default = 0.0) # 0.0 a 1.0
    #Multi tenant: Cada job pertence a um tenant 
    tenant_id = Column(String, index = True, nullable = False)
    user_id = Column(Integer, nullable = False)
    #Dados do job
    payload = Column(JSON)
    result = Column(JSON)
    error_message = Column(Text)
    #timestamps
    created_at = Column(DateTime, server_default = func.now())
    started_at = Column(DateTime, nullable = True)
    finished_at = Column(DateTime, nullable = True)

    def __repr__(self):
        return f"<Job id={self.id[:8]}... type={self.job_type} status={self.status}>"