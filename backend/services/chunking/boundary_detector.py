"""
Boundary Detector for identifying logical document boundaries.

Detects boundaries between document sections, clauses, tables, lists, etc.
using multiple signals with confidence scoring.

Signals used:
- Element type (Title, Table, List, etc.)
- Text content patterns (numbering, ALL CAPS, colons)
- Position (page breaks, coordinates)
- Surrounding elements
- Repeated formatting patterns
"""

import re
from typing import Any, Optional

from backend.services.chunking.models import (
    BoundaryDecision,
    LegalElement,
    SECTION_PATTERNS,
)


class BoundaryDetector:
    """
    Detects logical boundaries in a sequence of LegalElements.
    
    Returns a list of BoundaryDecision objects, one for each position
    between elements (plus start and end).
    """
    
    def __init__(self):
        """Initialize the boundary detector."""
        pass
    
    def detect(self, elements: list[LegalElement]) -> list[BoundaryDecision]:
        """
        Detect boundaries between elements.
        
        Args:
            elements: List of LegalElement objects
            
        Returns:
            List of BoundaryDecision objects (length = len(elements) + 1)
            Index 0 is before first element, index len is after last element
        """
        if not elements:
            return []
        
        # Initialize all boundaries as non-boundaries with low confidence
        num_boundaries = len(elements) + 1
        boundaries = [
            BoundaryDecision(is_boundary=False, confidence=0.0)
            for _ in range(num_boundaries)
        ]
        
        # First, apply strong signals
        self._apply_strong_signals(elements, boundaries)
        
        # Then, apply medium signals
        self._apply_medium_signals(elements, boundaries)
        
        # Finally, apply weak signals
        self._apply_weak_signals(elements, boundaries)
        
        # Post-process: ensure first element can be document title
        self._post_process(elements, boundaries)
        
        return boundaries
    
    def _apply_strong_signals(
        self,
        elements: list[LegalElement],
        boundaries: list[BoundaryDecision],
    ) -> None:
        """
        Apply strong boundary signals (confidence 0.9-1.0).
        
        Strong signals:
        - Title element at document start
        - Table element
        - List element
        - Numbered headings
        """
        for i, elem in enumerate(elements):
            # Skip noise elements
            if elem.is_noise:
                continue
            
            # Signal 1: First non-noise element is likely document title
            if i == 0 or all(e.is_noise for e in elements[:i]):
                if elem.element_type == "Title":
                    boundaries[i].is_boundary = True
                    boundaries[i].boundary_type = "document_title"
                    boundaries[i].confidence = 1.0
                    boundaries[i].reason = "First non-noise element is Title"
                elif elem.element_type in ("NarrativeText", "Header"):
                    # Check if it looks like a title
                    if self._looks_like_title(elem.text):
                        boundaries[i].is_boundary = True
                        boundaries[i].boundary_type = "document_title"
                        boundaries[i].confidence = 0.95
                        boundaries[i].reason = "First non-noise element looks like title"
            
            # Signal 2: Table elements are always their own boundary
            if elem.element_type == "Table":
                boundaries[i].is_boundary = True
                boundaries[i].boundary_type = "table"
                boundaries[i].confidence = 1.0
                boundaries[i].reason = "Table element"
                
                # End of table is also a boundary
                boundaries[i + 1].is_boundary = True
                boundaries[i + 1].boundary_type = "table"
                boundaries[i + 1].confidence = 1.0
                boundaries[i + 1].reason = "End of table"
            
            # Signal 3: List elements
            if elem.element_type in ("List", "ListItem"):
                # Start of list
                if i == 0 or elements[i - 1].element_type not in ("List", "ListItem"):
                    boundaries[i].is_boundary = True
                    boundaries[i].boundary_type = "list"
                    boundaries[i].confidence = 0.95
                    boundaries[i].reason = "Start of list"
            
            # Signal 4: Numbered headings (strong section/clause signal)
            if self._is_numbered_heading(elem):
                boundaries[i].is_boundary = True
                boundaries[i].boundary_type = "section"
                boundaries[i].confidence = 0.95
                boundaries[i].reason = f"Numbered heading: {elem.text[:50]}"
            
            # Signal 5: Title elements (potential section start)
            if elem.element_type == "Title":
                # Check if it's not the document title
                if not (i == 0 or all(e.is_noise for e in elements[:i])):
                    boundaries[i].is_boundary = True
                    boundaries[i].boundary_type = "section"
                    boundaries[i].confidence = 0.9
                    boundaries[i].reason = f"Title element: {elem.text[:50]}"
            
            # Signal 6: Header elements
            if elem.element_type == "Header":
                boundaries[i].is_boundary = True
                boundaries[i].boundary_type = "section"
                boundaries[i].confidence = 0.9
                boundaries[i].reason = f"Header element: {elem.text[:50]}"
    
    def _apply_medium_signals(
        self,
        elements: list[LegalElement],
        boundaries: list[BoundaryDecision],
    ) -> None:
        """
        Apply medium boundary signals (confidence 0.7-0.9).
        
        Medium signals:
        - ALL CAPS text
        - Text ending with colon
        - Significant whitespace before element
        """
        for i, elem in enumerate(elements):
            if elem.is_noise:
                continue
            
            # Only set boundary if not already set by strong signal
            if boundaries[i].is_boundary:
                continue
            
            # Signal 1: ALL CAPS text (potential heading)
            if self._is_all_caps(elem.text):
                boundaries[i].is_boundary = True
                boundaries[i].boundary_type = "section"
                boundaries[i].confidence = 0.8
                boundaries[i].reason = "ALL CAPS text"
            
            # Signal 2: Text ending with colon (potential heading)
            if elem.text.strip().endswith(":"):
                boundaries[i].is_boundary = True
                boundaries[i].boundary_type = "section"
                boundaries[i].confidence = 0.75
                boundaries[i].reason = "Text ends with colon"
            
            # Signal 3: Text looks like a heading (bold/large in metadata)
            # This would require font info from metadata, which we may not have
            # So we skip this for now
    
    def _apply_weak_signals(
        self,
        elements: list[LegalElement],
        boundaries: list[BoundaryDecision],
    ) -> None:
        """
        Apply weak boundary signals (confidence 0.5-0.7).
        
        Weak signals:
        - Page break between elements
        - Element type change (e.g., Title after NarrativeText)
        """
        for i in range(1, len(elements)):
            prev = elements[i - 1]
            curr = elements[i]
            
            if curr.is_noise or prev.is_noise:
                continue
            
            # Only set boundary if not already set
            if boundaries[i].is_boundary:
                continue
            
            # Signal 1: Page break between elements
            if (prev.page_number is not None and 
                curr.page_number is not None and
                curr.page_number > prev.page_number):
                boundaries[i].is_boundary = True
                boundaries[i].boundary_type = "paragraph_group"
                boundaries[i].confidence = 0.6
                boundaries[i].reason = "Page break"
            
            # Signal 2: Type change from NarrativeText to Title
            if prev.element_type == "NarrativeText" and curr.element_type == "Title":
                boundaries[i].is_boundary = True
                boundaries[i].boundary_type = "section"
                boundaries[i].confidence = 0.65
                boundaries[i].reason = "Type change: NarrativeText -> Title"
            
            # Signal 3: Type change from NarrativeText to Header
            if prev.element_type == "NarrativeText" and curr.element_type == "Header":
                boundaries[i].is_boundary = True
                boundaries[i].boundary_type = "section"
                boundaries[i].confidence = 0.65
                boundaries[i].reason = "Type change: NarrativeText -> Header"
            
            # Signal 4: Type change to Table
            if prev.element_type != "Table" and curr.element_type == "Table":
                # This should have been caught by strong signal, but just in case
                if not boundaries[i].is_boundary:
                    boundaries[i].is_boundary = True
                    boundaries[i].boundary_type = "table"
                    boundaries[i].confidence = 0.55
                    boundaries[i].reason = "Type change to Table"
    
    def _post_process(
        self,
        elements: list[LegalElement],
        boundaries: list[BoundaryDecision],
    ) -> None:
        """
        Post-process boundaries to ensure consistency.
        
        Rules:
        - First boundary should be document start
        - Consecutive boundaries of same type may be merged
        - Ensure document_title is only at the start
        """
        # Ensure first boundary is a document boundary
        if len(boundaries) > 0:
            if not boundaries[0].is_boundary:
                boundaries[0].is_boundary = True
                boundaries[0].boundary_type = "document_title"
                boundaries[0].confidence = 0.5
                boundaries[0].reason = "Document start"
        
        # Ensure document_title only appears once
        doc_title_indices = [
            i for i, b in enumerate(boundaries) 
            if b.is_boundary and b.boundary_type == "document_title"
        ]
        for idx in doc_title_indices[1:]:
            boundaries[idx].boundary_type = "section"
            boundaries[idx].reason = "Changed from document_title to section"
        
        # Ensure table boundaries are consistent
        # If we have table start without end, add end
        for i in range(len(boundaries) - 1):
            if (boundaries[i].is_boundary and 
                boundaries[i].boundary_type == "table" and
                not boundaries[i + 1].is_boundary):
                # Find the next boundary or end
                j = i + 1
                while j < len(boundaries) and not boundaries[j].is_boundary:
                    j += 1
                if j < len(boundaries):
                    boundaries[j].is_boundary = True
                    boundaries[j].boundary_type = "table"
                    boundaries[j].confidence = 1.0
                    boundaries[j].reason = "End of table (added for consistency)"
    
    def _looks_like_title(self, text: str) -> bool:
        """
        Check if text looks like a document title.
        
        Args:
            text: Text to check
            
        Returns:
            True if text looks like a title
        """
        if not text:
            return False
        
        text = text.strip()
        
        # Titles are typically short but meaningful
        if len(text) < 3:
            return False
        
        # Check for common title characteristics
        # ALL CAPS
        if self._is_all_caps(text):
            return True
        
        # Ends with colon
        if text.endswith(":"):
            return True
        
        # Contains words like AGREEMENT, CONTRACT, etc.
        title_keywords = [
            "agreement",
            "contract",
            "amendment",
            "addendum",
            "memorandum",
            "letter",
            "deed",
            "license",
            "lease",
            "terms",
            "conditions",
        ]
        
        text_lower = text.lower()
        for keyword in title_keywords:
            if keyword in text_lower:
                return True
        
        return False
    
    def _is_numbered_heading(self, element: LegalElement) -> bool:
        """
        Check if element is a numbered heading.
        
        Args:
            element: LegalElement to check
            
        Returns:
            True if element appears to be a numbered heading
        """
        if not element.text:
            return False
        
        text = element.text.strip()
        
        # A heading should be reasonably short (typically less than 120 characters)
        # If it is long narrative text, it is likely a body paragraph, not a heading
        if len(text) > 120 and element.element_type not in ("Title", "Header", "Subhead", "Heading"):
            return False
        
        # Check for bullet patterns (might be list, not heading)
        if re.match(r'^[•·*—\-]\s+', text):
            return False
        
        # Check for pure numbers (might be page number)
        if re.match(r'^\d+$', text):
            return False
        
        # Check against all section patterns
        for pattern in SECTION_PATTERNS:
            match = pattern.match(text)
            if match:
                return True
        
        # Check for Roman numerals
        if re.match(r'^[IVXLCDM]+$', text, re.IGNORECASE):
            return True
        
        # Check for letters
        if re.match(r'^[A-Z]$', text):
            return True
        
        return False
    
    def _is_all_caps(self, text: str) -> bool:
        """
        Check if text is in ALL CAPS.
        
        Args:
            text: Text to check
            
        Returns:
            True if text is all uppercase (with some exceptions)
        """
        if not text:
            return False
        
        text = text.strip()
        
        # Remove common punctuation
        text_clean = re.sub(r'[^\w\s]', '', text)
        
        if not text_clean:
            return False
        
        # Check if all alphabetic characters are uppercase
        # Allow for some exceptions like "I", "A" which are single letters
        uppercase_count = sum(1 for c in text_clean if c.isupper())
        alpha_count = sum(1 for c in text_clean if c.isalpha())
        
        if alpha_count == 0:
            return False
        
        return uppercase_count / alpha_count >= 0.9
