"""
Contract Draft Service.

Provides database persistence and retrieval for generated and edited contract drafts.
Replaces legacy disk-based markdown (.md) file persistence with robust DB storage.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from backend.database import SessionLocal
from backend.models.contract_draft import ContractDraft, ContractDraftVersion
from backend.models.documents import Document

logger = logging.getLogger(__name__)


def save_or_update_draft_in_db(
    document_id: str,
    content: str,
    contract_title: Optional[str] = None,
    contract_type: Optional[str] = None,
    parties: Optional[List[str]] = None,
    blueprint: Optional[List[dict]] = None,
    legal_citations: Optional[List[dict]] = None,
    review_comments: Optional[List[Any]] = None,
    compliance_score: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Save or update a contract draft in the database.
    Increments the version counter if an existing draft is updated.
    """
    cleaned_content = content or ""
    # Strip accidental wrapping markdown code fences if present
    cleaned_content = re.sub(r"^[ \t]*```[a-zA-Z0-9_-]*[ \t]*$", "", cleaned_content, flags=re.MULTILINE)
    cleaned_content = re.sub(r"\n{3,}", "\n\n", cleaned_content).strip()

    with SessionLocal() as db:
        # Check if draft record exists
        stmt = select(ContractDraft).where(ContractDraft.document_id == document_id)
        draft = db.execute(stmt).scalar_one_or_none()

        if draft:
            draft.content = cleaned_content
            if contract_title:
                draft.contract_title = contract_title
            if contract_type:
                draft.contract_type = contract_type
            if parties is not None:
                draft.parties = parties
            if blueprint is not None:
                draft.blueprint = blueprint
            if legal_citations is not None:
                draft.legal_citations = legal_citations
            if review_comments is not None:
                draft.review_comments = review_comments
            if compliance_score is not None:
                draft.compliance_score = float(compliance_score)
            draft.version = (draft.version or 1) + 1
            draft.updated_at = datetime.utcnow()
            logger.info(f"Updated contract draft in DB for document {document_id} (version {draft.version})")
        else:
            draft = ContractDraft(
                document_id=document_id,
                contract_title=contract_title or contract_type or "Contract",
                contract_type=contract_type or "Custom Contract",
                content=cleaned_content,
                parties=parties or [],
                blueprint=blueprint or [],
                legal_citations=legal_citations or [],
                review_comments=review_comments or [],
                compliance_score=float(compliance_score) if compliance_score is not None else 90.0,
                version=1,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(draft)
            logger.info(f"Created new contract draft in DB for document {document_id}")

        db.flush()

        # Record version snapshot history
        version_entry = ContractDraftVersion(
            draft_id=draft.id,
            document_id=document_id,
            version_number=draft.version,
            content=cleaned_content,
            change_summary=contract_title or contract_type or "Generated contract draft",
            created_by="ai_orchestrator",
            created_at=datetime.utcnow(),
        )
        db.add(version_entry)

        # Also update Document record status and timestamp if applicable
        doc_stmt = select(Document).where(Document.id == document_id)
        doc = db.execute(doc_stmt).scalar_one_or_none()
        if doc:
            doc.status = "COMPLETED"
            if contract_type:
                doc.contract_type = contract_type
            if parties and len(parties) >= 2:
                if not doc.company_name or doc.company_name in ("Your Organization", "Client", "Party A"):
                    doc.company_name = parties[0]
                if not doc.counterparty_name or doc.counterparty_name in ("N/A", "Counterparty", "Party B"):
                    doc.counterparty_name = parties[1]

        db.commit()
        db.refresh(draft)
        return draft.to_dict()


def get_draft_from_db(document_id: str, db: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve contract draft directly from the database.
    Supports reusing an existing database session for optimal connection pooling.
    """
    if db is not None:
        stmt = select(ContractDraft).where(ContractDraft.document_id == document_id)
        draft = db.execute(stmt).scalar_one_or_none()
        return draft.to_dict() if draft else None

    with SessionLocal() as session:
        stmt = select(ContractDraft).where(ContractDraft.document_id == document_id)
        draft = session.execute(stmt).scalar_one_or_none()
        return draft.to_dict() if draft else None


def update_draft_content(document_id: str, new_content: str) -> Dict[str, Any]:
    """
    Update the content of a contract draft directly in the database (e.g. from the web editor).
    Creates the draft record if it does not yet exist.
    """
    cleaned = new_content or ""
    with SessionLocal() as db:
        stmt = select(ContractDraft).where(ContractDraft.document_id == document_id)
        draft = db.execute(stmt).scalar_one_or_none()

        if draft:
            draft.content = cleaned
            draft.version = (draft.version or 1) + 1
            draft.updated_at = datetime.utcnow()

            version_entry = ContractDraftVersion(
                draft_id=draft.id,
                document_id=document_id,
                version_number=draft.version,
                content=cleaned,
                change_summary="User edited contract content",
                created_by="user_editor",
                created_at=datetime.utcnow(),
            )
            db.add(version_entry)

            db.commit()
            db.refresh(draft)
            logger.info(f"Updated contract draft content in DB for document {document_id} (v{draft.version})")
            return {
                "status": "success",
                "message": "Contract saved to database successfully.",
                "document_id": document_id,
                "version": draft.version,
            }
        else:
            # Create new draft entry with this content
            doc_stmt = select(Document).where(Document.id == document_id)
            doc = db.execute(doc_stmt).scalar_one_or_none()
            title = doc.name if doc else "Contract"
            ctype = doc.contract_type if doc else "Custom Contract"

            draft = ContractDraft(
                document_id=document_id,
                contract_title=title,
                contract_type=ctype,
                content=cleaned,
                version=1,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(draft)
            db.flush()

            version_entry = ContractDraftVersion(
                draft_id=draft.id,
                document_id=document_id,
                version_number=1,
                content=cleaned,
                change_summary="Initial contract created in editor",
                created_by="user_editor",
                created_at=datetime.utcnow(),
            )
            db.add(version_entry)

            db.commit()
            db.refresh(draft)
            logger.info(f"Created new contract draft in DB for document {document_id} from editor content")
            return {
                "status": "success",
                "message": "Contract created and saved to database successfully.",
                "document_id": document_id,
                "version": 1,
            }


def replace_text_in_draft(document_id: str, old_text: str, new_text: str) -> bool:
    """
    Replace a snippet (such as a redrafted clause) in the contract draft stored in DB.
    """
    if not old_text:
        return False

    with SessionLocal() as db:
        stmt = select(ContractDraft).where(ContractDraft.document_id == document_id)
        draft = db.execute(stmt).scalar_one_or_none()

        if draft and draft.content and old_text in draft.content:
            draft.content = draft.content.replace(old_text, new_text, 1)
            draft.version = (draft.version or 1) + 1
            draft.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Replaced text in DB contract draft for document {document_id} (v{draft.version})")
            return True

        return False


def get_draft_versions_from_db(document_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all historical snapshot versions of a contract draft from the database.
    """
    with SessionLocal() as db:
        stmt = (
            select(ContractDraftVersion)
            .where(ContractDraftVersion.document_id == document_id)
            .order_by(ContractDraftVersion.version_number.desc())
        )
        versions = db.execute(stmt).scalars().all()
        return [v.to_dict() for v in versions]
