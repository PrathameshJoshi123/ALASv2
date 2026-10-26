"""
Contract Analysis Routes.

Handles PDF contract upload, storage, and processing for legal document analysis.
"""

import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.celery_app import celery_app
from backend.config import settings
from backend.database import get_db
from backend.models import Document
from backend.schemas.response_schemas import (
    DocumentResponse,
    DocumentUploadResponse,
    PDFElementResponse,
    PDFProcessingResponse,
)
from backend.schemas.task_schemas import TaskStatusResponse, TaskSubmitResponse
from backend.tasks import process_pdf_task, process_and_chunk_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF contract",
    description="Upload a PDF file for contract analysis. The file is stored with a unique document ID.",
)
def upload_contract(
    file: UploadFile = File(..., description="PDF file to upload"),
    counterparty_name: Annotated[str | None, Form()] = None,
    company_name: Annotated[str | None, Form()] = None,
    contract_type: Annotated[str | None, Form()] = None,
    contract_prompt: Annotated[str | None, Form()] = None,
    auto_analyze: Annotated[bool, Form()] = True,
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    """
    Upload a PDF contract for analysis or template drafting.
    """
    # Validate file is PDF
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted",
        )
    
    # Generate unique document ID
    document_id = str(uuid.uuid4())
    
    # Create storage path
    upload_dir = settings.UPLOAD_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Use document ID as filename to ensure uniqueness
    file_extension = Path(file.filename).suffix
    storage_filename = f"{document_id}{file_extension}"
    storage_path = upload_dir / storage_filename
    
    # Save file
    try:
        content = file.file.read()
        with storage_path.open("wb") as buffer:
            buffer.write(content)
        logger.info(f"Saved contract: {storage_path}")
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {e}",
        )
    
    # Store document metadata in database
    try:
        document = Document(
            id=document_id,
            name=file.filename,
            storage_link=str(storage_path),
            date_created=datetime.utcnow(),
            counterparty_name=counterparty_name,
            company_name=company_name,
            contract_type=contract_type or "Service Agreement",
            status="PROCESSING",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        logger.info(f"Created document record: {document_id}")
    except Exception as e:
        logger.error(f"Failed to create document record: {e}")
        if storage_path.exists():
            storage_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create document record: {e}",
        )
    
    # Auto-trigger full extraction + chunking + orchestrator agent analysis pipeline ONLY if auto_analyze is True and contract_type is NOT template
    task_id = None
    if auto_analyze and contract_type != "generation_template":
        try:
            logger.info(f"Auto-triggering background analysis pipeline for document {document_id}")
            task = process_and_chunk_task.delay(
                document_id=document.id,
                file_path=str(storage_path),
                filename=document.name,
            )
            task_id = task.id
            logger.info(f"Auto-triggered task {task_id} for uploaded document {document_id}")
        except Exception as task_err:
            logger.error(f"Failed to auto-trigger analysis task for document {document_id}: {task_err}")
    else:
        logger.info(f"Skipping auto-analysis pipeline for document {document_id} (contract_type: {contract_type}, auto_analyze: {auto_analyze})")

    return DocumentUploadResponse(
        status="success",
        document_id=document_id,
        document_name=file.filename,
        storage_path=str(storage_path),
        task_id=task_id,
        message="PDF contract uploaded and analysis pipeline auto-triggered successfully",
    )


@router.post(
    "/{document_id}/process",
    response_model=TaskSubmitResponse,
    summary="Process a PDF contract (async)",
    description="Submit a PDF contract for background processing. Extracts structured elements using Unstructured AND automatically chunks them for embeddings/retrieval.",
)
def process_contract(
    document_id: str,
    db: Session = Depends(get_db),
) -> TaskSubmitResponse:
    """
    Submit a PDF contract for background processing.
    
    This endpoint queues the PDF for processing using Celery workers.
    The processing:
    1. Extracts structured elements (Titles, Paragraphs, Tables, etc.)
    2. Automatically chunks them into logical units for embeddings/retrieval
    3. Saves chunks to database with full traceability
    
    The extraction and chunking preserve the document hierarchy for precise legal analysis.
    
    Args:
        document_id: Unique identifier of the document to process
        db: Database session
        
    Returns:
        TaskSubmitResponse with task ID for tracking
    """
    # Get document from database
    result = db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )
    
    # Check if file exists
    storage_path = Path(document.storage_link)
    if not storage_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF file not found at {storage_path}",
        )
    
    # Submit task to Celery - use the chained task that auto-triggers chunking
    try:
        logger.info(f"Submitting processing task for document: {document_id}")
        
        task = process_and_chunk_task.delay(
            document_id=document.id,
            file_path=str(storage_path),
            filename=document.name,
        )
        
        logger.info(f"Task {task.id} submitted for document {document_id} (includes auto-chunking)")
        
        return TaskSubmitResponse(
            task_id=task.id,
            status="queued",
            message=f"PDF processing + chunking task queued for document {document_id}",
        )
        
    except Exception as e:
        logger.error(f"Failed to submit processing task for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue PDF processing: {e}",
        )


@router.post(
    "/{document_id}/analyze",
    response_model=TaskSubmitResponse,
    summary="Trigger orchestrator agent analysis only",
    description="Trigger the orchestrator agent contract analysis on an already processed and chunked contract document.",
)
def analyze_contract_agent(
    document_id: str,
    db: Session = Depends(get_db),
) -> TaskSubmitResponse:
    """
    Trigger the orchestrator agent contract analysis only.
    
    This expects the document is already uploaded and chunked. It triggers
    the deep agent analysis background task.
    """
    # Get document from database
    result = db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )
        
    try:
        logger.info(f"Submitting agent-only analysis task for document: {document_id}")
        
        # Reset document status to PROCESSING so UI and polling reflect active work
        document.status = "PROCESSING"
        db.commit()

        # Import task locally to avoid circular dependencies
        from backend.tasks.pdf_tasks import run_agent_analysis_task
        
        task = run_agent_analysis_task.delay(document_id=document.id)
        
        logger.info(f"Agent-only task {task.id} submitted for document {document_id}")
        
        return TaskSubmitResponse(
            task_id=task.id,
            status="queued",
            message=f"Agent-only analysis task queued for document {document_id}",
        )
    except Exception as e:
        logger.error(f"Failed to submit agent analysis task for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue agent analysis: {e}",
        )


class DraftContractRequest(BaseModel):
    """Request schema for contract drafting."""
    drafting_instructions: str = Field(..., description="Drafting requirements, values, and guidelines")
    contract_type: str | None = Field(default=None, description="Contract type")
    company_name: str | None = Field(default=None, description="Company / Client name")
    counterparty_name: str | None = Field(default=None, description="Counterparty name")
    favor_party: str | None = Field(default="Balanced", description="Posture: Balanced, Client-Favored, Counterparty-Favored")
    governing_law: str | None = Field(default="Indian Contract Act, 1872", description="Governing statutory jurisdiction")
    drafting_style: str | None = Field(default="Institutional Legal", description="Drafting style: Institutional Legal, Plain English Commercial, Regulatory Strict")


class CreateDraftRequest(BaseModel):
    """Request schema for creating a prompt-only contract draft."""
    contract_prompt: str = Field(..., description="Drafting requirements, values, and guidelines")
    contract_type: str | None = Field(default="Custom Contract", description="Type or title of the contract")
    company_name: str | None = Field(default=None, description="Company / Client name")
    counterparty_name: str | None = Field(default=None, description="Counterparty name")
    favor_party: str | None = Field(default="Balanced", description="Posture: Balanced, Client-Favored, Counterparty-Favored")
    governing_law: str | None = Field(default="Indian Contract Act, 1872", description="Governing statutory jurisdiction")
    drafting_style: str | None = Field(default="Institutional Legal", description="Drafting style: Institutional Legal, Plain English Commercial, Regulatory Strict")


class ReiterateContractRequest(BaseModel):
    """Request schema for contract reiteration."""
    instructions: str = Field(..., description="Instructions / requested edits for the contract draft")


@router.post(
    "/draft/create",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new contract draft from prompt",
    description="Create a document entry and trigger the multi-agent contract drafting orchestrator without requiring a template upload.",
)
def create_draft_contract_endpoint(
    request: CreateDraftRequest,
    db: Session = Depends(get_db),
) -> TaskSubmitResponse:
    """
    Create a new document entry and trigger contract drafting for prompt-only generation.
    """
    document_id = str(uuid.uuid4())
    
    # Store document record in database
    try:
        clean_type = (request.contract_type or "Custom_Contract").replace(" ", "_")
        doc_name = f"{clean_type}_{document_id[:8]}.pdf"
        document = Document(
            id=document_id,
            name=doc_name,
            storage_link="",
            date_created=datetime.utcnow(),
            counterparty_name=request.counterparty_name,
            company_name=request.company_name,
            contract_type=request.contract_type or "Custom Contract",
            status="PROCESSING",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        logger.info(f"Created prompt-only draft document record: {document_id}")
    except Exception as e:
        logger.error(f"Failed to create document record for prompt draft: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create document record: {e}",
        )
        
    try:
        logger.info(f"Submitting drafting task for document: {document_id}")
        from backend.tasks import run_agent_drafting_task
        
        task = run_agent_drafting_task.delay(
            document_id=document.id,
            drafting_instructions=request.contract_prompt,
            contract_type=request.contract_type or "Custom Contract",
            company_name=request.company_name,
            counterparty_name=request.counterparty_name,
            favor_party=request.favor_party or "Balanced",
            governing_law=request.governing_law or "Indian Contract Act, 1872",
            drafting_style=request.drafting_style or "Institutional Legal",
        )
        
        logger.info(f"Drafting task {task.id} queued for document {document_id}")
        
        return TaskSubmitResponse(
            task_id=task.id,
            status="queued",
            message=f"Contract drafting task queued for document {document_id}",
            document_id=document.id,
        )
    except Exception as e:
        logger.error(f"Failed to submit contract drafting task for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue contract drafting: {e}",
        )


@router.post(
    "/{document_id}/draft",
    response_model=TaskSubmitResponse,
    summary="Trigger contract drafting agent",
    description="Trigger the multi-agent contract drafting orchestrator based on the template document ID and drafting instructions.",
)
def draft_contract_endpoint(
    document_id: str,
    request: DraftContractRequest,
    db: Session = Depends(get_db),
) -> TaskSubmitResponse:
    """
    Trigger the multi-agent contract drafting orchestrator.
    """
    # Verify document exists
    result = db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document template with ID {document_id} not found",
        )
        
    try:
        logger.info(f"Submitting drafting task for document template: {document_id}")
        
        # Import task locally to avoid circular dependencies
        from backend.tasks import run_agent_drafting_task
        
        task = run_agent_drafting_task.delay(
            document_id=document.id,
            drafting_instructions=request.drafting_instructions,
            contract_type=request.contract_type or document.contract_type or "Custom Contract",
            company_name=request.company_name or document.company_name,
            counterparty_name=request.counterparty_name or document.counterparty_name,
            favor_party=request.favor_party or "Balanced",
            governing_law=request.governing_law or "Indian Contract Act, 1872",
            drafting_style=request.drafting_style or "Institutional Legal",
        )
        
        logger.info(f"Drafting task {task.id} submitted for document {document_id}")
        
        return TaskSubmitResponse(
            task_id=task.id,
            status="queued",
            message=f"Contract drafting task queued for document {document_id}",
            document_id=document.id,
        )
    except Exception as e:
        logger.error(f"Failed to submit contract drafting task for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue contract drafting: {e}",
        )


@router.post(
    "/{document_id}/draft/agent",
    response_model=TaskSubmitResponse,
    summary="Trigger contract drafting agent only",
    description="Trigger the contract drafting agent on an already processed and chunked contract template document.",
)
def draft_contract_agent_only_endpoint(
    document_id: str,
    request: DraftContractRequest,
    db: Session = Depends(get_db),
) -> TaskSubmitResponse:
    """
    Trigger the contract drafting agent only.
    """
    # Verify document exists
    result = db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document template with ID {document_id} not found",
        )
        
    try:
        logger.info(f"Submitting agent-only drafting task for document template: {document_id}")
        
        # Import task locally to avoid circular dependencies
        from backend.tasks import run_agent_drafting_task
        
        task = run_agent_drafting_task.delay(
            document_id=document.id,
            drafting_instructions=request.drafting_instructions,
            contract_type=request.contract_type or document.contract_type or "Custom Contract",
            company_name=request.company_name or document.company_name,
            counterparty_name=request.counterparty_name or document.counterparty_name,
            favor_party=request.favor_party or "Balanced",
            governing_law=request.governing_law or "Indian Contract Act, 1872",
            drafting_style=request.drafting_style or "Institutional Legal",
            auto_chunk=False,
        )
        
        logger.info(f"Agent-only drafting task {task.id} submitted for document {document_id}")
        
        return TaskSubmitResponse(
            task_id=task.id,
            status="queued",
            message=f"Agent-only contract drafting task queued for document {document_id}",
            document_id=document.id,
        )
    except Exception as e:
        logger.error(f"Failed to submit contract drafting agent task for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue agent-only contract drafting: {e}",
        )


@router.get(
    "/{document_id}/process/status/{task_id}",
    response_model=TaskStatusResponse,
    summary="Get PDF processing status",
    description="Check the status of a PDF processing task.",
)
def get_processing_status(
    document_id: str,
    task_id: str,
    db: Session = Depends(get_db),
) -> TaskStatusResponse:
    """
    Get the status of a PDF processing task.
    
    Args:
        document_id: Unique identifier of the document
        task_id: Celery task ID
        db: Database session
        
    Returns:
        TaskStatusResponse with current task status and result
    """
    # Verify document exists if valid document_id is provided
    resolved_doc_id = None
    if document_id and document_id not in ("undefined", "null", ""):
        result = db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        if document:
            resolved_doc_id = document.id

    # Check task status
    try:
        from celery.result import AsyncResult
        
        task_result = AsyncResult(task_id, app=celery_app)
        
        # If document_id was not resolved from DB, check task info or result
        if not resolved_doc_id:
            info = task_result.info if hasattr(task_result, "info") else None
            if isinstance(info, dict):
                resolved_doc_id = info.get("document_id")
            elif isinstance(task_result.result, dict):
                resolved_doc_id = task_result.result.get("document_id")
        
        return TaskStatusResponse(
            task_id=task_id,
            status=task_result.status,
            result=task_result.result if task_result.ready else None,
            state=task_result.state,
            successful=task_result.successful() if task_result.ready else False,
            document_id=resolved_doc_id,
        )
        
    except Exception as e:
        logger.error(f"Failed to check task status {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check task status: {e}",
        )


def _get_document_live_status(
    doc_id: str,
    db_status: str | None = None,
    db: Session | None = None,
) -> tuple[str, dict[str, bool]]:
    # 1. Primary: Check database records directly
    db_analysis_ready = False
    db_extraction_ready = False
    db_draft_ready = False

    def check_records(session):
        nonlocal db_analysis_ready, db_draft_ready, db_extraction_ready
        from backend.models.contract_analysis import ContractAnalysis
        from backend.models.contract_draft import ContractDraft
        from backend.models.document_extraction import DocumentExtraction

        db_analysis_ready = session.execute(
            select(ContractAnalysis.id).where(
                ContractAnalysis.document_id == doc_id,
                ContractAnalysis.analysis_complete == True,
            )
        ).scalar_one_or_none() is not None

        db_draft_ready = session.execute(
            select(ContractDraft.id).where(ContractDraft.document_id == doc_id)
        ).scalar_one_or_none() is not None

        db_extraction_ready = session.execute(
            select(DocumentExtraction.id).where(DocumentExtraction.document_id == doc_id)
        ).scalar_one_or_none() is not None

    try:
        if db is not None:
            check_records(db)
        else:
            from backend.database import SessionLocal
            with SessionLocal() as session:
                check_records(session)
    except Exception:
        pass

    markdown_ready = db_extraction_ready
    result_ready = db_analysis_ready or db_draft_ready or (db_status == "COMPLETED")
    final_analysis_ready = db_analysis_ready or db_draft_ready or (db_status == "COMPLETED")
    vector_store_ready = markdown_ready

    # Secondary fallback for legacy documents processed before database migration
    if not result_ready:
        report_json = Path("backend/storage/outputs") / f"{doc_id}_analysis_report.json"
        draft_md = Path("backend/storage/outputs") / f"{doc_id}_drafted_contract.md"
        result_ready = report_json.exists() or draft_md.exists()
        final_analysis_ready = report_json.exists()

    if not markdown_ready:
        output_json = Path("backend/storage/output") / f"{doc_id}.json"
        markdown_ready = output_json.exists()
        vector_store_ready = markdown_ready

    status_str = "COMPLETED" if result_ready else (db_status or "PROCESSING")

    live_dict = {
        "markdown_ready": markdown_ready,
        "result_ready": result_ready,
        "final_analysis_ready": final_analysis_ready,
        "vector_store_ready": vector_store_ready,
    }
    return status_str, live_dict


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document information",
    description="Retrieve metadata for a stored document.",
)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """
    Get information about a stored document.
    """
    result = db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )
    
    status_str, live_dict = _get_document_live_status(document.id, document.status, db=db)
    
    from backend.services.contract_analysis_service import get_contract_analysis_from_db
    db_analysis = get_contract_analysis_from_db(document.id, db=db) or {}
    
    # Check drafted contract in database first
    from backend.services.contract_draft_service import get_draft_from_db
    draft_record = get_draft_from_db(document.id, db=db)
    if draft_record and draft_record.get("content"):
        draft_content = draft_record.get("content", "")
        # Strip accidental markdown code block fences
        draft_content = re.sub(r"^[ \t]*```[a-zA-Z0-9_-]*[ \t]*$", "", draft_content, flags=re.MULTILINE)
        draft_content = re.sub(r"\n{3,}", "\n\n", draft_content).strip()
        db_analysis["analysis_markdown"] = draft_content
        db_analysis["draft"] = draft_record
        if not db_analysis.get("contract_type") and draft_record.get("contract_type"):
            db_analysis["contract_type"] = draft_record.get("contract_type")
        if not db_analysis.get("parties") and draft_record.get("parties"):
            db_analysis["parties"] = draft_record.get("parties")

    if not db_analysis.get("analysis_markdown"):
        # Primary: Check parsed elements stored directly in the database
        try:
            from backend.services.document_extraction_service import get_markdown_from_extraction
            extracted_md = get_markdown_from_extraction(document.id, db=db)
            if extracted_md:
                db_analysis["analysis_markdown"] = extracted_md
        except Exception as ex:
            logger.warning(f"Could not extract markdown from DB extraction for {document.id}: {ex}")

    # Fallback to database chunks if still empty
    if not db_analysis.get("analysis_markdown"):
        try:
            from backend.services.chunking.database import Chunk
            chunks = db.execute(
                select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.sequence_number.asc())
            ).scalars().all()
            if chunks:
                chunk_texts = [c.content for c in chunks if c.content and c.content.strip()]
                if chunk_texts:
                    db_analysis["analysis_markdown"] = "\n\n".join(chunk_texts)
        except Exception as e:
            logger.warning(f"Failed to extract markdown from chunks for {document.id}: {e}")

    # Fallback to clauses text if still empty
    if not db_analysis.get("analysis_markdown") and db_analysis.get("clauses"):
        clause_blocks = []
        for c in db_analysis.get("clauses", []):
            if isinstance(c, dict):
                title = c.get("section_title") or f"Clause {c.get('clause_number', '')}"
                raw = c.get("raw_text", "")
                clause_blocks.append(f"### {title}\n\n{raw}")
        if clause_blocks:
            db_analysis["analysis_markdown"] = "\n\n".join(clause_blocks)
    
    return DocumentResponse(
        id=document.id,
        name=document.name,
        original_filename=document.name,
        markdown_file=f"{document.id}.md",
        storage_link=document.storage_link,
        date_created=document.date_created.isoformat(),
        created_at=document.date_created.isoformat(),
        counterparty_name=document.counterparty_name or "N/A",
        company_name=document.company_name or "Your Organization",
        contract_type=db_analysis.get("contract_type") or document.contract_type or "Service Agreement",
        status=status_str,
        live=live_dict,
        overall_risk_score=float(db_analysis.get("overall_risk_score", 0.0) or 0.0),
        critical_issues=int(db_analysis.get("critical_issues", 0) or 0),
        high_issues=int(db_analysis.get("high_issues", 0) or 0),
        medium_issues=int(db_analysis.get("medium_issues", 0) or 0),
        low_issues=int(db_analysis.get("low_issues", 0) or 0),
        analysis_summary=db_analysis.get("analysis_summary") or db_analysis.get("summary") or "",
        recommended_actions=db_analysis.get("recommended_actions", []),
        clauses=db_analysis.get("clauses", []),
        analysis=db_analysis,
        draft=db_analysis.get("draft"),
        analysis_markdown=db_analysis.get("analysis_markdown", ""),
    )


@router.get(
    "/",
    summary="List all documents",
    description="List all uploaded documents with their metadata and pagination.",
)
def list_documents(
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
):
    """
    List all uploaded documents with metadata and analysis.
    """
    result = db.execute(select(Document).order_by(Document.date_created.desc()))
    documents = result.scalars().all()
    
    from backend.services.contract_analysis_service import get_contract_analysis_from_db

    res_list = []
    for doc in documents:
        status_str, live_dict = _get_document_live_status(doc.id, doc.status, db=db)
        db_analysis = get_contract_analysis_from_db(doc.id, db=db) or {}
        res_list.append(
            DocumentResponse(
                id=doc.id,
                name=doc.name,
                original_filename=doc.name,
                markdown_file=f"{doc.id}.md",
                storage_link=doc.storage_link,
                date_created=doc.date_created.isoformat(),
                created_at=doc.date_created.isoformat(),
                counterparty_name=doc.counterparty_name or "N/A",
                company_name=doc.company_name or "Your Organization",
                contract_type=db_analysis.get("contract_type") or doc.contract_type or "Service Agreement",
                status=status_str,
                live=live_dict,
                overall_risk_score=float(db_analysis.get("overall_risk_score", 0.0) or 0.0),
                critical_issues=int(db_analysis.get("critical_issues", 0) or 0),
                high_issues=int(db_analysis.get("high_issues", 0) or 0),
                medium_issues=int(db_analysis.get("medium_issues", 0) or 0),
                low_issues=int(db_analysis.get("low_issues", 0) or 0),
                analysis_summary=db_analysis.get("analysis_summary") or db_analysis.get("summary") or "",
                recommended_actions=db_analysis.get("recommended_actions", []),
                clauses=db_analysis.get("clauses", []),
            )
        )
    
    total = len(res_list)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = res_list[start:end]
    
    return {
        "items": paginated_items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


class ContractQARequest(BaseModel):
    """Request schema for asking a question about a contract."""
    question: str = Field(..., description="Question to ask about the contract")


@router.post(
    "/{document_id}/qa",
    summary="Ask a question about a contract document (Jurist AI QA)",
    description="Ask a question about a contract document using the retrieval agent.",
)
def ask_contract_question_endpoint(
    document_id: str,
    request: ContractQARequest,
    db: Session = Depends(get_db),
):
    """
    Answer a question groundedly for a contract document.
    """
    result = db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )
    
    try:
        from langchain_core.messages import HumanMessage
        from backend.agents.retrieval_agent import create_retrieval_agent
        from backend.services.chunking.database import Chunk

        # 1. Check if document has chunks available for retrieval
        chunk_count = db.execute(
            select(func.count(Chunk.chunk_id)).where(Chunk.document_id == document_id)
        ).scalar() or 0

        if chunk_count == 0:
            return {
                "status": "warning",
                "document_id": document_id,
                "question": request.question,
                "answer": f"Document '{document.name}' has not been chunked or processed yet. Please run or wait for document processing/chunking to complete before asking questions.",
                "citations": [],
            }

        logger.info(f"Invoking LangGraph Jurist RAG for document {document_id} with question: {request.question}")
        from backend.agents.jurist_rag_langgraph import run_jurist_rag
        from backend.models.contract_analysis import ContractChatMessage
        
        result_payload = run_jurist_rag(document_id=document_id, question=request.question)
        
        # Save Q&A to database for persistent history
        try:
            chat_record = ContractChatMessage(
                id=str(uuid.uuid4()),
                document_id=document_id,
                question=request.question,
                answer=result_payload.get("answer", ""),
                citations=result_payload.get("citations", []),
            )
            db.add(chat_record)
            db.commit()
            result_payload["id"] = chat_record.id
            result_payload["created_at"] = chat_record.created_at.isoformat()
        except Exception as save_err:
            logger.warning(f"Could not persist contract chat message for doc {document_id}: {save_err}")
            db.rollback()

        return result_payload
    except Exception as e:
        logger.error(f"Failed QA query for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run QA query: {e}",
        )


@router.get(
    "/{document_id}/qa/history",
    summary="Get saved Ask Jurist Q&A chat history for a contract",
    description="Retrieve all saved questions, answers, and citations for a contract document.",
)
def get_contract_qa_history_endpoint(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve saved chat history for a contract."""
    from backend.models.contract_analysis import ContractChatMessage
    messages = db.execute(
        select(ContractChatMessage)
        .where(ContractChatMessage.document_id == document_id)
        .order_by(ContractChatMessage.created_at.asc())
    ).scalars().all()

    return {
        "status": "success",
        "document_id": document_id,
        "total_messages": len(messages),
        "history": [m.to_dict() for m in messages],
    }


@router.delete(
    "/{document_id}/qa/history",
    summary="Clear Ask Jurist Q&A chat history for a contract",
    description="Delete all saved Q&A messages for a contract document.",
)
def clear_contract_qa_history_endpoint(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Clear chat history for a contract."""
    from backend.models.contract_analysis import ContractChatMessage
    from sqlalchemy import delete
    db.execute(
        delete(ContractChatMessage).where(ContractChatMessage.document_id == document_id)
    )
    db.commit()
    return {
        "status": "success",
        "document_id": document_id,
        "message": "Chat history cleared successfully.",
    }



@router.post(
    "/{document_id}/reiterate",
    response_model=TaskSubmitResponse,
    summary="Reiterate and apply edits to drafted contract",
    description="Trigger the contract drafting orchestrator in reiteration mode to apply specific edits to an existing drafted contract based on user instructions.",
)
def reiterate_contract_endpoint(
    document_id: str,
    request: ReiterateContractRequest,
    db: Session = Depends(get_db),
) -> TaskSubmitResponse:
    """
    Trigger the contract reiteration/edit process.
    """
    # Verify document exists
    result = db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )
        
    try:
        logger.info(f"Submitting contract reiteration task for document: {document_id}")
        
        # Import task locally to avoid circular dependencies
        from backend.tasks import run_agent_reiteration_task
        
        task = run_agent_reiteration_task.delay(
            document_id=document.id,
            instructions=request.instructions,
        )
        
        logger.info(f"Reiteration task {task.id} submitted for document {document_id}")
        
        return TaskSubmitResponse(
            task_id=task.id,
            status="queued",
            message=f"Contract reiteration task queued for document {document_id}",
        )
    except Exception as e:
        logger.error(f"Failed to submit contract reiteration task for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue contract reiteration: {e}",
        )


@router.get(
    "/{document_id}/logs",
    summary="Retrieve live contract analysis agent execution logs",
    description="Fetch real-time agent thinking steps, LangGraph node progress, and Indian Kanoon tool calls.",
)
def get_contract_agent_logs(
    document_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Fetch all persistent agent thinking steps, tool calls, and LangGraph node transitions
    for a contract analysis task directly from the storage log file.
    """
    from pathlib import Path
    log_file_path = Path("backend/storage/logs") / f"{document_id}_agent_execution.log"
    all_logs = []
    is_complete = False
    
    if log_file_path.exists():
        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    line_str = line.strip()
                    if not line_str or line_str.startswith("="):
                        continue
                    
                    if "CONTRACT ANALYSIS COMPLETE" in line_str:
                        is_complete = True
                    
                    log_type = "info"
                    if "Tool Call:" in line_str or "Tool '" in line_str or "Autonomous Tool Call:" in line_str:
                        log_type = "tool_call"
                    elif "Step:" in line_str or "running node" in line_str or "LangGraph Engine" in line_str:
                        log_type = "node"
                    elif "AI Response" in line_str or "Finding" in line_str:
                        log_type = "finding"
                    elif "Indian Kanoon" in line_str:
                        log_type = "kanoon"

                    all_logs.append({
                        "agent_name": "ContractLangGraphOrchestrator",
                        "type": log_type,
                        "detail": line_str,
                    })
        except Exception as e:
            logger.warning(f"Error reading contract log file {log_file_path}: {e}")

    return {
        "document_id": document_id,
        "is_complete": is_complete,
        "total_logs": len(all_logs),
        "logs": all_logs,
    }


@router.get(
    "/{document_id}/draft/versions",
    summary="Retrieve contract draft version history",
    description="Fetch all historical snapshots/versions of a drafted contract from the database.",
)
def get_contract_draft_versions_endpoint(
    document_id: str,
) -> dict:
    """
    Retrieve historical revision snapshots of the contract draft from the database.
    """
    from backend.services.contract_draft_service import get_draft_versions_from_db
    versions = get_draft_versions_from_db(document_id)
    return {
        "document_id": document_id,
        "total_versions": len(versions),
        "versions": versions,
    }


@router.get(
    "/{document_id}/draft/stream",
    summary="Real-time SSE stream of contract drafting progress",
    description="Subscribe to live Server-Sent Events (SSE) emitting milestone updates, Indian Kanoon searches, and section completions.",
)
async def stream_contract_drafting(
    document_id: str,
):
    """
    Server-Sent Events endpoint streaming real-time milestones and log events for contract drafting.
    """
    from backend.services.drafting_stream_service import DraftingStreamService

    return StreamingResponse(
        DraftingStreamService.subscribe_stream(document_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{document_id}/draft/events",
    summary="Get all historical contract drafting events",
    description="Fetch the list of historical milestone events for a drafting or reiteration task (useful as a polling fallback).",
)
def get_contract_draft_events(
    document_id: str,
) -> dict:
    """
    Retrieve all recorded drafting milestone events for a document.
    """
    from backend.services.drafting_stream_service import DraftingStreamService
    events = DraftingStreamService.get_events(document_id)
    is_complete = any(e.get("is_complete") for e in events)
    return {
        "document_id": document_id,
        "total_events": len(events),
        "is_complete": is_complete,
        "events": events,
    }


@router.get(
    "/{document_id}/draft/logs",
    summary="Retrieve contract drafting execution logs",
    description="Read real-time drafting log file containing LangGraph milestone steps and tool outputs.",
)
def get_contract_draft_logs(
    document_id: str,
) -> dict:
    """
    Read persistent execution log file for drafting or reiteration.
    """
    from pathlib import Path
    log_dir = Path("backend/storage/logs")
    draft_log = log_dir / f"{document_id}_drafting_execution.log"
    reiter_log = log_dir / f"{document_id}_reiteration_execution.log"
    
    target_log = draft_log if draft_log.exists() else reiter_log
    all_logs = []
    is_complete = False

    if target_log.exists():
        try:
            with open(target_log, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if not line_str or line_str.startswith("="):
                        continue
                    if "LANGGRAPH CONTRACT DRAFTING COMPLETE" in line_str or "COMPLETE" in line_str:
                        is_complete = True
                    all_logs.append({
                        "agent_name": "ContractDraftingLangGraph",
                        "detail": line_str,
                    })
        except Exception as e:
            logger.warning(f"Error reading draft log {target_log}: {e}")

    return {
        "document_id": document_id,
        "is_complete": is_complete,
        "total_logs": len(all_logs),
        "logs": all_logs,
    }



# ============================================================
# Post-Analysis Contract Revision & Redlining Endpoints
# ============================================================

from backend.services.contract_revision_service import (
    RedraftClauseRequest,
    ClauseRevisionResponse,
    ApplyRevisionRequest,
    generate_clause_redraft,
    apply_clause_revision_to_db,
)


@router.post(
    "/{document_id}/redraft-clause",
    response_model=ClauseRevisionResponse,
    summary="Redraft a specific clause based on analysis and prompt instructions",
    description="Intelligently redraft a specific contract clause resolving flagged legal risks and honoring custom user instructions.",
)
def redraft_contract_clause_endpoint(
    document_id: str,
    request: RedraftClauseRequest,
    db: Session = Depends(get_db),
) -> ClauseRevisionResponse:
    """Redraft an analyzed contract clause with statutory compliance."""
    result = db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )

    try:
        revision_res = generate_clause_redraft(document_id, request)
        return revision_res
    except Exception as e:
        logger.error(f"Failed to redraft clause for doc {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate clause redraft: {e}",
        )


@router.post(
    "/{document_id}/apply-revision",
    summary="Apply an approved revised clause to the contract",
    description="Save an approved clause redraft to the document analysis record and update risk metrics.",
)
def apply_contract_revision_endpoint(
    document_id: str,
    request: ApplyRevisionRequest,
    db: Session = Depends(get_db),
):
    """Apply an approved clause amendment to the contract record."""
    result = db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )

    try:
        apply_res = apply_clause_revision_to_db(
            document_id=document_id,
            clause_id=request.clause_id,
            revised_text=request.revised_text,
            rationale=request.rationale or "",
        )
        if apply_res.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=apply_res.get("message"),
            )
        return apply_res
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply clause revision for doc {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply revision: {e}",
        )


class SaveContractContentRequest(BaseModel):
    content: str


@router.post(
    "/{document_id}/save-content",
    summary="Save user edited contract content",
    description="Save edited contract markdown content to database and update document timestamp.",
)
def save_contract_content_endpoint(
    document_id: str,
    request: SaveContractContentRequest,
    db: Session = Depends(get_db),
):
    """Save user edits from the contract editor."""
    from backend.services.contract_revision_service import save_contract_content
    result = db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )
    try:
        res = save_contract_content(document_id, request.content)
        return res
    except Exception as e:
        logger.error(f"Failed to save contract content for doc {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save contract content: {e}",
        )


