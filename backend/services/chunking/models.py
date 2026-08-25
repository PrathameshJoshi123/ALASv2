"""
Internal data models for the chunking pipeline.

These dataclasses represent the intermediate data structures used during
processing, preserving all source information for traceability.
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class LegalElement:
    """
    Normalized representation of an Unstructured element.
    
    Every element retains its original source element ID and metadata
    for full traceability back to the PDF.
    
    Attributes:
        element_id: Unique identifier for this element (generated if missing)
        document_id: The document this element belongs to
        element_type: Original Unstructured element type (Title, NarrativeText, etc.)
        text: Normalized text content
        page_number: Page number in the original PDF (1-indexed)
        parent_id: Parent element ID from Unstructured hierarchy
        coordinates: Bounding box coordinates from Unstructured metadata
        source_metadata: Original metadata dictionary from Unstructured
        is_noise: Whether this element has been marked as noise
    """
    element_id: str
    document_id: str
    element_type: str
    text: str
    page_number: Optional[int] = None
    parent_id: Optional[str] = None
    coordinates: Optional[dict[str, Any]] = None
    source_metadata: dict[str, Any] = field(default_factory=dict)
    is_noise: bool = False
    
    def __post_init__(self):
        """Ensure element_id is set."""
        if not self.element_id:
            self.element_id = str(uuid.uuid4())


@dataclass
class BoundaryDecision:
    """
    Decision about whether a boundary exists between elements.
    
    Used by the boundary detector to communicate confidence levels
    and boundary types to the unit builder.
    
    Attributes:
        is_boundary: Whether a boundary exists at this position
        boundary_type: Type of boundary (section, clause, table, etc.)
        confidence: Confidence score (0.0 to 1.0)
        reason: Human-readable explanation for the decision
    """
    is_boundary: bool = False
    boundary_type: Optional[str] = None  # document_title, section, clause, subclause, table, list, paragraph_group
    confidence: float = 0.0
    reason: Optional[str] = None


@dataclass
class LogicalUnit:
    """
    A logical grouping of elements (section, clause, table, etc.).
    
    Units are created by grouping elements between detected boundaries.
    Each unit preserves all source element IDs for traceability.
    
    Attributes:
        unit_id: Unique identifier for this unit
        unit_type: Type of logical unit
        text: Combined text of all elements in this unit
        element_ids: List of source element IDs that make up this unit
        page_start: First page number in this unit
        page_end: Last page number in this unit
        section_number: Extracted section number (if applicable)
        section_title: Extracted section title (if applicable)
        clause_number: Extracted clause number (if applicable)
        clause_title: Extracted clause title (if applicable)
        metadata: Additional metadata dictionary
    """
    unit_id: str
    unit_type: str  # section, clause, subclause, table, list, paragraph_group, generic, document_title
    text: str
    element_ids: list[str] = field(default_factory=list)
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section_number: Optional[str] = None
    section_title: Optional[str] = None
    clause_number: Optional[str] = None
    clause_title: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Ensure unit_id is set."""
        if not self.unit_id:
            self.unit_id = str(uuid.uuid4())


@dataclass
class ChunkingConfig:
    """
    Configuration for the chunking pipeline.
    
    These parameters control how documents are split and chunked.
    
    Attributes:
        chunk_size: Target size for final chunks (characters)
        chunk_overlap: Overlap between chunks for retrieval
        max_unit_size: Maximum size for a logical unit before splitting (layout_aware only)
        chunking_strategy: Strategy to use ("layout_aware" or "recursive")
        length_function: Function to calculate text length
        separators: List of separators for RecursiveCharacterTextSplitter
    """
    chunk_size: int = 800
    chunk_overlap: int = 100
    max_unit_size: int = 2000
    chunking_strategy: str = "layout_aware"
    length_function: Callable[[str], int] = len
    separators: list[str] = field(default_factory=lambda: [
        "\n\n",  # Paragraph breaks first
        "\n",    # Line breaks
        ". ",    # Sentence boundaries
        " ",     # Word boundaries
        "",      # Character-level fallback
    ])


# Patterns for extracting section/clause numbers and titles
SECTION_PATTERNS = [
    # "7. TERMINATION" -> number="7", title="TERMINATION"
    re.compile(r'^(\d+)\s*\.?\s*(.+)$', re.IGNORECASE),
    # "Article I" -> number="I", title=None (or "Article I")
    re.compile(r'^Article\s+([IVXLCDM]+)\s*$', re.IGNORECASE),
    # "Section 2" -> number="2", title=None
    re.compile(r'^Section\s+(\d+)\s*$', re.IGNORECASE),
    # "Clause 3.2" -> number="3.2", title=None
    re.compile(r'^Clause\s+([\d.]+)\s*$', re.IGNORECASE),
    # "Part A" -> number="A", title=None
    re.compile(r'^Part\s+([A-Z])\s*$', re.IGNORECASE),
    # "Schedule B" -> number="B", title=None
    re.compile(r'^Schedule\s+([A-Z])\s*$', re.IGNORECASE),
    # "1.1 Introduction" -> number="1.1", title="Introduction"
    re.compile(r'^([\d.]+)\s+(.+)$', re.IGNORECASE),
    # "Chapter 1: Introduction" -> number="1", title="Introduction"
    re.compile(r'^Chapter\s+(\d+)\s*:?\s*(.*)$', re.IGNORECASE),
    # "Paragraph (a)" -> number="(a)", title=None
    re.compile(r'^Paragraph\s+\(([a-z])\)\s*$', re.IGNORECASE),
    # "3.2.1" -> number="3.2.1", title=None
    re.compile(r'^([\d.]+)\s*$'),
]

# Legal terms that should NOT be marked as noise even if short
LEGAL_TERMS = {
    "agreement",
    "contract",
    "party",
    "parties",
    "whereas",
    "witnesseth",
    "now therefore",
    "in witness whereof",
    "executed",
    "signed",
    "dated",
    "effective",
    "term",
    "terms",
    "condition",
    "conditions",
    "consideration",
    "hereby",
    "hereinafter",
    "hereto",
    "hereunder",
    "schedule",
    "exhibit",
    "article",
    "section",
    "clause",
    "subclause",
    "paragraph",
    "part",
    "chapter",
    "recital",
    "warrant",
    "warranty",
    "liability",
    "indemnify",
    "indemnification",
    "force majeure",
    "governing law",
    "jurisdiction",
    "arbitration",
    "mediation",
    "assignment",
    "amendment",
    "termination",
    "confidentiality",
    "confidential",
    "proprietary",
    "intellectual property",
}

# Common noise patterns
NOISE_PATTERNS = [
    # Page numbers: standalone numbers
    re.compile(r'^\d+$'),
    # Copyright notices
    re.compile(r'copyright|©|\b20\d{2}\b', re.IGNORECASE),
    # Confidential notices
    re.compile(r'confidential\b', re.IGNORECASE),
    # Page X of Y
    re.compile(r'page\s+\d+\s+(?:of|/)\s+\d+', re.IGNORECASE),
    # Draft watermarks
    re.compile(r'draft|for review|uncontrolled copy', re.IGNORECASE),
]
