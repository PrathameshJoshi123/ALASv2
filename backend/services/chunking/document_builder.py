"""
Document Builder for creating LangChain Document objects from logical units.

Converts LogicalUnit objects to LangChain Document objects with full
metadata for traceability, retrieval, and citations.
"""

import uuid
from typing import Any, Optional

from backend.services.chunking.models import (
    ChunkingConfig,
    LogicalUnit,
)


class DocumentBuilder:
    """
    Builds LangChain Document objects from LogicalUnit objects.
    
    Each Document contains:
    - page_content: The text content
    - metadata: Full traceability information including:
        - document_id
        - chunk_id
        - parent_unit_id
        - chunk_type
        - section_number/title
        - clause_number/title
        - page_start/end
        - source_element_ids
        - source_filename
        - chunk_index (if split)
        - total_chunks_in_unit (if split)
    """
    
    def __init__(self):
        """Initialize the document builder."""
        pass
    
    def create(
        self,
        units: list[LogicalUnit],
        document_id: str,
        filename: str,
        config: Optional[ChunkingConfig] = None,
    ) -> list[Any]:
        """
        Create LangChain Document objects from logical units.
        
        Args:
            units: List of LogicalUnit objects
            document_id: The source document ID
            filename: The source filename
            config: Optional ChunkingConfig (unused here but kept for interface)
            
        Returns:
            List of LangChain Document objects
        """
        documents = []
        
        for unit in units:
            doc = self._unit_to_document(unit, document_id, filename)
            documents.append(doc)
        
        return documents
    
    def _unit_to_document(
        self,
        unit: LogicalUnit,
        document_id: str,
        filename: str,
    ) -> Any:
        """
        Convert a single LogicalUnit to a LangChain Document.
        
        Args:
            unit: The LogicalUnit to convert
            document_id: The source document ID
            filename: The source filename
            
        Returns:
            LangChain Document object
        """
        # Generate unique chunk ID
        chunk_id = str(uuid.uuid4())
        
        # Build metadata dictionary
        metadata: dict[str, Any] = {
            "document_id": document_id,
            "chunk_id": chunk_id,
            "parent_unit_id": unit.unit_id,
            "chunk_type": unit.unit_type,
            "page_start": unit.page_start,
            "page_end": unit.page_end,
            "source_element_ids": unit.element_ids,
            "source_filename": filename,
        }
        
        # Add section/clause info if available
        if unit.section_number:
            metadata["section_number"] = unit.section_number
        if unit.section_title:
            metadata["section_title"] = unit.section_title
        if unit.clause_number:
            metadata["clause_number"] = unit.clause_number
        if unit.clause_title:
            metadata["clause_title"] = unit.clause_title
        
        # Add chunking metadata if this unit was split
        if "parent_unit_id" in unit.metadata:
            metadata["parent_unit_id"] = unit.metadata["parent_unit_id"]
        if "chunk_index" in unit.metadata:
            metadata["chunk_index"] = unit.metadata["chunk_index"]
        if "total_chunks_in_unit" in unit.metadata:
            metadata["total_chunks_in_unit"] = unit.metadata["total_chunks_in_unit"]
        
        # Add any additional metadata from the unit
        metadata.update(unit.metadata)
        
        # Import Document from langchain_core
        try:
            from langchain_core.documents import Document
            return Document(
                page_content=unit.text,
                metadata=metadata,
            )
        except ImportError:
            # Fallback: return a dictionary with the same structure
            # This allows the pipeline to continue even without langchain-core
            return {
                "page_content": unit.text,
                "metadata": metadata,
            }
