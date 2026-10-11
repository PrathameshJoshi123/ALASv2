"""
Database service layer for retrieving and saving contract analysis results.
"""

import uuid
import logging
from typing import Any, Optional
from sqlalchemy import select
from backend.database import SessionLocal
from backend.models.contract_analysis import ContractAnalysis, ContractObligation, ContractRisk

logger = logging.getLogger(__name__)


def get_contract_analysis_from_db(document_id: str) -> Optional[dict[str, Any]]:
    """
    Retrieve contract analysis, obligations, and risks from the database for a document.
    
    Args:
        document_id: Unique identifier for the document
        
    Returns:
        Dict representing the analysis, or None if not found
    """
    with SessionLocal() as db:
        # Fetch the analysis
        stmt = select(ContractAnalysis).where(ContractAnalysis.document_id == document_id)
        analysis = db.execute(stmt).scalar_one_or_none()
        
        if not analysis:
            return None
            
        # Fetch obligations
        stmt_ob = select(ContractObligation).where(ContractObligation.document_id == document_id)
        obligations = db.execute(stmt_ob).scalars().all()
        
        # Fetch risks
        stmt_risk = select(ContractRisk).where(ContractRisk.document_id == document_id)
        risks = db.execute(stmt_risk).scalars().all()
        
        # Format clauses array
        raw_clauses = getattr(analysis, "clauses", []) or []
        formatted_clauses = []
        for idx, c in enumerate(raw_clauses):
            if isinstance(c, dict):
                formatted_clauses.append({
                    "id": c.get("id") or str(idx + 1),
                    "clause_number": c.get("clause_number", idx + 1),
                    "clause_type": c.get("clause_type", "general"),
                    "section_title": c.get("section_title", f"Clause {idx + 1}"),
                    "raw_text": c.get("raw_text", ""),
                    "severity": str(c.get("severity", "LOW")).upper(),
                    "risk_description": c.get("risk_description", ""),
                    "legal_reasoning": c.get("legal_reasoning", ""),
                    "confidence_score": float(c.get("confidence_score", 85.0)),
                })

        return {
            "id": analysis.id,
            "document_id": analysis.document_id,
            "contract_type": analysis.contract_type,
            "parties": analysis.parties,
            "overall_risk_score": getattr(analysis, "overall_risk_score", 0.0) or 0.0,
            "critical_issues": getattr(analysis, "critical_issues", 0) or 0,
            "high_issues": getattr(analysis, "high_issues", 0) or 0,
            "medium_issues": getattr(analysis, "medium_issues", 0) or 0,
            "low_issues": getattr(analysis, "low_issues", 0) or 0,
            "recommended_actions": getattr(analysis, "recommended_actions", []) or [],
            "clauses": formatted_clauses,
            "key_findings": analysis.key_findings,
            "unresolved_questions": analysis.unresolved_questions,
            "confidence": analysis.confidence,
            "analysis_complete": analysis.analysis_complete,
            "summary": analysis.summary,
            "analysis_summary": analysis.summary,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            "updated_at": analysis.updated_at.isoformat() if analysis.updated_at else None,
            "obligations": [
                {
                    "id": ob.id,
                    "description": ob.description,
                    "category": getattr(ob, "category", None) or (ob.details.get("category") if isinstance(ob.details, dict) else None) or "General",
                    "details": ob.details
                }
                for ob in obligations
            ],
            "risks": [
                {
                    "id": r.id,
                    "description": r.description,
                    "category": getattr(r, "category", None) or (r.details.get("category") if isinstance(r.details, dict) else None) or "General",
                    "severity": r.severity,
                    "details": r.details
                }
                for r in risks
            ]
        }


def save_contract_analysis_to_db(document_id: str, analysis_data: dict[str, Any], overwrite: bool = True) -> dict[str, Any]:
    """
    Save contract analysis results, obligations, and risks to the database.
    Strictly checks if analysis already exists to avoid duplicate storing.
    
    Args:
        document_id: Unique identifier for the document
        analysis_data: Dictionary containing contract_type, parties, key_findings,
                       overall_risk_score, issue counts, recommended_actions, clauses,
                       obligations, risks, unresolved_questions, confidence, summary.
        overwrite: If True, deletes existing analysis before saving.
                       
    Returns:
        Dict with status of the operation
    """
    with SessionLocal() as db:
        # Check if analysis already exists
        stmt = select(ContractAnalysis).where(ContractAnalysis.document_id == document_id)
        existing = db.execute(stmt).scalar_one_or_none()
        
        if existing:
            if not overwrite:
                logger.warning(f"Analysis for document {document_id} already exists. Skipping save to prevent duplicates.")
                return {
                    "status": "skipped",
                    "message": "Analysis already exists for this document. No repeated storing allowed to prevent database clutter.",
                    "analysis_id": existing.id,
                    "document_id": document_id
                }
            else:
                logger.info(f"Analysis for document {document_id} already exists. Deleting it to overwrite.")
                db.delete(existing)
                db.commit()
            
        try:
            # Prepare clauses
            raw_clauses = analysis_data.get("clauses", [])
            clauses_json = []
            crit_count = 0
            high_count = 0
            med_count = 0
            low_count = 0

            for idx, c in enumerate(raw_clauses):
                if isinstance(c, dict):
                    sev = str(c.get("severity", "LOW")).upper()
                    if sev == "CRITICAL":
                        crit_count += 1
                    elif sev == "HIGH":
                        high_count += 1
                    elif sev == "MEDIUM":
                        med_count += 1
                    else:
                        low_count += 1
                    clauses_json.append(c)
                elif hasattr(c, "model_dump"):
                    c_dict = c.model_dump()
                    sev = str(c_dict.get("severity", "LOW")).upper()
                    if sev == "CRITICAL":
                        crit_count += 1
                    elif sev == "HIGH":
                        high_count += 1
                    elif sev == "MEDIUM":
                        med_count += 1
                    else:
                        low_count += 1
                    clauses_json.append(c_dict)

            # Issue counts override if provided in analysis_data
            critical_issues = int(analysis_data.get("critical_issues") or crit_count)
            high_issues = int(analysis_data.get("high_issues") or high_count)
            medium_issues = int(analysis_data.get("medium_issues") or med_count)
            low_issues = int(analysis_data.get("low_issues") or low_count)

            # Calculate risk score if not explicitly set
            raw_score = analysis_data.get("overall_risk_score")
            if raw_score is None or float(raw_score) == 0.0:
                overall_risk_score = min(100.0, float(critical_issues * 30 + high_issues * 20 + medium_issues * 10 + low_issues * 5))
            else:
                overall_risk_score = float(raw_score)

            # Create analysis record
            analysis_id = str(uuid.uuid4())
            analysis = ContractAnalysis(
                id=analysis_id,
                document_id=document_id,
                contract_type=analysis_data.get("contract_type"),
                parties=analysis_data.get("parties", []),
                overall_risk_score=overall_risk_score,
                critical_issues=critical_issues,
                high_issues=high_issues,
                medium_issues=medium_issues,
                low_issues=low_issues,
                recommended_actions=analysis_data.get("recommended_actions", []),
                clauses=clauses_json,
                key_findings=analysis_data.get("key_findings", []),
                unresolved_questions=analysis_data.get("unresolved_questions", []),
                confidence=float(analysis_data.get("confidence", 0.85)),
                analysis_complete=analysis_data.get("analysis_complete", True),
                summary=analysis_data.get("summary") or analysis_data.get("analysis_summary") or ""
            )
            db.add(analysis)
            
            # Save obligations
            raw_obligations = analysis_data.get("obligations", [])
            for ob in raw_obligations:
                category = "General"
                if isinstance(ob, str):
                    description = ob
                    details = {}
                elif isinstance(ob, dict):
                    description = ob.get("description", ob.get("text", str(ob)))
                    category = ob.get("category", "General")
                    details = {k: v for k, v in ob.items() if k not in ["description", "text"]}
                elif hasattr(ob, "model_dump"):
                    ob_dict = ob.model_dump()
                    description = ob_dict.get("description", str(ob_dict))
                    category = ob_dict.get("category", "General")
                    details = {k: v for k, v in ob_dict.items() if k != "description"}
                else:
                    description = str(ob)
                    details = {}
                    
                obligation = ContractObligation(
                    id=str(uuid.uuid4()),
                    analysis_id=analysis_id,
                    document_id=document_id,
                    description=description,
                    category=category,
                    details=details
                )
                db.add(obligation)
                
            # Save risks
            raw_risks = analysis_data.get("risks", [])
            for r in raw_risks:
                severity = None
                category = "General"
                if isinstance(r, str):
                    description = r
                    details = {}
                elif isinstance(r, dict):
                    description = r.get("description", r.get("text", str(r)))
                    severity = r.get("severity")
                    category = r.get("category", "General")
                    details = {k: v for k, v in r.items() if k not in ["description", "text", "severity"]}
                elif hasattr(r, "model_dump"):
                    r_dict = r.model_dump()
                    description = r_dict.get("description", str(r_dict))
                    severity = r_dict.get("severity")
                    category = r_dict.get("category", "General")
                    details = {k: v for k, v in r_dict.items() if k not in ["description", "severity"]}
                else:
                    description = str(r)
                    details = {}
                    
                risk = ContractRisk(
                    id=str(uuid.uuid4()),
                    analysis_id=analysis_id,
                    document_id=document_id,
                    description=description,
                    category=category,
                    severity=severity,
                    details=details
                )
                db.add(risk)
                
            db.commit()
            logger.info(f"Saved analysis results for document {document_id} to database.")
            return {
                "status": "success",
                "message": "Analysis, obligations, and risks saved successfully.",
                "analysis_id": analysis_id,
                "document_id": document_id
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save contract analysis for document {document_id}: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Failed to save to database: {e}"
            }
