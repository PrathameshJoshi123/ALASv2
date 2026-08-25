"""
Contract Analysis Routes.

Handles PDF contract upload, storage, and processing for legal document analysis.
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
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
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    """
    Upload a PDF contract for analysis.
    
    The PDF is stored in the uploads directory with a unique document ID.
    This document ID is used for all subsequent operations on the contract.
    
    Args:
        file: PDF file to upload
        db: Database session
        
    Returns:
        DocumentUploadResponse with document ID and storage path
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
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        logger.info(f"Created document record: {document_id}")
    except Exception as e:
        logger.error(f"Failed to create document record: {e}")
        # Clean up stored file if DB operation fails
        if storage_path.exists():
            storage_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create document record: {e}",
        )
    
    return DocumentUploadResponse(
        status="success",
        document_id=document_id,
        document_name=file.filename,
        storage_path=str(storage_path),
        message="PDF contract uploaded successfully",
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
    
    Args:
        document_id: Unique identifier of the document
        db: Database session
        
    Returns:
        DocumentResponse with document metadata
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
    
    return DocumentResponse(
        id=document.id,
        name=document.name,
        storage_link=document.storage_link,
        date_created=document.date_created.isoformat(),
    )


@router.get(
    "/",
    summary="List all documents",
    description="List all uploaded documents with their metadata.",
)
def list_documents(
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    """
    List all uploaded documents.
    
    Args:
        db: Database session
        
    Returns:
        List of DocumentResponse objects
    """
    result = db.execute(select(Document))
    documents = result.scalars().all()
    
    return [
        DocumentResponse(
            id=doc.id,
            name=doc.name,
            storage_link=doc.storage_link,
            date_created=doc.date_created.isoformat(),
        )
        for doc in documents
    ]
