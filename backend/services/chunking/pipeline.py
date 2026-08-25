"""
Main Chunking Pipeline for transforming Unstructured elements to LangChain Documents.

Implements the exact flow:
    Unstructured elements
        ↓
    Normalize elements
        ↓
    Mark possible noise
        ↓
    Detect logical boundaries
        ↓
    Build logical units
        ↓
    Split only oversized units
        ↓
    Create LangChain Documents
        ↓
    Save to database (optional)
"""

from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.services.chunking.database import (
    Chunk,
    save_chunks_to_db,
)
from backend.services.chunking.document_builder import DocumentBuilder
from backend.services.chunking.models import (
    ChunkingConfig,
    LegalElement,
)
from backend.services.chunking.normalizer import ElementNormalizer
from backend.services.chunking.noise_detector import NoiseDetector
from backend.services.chunking.boundary_detector import BoundaryDetector
from backend.services.chunking.unit_builder import UnitBuilder
from backend.services.chunking.splitter import UnitSplitter


class ChunkingPipeline:
    """
    Complete pipeline for processing Unstructured elements into LangChain Documents.
    
    The pipeline follows this exact flow:
    1. Normalize elements (generate IDs, normalize text, extract metadata)
    2. Mark noise (identify headers, footers, page numbers, etc.)
    3. Detect boundaries (find section, clause, table, list boundaries)
    4. Build logical units (group elements between boundaries)
    5. Split oversized units (fallback for units exceeding max size)
    6. Create LangChain Documents (with full traceability metadata)
    7. Save to database (optional)
    
    Every step preserves element IDs for full traceability.
    """
    
    def __init__(self, config: Optional[ChunkingConfig] = None):
        """
        Initialize the pipeline.
        
        Args:
            config: Optional ChunkingConfig. Defaults to standard settings.
        """
        self.config = config or ChunkingConfig()
        
        # Initialize all components
        self.normalizer = ElementNormalizer()
        self.noise_detector = NoiseDetector()
        self.boundary_detector = BoundaryDetector()
        self.unit_builder = UnitBuilder()
        self.splitter = UnitSplitter()
        self.document_builder = DocumentBuilder()
    
    def process(
        self,
        elements: list[dict[str, Any]],
        document_id: str,
        filename: str,
    ) -> list[Any]:
        """
        Process Unstructured elements through the selected chunking strategy.
        
        Args:
            elements: List of Unstructured element dictionaries
            document_id: The document ID to associate with these elements
            filename: The original filename
            
        Returns:
            List of LangChain Document objects (or dicts if langchain-core unavailable)
        """
        strategy = getattr(self.config, "chunking_strategy", "layout_aware")
        
        if strategy == "recursive":
            return self._process_recursive(elements, document_id, filename)
        else:
            return self._process_layout_aware(elements, document_id, filename)

    def _process_layout_aware(
        self,
        elements: list[dict[str, Any]],
        document_id: str,
        filename: str,
    ) -> list[Any]:
        """Process elements using the layout-aware chunking strategy."""
        # Step 1: Normalize elements
        legal_elements = self.normalizer.normalize(elements, document_id, filename)
        
        if not legal_elements:
            # Empty document
            return []
        
        # Step 2: Detect and mark noise
        legal_elements = self.noise_detector.mark_noise(legal_elements)
        
        # Step 3: Detect logical boundaries
        boundaries = self.boundary_detector.detect(legal_elements)
        
        # Step 4: Build logical units
        units = self.unit_builder.build(legal_elements, boundaries)
        
        if not units:
            # All elements were noise
            return []
        
        # Step 5: Split oversized units
        units = self.splitter.split(units, self.config)
        
        # Step 6: Create LangChain Documents
        documents = self.document_builder.create(units, document_id, filename)
        
        return documents

    def _process_recursive(
        self,
        elements: list[dict[str, Any]],
        document_id: str,
        filename: str,
    ) -> list[Any]:
        """Process elements using the recursive character text splitting strategy."""
        # Step 1: Normalize elements
        legal_elements = self.normalizer.normalize(elements, document_id, filename)
        
        if not legal_elements:
            return []
            
        # Step 2: Mark noise
        legal_elements = self.noise_detector.mark_noise(legal_elements)
        
        # Step 3: Filter out noise elements
        non_noise_elements = [e for e in legal_elements if not e.is_noise]
        
        if not non_noise_elements:
            return []
            
        # Step 4: Combine text and track source offsets
        combined_text = ""
        element_offsets = []
        
        for elem in non_noise_elements:
            start_pos = len(combined_text)
            combined_text += elem.text + "\n\n"
            end_pos = len(combined_text)
            element_offsets.append((start_pos, end_pos, elem.page_number, elem.element_id))
            
        # Step 5: Split text using RecursiveCharacterTextSplitter
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                length_function=self.config.length_function,
                separators=self.config.separators,
            )
        except ImportError:
            splitter = None
            
        if splitter is not None:
            chunks = splitter.split_text(combined_text)
        else:
            # Simple fallback splitting by paragraph/length
            chunks = self._simple_split_text(combined_text)
            
        # Step 6: Create LangChain Document objects (or dicts)
        documents = []
        current_pos = 0
        total_chunks = len(chunks)
        
        # Import UUID and langchain core Document safely
        import uuid
        try:
            from langchain_core.documents import Document as LCDocument
            has_langchain = True
        except ImportError:
            has_langchain = False
            
        for idx, chunk in enumerate(chunks):
            # Trace pages and elements overlapping this chunk
            clean_chunk = chunk.strip()
            idx_found = combined_text.find(clean_chunk, current_pos)
            if idx_found != -1:
                chunk_start = idx_found
                chunk_end = idx_found + len(clean_chunk)
                current_pos = chunk_start + len(clean_chunk)
            else:
                chunk_start = current_pos
                chunk_end = current_pos + len(chunk)
                current_pos = chunk_end
                
            pages = []
            source_element_ids = []
            for start, end, page, elem_id in element_offsets:
                if max(start, chunk_start) < min(end, chunk_end):
                    if page is not None:
                        pages.append(page)
                    source_element_ids.append(elem_id)
                    
            page_start = min(pages) if pages else None
            page_end = max(pages) if pages else None
            
            chunk_id = str(uuid.uuid4())
            metadata = {
                "document_id": document_id,
                "chunk_id": chunk_id,
                "chunk_type": "recursive_chunk",
                "page_start": page_start,
                "page_end": page_end,
                "source_element_ids": source_element_ids,
                "source_filename": filename,
                "chunk_index": idx,
                "total_chunks": total_chunks,
            }
            
            if has_langchain:
                doc = LCDocument(page_content=chunk, metadata=metadata)
            else:
                doc = {
                    "page_content": chunk,
                    "metadata": metadata,
                }
            documents.append(doc)
            
        return documents

    def _simple_split_text(self, text: str) -> list[str]:
        """Simple fallback text splitter grouping paragraphs by chunk size."""
        paragraphs = text.split("\n\n")
        chunks = []
        current = []
        current_len = 0
        for p in paragraphs:
            p_len = len(p)
            if current_len + p_len > self.config.chunk_size and current:
                chunks.append("\n\n".join(current))
                current = [p]
                current_len = p_len
            else:
                current.append(p)
                current_len += p_len + 2
        if current:
            chunks.append("\n\n".join(current))
        return chunks
    
    def process_and_save(
        self,
        elements: list[dict[str, Any]],
        document_id: str,
        filename: str,
        db: Session,
    ) -> list[Chunk]:
        """
        Process elements and save resulting chunks to the database.
        
        Args:
            elements: List of Unstructured element dictionaries
            document_id: The document ID to associate with these elements
            filename: The original filename
            db: SQLAlchemy database session
            
        Returns:
            List of saved Chunk objects
        """
        # Process through pipeline
        documents = self.process(elements, document_id, filename)
        
        # Save to database
        chunks = save_chunks_to_db(documents, document_id, db)
        
        return chunks
    
    def get_summary(self, documents: list[Any]) -> dict[str, Any]:
        """
        Get a summary of the processing results.
        
        Args:
            documents: List of LangChain Document objects from process()
            
        Returns:
            Summary dictionary with counts and statistics
        """
        summary = {
            "total_chunks": len(documents),
            "chunk_types": {},
            "page_ranges": [],
        }
        
        for doc in documents:
            if hasattr(doc, "metadata"):
                metadata = doc.metadata
            elif isinstance(doc, dict):
                metadata = doc.get("metadata", {})
            else:
                continue
            
            # Count by type
            chunk_type = metadata.get("chunk_type", "unknown")
            summary["chunk_types"][chunk_type] = summary["chunk_types"].get(chunk_type, 0) + 1
            
            # Track page ranges
            page_start = metadata.get("page_start")
            page_end = metadata.get("page_end")
            if page_start is not None and page_end is not None:
                summary["page_ranges"].append({
                    "start": page_start,
                    "end": page_end,
                })
        
        # Add section/clause info if available
        section_numbers = set()
        clause_numbers = set()
        
        for doc in documents:
            if hasattr(doc, "metadata"):
                metadata = doc.metadata
            elif isinstance(doc, dict):
                metadata = doc.get("metadata", {})
            else:
                continue
            
            if metadata.get("section_number"):
                section_numbers.add(metadata["section_number"])
            if metadata.get("clause_number"):
                clause_numbers.add(metadata["clause_number"])
        
        summary["sections_found"] = sorted(section_numbers)
        summary["clauses_found"] = sorted(clause_numbers)
        
        return summary


def create_pipeline(
    chunk_size: int = 800,
    chunk_overlap: int = 100,
    max_unit_size: int = 2000,
    chunking_strategy: str = "layout_aware",
) -> ChunkingPipeline:
    """
    Convenience function to create a pipeline with custom configuration.
    
    Args:
        chunk_size: Target chunk size in characters
        chunk_overlap: Overlap between chunks
        max_unit_size: Maximum logical unit size before splitting
        chunking_strategy: Strategy to use ("layout_aware" or "recursive")
        
    Returns:
        Configured ChunkingPipeline
    """
    config = ChunkingConfig(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        max_unit_size=max_unit_size,
        chunking_strategy=chunking_strategy,
    )
    return ChunkingPipeline(config)
