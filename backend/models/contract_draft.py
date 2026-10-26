"""
SQLAlchemy model for storing drafted contracts in the database.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import String, DateTime, Integer, Float, ForeignKey, JSON, Text, desc
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.documents import Document


class ContractDraft(Base):
    """
    SQLAlchemy model for storing contract drafting results, versions, and content.
    """
    __tablename__ = "contract_drafts"

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
        unique=True,  # One primary active draft record per document
    )

    contract_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    contract_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    parties: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    blueprint: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    legal_citations: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    review_comments: Mapped[list[Any]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    compliance_score: Mapped[float] = mapped_column(
        Float,
        default=90.0,
        nullable=False,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
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
        back_populates="draft",
    )

    # Relationship to Version History
    versions: Mapped[list["ContractDraftVersion"]] = relationship(
        "ContractDraftVersion",
        back_populates="draft",
        cascade="all, delete-orphan",
        order_by="desc(ContractDraftVersion.version_number)",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert model instance to dictionary representation."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "contract_title": self.contract_title,
            "contract_type": self.contract_type,
            "content": self.content,
            "parties": self.parties or [],
            "blueprint": self.blueprint or [],
            "legal_citations": self.legal_citations or [],
            "review_comments": self.review_comments or [],
            "compliance_score": float(self.compliance_score) if self.compliance_score is not None else 90.0,
            "version": int(self.version) if self.version is not None else 1,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"ContractDraft(id={self.id}, "
            f"document_id={self.document_id}, "
            f"version={self.version}, "
            f"title={self.contract_title})"
        )


class ContractDraftVersion(Base):
    """
    SQLAlchemy model for storing immutable snapshot versions of drafted contracts.
    Tracks each AI reiteration or manual edit with rationale and author type.
    """
    __tablename__ = "contract_draft_versions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
    )

    draft_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("contract_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    change_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_by: Mapped[str] = mapped_column(
        String(50),
        default="ai_orchestrator",  # 'ai_orchestrator', 'user_editor', 'reiteration'
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    draft: Mapped["ContractDraft"] = relationship(
        "ContractDraft",
        back_populates="versions",
    )

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="draft_versions",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert version instance to dictionary representation."""
        return {
            "id": self.id,
            "draft_id": self.draft_id,
            "document_id": self.document_id,
            "version_number": self.version_number,
            "content": self.content,
            "change_summary": self.change_summary,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"ContractDraftVersion(id={self.id}, "
            f"document_id={self.document_id}, "
            f"version_number={self.version_number}, "
            f"created_by={self.created_by})"
        )
