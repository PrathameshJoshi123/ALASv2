"""
SQLAlchemy models for storing structured contract analysis results, obligations, and risks.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import String, DateTime, Boolean, Float, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


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
