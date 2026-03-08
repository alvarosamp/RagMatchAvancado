'''
Salve e busca chunks com pgvector

Operações principais:
- save_chunks() -> persiste chunks + embeddings no banco
- search_similar() -> busca semantica por texto
- search_by_vector() -> busca semantica por embedding
'''
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.models import DocumentChunk, Edital
from app.pipeline.chunker import TextChunker
from app.pipeline.embedder import embed_text, embed_texts_batch
from app.logs.config import logger

#Salvando os chunks e os embeddings
def save_chunks(db: Session, edital : Edital, chunks : list[TextChunker]) -> int:
    '''
    Gera embeddings em lote e persiste eops documentschunks no banco
    Retorna o numero de chunks inseridos
    '''
    if not chunks:
        return 0
    
    texts = [c.text for c in chunks]
    embeddings = embed_texts_batch(texts)
    db_chunks = [
        DocumentChunk(
            edital_id = edital.id,
            chunk_idx = chunk.chunk_idx,
            text      = chunk.text,
            embedding = emb,
        )
        for chunk, emb in zip(chunks, embeddings)
    ]
    
    db.bulk_save_objects(db_chunks)
    db.commit()
    logger.info(f"{len(db_chunks)} chunks salvos para edital {edital.id}")
    return len(db_chunks)


#Busca semantica
def search_similar(db: Session, query: str, edital_id: int | None =None, top_k : int =5) -> list[dict]:
    '''
    Busca chunks semanticamente similares a query
    
    Args:
    - query: texto de busca
    - edital_id: se fornecido, filtra chunks para um edital específico
    - top_k: número de resultados a retornar
    
    Retorna lista de dicts com keys: chunk_idx, text, similarity
    '''
    vector = embed_text(query)
    return search_by_vector(db, vector, edital_id = edital_id, top_k = top_k)

def search_by_vector(db: Session, vector: list[float], edital_id:int | None = None, top_k: int =5) -> list[dict]:
    
    """Busca por vetor pré-computado usando distância cosseno (<=>)."""

    filter_clause = "WHERE dc.edital_id = :edital_id" if edital_id else ""

    sql =   text(f"""
    SELECT
        dc.id,
        dc.chunk_idx,
        dc.text,
        dc.edital_id,
        1 - (dc.embedding <=> CAST(:vector AS vector)) AS score
    FROM document_chunks dc
    {filter_clause}
    ORDER BY dc.embedding <=> CAST(:vector AS vector)
    LIMIT :top_k
    """)

    params: dict = {"vector": str(vector), "top_k": top_k}
    if edital_id:
        params["edital_id"] = edital_id

    rows = db.execute(sql, params).fetchall()

    results = [
    {
        "chunk_id":  row.id,
        "chunk_idx": row.chunk_idx,
        "text":      row.text,
        "edital_id": row.edital_id,
        "score":     round(float(row.score), 4),
    }
    for row in rows
    ]

    logger.info(f"[PGVector] Busca retornou {len(results)} chunks (top_k={top_k})")
    return results

#Inicialização da extensao pgvector

def ensure_pgvector_extension(db: Session):
    """Garante que a extensão pgvector esteja instalada no banco."""
    try:
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db.commit()
        logger.info("Extensão pgvector verificada/criada com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao garantir extensão pgvector: {e}")
        raise
    
