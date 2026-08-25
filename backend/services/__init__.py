"""
Services package.
Business logic and service layer components.
"""

from backend.services.pdf_service import PDFService, pdf_service

# Import chunking service if available
try:
    from backend.services.chunking import (
        ChunkingPipeline,
        LegalElement,
        LogicalUnit,
        BoundaryDecision,
        ChunkingConfig,
    )
    _HAS_CHUNKING = True
except ImportError:
    ChunkingPipeline = None
    LegalElement = None
    LogicalUnit = None
    BoundaryDecision = None
    ChunkingConfig = None
    _HAS_CHUNKING = False

__all__ = ["PDFService", "pdf_service"]
if _HAS_CHUNKING:
    __all__.extend([
        "ChunkingPipeline",
        "LegalElement",
        "LogicalUnit",
        "BoundaryDecision",
        "ChunkingConfig",
    ])
