"""
Document model for storing PDF contracts and their metadata.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Document(Base):
    """
    Document model representing uploaded PDF contracts.
    
    Attributes:
        id: Unique identifier for the document (UUID string)
        name: Original name of the document
        storage_link: Path to the stored PDF file
        date_created: Timestamp when the document was uploaded
    """
    
    __tablename__ = "documents"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    storage_link: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"Document(id={self.id}, name={self.name}, storage_link={self.storage_link})"
