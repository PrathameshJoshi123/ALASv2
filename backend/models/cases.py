import uuid
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import String, DateTime, Text, ForeignKey, JSON, Boolean, Float, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class Case(Base):
    """
    SQLAlchemy model representing a legal case.
    """
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="created",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    documents: Mapped[list["CaseDocument"]] = relationship(
        "CaseDocument",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    timelines: Mapped[list["CaseTimeline"]] = relationship(
        "CaseTimeline",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    analyses: Mapped[list["CaseAnalysis"]] = relationship(
        "CaseAnalysis",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    agent_memories: Mapped[list["CaseAgentMemory"]] = relationship(
        "CaseAgentMemory",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Case(id={self.id}, title={self.title}, status={self.status})"


class CaseDocument(Base):
    """
    SQLAlchemy model representing a document uploaded under a specific Case.
    """
    __tablename__ = "case_documents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
    )
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
    file_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    document_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="uploaded",
        nullable=False,
    )
    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    case: Mapped["Case"] = relationship("Case", back_populates="documents")
    chunks: Mapped[list["CaseDocumentChunk"]] = relationship(
        "CaseDocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    evidence_details: Mapped[list["EvidenceDetail"]] = relationship(
        "EvidenceDetail",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"CaseDocument(id={self.id}, case_id={self.case_id}, name={self.name}, type={self.document_type})"


class CaseDocumentChunk(Base):
    """
    SQLAlchemy model for storing chunks of case documents.
    """
    __tablename__ = "case_document_chunks"

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
        ForeignKey("case_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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

    document: Mapped["CaseDocument"] = relationship("CaseDocument", back_populates="chunks")

    def __repr__(self) -> str:
        return f"CaseDocumentChunk(id={self.id}, document_id={self.document_id}, sequence={self.sequence_number})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "content": self.content,
            "metadata": self.chunk_metadata,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "sequence_number": self.sequence_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EvidenceDetail(Base):
    """
    SQLAlchemy model caching the processed description, OCR text, and timeline metadata of images.
    """
    __tablename__ = "evidence_details"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
    )
    case_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("case_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    image_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    extracted_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    visual_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    key_objects: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    timeline_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    detected_timeline_event: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    document: Mapped["CaseDocument"] = relationship("CaseDocument", back_populates="evidence_details")

    def __repr__(self) -> str:
        return f"EvidenceDetail(id={self.id}, doc_id={self.case_document_id}, page={self.page_number})"


class CaseTimeline(Base):
    """
    SQLAlchemy model representing an extracted event in the case timeline.
    """
    __tablename__ = "case_timelines"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
    )
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    event_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    source_document_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("case_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_page: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    citation_quote: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    case: Mapped["Case"] = relationship("Case", back_populates="timelines")

    def __repr__(self) -> str:
        return f"CaseTimeline(id={self.id}, case_id={self.case_id}, date={self.event_date})"


class CaseAnalysis(Base):
    """
    SQLAlchemy model storing final and intermediate structured reports generated by the agents.
    """
    __tablename__ = "case_analyses"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
    )
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    content: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default={},
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    case: Mapped["Case"] = relationship("Case", back_populates="analyses")

    def __repr__(self) -> str:
        return f"CaseAnalysis(id={self.id}, case_id={self.case_id}, type={self.analysis_type})"


class CaseAgentMemory(Base):
    """
    SQLAlchemy model for storing persistent memories for agents across reiterations.
    """
    __tablename__ = "case_agent_memories"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
    )
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    memory_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    memory_value: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default={},
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    case: Mapped["Case"] = relationship("Case", back_populates="agent_memories")

    def __repr__(self) -> str:
        return f"CaseAgentMemory(id={self.id}, case_id={self.case_id}, agent={self.agent_name}, key={self.memory_key})"
