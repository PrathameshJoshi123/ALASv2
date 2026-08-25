"""
Celery tasks for PDF processing.
Handles background processing of PDF contracts using Unstructured library.
"""

import json
import logging
from pathlib import Path
from typing import Any

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


__all__ = ["process_pdf_task"]
