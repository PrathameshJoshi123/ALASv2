"""
Chunking Service for transforming Unstructured PDF elements into LangChain Documents.

This service implements a pipeline for:
- Normalizing Unstructured elements
- Detecting and marking noise
- Detecting logical boundaries (sections, clauses, tables)
- Building logical units
- Splitting oversized units
- Creating LangChain Document objects with full traceability
"""

from backend.services.chunking.models import (
    LegalElement,
    BoundaryDecision,
    LogicalUnit,
    ChunkingConfig,
)
from backend.services.chunking.pipeline import ChunkingPipeline

__all__ = [
    "LegalElement",
    "BoundaryDecision",
    "LogicalUnit",
    "ChunkingConfig",
    "ChunkingPipeline",
]
