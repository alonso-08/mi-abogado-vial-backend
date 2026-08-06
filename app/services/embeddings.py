import json
import logging
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.embedding import DocumentEmbedding

logger = logging.getLogger(__name__)


def store_embeddings(
    db: Session,
    document_id: UUID,
    chunks: list,
    embeddings: list[list[float]],
) -> int:
    """
    Store document chunks with their embeddings in PostgreSQL.

    Args:
        db: Database session
        document_id: UUID of the parent document
        chunks: List of LangChain Document objects
        embeddings: List of embedding vectors (one per chunk)

    Returns:
        int: Number of embeddings stored
    """
    count = 0
    for chunk, embedding in zip(chunks, embeddings):
        metadata = {
            "state": chunk.metadata.get("state", ""),
            "municipality": chunk.metadata.get("municipality", "general"),
            "page": chunk.metadata.get("page", 0),
            "source": chunk.metadata.get("source", ""),
        }

        db.add(
            DocumentEmbedding(
                document_id=document_id,
                content=chunk.page_content,
                page_number=chunk.metadata.get("page"),
                embedding=embedding,
                metadata_=metadata,
            )
        )
        count += 1

    db.commit()
    logger.info(f"Stored {count} embeddings for document {document_id}")
    return count


def search_similar(
    db: Session,
    query_embedding: list[float],
    state: str,
    municipality: Optional[str] = None,
    k: int = 6,
) -> list:
    """
    Search for similar document chunks using cosine distance.

    Args:
        db: Database session
        query_embedding: Query vector
        state: Mexican state to filter by
        municipality: Optional municipality to filter by
        k: Number of results to return

    Returns:
        List of (content, metadata, distance) tuples
    """
    embedding_str = str(query_embedding)

    if municipality:
        sql = text("""
            SELECT content, metadata, embedding <=> :embedding AS distance
            FROM document_embeddings
            WHERE document_id IN (
                SELECT id FROM documents WHERE status = 'active'
            )
            AND metadata->>'state' = :state
            AND (metadata->>'municipality' = :municipality OR metadata->>'municipality' = 'general')
            ORDER BY embedding <=> :embedding
            LIMIT :k
        """)
        params = {
            "embedding": embedding_str,
            "state": state,
            "municipality": municipality,
            "k": k,
        }
    else:
        sql = text("""
            SELECT content, metadata, embedding <=> :embedding AS distance
            FROM document_embeddings
            WHERE document_id IN (
                SELECT id FROM documents WHERE status = 'active'
            )
            AND metadata->>'state' = :state
            AND metadata->>'municipality' = 'general'
            ORDER BY embedding <=> :embedding
            LIMIT :k
        """)
        params = {"embedding": embedding_str, "state": state, "k": k}

    results = db.execute(sql, params).fetchall()
    return results


def delete_document_embeddings(db: Session, document_id: UUID) -> bool:
    """
    Delete all embeddings for a document.

    Args:
        db: Database session
        document_id: UUID of the document to delete embeddings for

    Returns:
        bool: True if successful
    """
    try:
        db.query(DocumentEmbedding).filter(
            DocumentEmbedding.document_id == document_id
        ).delete()
        db.commit()
        logger.info(f"Deleted embeddings for document {document_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting embeddings: {e}")
        db.rollback()
        return False


def get_embedding_count(db: Session, document_id: UUID) -> int:
    """Get the number of embeddings for a document."""
    return db.query(DocumentEmbedding).filter(
        DocumentEmbedding.document_id == document_id
    ).count()
