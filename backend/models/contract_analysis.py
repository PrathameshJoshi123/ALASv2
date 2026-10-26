"""
SQLAlchemy models for storing structured contract analysis results, obligations, and risks.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import String, DateTime, Boolean, Float, Integer, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.documents import Document


class ContractAnalysis(Base):
    """
    SQLAlchemy model for storing contract analysis results.
    """
    __tablename__ = "contract_analysis"
    
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
        unique=True,  # One analysis per document
    )
    
    contract_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    parties: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    
    key_findings: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    
    unresolved_questions: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    
    overall_risk_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    
    critical_issues: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    
    high_issues: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    
    medium_issues: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    
    low_issues: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    
    recommended_actions: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    
    clauses: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    
    legal_sources: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    
    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    
    analysis_complete: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
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

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="analysis",
    )

    clauses_rel: Mapped[list["ContractClause"]] = relationship(
        "ContractClause",
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="ContractClause.clause_number",
    )

    obligations: Mapped[list["ContractObligation"]] = relationship(
        "ContractObligation",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    
    risks: Mapped[list["ContractRisk"]] = relationship(
        "ContractRisk",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"ContractAnalysis(id={self.id}, "
            f"document_id={self.document_id}, "
            f"contract_type={self.contract_type}, "
            f"complete={self.analysis_complete})"
        )


class ContractObligation(Base):
    """
    SQLAlchemy model for storing contract obligations.
    """
    __tablename__ = "contract_obligations"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
    )
    
    analysis_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("contract_analysis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    
    category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        default="General",
    )
    
    # Store other fields like actor, action, beneficiary, trigger, citation in details
    details: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    analysis: Mapped["ContractAnalysis"] = relationship(
        "ContractAnalysis",
        back_populates="obligations",
    )

    def __repr__(self) -> str:
        return f"ContractObligation(id={self.id}, doc_id={self.document_id})"


class ContractRisk(Base):
    """
    SQLAlchemy model for storing contract risks.
    """
    __tablename__ = "contract_risks"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
    )
    
    analysis_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("contract_analysis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    
    severity: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        default="General",
    )
    
    # Store other fields like affected_party, mechanism, evidence, mitigations in details
    details: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    analysis: Mapped["ContractAnalysis"] = relationship(
        "ContractAnalysis",
        back_populates="risks",
    )

    def __repr__(self) -> str:
        return f"ContractRisk(id={self.id}, severity={self.severity})"


class ContractClause(Base):
    """
    SQLAlchemy model for storing structured, parsed, and analyzed contract clauses.
    Enables relational querying, severity indexing, and clause-level redrafting history.
    """
    __tablename__ = "contract_clauses"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
    )

    analysis_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("contract_analysis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    clause_number: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    clause_type: Mapped[str] = mapped_column(
        String(100),
        default="General",
        nullable=False,
    )

    section_title: Mapped[str] = mapped_column(
        String(255),
        default="Clause",
        nullable=False,
    )

    raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    original_raw_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    severity: Mapped[str] = mapped_column(
        String(50),
        default="LOW",  # CRITICAL, HIGH, MEDIUM, LOW, INFO, REVISED_SAFE
        nullable=False,
        index=True,
    )

    risk_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    legal_reasoning: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    confidence_score: Mapped[float] = mapped_column(
        Float,
        default=0.85,
        nullable=False,
    )

    is_revised: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    revision_rationale: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    revised_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    analysis: Mapped["ContractAnalysis"] = relationship(
        "ContractAnalysis",
        back_populates="clauses_rel",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "document_id": self.document_id,
            "clause_number": self.clause_number,
            "clause_type": self.clause_type,
            "section_title": self.section_title,
            "raw_text": self.raw_text,
            "original_raw_text": self.original_raw_text,
            "severity": self.severity,
            "risk_description": self.risk_description or "",
            "legal_reasoning": self.legal_reasoning or "",
            "confidence_score": float(self.confidence_score) if self.confidence_score is not None else 0.85,
            "is_revised": bool(self.is_revised),
            "revision_rationale": self.revision_rationale or "",
            "revised_at": self.revised_at.isoformat() if self.revised_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"ContractClause(id={self.id}, num={self.clause_number}, title={self.section_title}, severity={self.severity})"


class ContractChatMessage(Base):
    """
    SQLAlchemy model for storing Ask Jurist contract Q&A conversations.
    """
    __tablename__ = "contract_chat_messages"

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

    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    citations: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "question": self.question,
            "answer": self.answer,
            "citations": self.citations or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
