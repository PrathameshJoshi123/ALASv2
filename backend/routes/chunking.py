"""
Chunking Routes for processing PDF elements into retrievable chunks.

Provides endpoints for:
- Triggering chunking of processed PDF elements
- Getting chunking status
- Retrieving chunks for a document
- Re-chunking with custom configuration
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.celery_app import celery_app
from backend.database import get_db
from backend.models.documents import Document
from backend.schemas.response_schemas import (
    DocumentResponse,
)
from backend.schemas.task_schemas import (
    TaskStatusResponse,
    TaskSubmitResponse,
)
from backend.tasks.chunking_tasks import (
    chunk_document_task,
    rechunk_document_task,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chunking", tags=["chunking"])


@router.post(
    "/{document_id}/chunk",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger chunking of a document",
    description="Submit a document for chunking. Processes the PDF elements into retrievable chunks for embeddings and citations.",
)
def chunk_document(
    document_id: str,
    strategy: Optional[str] = None,
    db: Session = Depends(get_db),
) -> TaskSubmitResponse:
    """
    Trigger chunking of a processed PDF document.
    
    This endpoint queues the document's processed elements for chunking.
    The chunking pipeline:
    1. Normalizes Unstructured elements
    2. Marks noise (headers, footers, page numbers)
    3. Detects logical boundaries (sections, clauses, tables)
    4. Builds logical units
    5. Splits oversized units
    6. Creates LangChain Documents with full traceability
    7. Saves to database with pdf_id foreign key
    
    Args:
        document_id: Unique identifier of the document to chunk
        strategy: Chunking strategy to use ("layout_aware" or "recursive")
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
    
    # Check if processed elements exist
    import json
    from pathlib import Path
    
    output_dir = Path("backend/storage/output")
    output_file = output_dir / f"{document_id}.json"
    
    if not output_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Processed elements not found for document {document_id}. "
                   f"Please process the PDF first.",
        )
    
    # Load elements from file
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            output_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load elements for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load processed elements: {e}",
        )
    
    elements = output_data.get("elements", [])
    if not elements:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No elements found in processed output for document {document_id}",
        )
    
    # Submit task to Celery
    try:
        logger.info(f"Submitting chunking task for document: {document_id} with strategy: {strategy}")
        
        task = chunk_document_task.delay(
            document_id=document.id,
            elements=elements,
            filename=document.name,
            config={"strategy": strategy} if strategy else None,
        )
        
        logger.info(f"Chunking task {task.id} submitted for document {document_id}")
        
        return TaskSubmitResponse(
            task_id=task.id,
            status="queued",
            message=f"Chunking task queued for document {document_id}",
        )
        
    except Exception as e:
        logger.error(f"Failed to submit chunking task for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue chunking task: {e}",
        )


@router.get(
    "/{document_id}/chunk/status/{task_id}",
    response_model=TaskStatusResponse,
    summary="Get chunking task status",
    description="Check the status of a chunking task.",
)
def get_chunking_status(
    document_id: str,
    task_id: str,
    db: Session = Depends(get_db),
) -> TaskStatusResponse:
    """
    Get the status of a chunking task.
    
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
        logger.error(f"Failed to check chunking task status {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check task status: {e}",
        )


@router.get(
    "/{document_id}/chunks",
    summary="List all chunks for a document",
    description="Retrieve all processed chunks for a document.",
)
def get_document_chunks(
    document_id: str,
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    Get all chunks for a document.
    
    Args:
        document_id: Unique identifier of the document
        db: Database session
        
    Returns:
        List of chunk dictionaries with content and metadata
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
    
    # Get chunks
    try:
        from backend.services.chunking.database import get_chunks_by_document
        
        chunks = get_chunks_by_document(document_id, db)
        
        # Convert to dictionaries
        return [chunk.to_dict() for chunk in chunks]
        
    except Exception as e:
        logger.error(f"Failed to get chunks for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chunks: {e}",
        )


@router.post(
    "/{document_id}/rechunk",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-chunk a document",
    description="Re-process a document's chunks with new configuration. Deletes existing chunks first.",
)
def rechunk_document(
    document_id: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    max_unit_size: Optional[int] = None,
    strategy: Optional[str] = None,
    db: Session = Depends(get_db),
) -> TaskSubmitResponse:
    """
    Re-chunk a document with custom configuration.
    
    This endpoint:
    1. Deletes existing chunks for the document
    2. Re-processes the elements with new configuration
    3. Saves new chunks
    
    Args:
        document_id: Unique identifier of the document to re-chunk
        chunk_size: Target chunk size in characters (default: 800)
        chunk_overlap: Overlap between chunks (default: 100)
        max_unit_size: Maximum logical unit size before splitting (default: 2000)
        strategy: Chunking strategy to use ("layout_aware" or "recursive")
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
    
    # Build config
    config = {}
    if chunk_size is not None:
        config["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        config["chunk_overlap"] = chunk_overlap
    if max_unit_size is not None:
        config["max_unit_size"] = max_unit_size
    if strategy is not None:
        config["strategy"] = strategy
    
    # Submit task to Celery
    try:
        logger.info(f"Submitting re-chunking task for document: {document_id} with strategy: {strategy}")
        
        task = rechunk_document_task.delay(
            document_id=document.id,
            config=config if config else None,
        )
        
        logger.info(f"Re-chunking task {task.id} submitted for document {document_id}")
        
        return TaskSubmitResponse(
            task_id=task.id,
            status="queued",
            message=f"Re-chunking task queued for document {document_id}",
        )
        
    except Exception as e:
        logger.error(f"Failed to submit re-chunking task for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue re-chunking task: {e}",
        )


@router.delete(
    "/{document_id}/chunks",
    summary="Delete all chunks for a document",
    description="Delete all processed chunks for a document.",
)
def delete_document_chunks(
    document_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Delete all chunks for a document.
    
    Args:
        document_id: Unique identifier of the document
        db: Database session
        
    Returns:
        Dictionary with deletion count
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
    
    # Delete chunks
    try:
        from backend.services.chunking.database import delete_chunks_by_document
        
        deleted_count = delete_chunks_by_document(document_id, db)
        
        # Delete chunks from Chroma DB
        try:
            from backend.services.vector_storage import delete_chunks_from_vector_db
            delete_chunks_from_vector_db(document_id)
        except Exception as e:
            logger.error(f"Failed to delete chunks from Chroma DB for document {document_id}: {e}")
            raise e
        
        return {
            "status": "success",
            "document_id": document_id,
            "deleted_count": deleted_count,
            "message": f"Deleted {deleted_count} chunks for document {document_id}",
        }
        
    except Exception as e:
        logger.error(f"Failed to delete chunks for document {document_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete chunks: {e}",
        )


@router.post(
    "/{document_id}/extract-mentions",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger entity & mention extraction for a document",
    description="Submit a document's chunks for parallel entity and mention extraction.",
)
def extract_document_mentions(
    document_id: str,
    db: Session = Depends(get_db),
) -> TaskSubmitResponse:
    """
    Trigger entity & mention extraction.
    
    Args:
        document_id: Unique identifier of the document
        db: Database session
        
    Returns:
        TaskSubmitResponse with Celery task ID
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
        from backend.tasks.entity_mention_tasks import analyze_document_entities_task
        
        task = analyze_document_entities_task.delay(document_id=document_id)
        
        return TaskSubmitResponse(
            task_id=task.id,
            status="queued",
            message=f"Entity mention extraction task queued for document {document_id}",
        )
    except Exception as e:
        logger.error(f"Failed to submit mention extraction task for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue mention extraction task: {e}",
        )


@router.get(
    "/{document_id}/mentions",
    summary="List all extracted entity mentions for a document",
    description="Retrieve all extracted entity mentions for a document.",
)
def get_document_mentions(
    document_id: str,
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    Get all extracted entity mentions for a document.
    
    Args:
        document_id: Unique identifier of the document
        db: Database session
        
    Returns:
        List of entity mention dictionaries
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
        from backend.models.entity_mention import EntityMention
        
        result = db.execute(
            select(EntityMention)
            .where(EntityMention.document_id == document_id)
            .order_by(EntityMention.chunk_id, EntityMention.start_char)
        )
        mentions = result.scalars().all()
        return [mention.to_dict() for mention in mentions]
    except Exception as e:
        logger.error(f"Failed to get mentions for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve mentions: {e}",
        )


from pydantic import BaseModel

class QAQueryRequest(BaseModel):
    query: str


@router.post(
    "/{document_id}/embed",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually generate vector embeddings for a document's chunks",
    description="Retrieve all chunks for the document sequentially from the relational database, embed them using nomic-embed-text, and store them in Chroma DB.",
)
def embed_document_chunks(
    document_id: str,
    db: Session = Depends(get_db),
) -> TaskSubmitResponse:
    """
    Manually retrieve database chunks for a document sequentially and save their embeddings in Chroma DB.
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
        from backend.tasks.chunking_tasks import embed_document_chunks_task
        
        # Submit Celery task
        task = embed_document_chunks_task.delay(document_id=document_id)
        
        return TaskSubmitResponse(
            task_id=task.id,
            status="queued",
            message=f"Manual embedding generation task queued for document {document_id}",
        )
    except Exception as e:
        logger.error(f"Failed to manually embed chunks for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to manually embed chunks: {str(e)}",
        )


@router.post(
    "/{document_id}/qa",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ask the retrieval agent a question about the document",
    description="Invokes the retrieval agent using vector search, BM25, and database context retrieval to answer the question.",
)
def question_answer_document(
    document_id: str,
    request: QAQueryRequest,
    db: Session = Depends(get_db),
) -> TaskSubmitResponse:
    """
    Ask a question about a document. The retrieval agent will plan, reason, retrieve, and answer.
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
        from backend.tasks.chunking_tasks import qa_retrieval_agent_task
        
        # Submit Celery task
        task = qa_retrieval_agent_task.delay(document_id=document_id, query=request.query)
        
        return TaskSubmitResponse(
            task_id=task.id,
            status="queued",
            message=f"QA retrieval agent task queued for document {document_id}",
        )
    except Exception as e:
        logger.error(f"QA agent invocation failed for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"QA agent failed: {str(e)}",
        )
