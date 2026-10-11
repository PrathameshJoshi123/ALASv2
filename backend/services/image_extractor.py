import logging
import pymupdf  # PyMuPDF
from pathlib import Path
from typing import Any, List, Dict
from backend.config import settings

logger = logging.getLogger(__name__)

def get_extracted_dir() -> Path:
    """Ensure the directory for extracted images exists."""
    extracted_dir = settings.UPLOAD_DIR / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    return extracted_dir

def extract_images_from_pdf(pdf_path: str | Path, document_id: str) -> List[Dict[str, Any]]:
    """
    Extract embedded images from a PDF file on a page-by-page basis.
    
    Args:
        pdf_path: Path to the PDF file.
        document_id: Unique ID of the document (used to isolate extracted images).
        
    Returns:
        List of dictionaries detailing the extracted images:
        [
            {
                "page_number": int (1-based),
                "image_path": str,
                "filename": str
            },
            ...
        ]
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")
        
    extracted_images = []
    output_dir = get_extracted_dir() / document_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Extracting images from PDF: {pdf_path} to {output_dir}")
    
    try:
        doc = pymupdf.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            
            for img_idx, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Format: documentId_pageNumber_imageIndex.ext
                img_filename = f"{document_id}_p{page_num + 1}_img{img_idx + 1}.{image_ext}"
                img_path = output_dir / img_filename
                
                with open(img_path, "wb") as f:
                    f.write(image_bytes)
                    
                extracted_images.append({
                    "page_number": page_num + 1,
                    "image_path": str(img_path),
                    "filename": img_filename
                })
                logger.info(f"Extracted image: {img_filename}")
                
    except Exception as e:
        logger.error(f"Failed to extract images from PDF {pdf_path}: {e}", exc_info=True)
        raise e
        
    return extracted_images

def process_file_images(file_path: str | Path, document_id: str) -> List[Dict[str, Any]]:
    """
    Scans a document file and extracts all target images.
    If it is already an image file, it returns it directly.
    
    Args:
        file_path: Path to the uploaded document file.
        document_id: Unique ID of the document record.
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()
    
    if suffix in [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"]:
        # If it's already an image, return it as a single page standalone image
        return [{
            "page_number": 1,
            "image_path": str(file_path),
            "filename": file_path.name
        }]
    elif suffix == ".pdf":
        return extract_images_from_pdf(file_path, document_id)
    else:
        logger.warning(f"Unsupported file type for image extraction: {suffix}")
        return []
