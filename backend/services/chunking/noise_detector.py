"""
Noise Detector for identifying and marking likely noise in documents.

Marks (does not delete) elements that are likely noise such as:
- Repeated headers and footers
- Page numbers
- Repeated document titles
- Copyright/confidentiality notices

Uses multiple signals: page frequency, position, text similarity, element type.
Preserves legally important short text.
"""

import re
from collections import Counter, defaultdict
from typing import Any

from backend.services.chunking.models import (
    LEGAL_TERMS,
    LegalElement,
    NOISE_PATTERNS,
)


class NoiseDetector:
    """
    Detects and marks likely noise in normalized elements.
    
    Uses a combination of:
    - Page frequency analysis
    - Position analysis (coordinates)
    - Text pattern matching
    - Element type analysis
    
    Does NOT delete elements - only marks them with is_noise=True.
    This allows for reversible processing and debugging.
    """
    
    # Minimum page count threshold for frequency-based detection
    MIN_PAGE_THRESHOLD = 3
    
    # Threshold for considering text "frequent" (appears on this % of pages)
    FREQUENCY_THRESHOLD = 0.5
    
    # Y-coordinate thresholds for top/bottom of page detection
    # These are relative to page height (0.0 to 1.0)
    TOP_THRESHOLD = 0.1  # Top 10% of page
    BOTTOM_THRESHOLD = 0.9  # Bottom 10% of page
    
    def __init__(self):
        """Initialize the noise detector."""
        pass
    
    def mark_noise(self, elements: list[LegalElement]) -> list[LegalElement]:
        """
        Mark likely noise elements in the list.
        
        Args:
            elements: List of LegalElement objects
            
        Returns:
            Same list with is_noise flag updated for likely noise elements
        """
        if not elements:
            return elements
        
        # Get page numbers for all elements
        page_numbers = [e.page_number for e in elements if e.page_number is not None]
        if not page_numbers:
            return elements
        
        unique_pages = set(page_numbers)
        
        # If document has fewer than MIN_PAGE_THRESHOLD pages,
        # frequency-based detection is less reliable
        if len(unique_pages) < self.MIN_PAGE_THRESHOLD:
            # Still check for obvious noise patterns
            self._mark_pattern_noise(elements)
            return elements
        
        # Group elements by text for frequency analysis
        text_to_elements = defaultdict(list)
        for elem in elements:
            text_key = self._get_text_key(elem.text)
            if text_key:
                text_to_elements[text_key].append(elem)
        
        # Group elements by page for position analysis
        page_to_elements = defaultdict(list)
        for elem in elements:
            if elem.page_number is not None:
                page_to_elements[elem.page_number].append(elem)
        
        # Detect repeated headers/footers
        self._mark_repeated_headers_footers(elements, text_to_elements, page_to_elements)
        
        # Detect page numbers
        self._mark_page_numbers(elements)
        
        # Detect repeated document titles
        self._mark_repeated_titles(elements, text_to_elements)
        
        # Detect copyright/confidentiality notices
        self._mark_copyright_notices(elements)
        
        # Detect pattern-based noise
        self._mark_pattern_noise(elements)
        
        return elements
    
    def _get_text_key(self, text: str) -> str:
        """
        Generate a normalized key for text comparison.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text key (lowercase, stripped)
        """
        if not text:
            return ""
        # Normalize for comparison
        key = text.strip().lower()
        # Remove page numbers from text (e.g., "Header Text 1" vs "Header Text 2")
        key = re.sub(r'\d+$', '', key).strip()
        return key
    
    def _mark_repeated_headers_footers(
        self,
        elements: list[LegalElement],
        text_to_elements: dict[str, list[LegalElement]],
        page_to_elements: dict[int, list[LegalElement]],
    ) -> None:
        """
        Mark elements that appear repeatedly at the top or bottom of pages.
        
        Args:
            elements: All elements
            text_to_elements: Elements grouped by normalized text
            page_to_elements: Elements grouped by page number
        """
        for text_key, elems in text_to_elements.items():
            if len(elems) < 2:
                continue
            
            # Check if this text appears on a significant percentage of pages
            pages_with_text = set(e.page_number for e in elems if e.page_number is not None)
            total_pages = len(set(e.page_number for e in elements if e.page_number is not None))
            
            if len(pages_with_text) / total_pages < self.FREQUENCY_THRESHOLD:
                continue
            
            # Check if elements are consistently at top or bottom of pages
            top_count = 0
            bottom_count = 0
            
            for elem in elems:
                if elem.coordinates and self._is_at_page_top(elem.coordinates):
                    top_count += 1
                if elem.coordinates and self._is_at_page_bottom(elem.coordinates):
                    bottom_count += 1
            
            # If most occurrences are at top, it's likely a header
            if top_count > len(elems) * 0.7:
                for elem in elems:
                    # Don't mark if it's a legal term
                    if not self._is_legally_important(elem.text):
                        elem.is_noise = True
            
            # If most occurrences are at bottom, it's likely a footer
            elif bottom_count > len(elems) * 0.7:
                for elem in elems:
                    # Don't mark if it's a legal term
                    if not self._is_legally_important(elem.text):
                        elem.is_noise = True
    
    def _is_at_page_top(self, coordinates: dict[str, Any]) -> bool:
        """
        Check if element is at the top of the page.
        
        Args:
            coordinates: Element coordinates dictionary
            
        Returns:
            True if element is in the top THRESHOLD of the page
        """
        # Coordinates format from Unstructured: dict with points
        # points can be: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
        # or for some elements: {"points": [...], "system": "..."}
        points = coordinates.get("points", coordinates)
        if not points or not isinstance(points, list):
            return False
        
        # Get y-coordinates
        y_coords = [p[1] for p in points if isinstance(p, (list, tuple)) and len(p) >= 2]
        if not y_coords:
            return False
        
        # Find min y (top of element)
        min_y = min(y_coords)
        
        # We need page height to calculate relative position
        # If we don't have it, assume based on typical coordinates
        # This is a heuristic - coordinates are typically in points (72 per inch)
        # A typical letter page is 792 points tall (11 inches)
        page_height = 792  # Default assumption
        
        # If we have all 4 points, we might be able to infer page height
        if len(points) >= 4:
            all_y = [p[1] for p in points if isinstance(p, (list, tuple)) and len(p) >= 2]
            page_height = max(all_y) - min(all_y)
            if page_height < 100:  # Probably not page height
                page_height = 792
        
        # Calculate relative position (0.0 = top, 1.0 = bottom)
        relative_y = min_y / page_height if page_height > 0 else 0.5
        
        return relative_y <= self.TOP_THRESHOLD
    
    def _is_at_page_bottom(self, coordinates: dict[str, Any]) -> bool:
        """
        Check if element is at the bottom of the page.
        
        Args:
            coordinates: Element coordinates dictionary
            
        Returns:
            True if element is in the bottom THRESHOLD of the page
        """
        points = coordinates.get("points", coordinates)
        if not points or not isinstance(points, list):
            return False
        
        y_coords = [p[1] for p in points if isinstance(p, (list, tuple)) and len(p) >= 2]
        if not y_coords:
            return False
        
        max_y = max(y_coords)
        
        page_height = 792  # Default
        if len(points) >= 4:
            all_y = [p[1] for p in points if isinstance(p, (list, tuple)) and len(p) >= 2]
            page_height = max(all_y) - min(all_y)
            if page_height < 100:
                page_height = 792
        
        relative_y = max_y / page_height if page_height > 0 else 0.5
        
        return relative_y >= self.BOTTOM_THRESHOLD
    
    def _mark_page_numbers(self, elements: list[LegalElement]) -> None:
        """
        Mark standalone page numbers as noise.
        
        Args:
            elements: All elements
        """
        for elem in elements:
            if elem.is_noise:
                continue
            
            text = elem.text.strip()
            
            # Check if text is just a number (potential page number)
            if re.match(r'^\d+$', text):
                # Additional checks to confirm it's a page number:
                # - Should be a reasonable page number (< 10000)
                # - Element type should be NarrativeText or similar
                # - Should be short (1-4 digits typically)
                try:
                    page_num = int(text)
                    if 1 <= page_num <= 10000 and len(text) <= 5:
                        # Check if this matches the element's page_number
                        # If element is on page 5 but text is "7", it might not be a page number
                        if elem.page_number is None or abs(elem.page_number - page_num) > 2:
                            elem.is_noise = True
                except ValueError:
                    pass
    
    def _mark_repeated_titles(
        self,
        elements: list[LegalElement],
        text_to_elements: dict[str, list[LegalElement]],
    ) -> None:
        """
        Mark Title elements that appear multiple times (likely document title repeated).
        
        Args:
            elements: All elements
            text_to_elements: Elements grouped by normalized text
        """
        # Find all Title elements
        title_elements = [e for e in elements if e.element_type == "Title"]
        
        if len(title_elements) <= 1:
            return
        
        # First Title is likely the document title - keep it
        first_title = title_elements[0]
        
        # Mark subsequent Titles with same text as noise
        for text_key, elems in text_to_elements.items():
            title_elems = [e for e in elems if e.element_type == "Title"]
            if len(title_elems) > 1:
                # Keep the first one, mark others
                for elem in title_elems[1:]:
                    if elem != first_title:
                        elem.is_noise = True
    
    def _mark_copyright_notices(self, elements: list[LegalElement]) -> None:
        """
        Mark copyright and confidentiality notices as noise.
        
        Args:
            elements: All elements
        """
        for elem in elements:
            if elem.is_noise:
                continue
            
            text_lower = elem.text.lower()
            
            # Check for copyright patterns
            for pattern in NOISE_PATTERNS:
                if pattern.search(elem.text):
                    # Only mark if it's not a legal term
                    if not self._is_legally_important(elem.text):
                        elem.is_noise = True
                        break
    
    def _mark_pattern_noise(self, elements: list[LegalElement]) -> None:
        """
        Mark elements matching common noise patterns.
        
        Args:
            elements: All elements
        """
        for elem in elements:
            if elem.is_noise:
                continue
            
            text = elem.text.strip()
            
            # Skip legal terms
            if self._is_legally_important(text):
                continue
            
            # Very short text (1-2 characters) is often noise
            # But preserve single-letter section markers
            if len(text) <= 2:
                # Check if it looks like a section marker
                if re.match(r'^[A-Z]\.?$', text) or re.match(r'^\d+\.?$', text):
                    # Keep it - might be section marker
                    pass
                else:
                    elem.is_noise = True
                    continue
            
            # Check for common noise strings
            noise_strings = [
                "page",
                "of",
                "draft",
                "copy",
                "uncontrolled",
                "version",
                "revision",
                "date:",
                "author:",
            ]
            
            text_lower = text.lower()
            for noise_str in noise_strings:
                if noise_str in text_lower:
                    elem.is_noise = True
                    break
    
    def _is_legally_important(self, text: str) -> bool:
        """
        Check if text contains legally important terms.
        
        Args:
            text: Text to check
            
        Returns:
            True if text contains legally important terms
        """
        text_lower = text.lower()
        
        # Check exact matches
        for term in LEGAL_TERMS:
            if term in text_lower:
                return True
        
        # Check for common legal phrases
        legal_phrases = [
            "in witness whereof",
            "now therefore",
            "schedule a",
            "schedule b",
            "schedule c",
            "exhibit a",
            "exhibit b",
            "article i",
            "article ii",
            "article iii",
            "section 1",
            "section 2",
            "clause 1",
            "part a",
            "part b",
        ]
        
        for phrase in legal_phrases:
            if phrase in text_lower:
                return True
        
        return False
