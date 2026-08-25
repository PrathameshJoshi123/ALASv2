"""
Unit Builder for creating logical document units from elements and boundaries.

Groups elements between detected boundaries into LogicalUnit objects,
attaching headings to their content and extracting metadata.
"""

import re
from typing import Any, Optional

from backend.services.chunking.models import (
    BoundaryDecision,
    LegalElement,
    LogicalUnit,
    SECTION_PATTERNS,
)


class UnitBuilder:
    """
    Builds logical units from elements and boundary decisions.
    
    Logical units represent semantic groupings in the document:
    - document_title
    - section
    - clause
    - subclause
    - table
    - list
    - paragraph_group
    - generic
    """
    
    def __init__(self):
        """Initialize the unit builder."""
        pass
    
    def build(
        self,
        elements: list[LegalElement],
        boundaries: list[BoundaryDecision],
    ) -> list[LogicalUnit]:
        """
        Build logical units from elements and boundaries.
        
        Args:
            elements: List of LegalElement objects
            boundaries: List of BoundaryDecision objects
            
        Returns:
            List of LogicalUnit objects
        """
        if not elements or not boundaries:
            return []
        
        # Filter out noise elements but keep their IDs for tracking
        non_noise_elements = [
            e for e in elements if not e.is_noise
        ]
        
        if not non_noise_elements:
            # All elements are noise, return empty list
            return []
        
        # Create a mapping from original index to non-noise index
        # This is needed because boundaries are indexed by original element positions
        noise_mask = [e.is_noise for e in elements]
        
        # Build units by grouping elements between boundaries
        units = []
        current_unit_elements = []
        current_unit_boundary = None
        
        # Track boundary indices
        boundary_indices = [
            i for i, b in enumerate(boundaries) if b.is_boundary
        ]
        
        # Process each element
        for orig_idx, elem in enumerate(elements):
            if elem.is_noise:
                # Skip noise but track it
                continue
            
            # Check if we've hit a boundary before this element
            if orig_idx in boundary_indices:
                # Save previous unit if it exists
                if current_unit_elements:
                    unit = self._create_unit(
                        current_unit_elements,
                        current_unit_boundary,
                    )
                    units.append(unit)
                
                # Start new unit
                boundary_idx = boundary_indices.index(orig_idx)
                current_unit_boundary = boundaries[orig_idx]
                current_unit_elements = [elem]
            else:
                # Add to current unit
                current_unit_elements.append(elem)
        
        # Save the last unit
        if current_unit_elements:
            unit = self._create_unit(
                current_unit_elements,
                current_unit_boundary,
            )
            units.append(unit)
        
        # Merge adjacent units with same type if they're small
        units = self._merge_small_units(units)
        
        # Extract metadata from headings
        units = self._extract_heading_metadata(units)
        
        return units
    
    def _create_unit(
        self,
        elements: list[LegalElement],
        boundary: Optional[BoundaryDecision],
    ) -> LogicalUnit:
        """
        Create a LogicalUnit from a group of elements.
        
        Args:
            elements: Elements in this unit
            boundary: The boundary that started this unit
            
        Returns:
            LogicalUnit object
        """
        if not elements:
            return LogicalUnit(unit_id="", unit_type="generic", text="")
        
        # Determine unit type
        unit_type = self._determine_unit_type(elements, boundary)
        
        # Combine text
        text = self._combine_text(elements)
        
        # Collect element IDs
        element_ids = [e.element_id for e in elements]
        
        # Determine page range
        page_numbers = [
            e.page_number for e in elements if e.page_number is not None
        ]
        page_start = min(page_numbers) if page_numbers else None
        page_end = max(page_numbers) if page_numbers else None
        
        # Collect source metadata
        source_metadata = {}
        for elem in elements:
            source_metadata[elem.element_id] = elem.source_metadata
        
        return LogicalUnit(
            unit_id="",  # Will be auto-generated
            unit_type=unit_type,
            text=text,
            element_ids=element_ids,
            page_start=page_start,
            page_end=page_end,
            metadata={"source_metadata": source_metadata},
        )
    
    def _determine_unit_type(
        self,
        elements: list[LegalElement],
        boundary: Optional[BoundaryDecision],
    ) -> str:
        """
        Determine the type of logical unit.
        
        Args:
            elements: Elements in the unit
            boundary: The boundary that started this unit
            
        Returns:
            Unit type string
        """
        # If boundary specifies a type, use it
        if boundary and boundary.boundary_type:
            # Handle special cases
            if boundary.boundary_type == "document_title":
                return "document_title"
            elif boundary.boundary_type == "table":
                return "table"
            elif boundary.boundary_type == "list":
                return "list"
            elif boundary.boundary_type in ("section", "clause", "subclause"):
                # Check if it's actually a clause or subclause
                first_text = elements[0].text if elements else ""
                if self._is_clause_heading(first_text):
                    return "clause"
                elif self._is_subclause_heading(first_text):
                    return "subclause"
                else:
                    return boundary.boundary_type
            return boundary.boundary_type
        
        # Default type based on element types
        element_types = {e.element_type for e in elements}
        
        if "Table" in element_types:
            return "table"
        if "List" in element_types or "ListItem" in element_types:
            return "list"
        if "Title" in element_types:
            return "section"
        if "Header" in element_types:
            return "section"
        
        # If we have NarrativeText, it's either a section or paragraph group
        if "NarrativeText" in element_types:
            # Check if first element looks like a heading
            first_text = elements[0].text if elements else ""
            if self._is_clause_heading(first_text):
                return "clause"
            if self._is_section_heading(first_text):
                return "section"
            return "paragraph_group"
        
        return "generic"
    
    def _combine_text(self, elements: list[LegalElement]) -> str:
        """
        Combine text from multiple elements.
        
        Args:
            elements: Elements to combine
            
        Returns:
            Combined text string
        """
        texts = [e.text for e in elements if e.text]
        return "\n\n".join(texts)
    
    def _is_section_heading(self, text: str) -> bool:
        """
        Check if text looks like a section heading.
        
        Args:
            text: Text to check
            
        Returns:
            True if text looks like a section heading
        """
        if not text:
            return False
        
        text = text.strip()
        
        # Check patterns
        for pattern in SECTION_PATTERNS[:8]:  # First 8 patterns are section-level
            if pattern.match(text):
                return True
        
        # Check for ALL CAPS
        if text.isupper() and len(text) > 2:
            return True
        
        # Check for words followed by colons
        if text.endswith(":") and len(text) > 3:
            return True
        
        return False
    
    def _is_clause_heading(self, text: str) -> bool:
        """
        Check if text looks like a clause heading.
        
        Args:
            text: Text to check
            
        Returns:
            True if text looks like a clause heading
        """
        if not text:
            return False
        
        text = text.strip()
        
        # Check for clause patterns
        clause_patterns = [
            r'^Clause\s+',
            r'^\d+\.\d+',
            r'^\d+\.\d+\.\d+',
            r'^Paragraph\s+',
            r'^\([a-z]\)',
            r'^\([ivx]+\)',
        ]
        
        for pattern in clause_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _is_subclause_heading(self, text: str) -> bool:
        """
        Check if text looks like a subclause heading.
        
        Args:
            text: Text to check
            
        Returns:
            True if text looks like a subclause heading
        """
        if not text:
            return False
        
        text = text.strip()
        
        # Check for subclause patterns (more nested)
        subclause_patterns = [
            r'^\d+\.\d+\.\d+',
            r'^\([a-z]\)\s+',
            r'^Subclause\s+',
            r'^[ivx]+\.[a-z]',
        ]
        
        for pattern in subclause_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _merge_small_units(self, units: list[LogicalUnit]) -> list[LogicalUnit]:
        """
        Merge adjacent units with same type if they're small.
        
        This helps avoid creating too many tiny units.
        
        Args:
            units: List of units
            
        Returns:
            List of merged units
        """
        if len(units) <= 1:
            return units
        
        merged = []
        i = 0
        
        while i < len(units):
            current = units[i]
            
            # Look ahead to see if we should merge
            if i < len(units) - 1:
                next_unit = units[i + 1]
                
                # Merge if same type and both are small
                if (current.unit_type == next_unit.unit_type and
                    len(current.text) < 200 and
                    len(next_unit.text) < 200 and
                    current.unit_type in ("paragraph_group", "NarrativeText")):
                    # Create merged unit
                    merged_text = current.text + "\n\n" + next_unit.text
                    merged_ids = current.element_ids + next_unit.element_ids
                    
                    # Determine page range
                    pages = []
                    if current.page_start is not None:
                        pages.append(current.page_start)
                    if current.page_end is not None:
                        pages.append(current.page_end)
                    if next_unit.page_start is not None:
                        pages.append(next_unit.page_start)
                    if next_unit.page_end is not None:
                        pages.append(next_unit.page_end)
                    
                    page_start = min(pages) if pages else None
                    page_end = max(pages) if pages else None
                    
                    merged_unit = LogicalUnit(
                        unit_id="",
                        unit_type=current.unit_type,
                        text=merged_text,
                        element_ids=merged_ids,
                        page_start=page_start,
                        page_end=page_end,
                    )
                    
                    # Combine metadata
                    merged_unit.metadata = {
                        **current.metadata,
                        **next_unit.metadata,
                    }
                    
                    merged.append(merged_unit)
                    i += 2  # Skip next unit
                    continue
            
            merged.append(current)
            i += 1
        
        return merged
    
    def _extract_heading_metadata(self, units: list[LogicalUnit]) -> list[LogicalUnit]:
        """
        Extract section/clause numbers and titles from heading text.
        
        Args:
            units: List of units
            
        Returns:
            List of units with metadata extracted
        """
        for unit in units:
            if not unit.text:
                continue
            
            # Get first line (potential heading)
            first_line = unit.text.split("\n")[0].strip()
            
            # Try to extract section number and title
            for pattern in SECTION_PATTERNS:
                match = pattern.match(first_line)
                if match:
                    groups = match.groups()
                    
                    # Most patterns have 1-2 groups
                    if len(groups) >= 1 and groups[0]:
                        if unit.unit_type in ("section", "document_title"):
                            unit.section_number = groups[0]
                            unit.section_title = groups[1] if len(groups) >= 2 and groups[1] else None
                        elif unit.unit_type == "clause":
                            unit.clause_number = groups[0]
                            unit.clause_title = groups[1] if len(groups) >= 2 and groups[1] else None
                        elif unit.unit_type == "subclause":
                            unit.clause_number = groups[0]
                            unit.clause_title = groups[1] if len(groups) >= 2 and groups[1] else None
                    break
            
            # Special handling for "IN WITNESS WHEREOF" and similar
            if "IN WITNESS WHEREOF" in first_line.upper():
                unit.unit_type = "section"
                unit.section_title = "IN WITNESS WHEREOF"
            
            # Handle title-only units
            if unit.unit_type == "document_title":
                unit.section_title = first_line
        
        return units
