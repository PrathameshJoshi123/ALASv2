"""
Celery tasks for PDF processing.
Handles background processing of PDF contracts using Unstructured library.
"""

import json
import logging
from pathlib import Path
from typing import Any

from celery import chain

from backend.celery_app import celery_app
from celery.utils.log import get_task_logger

from backend.services.pdf_service import PDFService

logger = get_task_logger(__name__)

# Initialize PDF service for background tasks
pdf_service = PDFService(
    strategy="fast",  # Let Unstructured choose the best strategy
    infer_table_structure=False,
    include_page_breaks=True,
    languages=["eng"],  # Default to English, can be overridden per task
)


@celery_app.task(bind=True, name="process_pdf_task")
def process_pdf_task(
    self,
    document_id: str,
    file_path: str,
    filename: str,
) -> dict[str, Any]:
    """
    Background task to process a PDF contract.
    
    Extracts structured elements from the PDF using Unstructured:
    - Titles
    - Paragraphs (NarrativeText)
    - Tables
    - Other document elements
    
    Args:
        document_id: Unique identifier for the document
        file_path: Path to the PDF file
        filename: Original filename of the document
        
    Returns:
        Dictionary with processing results:
        {
            "status": "success" or "error",
            "document_id": str,
            "elements_count": int,
            "elements": list of element dicts,
            "error": str (if error)
        }
    """
    try:
        logger.info(f"Starting PDF processing for document: {document_id}")
        
        # Verify file exists
        storage_path = Path(file_path)
        if not storage_path.exists():
            error_msg = f"PDF file not found: {file_path}"
            logger.error(error_msg)
            # Save error to output folder
            output_dir = Path("backend/storage/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{document_id}_error.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({"status": "error", "document_id": document_id, "error": error_msg}, f, indent=2)
            return {
                "status": "error",
                "document_id": document_id,
                "error": error_msg,
                "output_file": str(output_file),
            }
        
        # Process PDF
        elements = pdf_service.process_pdf(
            file_path=storage_path,
            filename=filename,
        )
        
        logger.info(f"Processed document {document_id}: extracted {len(elements)} elements")
        
        # Save output to file in output folder
        output_dir = Path("backend/storage/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{document_id}.json"
        
        output_data = {
            "status": "success",
            "document_id": document_id,
            "filename": filename,
            "elements_count": len(elements),
            "elements": elements,
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved output to: {output_file}")
        
        return {
            "status": "success",
            "document_id": document_id,
            "elements_count": len(elements),
            "elements": elements,
            "output_file": str(output_file),
        }
        
    except ImportError as e:
        error_msg = f"Unstructured library not available: {e}"
        logger.error(error_msg)
        # Save error to output folder
        output_dir = Path("backend/storage/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{document_id}_error.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"status": "error", "document_id": document_id, "error": error_msg}, f, indent=2)
        return {
            "status": "error",
            "document_id": document_id,
            "error": error_msg,
            "output_file": str(output_file),
        }
    except Exception as e:
        error_msg = f"Failed to process PDF: {e}"
        logger.error(f"Error processing document {document_id}: {e}")
        # Save error to output folder
        output_dir = Path("backend/storage/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{document_id}_error.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"status": "error", "document_id": document_id, "error": error_msg}, f, indent=2)
        return {
            "status": "error",
            "document_id": document_id,
            "error": error_msg,
            "output_file": str(output_file),
        }


@celery_app.task(bind=True, name="process_and_chunk_task")
def process_and_chunk_task(
    self,
    document_id: str,
    file_path: str,
    filename: str,
) -> dict[str, Any]:
    """
    Background task to process PDF AND automatically chunk it using Celery chain.
    
    This task chains PDF processing with automatic chunking:
    1. process_pdf_task extracts elements
    2. chunk_document_task processes elements into chunks
    
    Args:
        document_id: Unique identifier for the document
        file_path: Path to the PDF file
        filename: Original filename of the document
        
    Returns:
        Dictionary with combined results from both tasks
    """
    try:
        from backend.tasks.chunking_tasks import chunk_document_task
        
        logger.info(f"Starting chained PDF processing + chunking for document: {document_id}")
        
        # Create the chain: PDF processing -> Chunking
        # The result of process_pdf_task is passed to chunk_document_task
        # But chunk_document_task expects (document_id, elements, filename)
        # So we need to use a helper function or modify the chain
        
        # For now, we'll call them sequentially to maintain simplicity
        # Celery chains with complex argument passing require signature manipulation
        
        # Step 1: Process PDF
        pdf_result = process_pdf_task(document_id, file_path, filename)
        
        if pdf_result.get("status") != "success":
            return {
                **pdf_result,
                "chunking": {"status": "skipped", "reason": "PDF processing failed"},
            }
        
        # Step 2: Chunk the elements
        elements = pdf_result.get("elements", [])
        chunk_result = chunk_document_task(document_id, elements, filename)
        
        # Step 3: Analyze chunk contexts
        context_result = None
        if chunk_result.get("status") == "success":
            try:
                logger.info(f"Triggering context analysis for document: {document_id}")
                from backend.tasks.context_tasks import analyze_chunks_context_task
                context_result = analyze_chunks_context_task(document_id)
            except Exception as context_err:
                logger.error(f"Failed context analysis in chained processing: {context_err}", exc_info=True)
                context_result = {"status": "error", "error": str(context_err)}
        
        # Combine results
        return {
            "status": "success",
            "document_id": document_id,
            "pdf_result": pdf_result,
            "chunk_result": chunk_result,
            "context_result": context_result,
        }
        
    except Exception as e:
        error_msg = f"Failed in chained processing: {e}"
        logger.error(f"Error in chained task for document {document_id}: {e}", exc_info=True)
        return {
            "status": "error",
            "document_id": document_id,
            "error": error_msg,
        }


__all__ = ["process_pdf_task", "process_and_chunk_task"]
