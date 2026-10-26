"""
SQLAlchemy model for storing parsed PDF document extractions.
Replaces legacy disk-based element JSON files (backend/storage/output/{document_id}.json).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import String, DateTime, Integer, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.documents import Document


class DocumentExtraction(Base):
    """
    SQLAlchemy model for storing structured elements and raw text
    extracted during document parsing.
    """
    __tablename__ = "document_extractions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
    )

    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,  # One primary extraction record per document
    )

    filename: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    elements_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    elements: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    extracted_text: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="COMPLETED",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationship to Document
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="extraction",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert model instance to dictionary representation."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "filename": self.filename,
            "elements_count": self.elements_count,
            "elements": self.elements or [],
            "extracted_text": self.extracted_text,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"DocumentExtraction(id={self.id}, "
            f"document_id={self.document_id}, "
            f"elements_count={self.elements_count}, "
            f"status={self.status})"
        )
