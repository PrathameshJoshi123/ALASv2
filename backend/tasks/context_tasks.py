"""
Celery tasks for document chunk context analysis.
"""

import logging
from typing import Any

from backend.celery_app import celery_app
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@celery_app.task(bind=True, name="analyze_chunks_context_task")
def analyze_chunks_context_task(
    self,
    document_id: str,
) -> dict[str, Any]:
    """
    Background task to analyze the context of all chunks of a document.
    
    Args:
        document_id: Unique identifier for the document
        
    Returns:
        Dictionary with analysis results
    """
    try:
        logger.info(f"Starting chunk context analysis for document: {document_id}")
        
        # Import here to avoid circular imports
        from backend.database import SessionLocal
        from backend.models.documents import Document
        from sqlalchemy import select
        
        with SessionLocal() as db:
            # Verify document exists
            result = db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            if not document:
                return {
                    "status": "error",
                    "document_id": document_id,
                    "error": f"Document {document_id} not found",
                }
            
            document_metadata = {"filename": document.name}
            
            from backend.services.chunking.database import get_chunks_by_document
            # Fetch all chunks for this document
            chunks = get_chunks_by_document(document_id, db)
            if not chunks:
                logger.warning(f"No chunks found for document {document_id}")
                return {
                    "status": "success",
                    "document_id": document_id,
                    "analyzed_count": 0,
                    "message": "No chunks found to analyze",
                }
            
            logger.info(f"Found {len(chunks)} chunks to analyze for document {document_id}")
            
            # Fetch sequentially using the db helper
            from backend.agents.orchestrator_agent import get_optimized_chunks_from_db
            merged_chunks = get_optimized_chunks_from_db(document_id)
            
            logger.info(f"Merged {len(chunks)} chunks into {len(merged_chunks)} groups for analysis")
            
            # We no longer run chunk_context_agent since it was discarded.
            # Downstream context tasks should interact with the new orchestrator or specialists.
            results = merged_chunks
            
            logger.info(f"Successfully processed {len(results)} groups for document {document_id}")
            
            return {
                "status": "success",
                "document_id": document_id,
                "chunks_count": len(chunks),
                "analyzed_count": len(results),
            }
            
    except Exception as e:
        error_msg = f"Failed in chunk context analysis task: {e}"
        logger.error(f"Error in chunk context analysis task for document {document_id}: {e}", exc_info=True)
        return {
            "status": "error",
            "document_id": document_id,
            "error": error_msg,
        }


__all__ = ["analyze_chunks_context_task"]
