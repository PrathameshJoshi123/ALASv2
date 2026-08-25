"""
Element Normalizer for Unstructured PDF elements.

Normalizes raw Unstructured elements into LegalElement objects while
preserving all source metadata for traceability.
"""

import re
import uuid
from typing import Any, Optional

from backend.services.chunking.models import LegalElement


class ElementNormalizer:
    """
    Normalizes Unstructured elements into LegalElement objects.
    
    Handles:
    - Safe text extraction
    - Whitespace normalization
    - ID generation/preservation
    - Metadata extraction
    - Empty element filtering
    """
    
    # Element types that contain structural information even if empty
    STRUCTURAL_TYPES = {"Title", "Header", "Footer", "Table", "List", "PageBreak"}
    
    # Element types that are always noise
    ALWAYS_NOISE_TYPES = {"PageBreak"}
    
    def __init__(self):
        """Initialize the normalizer."""
        pass
    
    def normalize(
        self,
        elements: list[dict[str, Any]],
        document_id: str,
        filename: Optional[str] = None,
    ) -> list[LegalElement]:
        """
        Normalize a list of Unstructured elements.
        
        Args:
            elements: List of Unstructured element dictionaries
            document_id: The document ID to associate with these elements
            filename: Optional filename for metadata
            
        Returns:
            List of normalized LegalElement objects
        """
        normalized = []
        
        for element in elements:
            legal_element = self._normalize_element(element, document_id, filename)
            if legal_element is not None:
                normalized.append(legal_element)
        
        return normalized
    
    def _normalize_element(
        self,
        element: dict[str, Any],
        document_id: str,
        filename: Optional[str],
    ) -> Optional[LegalElement]:
        """
        Normalize a single Unstructured element.
        
        Args:
            element: Unstructured element dictionary
            document_id: Document ID
            filename: Optional filename
            
        Returns:
            LegalElement or None if element is truly empty
        """
        # Extract element type
        element_type = element.get("type", "Unknown")
        
        # Extract text safely
        text = element.get("text", "")
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
        
        # Normalize whitespace
        text = self._normalize_whitespace(text)
        
        # Check if element is truly empty (no text, no structural info)
        if not text and element_type not in self.STRUCTURAL_TYPES:
            return None
        
        # Extract element_id
        element_id = element.get("element_id", "")
        if not element_id:
            element_id = str(uuid.uuid4())
        
        # Extract page number
        page_number = None
        metadata = element.get("metadata", {})
        if isinstance(metadata, dict):
            page_number = metadata.get("page_number")
            if page_number is not None:
                try:
                    page_number = int(page_number)
                except (ValueError, TypeError):
                    page_number = None
        
        # Extract parent_id
        parent_id = metadata.get("parent_id") if isinstance(metadata, dict) else None
        
        # Extract coordinates
        coordinates = metadata.get("coordinates") if isinstance(metadata, dict) else None
        
        # Build source_metadata
        source_metadata = dict(metadata) if isinstance(metadata, dict) else {}
        if filename:
            source_metadata["filename"] = filename
        
        # Check if this element type is always noise
        is_noise = element_type in self.ALWAYS_NOISE_TYPES
        
        return LegalElement(
            element_id=element_id,
            document_id=document_id,
            element_type=element_type,
            text=text,
            page_number=page_number,
            parent_id=parent_id,
            coordinates=coordinates,
            source_metadata=source_metadata,
            is_noise=is_noise,
        )
    
    def _normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace in text.
        
        Preserves paragraph structure while collapsing multiple spaces
        and handling various whitespace characters.
        
        Args:
            text: Input text
            
        Returns:
            Text with normalized whitespace
        """
        if not text:
            return ""
        
        # Replace various whitespace characters with regular spaces
        # except newlines which preserve paragraph structure
        text = text.replace("\r\n", "\n")  # Normalize Windows line endings
        text = text.replace("\r", "\n")    # Normalize Mac line endings
        text = text.replace("\t", " ")     # Tabs to spaces
        
        # Replace non-breaking spaces and other special spaces
        text = re.sub(r'[\u00A0\u2000-\u200F\u2028-\u202F\u205F\u3000]', ' ', text)
        
        # Collapse multiple consecutive spaces to single space
        # but preserve newlines
        lines = text.split("\n")
        normalized_lines = []
        for line in lines:
            # Collapse multiple spaces within a line
            line = re.sub(r' {2,}', ' ', line)
            # Strip leading/trailing spaces from each line
            line = line.strip()
            normalized_lines.append(line)
        
        # Join lines back together
        result = "\n".join(normalized_lines)
        
        # Collapse multiple consecutive newlines to two (paragraph breaks)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result
