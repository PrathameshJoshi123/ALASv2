"""
Database persistence layer for saving chunks to the database.

Saves LangChain Document objects as Chunk SQLAlchemy models with
foreign key relationship to the Document model.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, Integer, String, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.documents import Document


class Chunk(Base):
    """
    SQLAlchemy model for storing document chunks.
    
    Each chunk represents a processed unit of text from a PDF document,
    with full traceability back to the original elements and pages.
    
    Attributes:
        id: Primary key (UUID string)
        document_id: Foreign key to Document model
        chunk_id: Unique chunk identifier
        content: The text content of the chunk
        chunk_metadata: JSON field with all metadata (section info, page ranges, etc.)
        page_start: First page number in this chunk
        page_end: Last page number in this chunk
        unit_type: Type of logical unit (section, clause, table, etc.)
        source_element_ids: JSON list of original Unstructured element IDs
        sequence_number: Sequential order number within the document (1, 2, 3, ...)
        created_at: Timestamp when chunk was created
    """
    
    __tablename__ = "chunks"
    
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
    )
    
    chunk_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default={},
        nullable=False,
    )
    
    page_start: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    page_end: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    unit_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    source_element_ids: Mapped[list[str]] = mapped_column(
        JSON,
        default=[],
        nullable=False,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationship to parent Document (forward reference)
    document: Mapped[Optional["Document"]] = relationship(
        "Document",
        back_populates="chunks",
        lazy="joined",
    )
    
    def __repr__(self) -> str:
        return (
            f"Chunk(id={self.id}, "
            f"document_id={self.document_id}, "
            f"sequence={self.sequence_number}, "
            f"unit_type={self.unit_type}, "
            f"page_start={self.page_start}, "
            f"page_end={self.page_end})"
        )
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert chunk to dictionary representation.
        
        Returns:
            Dictionary with all chunk data
        """
        return {
            "id": self.id,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "content": self.content,
            "metadata": self.chunk_metadata,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "unit_type": self.unit_type,
            "source_element_ids": self.source_element_ids,
            "sequence_number": self.sequence_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def save_chunks_to_db(
    documents: list[Any],
    document_id: str,
    db_session: Any,
) -> list[Chunk]:
    """
    Save LangChain Document objects to the database as Chunk models.
    
    Args:
        documents: List of LangChain Document objects (or dicts with page_content and metadata)
        document_id: The parent document ID
        db_session: SQLAlchemy database session
        
    Returns:
        List of saved Chunk objects
    """
    chunks = []
    
    for idx, doc in enumerate(documents, start=1):
        # Extract data from LangChain Document or dict
        if hasattr(doc, "page_content"):
            content = doc.page_content
            metadata = getattr(doc, "metadata", {})
        elif isinstance(doc, dict):
            content = doc.get("page_content", "")
            metadata = doc.get("metadata", {})
        else:
            # Skip invalid documents
            continue
        
        # Create Chunk object with sequential number
        chunk = Chunk(
            id=str(uuid.uuid4()),
            document_id=document_id,
            chunk_id=metadata.get("chunk_id", str(uuid.uuid4())),
            content=content,
            chunk_metadata=metadata,
            page_start=metadata.get("page_start"),
            page_end=metadata.get("page_end"),
            unit_type=metadata.get("chunk_type"),
            source_element_ids=metadata.get("source_element_ids", []),
            sequence_number=idx,
        )
        
        db_session.add(chunk)
        chunks.append(chunk)
    
    db_session.commit()
    
    return chunks


def get_chunks_by_document(
    document_id: str,
    db_session: Any,
) -> list[Chunk]:
    """
    Retrieve all chunks for a document.
    
    Args:
        document_id: The document ID to query
        db_session: SQLAlchemy database session
        
    Returns:
        List of Chunk objects for the document, ordered by sequence_number
    """
    from sqlalchemy import select
    
    result = db_session.execute(
        select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.sequence_number)
    )
    return result.scalars().all()


def delete_chunks_by_document(
    document_id: str,
    db_session: Any,
) -> int:
    """
    Delete all chunks for a document.
    
    Args:
        document_id: The document ID to delete chunks for
        db_session: SQLAlchemy database session
        
    Returns:
        Number of chunks deleted
    """
    from sqlalchemy import delete
    
    result = db_session.execute(
        delete(Chunk).where(Chunk.document_id == document_id)
    )
    db_session.commit()
    return result.rowcount
