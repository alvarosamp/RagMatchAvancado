from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship, synonym
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import enum

Base = declarative_base()

EMBEDDING_DIM = 768  # nomic-embed-text via Ollama


# ──────────────────────────────────────────
# Produtos / Catálogo
# ──────────────────────────────────────────

class Product(Base):
    __tablename__ = "products"

    id            = Column(Integer, primary_key=True, index=True)
    model         = Column(String, unique=True, index=True)   # ex: "TL-SG3210"
    category      = Column(String)                             # ex: "switch"
    data          = Column(JSON)                               # specs completas
    manufacturer  = Column(String)                              # ex: "TP-Link", "Cisco"
    is_competitor = Column(Boolean, default=False, index=True)  # False = catálogo próprio

    matching_results = relationship(
        "MatchingResult",
        back_populates="product",
        cascade="all, delete-orphan",
    )


class OpportunityDecision(Base):
    """Decisao humana sobre uma oportunidade encontrada no PNCP."""
    __tablename__ = "opportunity_decisions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id_pncp",
            name="uq_opportunity_decisions_tenant_id_pncp",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    id_pncp = Column(String, nullable=False, index=True)
    score = Column(Integer)
    priority = Column(String)
    decision = Column(String, nullable=False, index=True)
    reason = Column(Text)
    notice_snapshot = Column(JSON)
    crm_notice_id = Column(String(36), index=True)
    import_job_id = Column(String)
    pncp_files_count = Column(Integer, default=0)
    import_error = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PncpRadarItem(Base):
    """Oportunidade PNCP capturada pela rotina diaria do Radar."""
    __tablename__ = "pncp_radar_items"
    __table_args__ = (
        UniqueConstraint(
            "id_pncp",
            name="uq_pncp_radar_items_id_pncp",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    id_pncp = Column(String, nullable=False, index=True)
    notice = Column(JSON, nullable=False)
    search_terms = Column(String)
    status = Column(String, nullable=False, default="active", index=True)
    first_seen_at = Column(DateTime, server_default=func.now())
    last_seen_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)


# ──────────────────────────────────────────
# Editais
# ──────────────────────────────────────────

class Edital(Base):
    """Representa um edital de licitação importado."""
    __tablename__ = "editais"

    id           = Column(Integer, primary_key=True, index=True)
    filename     = Column(String, nullable=False)
    source_hash  = Column(String, index=True)
    business_key = Column(String, index=True)
    status       = Column(String, nullable=False, default="done", index=True)
    full_text    = Column(Text)                          # texto bruto extraído
    parsed_at    = Column(DateTime, server_default=func.now())
    tenant_id    = Column(String, ForeignKey("tenants.slug"), index=True, nullable=False)
    import_batch_id = Column(Integer, ForeignKey("import_batches.id", ondelete="SET NULL"), index=True)
    source_path  = Column(String)
    analysis_only = Column(Boolean, default=False, index=True)

    tenant       = relationship("Tenant", back_populates="editais")
    chunks       = relationship("DocumentChunk", back_populates="edital", cascade="all, delete-orphan")
    requirements = relationship("Requirement",   back_populates="edital", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Fragmento do edital com embedding vetorial."""
    __tablename__ = "document_chunks"

    id        = Column(Integer, primary_key=True, index=True)
    edital_id = Column(Integer, ForeignKey("editais.id"), nullable=False, index=True)
    chunk_idx = Column(Integer)                          # ordem no documento
    text      = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM))            # pgvector

    edital = relationship("Edital", back_populates="chunks")


# ──────────────────────────────────────────
# Requisitos extraídos do edital
# ──────────────────────────────────────────

class Requirement(Base):
    """Requisito técnico extraído de um edital."""
    __tablename__ = "requirements"

    id           = Column(Integer, primary_key=True, index=True)
    edital_id    = Column(Integer, ForeignKey("editais.id"), nullable=False, index=True)
    attribute    = Column(String)   # ex: "portas_rj45"
    raw_value    = Column(String)   # ex: "mínimo 16 portas RJ-45"
    parsed_value = Column(String)   # ex: "16"
    unit         = Column(String)   # ex: "portas"

    edital           = relationship("Edital",         back_populates="requirements")
    matching_results = relationship(
        "MatchingResult",
        back_populates="requirement",
        cascade="all, delete-orphan",
    )


class AnalysisDocument(Base):
    """Resultado estruturado de uma analise repetivel de documento."""
    __tablename__ = "analysis_documents"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source_kind",
            "source_hash",
            name="uq_analysis_documents_tenant_kind_hash",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    import_batch_id = Column(Integer, ForeignKey("import_batches.id", ondelete="SET NULL"), index=True)
    source_kind = Column(String, nullable=False, index=True)
    schema_name = Column(String, index=True)
    schema_version = Column(String, index=True)
    source_hash = Column(String, nullable=False, index=True)
    business_key = Column(String, index=True)  # identificador do documento (n_interno/numero_pregao) p/ deduplicar
    source_name = Column(String)
    source_path = Column(String)
    analysis_only = Column(Boolean, default=False, index=True)
    crm_notice_id = Column(String, index=True)
    status = Column(String, nullable=False, default="done", index=True)
    full_text = Column(Text)
    result = Column(JSON)
    tokens_used = Column(Integer, default=0)
    processing_ms = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    items = relationship(
        "AnalysisItem",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )


class ImportBatch(Base):
    """Lote de importacao para desfazer historicos sem depender do nome do arquivo."""
    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    label = Column(String, nullable=False)
    source_path = Column(String)
    source_mode = Column(String, default="upload")
    analysis_only = Column(Boolean, default=False, index=True)
    sync_targets = Column(JSON)
    total_files = Column(Integer, default=0)
    status = Column(String, nullable=False, default="open", index=True)
    created_by = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DocumentSchema(Base):
    """Contrato versionado para importar documentos sem acoplar tudo a edital."""
    __tablename__ = "document_schemas"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "name",
            "version",
            name="uq_document_schemas_tenant_name_version",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    version = Column(String, nullable=False, index=True)
    title = Column(String)
    description = Column(Text)
    required_fields = Column(JSON)
    item_collection_path = Column(String)
    item_identity_fields = Column(JSON)
    business_key_fields = Column(JSON)
    sync_targets = Column(JSON)
    export_templates = Column(JSON)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AnalysisItem(Base):
    """Item extraido de edital, ata ou datasheet e salvo para reuso."""
    __tablename__ = "analysis_items"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(
        Integer,
        ForeignKey("analysis_documents.id"),
        nullable=False,
        index=True,
    )
    item_number = Column(String, index=True)
    item_type = Column(String, index=True)
    description = Column(Text)
    brand = Column(String)
    model = Column(String)
    quantity = Column(Float)
    unit = Column(String)
    unit_value = Column(Float)
    total_value = Column(Float)
    supplier = Column(String)
    supplier_tax_id = Column(String)
    raw_text = Column(Text)
    raw_payload = Column(JSON)
    categoria = Column(String, index=True)
    uf = Column(String, index=True)
    lote_grupo = Column(String)
    garantia = Column(String)
    prazo_entrega = Column(String, index=True)
    caracteristicas_tecnicas = Column(Text)
    exclusividade_me_epp_item = Column(String)
    risco_associado = Column(Text)
    direcionamento_marca_tipo = Column(String)
    direcionamento_marca_justificativa = Column(Text)
    has_direcionamento_marca = Column(Boolean, default=False, index=True)
    has_risco = Column(Boolean, default=False, index=True)
    caracteristicas_bi = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())

    analysis = relationship("AnalysisDocument", back_populates="items")


# ──────────────────────────────────────────
# Resultado de Matching
# ──────────────────────────────────────────

class MatchStatus(str, enum.Enum):
    ATENDE     = "atende"
    NAO_ATENDE = "nao_atende"
    VERIFICAR  = "verificar"


class MatchingResult(Base):
    __tablename__ = "matching_results"

    id             = Column(Integer, primary_key=True, index=True)
    product_id     = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    requirement_id = Column("requirements_id", Integer, ForeignKey("requirements.id"), nullable=False, index=True)
    status         = Column(Enum(MatchStatus), nullable=False)
    score          = Column(Float, default=0.0)   # 0.0 – 1.0
    details        = Column(Text)
    llm_reasoning  = Column(Text)                 # justificativa do LLM
    created_at     = Column(DateTime, server_default=func.now())

    requirements_id = synonym("requirement_id")
    product     = relationship("Product",     back_populates="matching_results")
    requirement = relationship("Requirement", back_populates="matching_results")
