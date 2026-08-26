"""
SQLAlchemy models package.
All database models should be defined here.
"""

from backend.database import Base
from backend.models.documents import Document
from backend.models.chunk_context import ChunkContext
from backend.models.entity_mention import EntityMention

# Import Chunk model from chunking service
try:
    from backend.services.chunking.database import Chunk
    _HAS_CHUNK = True
except ImportError:
    Chunk = None
    _HAS_CHUNK = False

__all__ = ["Base", "Document", "ChunkContext", "EntityMention"]
if _HAS_CHUNK:
    __all__.append("Chunk")

