from sqlalchemy import (
    JSON, Column, Integer, String, ForeignKey,
    Text, Float, DateTime, Enum
)
from sqlalchemy.orm import declarative_base, relationship
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

    id       = Column(Integer, primary_key=True, index=True)
    model    = Column(String, unique=True, index=True)   # ex: "TL-SG3210"
    category = Column(String)                             # ex: "switch"
    data     = Column(JSON)                               # specs completas

    matching_results = relationship("MatchingResult", back_populates="product")


# ──────────────────────────────────────────
# Editais
# ──────────────────────────────────────────

class Edital(Base):
    """Representa um edital de licitação importado."""
    __tablename__ = "editais"

    id           = Column(Integer, primary_key=True, index=True)
    filename     = Column(String, nullable=False)
    full_text    = Column(Text)                          # texto bruto extraído
    parsed_at    = Column(DateTime, server_default=func.now())
    tenant_id    = Column(String, index=True)            # multi-tenant

    chunks       = relationship("DocumentChunk", back_populates="edital", cascade="all, delete-orphan")
    requirements = relationship("Requirement",   back_populates="edital", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Fragmento do edital com embedding vetorial."""
    __tablename__ = "document_chunks"

    id        = Column(Integer, primary_key=True, index=True)
    edital_id = Column(Integer, ForeignKey("editais.id"), nullable=False)
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
    edital_id    = Column(Integer, ForeignKey("editais.id"), nullable=False)
    attribute    = Column(String)   # ex: "portas_rj45"
    raw_value    = Column(String)   # ex: "mínimo 16 portas RJ-45"
    parsed_value = Column(String)   # ex: "16"
    unit         = Column(String)   # ex: "portas"

    edital           = relationship("Edital",         back_populates="requirements")
    matching_results = relationship("MatchingResult", back_populates="requirement")


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
    product_id     = Column(Integer, ForeignKey("products.id"),     nullable=False)
    requirements_id = Column(Integer, ForeignKey("requirements.id"), nullable=False)
    status         = Column(Enum(MatchStatus), nullable=False)
    score          = Column(Float, default=0.0)   # 0.0 – 1.0
    details        = Column(Text)
    llm_reasoning  = Column(Text)                 # justificativa do LLM
    created_at     = Column(DateTime, server_default=func.now())

    product     = relationship("Product",     back_populates="matching_results")
    requirement = relationship("Requirement", back_populates="matching_results")