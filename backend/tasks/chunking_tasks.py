"""
Celery tasks for chunking processed PDF elements.

Handles background processing of PDF elements into chunks
using the chunking service pipeline.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

from backend.celery_app import celery_app
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@celery_app.task(bind=True, name="chunk_document_task")
def chunk_document_task(
    self,
    document_id: str,
    elements: list[dict[str, Any]],
    filename: str,
    config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Background task to chunk PDF elements into LangChain Documents.
    
    This task takes the processed elements from PDF extraction and
    processes them through the chunking pipeline to create retrievable
    chunks for embeddings and citations.
    
    Args:
        document_id: Unique identifier for the document
        elements: List of Unstructured element dictionaries
        filename: Original filename of the document
        config: Optional configuration overrides
        
    Returns:
        Dictionary with processing results:
        {
            "status": "success" or "error",
            "document_id": str,
            "chunks_count": int,
            "chunks": list of chunk dicts (optional),
            "error": str (if error)
        }
    """
    try:
        logger.info(f"Starting chunking for document: {document_id}")
        
        # Import here to avoid circular imports
        from backend.database import SessionLocal
        
        # Create pipeline
        if config:
            from backend.services.chunking.pipeline import create_pipeline
            pipeline = create_pipeline(
                chunk_size=config.get("chunk_size", 800),
                chunk_overlap=config.get("chunk_overlap", 100),
                max_unit_size=config.get("max_unit_size", 2000),
                chunking_strategy=config.get("chunking_strategy") or config.get("strategy") or "layout_aware",
            )
        else:
            from backend.services.chunking.pipeline import ChunkingPipeline
            pipeline = ChunkingPipeline()
        
        # Process and save
        with SessionLocal() as db:
            chunks = pipeline.process_and_save(elements, document_id, filename, db)
        
        logger.info(f"Successfully chunked document {document_id}: {len(chunks)} chunks")
        
        # Get summary
        # We need to re-process to get documents for summary
        # (save_chunks_to_db returns Chunk objects, not Documents)
        documents = pipeline.process(elements, document_id, filename)
        summary = pipeline.get_summary(documents)
        
        return {
            "status": "success",
            "document_id": document_id,
            "chunks_count": len(chunks),
            "summary": summary,
        }
        
    except ImportError as e:
        error_msg = f"Chunking dependencies not available: {e}"
        logger.error(error_msg)
        return {
            "status": "error",
            "document_id": document_id,
            "error": error_msg,
        }
    except Exception as e:
        error_msg = f"Failed to chunk document: {e}"
        logger.error(f"Error chunking document {document_id}: {e}", exc_info=True)
        return {
            "status": "error",
            "document_id": document_id,
            "error": error_msg,
        }


@celery_app.task(bind=True, name="rechunk_document_task")
def rechunk_document_task(
    self,
    document_id: str,
    config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Re-chunk a document with new configuration.
    
    This task deletes existing chunks and re-processes the document
    with the given configuration.
    
    Args:
        document_id: Unique identifier for the document
        config: Optional configuration overrides
            {
                "chunk_size": int,
                "chunk_overlap": int,
                "max_unit_size": int,
            }
        
    Returns:
        Dictionary with processing results
    """
    try:
        logger.info(f"Re-chunking document {document_id} with config: {config}")
        
        from sqlalchemy import select
        from backend.database import SessionLocal
        from backend.models.documents import Document
        from backend.services.chunking.pipeline import create_pipeline
        from backend.services.chunking.database import (
            Chunk,
            delete_chunks_by_document,
            save_chunks_to_db,
        )
        
        # Get document
        with SessionLocal() as db:
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
            
            # Get processed elements from storage
            # Elements are typically stored in backend/storage/output/{document_id}.json
            output_dir = Path("backend/storage/output")
            output_file = output_dir / f"{document_id}.json"
            
            if not output_file.exists():
                return {
                    "status": "error",
                    "document_id": document_id,
                    "error": f"Processed elements not found at {output_file}",
                }
            
            with open(output_file, "r", encoding="utf-8") as f:
                output_data = json.load(f)
            
            elements = output_data.get("elements", [])
            
            # Delete existing chunks
            deleted_count = delete_chunks_by_document(document_id, db)
            logger.info(f"Deleted {deleted_count} existing chunks for document {document_id}")
            
            # Create pipeline with custom config
            config_obj = None
            if config:
                config_obj = create_pipeline(
                    chunk_size=config.get("chunk_size", 800),
                    chunk_overlap=config.get("chunk_overlap", 100),
                    max_unit_size=config.get("max_unit_size", 2000),
                    chunking_strategy=config.get("chunking_strategy") or config.get("strategy") or "layout_aware",
                )
            else:
                from backend.services.chunking.pipeline import ChunkingPipeline
                config_obj = ChunkingPipeline()
            
            # Process elements
            documents = config_obj.process(elements, document_id, document.name)
            
            # Save new chunks
            # Save new chunks
            chunks = save_chunks_to_db(documents, document_id, db)
            
            # Commit all changes
            db.commit()
            
            logger.info(f"Re-chunked document {document_id}: {len(chunks)} new chunks")
            
            # Analyze context of new chunks
            context_summary = None
            try:
                logger.info(f"Analyzing chunks context for re-chunked document: {document_id}")
                from backend.tasks.context_tasks import analyze_chunks_context_task
                context_res = analyze_chunks_context_task(document_id)
                context_summary = context_res
            except Exception as e:
                logger.error(f"Failed to analyze chunks context after re-chunking: {e}", exc_info=True)
                context_summary = {"status": "error", "error": str(e)}
            
            # Get summary
            summary = config_obj.get_summary(documents)
            
            return {
                "status": "success",
                "document_id": document_id,
                "chunks_count": len(chunks),
                "deleted_count": deleted_count,
                "summary": summary,
                "context_analysis": context_summary,
            }
        
    except Exception as e:
        error_msg = f"Failed to re-chunk document: {e}"
        logger.error(f"Error re-chunking document {document_id}: {e}", exc_info=True)
        return {
            "status": "error",
            "document_id": document_id,
            "error": error_msg,
        }


__all__ = ["chunk_document_task", "rechunk_document_task"]

