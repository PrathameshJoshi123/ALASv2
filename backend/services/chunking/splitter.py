"""
Splitter for dividing oversized logical units into smaller chunks.

Uses RecursiveCharacterTextSplitter from LangChain as a fallback
when logical units exceed the maximum size.
"""

import uuid
from typing import Any, Optional

from backend.services.chunking.models import (
    ChunkingConfig,
    LogicalUnit,
)


class UnitSplitter:
    """
    Splits oversized logical units using RecursiveCharacterTextSplitter.
    
    The splitter is ONLY a fallback - logical grouping has priority.
    Child chunks inherit all parent metadata.
    """
    
    def __init__(self):
        """Initialize the splitter."""
        self._splitter_cache: dict[tuple, Any] = {}
    
    def split(
        self,
        units: list[LogicalUnit],
        config: ChunkingConfig,
    ) -> list[LogicalUnit]:
        """
        Split oversized units.
        
        Args:
            units: List of LogicalUnit objects
            config: ChunkingConfig with splitting parameters
            
        Returns:
            List of LogicalUnit objects (some may be split)
        """
        if not units:
            return []
        
        split_units = []
        
        for unit in units:
            # Check if unit needs splitting
            text_length = config.length_function(unit.text)
            
            if text_length <= config.max_unit_size:
                # Unit is fine as-is
                split_units.append(unit)
            else:
                # Unit needs splitting
                child_units = self._split_unit(unit, config)
                split_units.extend(child_units)
        
        return split_units
    
    def _split_unit(
        self,
        unit: LogicalUnit,
        config: ChunkingConfig,
    ) -> list[LogicalUnit]:
        """
        Split a single oversized unit into child units.
        
        Args:
            unit: The unit to split
            config: ChunkingConfig
            
        Returns:
            List of child LogicalUnit objects
        """
        # Get or create the text splitter
        cache_key = (
            config.chunk_size,
            config.chunk_overlap,
            tuple(config.separators),
        )
        
        if cache_key not in self._splitter_cache:
            try:
                from langchain_text_splitters import RecursiveCharacterTextSplitter
                
                self._splitter_cache[cache_key] = RecursiveCharacterTextSplitter(
                    chunk_size=config.chunk_size,
                    chunk_overlap=config.chunk_overlap,
                    length_function=config.length_function,
                    separators=config.separators,
                )
            except ImportError:
                # Fallback to simple splitting
                self._splitter_cache[cache_key] = None
        
        splitter = self._splitter_cache[cache_key]
        
        if splitter is None:
            # Simple fallback splitting
            return self._simple_split(unit, config)
        
        # Use LangChain splitter
        try:
            chunks = splitter.split_text(unit.text)
        except Exception:
            # If splitting fails, return original unit
            return [unit]
        
        # Create child units from chunks
        child_units = []
        total_chunks = len(chunks)
        
        for idx, chunk_text in enumerate(chunks):
            child_unit = LogicalUnit(
                unit_id=str(uuid.uuid4()),
                unit_type=unit.unit_type,
                text=chunk_text,
                element_ids=unit.element_ids,  # Preserve source IDs
                page_start=unit.page_start,
                page_end=unit.page_end,
                section_number=unit.section_number,
                section_title=unit.section_title,
                clause_number=unit.clause_number,
                clause_title=unit.clause_title,
                metadata={
                    **unit.metadata,
                    "parent_unit_id": unit.unit_id,
                    "chunk_index": idx,
                    "total_chunks_in_unit": total_chunks,
                },
            )
            child_units.append(child_unit)
        
        return child_units
    
    def _simple_split(
        self,
        unit: LogicalUnit,
        config: ChunkingConfig,
    ) -> list[LogicalUnit]:
        """
        Simple fallback splitting when LangChain is not available.
        
        Args:
            unit: The unit to split
            config: ChunkingConfig
            
        Returns:
            List of child LogicalUnit objects
        """
        text = unit.text
        chunk_size = config.chunk_size
        overlap = config.chunk_overlap
        
        # Split on paragraph boundaries first
        paragraphs = text.split("\n\n")
        
        if len(paragraphs) <= 1:
            # No paragraphs, split on sentences
            sentences = self._split_sentences(text)
            if len(sentences) <= 1:
                # Just return original - can't split meaningfully
                return [unit]
            
            # Group sentences into chunks
            chunks = []
            current_chunk = []
            current_length = 0
            
            for sent in sentences:
                sent_len = config.length_function(sent)
                
                if current_length + sent_len <= chunk_size:
                    current_chunk.append(sent)
                    current_length += sent_len + 1  # +1 for space
                else:
                    if current_chunk:
                        chunks.append(" ".join(current_chunk))
                    current_chunk = [sent]
                    current_length = sent_len
            
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            
            if not chunks:
                return [unit]
        else:
            # Split by paragraphs
            chunks = []
            current_chunk_paragraphs = []
            current_length = 0
            
            for para in paragraphs:
                para_len = config.length_function(para)
                
                if current_length + para_len <= chunk_size:
                    current_chunk_paragraphs.append(para)
                    current_length += para_len + 2  # +2 for \n\n
                else:
                    if current_chunk_paragraphs:
                        chunks.append("\n\n".join(current_chunk_paragraphs))
                    current_chunk_paragraphs = [para]
                    current_length = para_len
            
            if current_chunk_paragraphs:
                chunks.append("\n\n".join(current_chunk_paragraphs))
            
            if not chunks:
                return [unit]
        
        # Create child units
        child_units = []
        total_chunks = len(chunks)
        
        for idx, chunk_text in enumerate(chunks):
            child_unit = LogicalUnit(
                unit_id=str(uuid.uuid4()),
                unit_type=unit.unit_type,
                text=chunk_text,
                element_ids=unit.element_ids,
                page_start=unit.page_start,
                page_end=unit.page_end,
                section_number=unit.section_number,
                section_title=unit.section_title,
                clause_number=unit.clause_number,
                clause_title=unit.clause_title,
                metadata={
                    **unit.metadata,
                    "parent_unit_id": unit.unit_id,
                    "chunk_index": idx,
                    "total_chunks_in_unit": total_chunks,
                },
            )
            child_units.append(child_unit)
        
        return child_units
    
    def _split_sentences(self, text: str) -> list[str]:
        """
        Split text into sentences.
        
        Args:
            text: Text to split
            
        Returns:
            List of sentences
        """
        # Simple sentence splitting - look for sentence-ending punctuation
        # followed by whitespace and a capital letter
        sentences = []
        current = []
        
        for char in text:
            current.append(char)
            
            # Check if we're at a sentence boundary
            if char in ".!?" and len(current) > 1:
                # Look ahead (but we're processing sequentially, so we need to check)
                # Instead, we'll check the last few characters
                pass
        
        # Simpler approach: split on punctuation followed by space and capital
        import re
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        sentences = re.split(sentence_pattern, text)
        
        # Filter out empty strings
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences if sentences else [text]
