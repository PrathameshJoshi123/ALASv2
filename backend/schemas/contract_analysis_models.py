"""
Pydantic Schemas for Contract Analysis.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator


def normalize_string_item(item: Any, item_type: str = "general") -> str:
    """Normalize a single item (string, dict, or primitive) to a readable string."""
    if item is None:
        return ""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, (int, float, bool)):
        return str(item)
    if isinstance(item, dict):
        if item_type == "party":
            name = item.get("name") or item.get("entity") or item.get("party") or ""
            role = item.get("role") or item.get("designation") or ""
            if name and role:
                return f"{name} ({role})".strip()
            if name:
                return str(name).strip()
            if role:
                return str(role).strip()

        if item_type == "finding":
            clause = item.get("clause") or item.get("section") or item.get("title") or ""
            finding = (
                item.get("finding")
                or item.get("description")
                or item.get("issue")
                or item.get("risk")
                or item.get("details")
                or item.get("explanation")
                or item.get("summary")
                or item.get("rationale")
                or item.get("text")
                or ""
            )
            severity = item.get("severity") or ""

            parts = []
            if severity:
                parts.append(f"[{str(severity).upper()}]")
            if clause and finding:
                if str(clause).lower() in str(finding).lower():
                    parts.append(str(finding).strip())
                else:
                    parts.append(f"{str(clause).strip()}: {str(finding).strip()}")
            elif finding:
                parts.append(str(finding).strip())
            elif clause:
                parts.append(str(clause).strip())

            if parts:
                return " ".join(parts).strip()

        if item_type == "action":
            action = (
                item.get("action")
                or item.get("recommendation")
                or item.get("recommendations")
                or item.get("suggestion")
                or item.get("remedy")
                or item.get("mitigation")
                or item.get("description")
                or item.get("step")
                or item.get("revision")
                or item.get("text")
                or ""
            )
            clause = item.get("clause") or item.get("section") or ""
            if clause and action and str(clause).lower() not in str(action).lower():
                return f"{str(clause).strip()}: {str(action).strip()}".strip()
            if action:
                return str(action).strip()

        if item_type == "question":
            question = (
                item.get("question")
                or item.get("query")
                or item.get("unresolved_question")
                or item.get("issue")
                or item.get("ambiguity")
                or item.get("clarification")
                or item.get("point")
                or item.get("text")
                or item.get("description")
                or ""
            )
            if question:
                return str(question).strip()

        # Fallback for generic dict: search all common text fields
        for key in (
            "finding", "action", "question", "description", "recommendation",
            "suggestion", "remedy", "mitigation", "issue", "risk", "query",
            "text", "summary", "details", "explanation", "clause", "name"
        ):
            if item.get(key) and isinstance(item[key], (str, int, float)):
                val = str(item[key]).strip()
                if val:
                    return val

        # If nothing matched, join string representation of key-values
        str_vals = [f"{k}: {v}" for k, v in item.items() if v and not isinstance(v, (dict, list))]
        if str_vals:
            return "; ".join(str_vals)
        return json.dumps(item)

    if isinstance(item, (list, tuple)):
        return ", ".join(filter(None, [normalize_string_item(x, item_type) for x in item]))

    return str(item).strip()


def normalize_string_list(items: Any, item_type: str = "general") -> List[str]:
    """Ensure input is converted into a list of non-empty strings."""
    if not items:
        return []
    if isinstance(items, str):
        return [items.strip()] if items.strip() else []
    if not isinstance(items, (list, tuple, set)):
        items = [items]

    result = []
    for it in items:
        s = normalize_string_item(it, item_type)
        if s:
            result.append(s)
    return result


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

    @field_validator("parties", mode="before")
    @classmethod
    def _validate_parties(cls, v: Any) -> List[str]:
        return normalize_string_list(v, "party")

    @field_validator("key_findings", mode="before")
    @classmethod
    def _validate_key_findings(cls, v: Any) -> List[str]:
        return normalize_string_list(v, "finding")

    @field_validator("recommended_actions", mode="before")
    @classmethod
    def _validate_recommended_actions(cls, v: Any) -> List[str]:
        return normalize_string_list(v, "action")

    @field_validator("unresolved_questions", mode="before")
    @classmethod
    def _validate_unresolved_questions(cls, v: Any) -> List[str]:
        return normalize_string_list(v, "question")
