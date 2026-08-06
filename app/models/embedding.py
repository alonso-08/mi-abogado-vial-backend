import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import VECTOR
from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocumentEmbedding(Base):
    __tablename__ = "document_embeddings"

    id = Column(Integer, primary_key=True)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)
    page_number = Column(Integer)
    embedding = Column(VECTOR(384), nullable=False)  # all-MiniLM-L6-v2 produces 384 dimensions
    metadata_ = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
