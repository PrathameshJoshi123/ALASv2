"""
SQLAlchemy models package.
All database models should be defined here.
"""

from backend.database import Base
from backend.models.documents import Document

__all__ = ["Base", "Document"]
