"""
SQLAlchemy model for storing extracted entity mentions.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import String, DateTime, Float, ForeignKey, JSON, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class EntityMention(Base):
    """
    SQLAlchemy model for storing entity mentions extracted from document chunks.
    
    Attributes:
        id: Primary key (UUID string)
        document_id: Foreign key to Document model
        chunk_id: The chunk ID from which the mention was extracted
        mention_id: Local chunk-specific mention identifier (e.g., m_001)
        surface_text: Exact text match in document chunk
        entity_type: Broad taxonomy family of the entity
        subtype: Specific type/role subtype
        mention_form: Grammatical form of mention (e.g. PROPER_NAME, DEFINED_TERM)
        resolution_status: Status of resolution (e.g. UNRESOLVED)
        canonical_name_hint: Optional hint for entity resolver
        attributes: Custom attributes dictionary
        provenance: Location and citation context dictionary
        start_char: Exact start character offset in the chunk
        end_char: Exact end character offset in the chunk
        confidence: Extraction confidence score (0.0 to 1.0)
        agent_name: Name of the extraction agent
        agent_version: Version of the agent
        prompt_version: Version of the prompt/skill
        model_name: Name of the model used for extraction
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    
    __tablename__ = "entity_mentions"
    
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
    
    mention_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    
    surface_text: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    
    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    subtype: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    mention_form: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    resolution_status: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="UNRESOLVED",
    )
    
    canonical_name_hint: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    
    provenance: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    
    start_char: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    
    end_char: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    
    confidence: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )
    
    agent_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    agent_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    
    prompt_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    
    model_name: Mapped[str] = mapped_column(
        String(100),
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
    
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_id",
            "start_char",
            "end_char",
            "entity_type",
            name="uq_entity_mentions_provenance"
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"EntityMention(id={self.id}, "
            f"document_id={self.document_id}, "
            f"chunk_id={self.chunk_id}, "
            f"mention_id={self.mention_id}, "
            f"surface_text={self.surface_text}, "
            f"entity_type={self.entity_type}, "
            f"offsets={self.start_char}-{self.end_char})"
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert mention to dict representation."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "mention_id": self.mention_id,
            "surface_text": self.surface_text,
            "entity_type": self.entity_type,
            "subtype": self.subtype,
            "mention_form": self.mention_form,
            "resolution_status": self.resolution_status,
            "canonical_name_hint": self.canonical_name_hint,
            "attributes": self.attributes,
            "provenance": self.provenance,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "confidence": self.confidence,
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "prompt_version": self.prompt_version,
            "model_name": self.model_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
