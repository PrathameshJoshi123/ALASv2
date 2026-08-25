"""
PDF Service for processing PDF documents using Unstructured library.

This service extracts structured elements from PDF files including:
- Titles
- NarrativeText (paragraphs)
- Tables
- Other document elements

The extraction follows the document hierarchy precisely, which is critical
for legal document analysis.
"""

import logging
from pathlib import Path
from typing import Any, Optional

try:
    from unstructured.partition.pdf import partition_pdf
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False
    partition_pdf = None

logger = logging.getLogger(__name__)


class PDFService:
    """
    Service for processing PDF documents using Unstructured.
    
    Processes PDFs and extracts structured elements with proper hierarchy:
    - Title elements
    - NarrativeText (paragraphs)
    - Table elements
    - Other document components
    """
    
    def __init__(
        self,
        strategy: str = "fast",
        infer_table_structure: bool = False,
        include_page_breaks: bool = True,
        languages: Optional[list[str]] = None,
    ):
        """
        Initialize PDF Service.
        
        Args:
            strategy: Extraction strategy ('auto', 'fast', 'hi_res', 'ocr_only')
            infer_table_structure: Whether to infer table structure
            include_page_breaks: Whether to include page breaks in output
            languages: List of languages for OCR (e.g., ["eng", "deu"])
        """
        self.strategy = strategy
        self.infer_table_structure = infer_table_structure
        self.include_page_breaks = include_page_breaks
        self.languages = languages or ["eng"]
        
        if not UNSTRUCTURED_AVAILABLE:
            logger.warning("Unstructured library not available. PDF processing will fail.")
    
    def process_pdf(
        self,
        file_path: str | Path,
        filename: Optional[str] = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        Process a PDF file and extract structured elements.
        
        Args:
            file_path: Path to the PDF file
            filename: Optional filename override
            **kwargs: Additional arguments to pass to partition_pdf
            
        Returns:
            List of element dictionaries with structure:
            [
                {
                    "type": "Title",
                    "text": "EMPLOYMENT AGREEMENT",
                    "metadata": {
                        "page_number": 1,
                        "filename": "contract.pdf",
                        ...
                    }
                },
                {
                    "type": "NarrativeText",
                    "text": "This agreement is made between...",
                    "metadata": {...}
                },
                ...
            ]
        """
        if not UNSTRUCTURED_AVAILABLE:
            raise ImportError(
                "Unstructured library is not installed. "
                "Install it with: pip install unstructured[pdf]"
            )
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        if not file_path.suffix.lower() == ".pdf":
            raise ValueError(f"File must be a PDF: {file_path}")
        
        logger.info(f"Processing PDF: {file_path}")
        
        # Process PDF using Unstructured with proper parameters
        elements = partition_pdf(
            filename=str(file_path),
            strategy=self.strategy,
            infer_table_structure=self.infer_table_structure,
            include_page_breaks=self.include_page_breaks,
            languages=self.languages,
            **kwargs,
        )
        
        # Manually convert elements to structured JSON format
        normalized_elements = []
        for element in elements:
            # Get element type from class name (e.g., Title -> "Title")
            element_type = type(element).__name__
            
            # Get text safely
            element_text = getattr(element, "text", "")
            
            # Build metadata
            element_metadata = {
                "filename": filename or file_path.name,
                "filetype": "application/pdf",
            }
            
            # Add metadata from the element if available
            if hasattr(element, "metadata") and element.metadata:
                if hasattr(element.metadata, "to_dict"):
                    element_metadata.update(element.metadata.to_dict())
                else:
                    element_metadata.update(element.metadata)
            
            # Add element ID if available
            element_dict = {
                "type": element_type,
                "text": element_text,
                "metadata": element_metadata,
            }
            
            if hasattr(element, "element_id"):
                element_dict["element_id"] = element.element_id
            
            normalized_elements.append(element_dict)
        
        logger.info(f"Extracted {len(normalized_elements)} elements from PDF")
        
        return normalized_elements
    
    def process_pdf_to_elements(
        self,
        file_path: str | Path,
        filename: Optional[str] = None,
    ) -> list[Any]:
        """
        Process PDF and return raw Unstructured elements.
        
        This is useful when you need the raw element objects for further processing.
        
        Args:
            file_path: Path to the PDF file
            filename: Optional filename override
            
        Returns:
            List of raw Unstructured element objects
        """
        if not UNSTRUCTURED_AVAILABLE:
            raise ImportError(
                "Unstructured library is not installed. "
                "Install it with: pip install unstructured[pdf]"
            )
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        logger.info(f"Processing PDF to elements: {file_path}")
        
        elements = partition_pdf(
            filename=str(file_path),
            strategy=self.strategy,
            infer_table_structure=self.infer_table_structure,
            include_page_breaks=self.include_page_breaks,
            languages=self.languages,
        )
        
        logger.info(f"Extracted {len(elements)} raw elements from PDF")
        return elements


# Singleton instance for easy access
pdf_service = PDFService()
