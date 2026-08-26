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
        from backend.services.chunking.database import get_chunks_by_document
        from backend.agents.chunk_context_agent import analyze_chunk
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
            
            # Merge small chunks (< 200 words) with neighbors to reduce API calls
            from backend.agents.chunk_context_agent import MIN_CHUNK_WORDS, MAX_MERGED_WORDS, merge_small_chunks
            merged_chunks = merge_small_chunks(chunks)
            
            logger.info(f"Merged {len(chunks)} chunks into {len(merged_chunks)} groups for analysis")
            logger.info(f"Chunk merging: MIN_WORDS={MIN_CHUNK_WORDS}, MAX_MERGED_WORDS={MAX_MERGED_WORDS}")
            
            analyzed_count = 0
            # Build a mapping of chunk_id to index for faster lookup
            chunk_id_to_index = {chunk.chunk_id: idx for idx, chunk in enumerate(chunks)}
            chunk_id_to_chunk = {chunk.chunk_id: chunk for chunk in chunks}
            
            # Iterate and analyze each merged chunk group
            for chunk_group in merged_chunks:
                current_chunk_ids = chunk_group["chunk_ids"]
                current_chunk_text = chunk_group["merged_text"]
                original_texts = chunk_group.get("original_texts", {})
                
                # Skip if no chunk IDs in this group
                if not current_chunk_ids:
                    logger.warning(f"Skipping chunk group with no chunk_ids")
                    continue
                
                # Get previous/next text from non-merged chunks for context
                # Find the position of the first and last chunk in this group
                first_chunk_id = current_chunk_ids[0]
                last_chunk_id = current_chunk_ids[-1]
                
                first_chunk_idx = chunk_id_to_index.get(first_chunk_id, 0)
                last_chunk_idx = chunk_id_to_index.get(last_chunk_id, len(chunks) - 1)
                
                # Get previous chunk (from original list, not in this group)
                prev_idx = first_chunk_idx - 1
                previous_text = None
                if prev_idx >= 0:
                    prev_chunk = chunk_id_to_chunk.get(chunks[prev_idx].chunk_id)
                    if prev_chunk and prev_chunk.chunk_id not in current_chunk_ids:
                        previous_text = prev_chunk.content
                
                # Get next chunk (from original list, not in this group)
                next_idx = last_chunk_idx + 1
                next_text = None
                if next_idx < len(chunks):
                    next_chunk = chunk_id_to_chunk.get(chunks[next_idx].chunk_id)
                    if next_chunk and next_chunk.chunk_id not in current_chunk_ids:
                        next_text = next_chunk.content
                
                try:
                    # Run the agent on the merged chunk group
                    # Pass the first chunk_id as the representative
                    analyze_chunk(
                        current_chunk_id=current_chunk_ids[0],
                        current_chunk_text=current_chunk_text,
                        document_id=document_id,
                        previous_chunk_text=previous_text,
                        next_chunk_text=next_text,
                        document_metadata=document_metadata,
                        db_session=db,
                        merged_chunk_ids=current_chunk_ids,
                        is_merged=len(current_chunk_ids) > 1
                    )
                    analyzed_count += 1
                except Exception as e:
                    logger.error(f"Failed to analyze chunk group {current_chunk_ids}: {e}", exc_info=True)
                    # Continue analyzing other chunks even if one fails
            
            logger.info(f"Successfully analyzed {analyzed_count}/{len(chunks)} chunks for document {document_id}")
            
            return {
                "status": "success",
                "document_id": document_id,
                "chunks_count": len(chunks),
                "analyzed_count": analyzed_count,
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
