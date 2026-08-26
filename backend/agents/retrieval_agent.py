import os
import json
import re
import math
import logging
from typing import Any, List, Dict, Optional
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from langchain_mistralai import ChatMistralAI
from deepagents import create_deep_agent
from langchain_quickjs import CodeInterpreterMiddleware

from backend.database import SessionLocal
from backend.services.chunking.database import Chunk
from backend.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# BM25 Helper Class
# ============================================================

class SimpleBM25:
    """
    A lightweight, pure-Python implementation of the BM25 algorithm.
    """
    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.avg_doc_len = sum(len(doc) for doc in corpus) / self.corpus_size if self.corpus_size > 0 else 0
        self.doc_freqs = []
        self.doc_lens = []
        self.idf = {}
        
        nd = {}  # term -> number of docs containing term
        for doc in corpus:
            self.doc_lens.append(len(doc))
            frequencies = {}
            for term in doc:
                frequencies[term] = frequencies.get(term, 0) + 1
            self.doc_freqs.append(frequencies)
            
            for term in frequencies:
                nd[term] = nd.get(term, 0) + 1
                
        for term, freq in nd.items():
            self.idf[term] = math.log(1 + (self.corpus_size - freq + 0.5) / (freq + 0.5))
            
    def get_scores(self, query: List[str]) -> List[float]:
        scores = [0.0] * self.corpus_size
        for i in range(self.corpus_size):
            doc_len = self.doc_lens[i]
            frequencies = self.doc_freqs[i]
            score = 0.0
            for term in query:
                if term not in frequencies:
                    continue
                freq = frequencies[term]
                numerator = self.idf.get(term, 0.0) * freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)
                score += numerator / denominator
            scores[i] = score
        return scores


# ============================================================
# Retrieval & Search Tools
# ============================================================

def search_chunks_vector_db(document_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search document chunks using semantic similarity search in Chroma DB.
    
    Args:
        document_id: Unique identifier for the document
        query: Search query/question
        limit: Maximum number of chunks to return (default: 5)
    """
    logger.info(f"Vector search in Chroma DB for doc {document_id}: '{query}'")
    try:
        from backend.services.vector_storage import get_vector_store
        vectorstore = get_vector_store()
        
        results = vectorstore.similarity_search(
            query,
            k=limit,
            filter={"document_id": document_id}
        )
        
        top_chunks = []
        for doc in results:
            top_chunks.append({
                "chunk_id": doc.metadata.get("chunk_id"),
                "content": doc.page_content,
                "sequence_number": doc.metadata.get("sequence_number"),
                "page_start": doc.metadata.get("page_start"),
                "page_end": doc.metadata.get("page_end"),
                "unit_type": doc.metadata.get("chunk_type") or doc.metadata.get("unit_type"),
            })
        return top_chunks
    except Exception as e:
        logger.error(f"Vector search failed: {e}", exc_info=True)
        return []


def search_chunks_bm25(document_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search document chunks in the SQL database using keyword BM25 search.
    
    Args:
        document_id: Unique identifier for the document
        query: Search query/keywords
        limit: Maximum number of chunks to return (default: 5)
    """
    logger.info(f"BM25 search in SQL DB for doc {document_id}: '{query}'")
    try:
        with SessionLocal() as db:
            result = db.execute(
                select(Chunk)
                .where(Chunk.document_id == document_id)
                .order_by(Chunk.sequence_number)
            )
            chunks = result.scalars().all()
            
            if not chunks:
                return []
                
            def tokenize(text: str) -> List[str]:
                return re.findall(r'\w+', text.lower())
                
            corpus = [tokenize(c.content) for c in chunks]
            tokenized_query = tokenize(query)
            
            bm25 = SimpleBM25(corpus)
            scores = bm25.get_scores(tokenized_query)
            
            ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            
            top_chunks = []
            for i in ranked_indices[:limit]:
                if scores[i] > 0.0:
                    top_chunks.append({
                        "chunk_id": chunks[i].chunk_id,
                        "content": chunks[i].content,
                        "sequence_number": chunks[i].sequence_number,
                        "page_start": chunks[i].page_start,
                        "page_end": chunks[i].page_end,
                        "score": scores[i],
                    })
            return top_chunks
    except Exception as e:
        logger.error(f"BM25 search failed: {e}", exc_info=True)
        return []


def get_chunk_by_sequence(document_id: str, sequence_number: int) -> Dict[str, Any]:
    """
    Retrieve a single specific chunk by its sequence number from the SQL database.
    
    Args:
        document_id: Unique identifier for the document
        sequence_number: Sequence number of the chunk (1-indexed)
    """
    with SessionLocal() as db:
        result = db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .where(Chunk.sequence_number == sequence_number)
        )
        chunk = result.scalar_one_or_none()
        if chunk:
            return chunk.to_dict()
        return {}


def get_surrounding_chunks(document_id: str, sequence_number: int, context_window: int = 1) -> List[Dict[str, Any]]:
    """
    Retrieve neighboring chunks around a given sequence number from the SQL database.
    Use this to read context before and after a matched chunk.
    
    Args:
        document_id: Unique identifier for the document
        sequence_number: Sequence number of the target chunk
        context_window: Number of chunks before and after to fetch (default: 1)
    """
    with SessionLocal() as db:
        start = max(1, sequence_number - context_window)
        end = sequence_number + context_window
        result = db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .where(Chunk.sequence_number.between(start, end))
            .order_by(Chunk.sequence_number)
        )
        chunks = result.scalars().all()
        return [c.to_dict() for c in chunks]


def get_total_chunks_count(document_id: str) -> int:
    """
    Retrieve the total number of chunks (maximum sequence number) available in the SQL database for a document.
    
    Args:
        document_id: Unique identifier for the document
    """
    with SessionLocal() as db:
        result = db.execute(
            select(func.count(Chunk.chunk_id))
            .where(Chunk.document_id == document_id)
        )
        return result.scalar() or 0


# ============================================================
# Response Model & Agent Definition
# ============================================================

class RetrievalAgentResult(BaseModel):
    """
    Result representing the agent's answer and findings.
    """
    answer: str = Field(description="The final comprehensive answer answering the user's query.")
    citations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Citations supporting the answer, containing chunk_id, page_start, page_end, content snippet, and optional clause/section references."
    )
    unresolved_parts: List[str] = Field(
        default_factory=list,
        description="Any parts of the user query that could not be resolved or answered based on the retrieved document contents."
    )


RETRIEVAL_AGENT_PROMPT = """
You are the Document Retrieval & QA Agent.

Your job is to answer questions about a legal document by retrieving the most relevant chunks using your search tools.

REASONING AND PLANNING PROCESS:
1. Deconstruct the user's question to identify key concepts, dates, parties, obligations, or definitions.
2. Use `search_chunks_vector_db` for semantic search (concepts, synonym matching).
3. Use `search_chunks_bm25` for keyword search (exact names, specific section numbers, abbreviations).
4. If you find a relevant chunk that refers to a section or contains references like "the foregoing" or "this Section 4", retrieve neighboring chunks using `get_surrounding_chunks` or specific sequence numbers using `get_chunk_by_sequence` to resolve context.
5. If the document references a defined term, use keyword search to find where it is defined.
6. Plan your search strategy step-by-step. If your first search yields no results, adjust your query and try again.
7. Synthesize a complete and accurate answer. Provide citations (chunk_id, page numbers, text snippets) for all claims.

STRICT GUIDELINES:
- Always use the actual `document_id` UUID provided in the request instructions.
- Do not invent information or make assumptions. If the document does not contain the answer, state that it is UNKNOWN or unresolved.
"""

def get_ministral_model() -> ChatMistralAI:
    """Initialize the Ministral model for the retrieval agent."""
    api_key = settings.MISTRAL_API_KEY or os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY is not configured.")
    return ChatMistralAI(
        model="ministral-14b-2512",
        api_key=api_key,
        temperature=0.0,
    )


def create_retrieval_agent() -> Any:
    """
    Create the retrieval agent.
    """
    from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
    
    backend = CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(
                namespace=lambda rt: ("document-retrieval", "v1")
            ),
            "/skills/": StoreBackend(
                namespace=lambda rt: ("document-retrieval", "v1")
            ),
        },
    )
    
    return create_deep_agent(
        model=get_ministral_model(),
        system_prompt=RETRIEVAL_AGENT_PROMPT,
        backend=backend,
        skills=["backend/skills/document-retrieval"],
        tools=[
            search_chunks_vector_db,
            search_chunks_bm25,
            get_chunk_by_sequence,
            get_surrounding_chunks,
            get_total_chunks_count,
        ],
        middleware=[
            CodeInterpreterMiddleware()
        ],
        response_format=RetrievalAgentResult,
    )
