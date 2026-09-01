"""
Document model for storing PDF contracts and their metadata.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign

from backend.database import Base

if TYPE_CHECKING:
    from backend.services.chunking.database import Chunk
    from backend.models.contract_analysis import ContractAnalysis


class Document(Base):
    """
    Document model representing uploaded PDF contracts.
    
    Attributes:
        id: Unique identifier for the document (UUID string)
        name: Original name of the document
        storage_link: Path to the stored PDF file
        date_created: Timestamp when the document was uploaded
        chunks: Relationship to Chunk models (processed chunks from this document)
    """
    
    __tablename__ = "documents"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    storage_link: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    counterparty_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    contract_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        default="Service Agreement",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="uploaded",
        nullable=False,
    )
    
    # Relationship to chunks (using forward reference to avoid circular import)
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    
    # Relationship to analysis (one-to-one)
    analysis: Mapped[Optional["ContractAnalysis"]] = relationship(
        "ContractAnalysis",
        primaryjoin="Document.id == foreign(ContractAnalysis.document_id)",
        uselist=False,
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"Document(id={self.id}, name={self.name}, status={self.status}, storage_link={self.storage_link})"
