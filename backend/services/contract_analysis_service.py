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
        
        return {
            "id": analysis.id,
            "document_id": analysis.document_id,
            "contract_type": analysis.contract_type,
            "parties": analysis.parties,
            "key_findings": analysis.key_findings,
            "unresolved_questions": analysis.unresolved_questions,
            "confidence": analysis.confidence,
            "analysis_complete": analysis.analysis_complete,
            "summary": analysis.summary,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            "updated_at": analysis.updated_at.isoformat() if analysis.updated_at else None,
            "obligations": [
                {
                    "id": ob.id,
                    "description": ob.description,
                    "details": ob.details
                }
                for ob in obligations
            ],
            "risks": [
                {
                    "id": r.id,
                    "description": r.description,
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
            # Create analysis record
            analysis_id = str(uuid.uuid4())
            analysis = ContractAnalysis(
                id=analysis_id,
                document_id=document_id,
                contract_type=analysis_data.get("contract_type"),
                parties=analysis_data.get("parties", []),
                key_findings=analysis_data.get("key_findings", []),
                unresolved_questions=analysis_data.get("unresolved_questions", []),
                confidence=analysis_data.get("confidence", 0.0),
                analysis_complete=analysis_data.get("analysis_complete", True),
                summary=analysis_data.get("summary", "")
            )
            db.add(analysis)
            
            # Save obligations
            raw_obligations = analysis_data.get("obligations", [])
            for ob in raw_obligations:
                if isinstance(ob, str):
                    description = ob
                    details = {}
                elif isinstance(ob, dict):
                    description = ob.get("description", ob.get("text", str(ob)))
                    details = {k: v for k, v in ob.items() if k not in ["description", "text"]}
                else:
                    description = str(ob)
                    details = {}
                    
                obligation = ContractObligation(
                    id=str(uuid.uuid4()),
                    analysis_id=analysis_id,
                    document_id=document_id,
                    description=description,
                    details=details
                )
                db.add(obligation)
                
            # Save risks
            raw_risks = analysis_data.get("risks", [])
            for r in raw_risks:
                severity = None
                if isinstance(r, str):
                    description = r
                    details = {}
                elif isinstance(r, dict):
                    description = r.get("description", r.get("text", str(r)))
                    severity = r.get("severity")
                    details = {k: v for k, v in r.items() if k not in ["description", "text", "severity"]}
                else:
                    description = str(r)
                    details = {}
                    
                risk = ContractRisk(
                    id=str(uuid.uuid4()),
                    analysis_id=analysis_id,
                    document_id=document_id,
                    description=description,
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
