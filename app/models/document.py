import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    state = Column(String(50), nullable=False, index=True)
    document_type = Column(String(50), default="general")
    description = Column(Text, nullable=True)
    source = Column(String(50), default="admin")  # admin, user_contribution, scraping
    source_url = Column(String(500), nullable=True)
    file_path = Column(String(500), nullable=False)
    index_path = Column(String(500), nullable=True)
    status = Column(String(20), default="active")  # active, inactive, pending
    version = Column(Integer, default=1)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    uploader = relationship("User", foreign_keys=[uploaded_by])
    municipalities = relationship(
        "DocumentMunicipality", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentSuggestion(Base):
    __tablename__ = "document_suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    title = Column(String(255), nullable=False)
    state = Column(String(50), nullable=False)
    source_url = Column(String(500), nullable=True)
    file_path = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending, approved, rejected
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
