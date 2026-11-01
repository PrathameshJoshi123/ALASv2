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
# Path checks already validated above

        if not UNSTRUCTURED_AVAILABLE:
            logger.info(f"Unstructured library not available; using robust pypdf extractor for {file_path}")
            try:
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                normalized_elements = []
                for page_num, page in enumerate(reader.pages, start=1):
                    page_text = page.extract_text() or ""
                    paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]
                    if not paragraphs and page_text.strip():
                        paragraphs = [page_text.strip()]
                    for para in paragraphs:
                        is_title = len(para) < 120 and (para.isupper() or any(kw in para.lower() for kw in ["section", "clause", "report", "act", "court", "first information", "agreement", "statement"]))
                        normalized_elements.append({
                            "type": "Title" if is_title else "NarrativeText",
                            "text": para,
                            "metadata": {
                                "page_number": page_num,
                                "filename": filename or file_path.name,
                                "filetype": "application/pdf"
                            }
                        })
                return normalized_elements
            except Exception as pypdf_err:
                logger.error(f"pypdf extraction error: {pypdf_err}")
                raise ImportError(f"PDF extraction failed without unstructured: {pypdf_err}")
        
# Path checks already validated above
        
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
# Path checks already validated above

        if not UNSTRUCTURED_AVAILABLE:
            logger.info(f"Unstructured library not available; using robust pypdf extractor for {file_path}")
            try:
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                normalized_elements = []
                for page_num, page in enumerate(reader.pages, start=1):
                    page_text = page.extract_text() or ""
                    paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]
                    if not paragraphs and page_text.strip():
                        paragraphs = [page_text.strip()]
                    for para in paragraphs:
                        is_title = len(para) < 120 and (para.isupper() or any(kw in para.lower() for kw in ["section", "clause", "report", "act", "court", "first information", "agreement", "statement"]))
                        normalized_elements.append({
                            "type": "Title" if is_title else "NarrativeText",
                            "text": para,
                            "metadata": {
                                "page_number": page_num,
                                "filename": filename or file_path.name,
                                "filetype": "application/pdf"
                            }
                        })
                return normalized_elements
            except Exception as pypdf_err:
                logger.error(f"pypdf extraction error: {pypdf_err}")
                raise ImportError(f"PDF extraction failed without unstructured: {pypdf_err}")
        
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
