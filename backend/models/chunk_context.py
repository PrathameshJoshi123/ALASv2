"""
SQLAlchemy model for storing chunk context memory.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import String, DateTime, Boolean, Float, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class ChunkContext(Base):
    """
    SQLAlchemy model for storing chunk contextual extraction memory.
    
    Each record represents context analyzed for a single document chunk,
    containing fields like section type, speaker, procedural stage, topics,
    legal domains, continuity indicators, dependencies, citations, and the raw JSON.
    """
    
    __tablename__ = "chunk_context"
    
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
        nullable=False,
        index=True,
    )
    
    section_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    speaker: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    procedural_stage: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    document_role: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    section_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    topics: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    
    legal_domains: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    
    context_dependencies: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    
    important_references: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    
    context_warnings: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    
    is_continuation: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    is_boundary_chunk: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    is_merged: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    merged_chunk_ids: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    
    confidence: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )
    
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    prompt_version: Mapped[str] = mapped_column(
        String(50),
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
    
    raw_output: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return (
            f"ChunkContext(id={self.id}, "
            f"document_id={self.document_id}, "
            f"chunk_id={self.chunk_id}, "
            f"section_type={self.section_type}, "
            f"speaker={self.speaker}, "
            f"merged={self.is_merged}, "
            f"confidence={self.confidence})"
        )
