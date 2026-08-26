"""
Celery tasks for extracting entity mentions from document chunks.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from celery.utils.log import get_task_logger

from backend.celery_app import celery_app
from backend.database import SessionLocal
# Imports corrected (entity_mention_agent discarded)
from backend.models.documents import Document
from backend.models.chunk_context import ChunkContext

logger = get_task_logger(__name__)


@celery_app.task(bind=True, name="analyze_single_chunk_entities_task")
def analyze_single_chunk_entities_task(
    self,
    document_id: str,
    chunk_id: str,
    chunk_text: str,
    document_role: Optional[str] = None,
    chunk_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Celery task to analyze and extract mentions for a single chunk (Legacy stub).
    """
    return {
        "status": "success",
        "chunk_id": chunk_id,
        "mentions_count": 0,
    }


def _process_chunk_thread(
    document_id: str,
    chunk_id: str,
    chunk_text: str,
    document_role: Optional[str],
    chunk_context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Worker function run inside a thread pool to process one chunk (Legacy stub).
    """
    return {
        "status": "success",
        "chunk_id": chunk_id,
        "mentions_count": 0,
    }


@celery_app.task(bind=True, name="analyze_document_entities_task")
def analyze_document_entities_task(
    self,
    document_id: str,
) -> Dict[str, Any]:
    """
    Background task to extract entity mentions for all chunks of a document.
    Runs chunk extraction in parallel using dynamic subagent workflows.
    """
    try:
        logger.info(f"Starting entity mention extraction for document: {document_id}")
        
        with SessionLocal() as db:
            # 1. Verify document exists
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
            
            # Fetch all chunks
            from backend.services.chunking.database import get_chunks_by_document
            chunks = get_chunks_by_document(document_id, db)
            if not chunks:
                logger.warning(f"No chunks found for document {document_id}")
                return {
                    "status": "success",
                    "document_id": document_id,
                    "mentions_extracted": 0,
                    "message": "No chunks found to extract mentions from",
                }
            
            # Fetch chunk contexts
            contexts_result = db.execute(
                select(ChunkContext).where(ChunkContext.document_id == document_id)
            )
            chunk_contexts = contexts_result.scalars().all()
            
            # Map chunk_id to its context data
            context_map = {}
            for ctx in chunk_contexts:
                context_map[ctx.chunk_id] = {
                    "section_type": ctx.section_type,
                    "source_voice": ctx.speaker,
                    "actors": ctx.raw_output.get("perspective", {}).get("actor_roles", []) if ctx.raw_output else [],
                    "context_dependencies": ctx.context_dependencies,
                    "important_references": ctx.important_references
                }
                
            logger.info(f"Found {len(chunks)} chunks and {len(chunk_contexts)} contexts for document {document_id}")
            
            # Determine document role/type
            document_role = None
            if chunk_contexts:
                for ctx in chunk_contexts:
                    if ctx.document_role:
                        document_role = ctx.document_role
                        break
            
            if not document_role:
                document_role = "CONTRACT" if "agreement" in document.name.lower() or "contract" in document.name.lower() else "UNKNOWN"
            
            # The entity extraction logic has been deprecated with the removal of entity_mention_agent.py.
            # Downstream tasks should run analysis through the orchestrator.
            results = []
            total_mentions = 0
            
            logger.info(
                f"Skipped legacy mention extraction for document {document_id}."
            )
            
            return {
                "status": "success",
                "document_id": document_id,
                "chunks_count": len(chunks),
                "processed_count": len(results),
                "total_mentions": total_mentions,
            }
            
    except Exception as e:
        error_msg = f"Failed in entity extraction task: {e}"
        logger.error(f"Error in entity extraction task for document {document_id}: {e}", exc_info=True)
        return {
            "status": "error",
            "document_id": document_id,
            "error": error_msg,
        }


__all__ = ["analyze_single_chunk_entities_task", "analyze_document_entities_task"]
