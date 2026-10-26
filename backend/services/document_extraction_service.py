"""
Document Extraction Service.

Provides database persistence and retrieval for parsed PDF elements and extracted text.
Replaces legacy disk-based element files (backend/storage/output/{document_id}.json).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import select

from backend.database import SessionLocal
from backend.models.document_extraction import DocumentExtraction
from backend.models.documents import Document

logger = logging.getLogger(__name__)


def save_document_extraction_to_db(
    document_id: str,
    elements: List[Dict[str, Any]],
    filename: Optional[str] = None,
    extracted_text: Optional[str] = None,
    status: str = "COMPLETED",
) -> Dict[str, Any]:
    """
    Save or update parsed PDF document elements and extracted text directly in the database.
    """
    clean_elements = elements or []
    
    # Synthesize plain extracted text if not provided
    if extracted_text is None:
        text_lines = []
        for el in clean_elements:
            if isinstance(el, dict):
                t = el.get("text", "").strip()
                if t:
                    text_lines.append(t)
        final_text = "\n\n".join(text_lines)
    else:
        final_text = extracted_text

    with SessionLocal() as db:
        stmt = select(DocumentExtraction).where(DocumentExtraction.document_id == document_id)
        extraction = db.execute(stmt).scalar_one_or_none()

        if extraction:
            extraction.elements_count = len(clean_elements)
            extraction.elements = clean_elements
            extraction.extracted_text = final_text
            extraction.status = status
            if filename:
                extraction.filename = filename
            extraction.updated_at = datetime.utcnow()
            logger.info(f"Updated document extraction in DB for {document_id} ({len(clean_elements)} elements)")
        else:
            extraction = DocumentExtraction(
                document_id=document_id,
                filename=filename,
                elements_count=len(clean_elements),
                elements=clean_elements,
                extracted_text=final_text,
                status=status,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(extraction)
            logger.info(f"Created new document extraction in DB for {document_id} ({len(clean_elements)} elements)")

        db.commit()
        db.refresh(extraction)
        return extraction.to_dict()


def get_document_extraction_from_db(document_id: str, db: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve parsed document extraction records from the database.
    Supports reusing an existing database session.
    """
    if db is not None:
        stmt = select(DocumentExtraction).where(DocumentExtraction.document_id == document_id)
        extraction = db.execute(stmt).scalar_one_or_none()
        return extraction.to_dict() if extraction else None

    with SessionLocal() as session:
        stmt = select(DocumentExtraction).where(DocumentExtraction.document_id == document_id)
        extraction = session.execute(stmt).scalar_one_or_none()
        return extraction.to_dict() if extraction else None


def has_document_extraction_in_db(document_id: str, db: Optional[Any] = None) -> bool:
    """
    Check if a document already has parsed extraction records stored in the database.
    """
    if db is not None:
        stmt = select(DocumentExtraction.id).where(DocumentExtraction.document_id == document_id)
        return db.execute(stmt).scalar_one_or_none() is not None

    with SessionLocal() as session:
        stmt = select(DocumentExtraction.id).where(DocumentExtraction.document_id == document_id)
        return session.execute(stmt).scalar_one_or_none() is not None


def get_markdown_from_extraction(document_id: str, db: Optional[Any] = None) -> Optional[str]:
    """
    Synthesize markdown representation from parsed elements stored in the database.
    """
    extraction = get_document_extraction_from_db(document_id, db=db)
    if not extraction:
        return None

    elements = extraction.get("elements", [])
    if not elements:
        return extraction.get("extracted_text") or None

    lines = []
    for el in elements:
        if isinstance(el, dict):
            txt = el.get("text", "").strip()
            if not txt:
                continue
            el_type = el.get("type", "")
            if el_type == "Title":
                lines.append(f"\n### {txt}\n")
            elif el_type == "Header":
                lines.append(f"\n#### {txt}\n")
            else:
                lines.append(txt)

    return "\n\n".join(lines).strip() if lines else None
