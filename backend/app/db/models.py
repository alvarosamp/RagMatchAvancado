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
    source_kind = Column(String, nullable=False, index=True)
    source_hash = Column(String, nullable=False, index=True)
    business_key = Column(String, index=True)  # identificador do documento (n_interno/numero_pregao) p/ deduplicar
    source_name = Column(String)
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
