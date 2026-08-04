from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class DocumentType(Base):
    __tablename__ = "document_types"

    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    state = Column(String(50), nullable=False, index=True)
    level = Column(String(20), nullable=False)
    priority = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
