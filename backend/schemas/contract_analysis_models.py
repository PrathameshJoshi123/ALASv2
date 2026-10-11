"""
Pydantic Schemas for Contract Analysis.
"""

from __future__ import annotations

import uuid
from typing import List, Optional
from pydantic import BaseModel, Field


class ClauseAnalysisItem(BaseModel):
    """Clause-by-clause analysis item."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    clause_number: int = 1
    clause_type: str = "general"
    section_title: str = "Clause"
    raw_text: str = ""
    severity: str = "LOW"  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    risk_description: str = ""
    legal_reasoning: str = ""
    confidence_score: float = 0.0


class ObligationItem(BaseModel):
    """Obligation item."""
    description: str = ""
    category: Optional[str] = Field(
        default="General",
        description="Category such as 'Payment & Financial', 'Performance & Delivery', 'Maintenance & Services', 'Compliance & Legal', 'General'"
    )
    actor: Optional[str] = None
    action: Optional[str] = None
    beneficiary: Optional[str] = None
    deadline: Optional[str] = None
    trigger: Optional[str] = None
    citation: Optional[str] = None


class RiskItem(BaseModel):
    """Risk item."""
    description: str = ""
    category: Optional[str] = Field(
        default="General",
        description="Category such as 'Financial & Payment', 'Construction & Title', 'Compliance & Legal', 'Operational & Facility', 'General'"
    )
    severity: Optional[str] = "MEDIUM"
    affected_party: Optional[str] = None
    mechanism: Optional[str] = None
    mitigation: Optional[str] = None
    citation: Optional[str] = None


class LegalSourceItem(BaseModel):
    """Researched Indian Kanoon Precedent or Statutory Source."""
    doc_id: str = ""
    title: str = ""
    url: str = ""
    statute_or_court: Optional[str] = None
    relevance_summary: str = ""
    key_provision_or_ratio: Optional[str] = None


class ContractAnalysisResult(BaseModel):
    """
    Final result produced by the contract analysis orchestrator.
    """
    contract_type: Optional[str] = None
    parties: List[str] = Field(default_factory=list)
    overall_risk_score: float = Field(
        default=0.0,
        description="Overall risk score percentage from 0.0 to 100.0",
    )
    critical_issues: int = 0
    high_issues: int = 0
    medium_issues: int = 0
    low_issues: int = 0
    key_findings: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    clauses: List[ClauseAnalysisItem] = Field(default_factory=list)
    obligations: List[ObligationItem] = Field(default_factory=list)
    risks: List[RiskItem] = Field(default_factory=list)
    legal_sources: List[LegalSourceItem] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
    )
    analysis_complete: bool = False
    summary: str = ""
