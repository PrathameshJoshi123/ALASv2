"""
Contract Analysis Routes.

Handles PDF contract upload, storage, and processing for legal document analysis.
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
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


class CreateDraftRequest(BaseModel):
    """Request schema for creating a prompt-only contract draft."""
    contract_prompt: str = Field(..., description="Drafting requirements, values, and guidelines")
    contract_type: str | None = Field(default="Custom Contract", description="Type or title of the contract")
    company_name: str | None = Field(default=None, description="Company name")
    counterparty_name: str | None = Field(default=None, description="Counterparty name")


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
        )
        
        logger.info(f"Drafting task {task.id} queued for document {document_id}")
        
        return TaskSubmitResponse(
            task_id=task.id,
            status="queued",
            message=f"Contract drafting task queued for document {document_id}",
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
        )
        
        logger.info(f"Drafting task {task.id} submitted for document {document_id}")
        
        return TaskSubmitResponse(
            task_id=task.id,
            status="queued",
            message=f"Contract drafting task queued for document {document_id}",
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
            auto_chunk=False,
        )
        
        logger.info(f"Agent-only drafting task {task.id} submitted for document {document_id}")
        
        return TaskSubmitResponse(
            task_id=task.id,
            status="queued",
            message=f"Agent-only contract drafting task queued for document {document_id}",
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
    
    # Check task status
    try:
        from celery.result import AsyncResult
        
        task_result = AsyncResult(task_id, app=celery_app)
        
        return TaskStatusResponse(
            task_id=task_id,
            status=task_result.status,
            result=task_result.result if task_result.ready else None,
            state=task_result.state,
            successful=task_result.successful() if task_result.ready else False,
        )
        
    except Exception as e:
        logger.error(f"Failed to check task status {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check task status: {e}",
        )


def _get_document_live_status(doc_id: str, db_status: str | None = None) -> tuple[str, dict[str, bool]]:
    output_json = Path("backend/storage/output") / f"{doc_id}.json"
    report_json = Path("backend/storage/outputs") / f"{doc_id}_analysis_report.json"
    
    markdown_ready = output_json.exists()
    result_ready = report_json.exists()
    final_analysis_ready = report_json.exists()
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
    
    status_str, live_dict = _get_document_live_status(document.id, document.status)
    
    from backend.services.contract_analysis_service import get_contract_analysis_from_db
    db_analysis = get_contract_analysis_from_db(document.id) or {}
    
    draft_md_file = Path("backend/storage/outputs") / f"{document.id}_drafted_contract.md"
    if draft_md_file.exists():
        try:
            draft_content = draft_md_file.read_text(encoding="utf-8")
            db_analysis["analysis_markdown"] = draft_content
        except Exception as e:
            logger.warning(f"Failed to read drafted contract markdown for document {document.id}: {e}")
    
    return DocumentResponse(
        id=document.id,
        name=document.name,
        original_filename=document.name,
        markdown_file=f"{document.id}.json",
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
        status_str, live_dict = _get_document_live_status(doc.id, doc.status)
        db_analysis = get_contract_analysis_from_db(doc.id) or {}
        res_list.append(
            DocumentResponse(
                id=doc.id,
                name=doc.name,
                original_filename=doc.name,
                markdown_file=f"{doc.id}.json",
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

        agent = create_retrieval_agent()
        prompt_msg = (
            f"Target Document ID: '{document_id}'\n\n"
            f"Question: {request.question}\n\n"
            f"Instructions:\n"
            f"1. Call search_chunks_vector_db or search_chunks_bm25 using document_id '{document_id}' to retrieve relevant sections.\n"
            f"2. If needed, call get_surrounding_chunks or get_chunk_by_sequence to read surrounding context.\n"
            f"3. Synthesize a complete grounded answer with citations. If no relevant info is found, state that directly."
        )
        
        state = agent.invoke({"messages": [HumanMessage(content=prompt_msg)]})
        agent_result = state.get("structured_response") or state.get("response")
        
        answer_text = ""
        citations = []
        
        if agent_result:
            if hasattr(agent_result, "model_dump"):
                res_dict = agent_result.model_dump()
                answer_text = res_dict.get("answer", "")
                citations = res_dict.get("citations", [])
                if not answer_text and res_dict.get("unresolved_parts"):
                    answer_text = "Based on the contract document, the following details could not be resolved:\n" + "\n".join(f"- {u}" for u in res_dict["unresolved_parts"])
            elif isinstance(agent_result, dict):
                answer_text = agent_result.get("answer", "")
                citations = agent_result.get("citations", [])
                if not answer_text and agent_result.get("unresolved_parts"):
                    answer_text = "Based on the contract document, the following details could not be resolved:\n" + "\n".join(f"- {u}" for u in agent_result["unresolved_parts"])
            else:
                answer_text = str(agent_result)
        
        if not answer_text:
            messages = state.get("messages", [])
            for msg in reversed(messages):
                if hasattr(msg, "type") and msg.type == "ai":
                    content = getattr(msg, "content", "")
                    if isinstance(content, str) and content.strip():
                        answer_text = content.strip()
                        break
                    elif isinstance(content, list):
                        text_parts = [
                            b.get("text", "") if isinstance(b, dict) else str(b)
                            for b in content
                            if not isinstance(b, dict) or b.get("type") == "text"
                        ]
                        extracted = "\n".join(filter(None, text_parts)).strip()
                        if extracted:
                            answer_text = extracted
                            break
        
        if not answer_text:
            answer_text = "Based on the provided contract document, no relevant information was found for your question."
            
        return {
            "status": "success",
            "document_id": document_id,
            "question": request.question,
            "answer": answer_text,
            "citations": citations,
        }
    except Exception as e:
        logger.error(f"Failed QA query for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run QA query: {e}",
        )


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
