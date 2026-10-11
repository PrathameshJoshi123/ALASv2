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


ENGLISH_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from", "further", "had",
    "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were", "what", "when", "where",
    "which", "while", "who", "whom", "why", "with", "would", "you", "your", "yours"
}


def clean_and_stem_tokens(text: str) -> List[str]:
    """Extract tokens, remove stopwords, and normalize prefixes for BM25 matching."""
    raw_tokens = re.findall(r'\w+', text.lower())
    clean_tokens = []
    for token in raw_tokens:
        if token in ENGLISH_STOP_WORDS or len(token) < 2:
            continue
        stemmed = token[:5] if len(token) > 6 else token
        clean_tokens.append(stemmed)
    return clean_tokens or raw_tokens


# ============================================================
# Retrieval & Search Tools
# ============================================================

def search_chunks_vector_db(document_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search document chunks using semantic similarity search in Chroma DB.
    Self-healing: If Chroma DB returns 0 results for document_id, automatically populates Chroma DB
    from the SQL Chunk database on the fly and retries search.
    
    Args:
        document_id: Unique identifier for the document
        query: Search query/question
        limit: Maximum number of chunks to return (default: 10)
    """
    logger.info(f"Vector search in Chroma DB for doc {document_id}: '{query}'")
    try:
        from backend.services.vector_storage import get_vector_store, store_chunks_in_vector_db
        vectorstore = get_vector_store()
        
        results = vectorstore.similarity_search(
            query,
            k=limit,
            filter={"document_id": document_id}
        )
        
        # Self-healing index recovery if 0 results returned from Chroma
        if not results:
            logger.warning(f"Chroma DB returned 0 vector search results for doc {document_id}. Syncing SQL chunks to Chroma DB...")
            with SessionLocal() as db:
                sql_chunks = db.execute(
                    select(Chunk)
                    .where(Chunk.document_id == document_id)
                    .order_by(Chunk.sequence_number)
                ).scalars().all()
                
                if sql_chunks:
                    logger.info(f"Auto-syncing {len(sql_chunks)} SQL chunks to Chroma DB for doc {document_id}...")
                    store_chunks_in_vector_db(sql_chunks, document_id)
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
        logger.error(f"Vector search failed for doc {document_id}: {e}", exc_info=True)
        return []


def search_chunks_bm25(document_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search document chunks in the SQL database using smart keyword BM25 search + SQL ILIKE fallback.
    
    Args:
        document_id: Unique identifier for the document
        query: Search query/keywords
        limit: Maximum number of chunks to return (default: 10)
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
                
            corpus = [clean_and_stem_tokens(c.content) for c in chunks]
            tokenized_query = clean_and_stem_tokens(query)
            
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
                    
            # Fallback to SQL ILIKE search if BM25 scores 0 results
            if not top_chunks and tokenized_query:
                logger.info(f"BM25 scored 0 results for doc {document_id}. Falling back to SQL ILIKE search...")
                keywords = [k for k in query.split() if k.lower() not in ENGLISH_STOP_WORDS]
                if keywords:
                    first_kw = keywords[0]
                    ilike_res = db.execute(
                        select(Chunk)
                        .where(Chunk.document_id == document_id)
                        .where(Chunk.content.ilike(f"%{first_kw}%"))
                        .order_by(Chunk.sequence_number)
                        .limit(limit)
                    ).scalars().all()
                    for c in ilike_res:
                        top_chunks.append({
                            "chunk_id": c.chunk_id,
                            "content": c.content,
                            "sequence_number": c.sequence_number,
                            "page_start": c.page_start,
                            "page_end": c.page_end,
                            "score": 1.0,
                        })
                        
            return top_chunks
    except Exception as e:
        logger.error(f"BM25 search failed: {e}", exc_info=True)
        return []


def hybrid_search_chunks(document_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Perform hybrid retrieval combining vector similarity search and BM25 keyword matching into 1 tool call.
    Deduplicates results and returns top relevant chunks ordered by sequence number.
    
    Args:
        document_id: Unique identifier for the document
        query: Search query/question
        limit: Maximum number of chunks to return (default: 10)
    """
    logger.info(f"Hybrid search tool call for doc {document_id}: '{query}'")
    vector_chunks = search_chunks_vector_db(document_id, query, limit=limit)
    bm25_chunks = search_chunks_bm25(document_id, query, limit=limit)
    
    seen_ids = set()
    combined_chunks = []
    
    for c in vector_chunks + bm25_chunks:
        cid = c.get("chunk_id") or c.get("sequence_number")
        if cid and cid not in seen_ids:
            seen_ids.add(cid)
            combined_chunks.append(c)
            
    combined_chunks.sort(key=lambda x: x.get("sequence_number") or 0)
    return combined_chunks[:limit]


def get_all_document_chunks(document_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all chunks for a document ordered by sequence number.
    Use this tool when you need to inspect the complete contract or perform full document analysis.
    
    Args:
        document_id: Unique identifier for the document
    """
    logger.info(f"Retrieving ALL chunks for doc {document_id}")
    with SessionLocal() as db:
        result = db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.sequence_number)
        )
        return [c.to_dict() for c in result.scalars().all()]


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
2. Use `hybrid_search_chunks` as your primary tool to perform combined semantic vector search and smart keyword search in 1 call.
3. If analyzing full contract structure, broad obligations, or top summary points, use `get_all_document_chunks` to inspect all contract text.
4. Use `search_chunks_vector_db` or `search_chunks_bm25` for specific targeted follow-up queries.
5. If you find a relevant chunk that refers to a section or contains references like "the foregoing" or "this Section 4", retrieve neighboring chunks using `get_surrounding_chunks` or specific sequence numbers using `get_chunk_by_sequence` to resolve context.
6. Plan your search strategy step-by-step. Synthesize a complete and accurate answer. Provide citations (chunk_id, page numbers, text snippets) for all claims.

STRICT TRUTHFULNESS & ANTI-HALLUCINATION GUIDELINES:
- Always use the actual `document_id` UUID provided in the request instructions.
- NEVER invent, extrapolate, hypothesize, or assume information not explicitly stated in the retrieved contract text.
- IF NO ANSWER IS FOUND or information is not present in the retrieved chunks: STATE THE TRUTH DIRECTLY. Explicitly state in the `answer` field what was searched for and that the information was NOT found in the contract document. Example: "Based on the provided contract document, no information or clause was found regarding [topic]."
- DO NOT use external general knowledge to answer questions about contract details if those details are not in the document.
- If only partial information is found, answer ONLY what is supported by retrieved chunks, and list all missing/unverified aspects in `unresolved_parts`.
- DO NOT leave the `answer` field empty under any circumstances.
"""

def get_ministral_model() -> Any:
    """Initialize the 14B Ministral model for the QA retrieval agent with exponential backoff retries."""
    from backend.utils.llm_utils import get_resilient_llm, ORCHESTRATOR_MODEL_NAME
    return get_resilient_llm(model_name=ORCHESTRATOR_MODEL_NAME, temperature=0.0)


def create_retrieval_agent() -> Any:
    """
    Create the multi-turn retrieval agent for complex reasoning tasks.
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
    
    from langgraph.store.memory import InMemoryStore
    store = InMemoryStore()
    
    return create_deep_agent(
        model=get_ministral_model(),
        system_prompt=RETRIEVAL_AGENT_PROMPT,
        backend=backend,
        store=store,
        skills=["backend/skills/document-retrieval"],
        tools=[
            hybrid_search_chunks,
            get_all_document_chunks,
            search_chunks_vector_db,
            search_chunks_bm25,
            get_chunk_by_sequence,
            get_surrounding_chunks,
            get_total_chunks_count,
        ],
        middleware=[],
        response_format=RetrievalAgentResult,
    )


def hybrid_retrieve_contract_chunks(document_id: str, query: str, top_k: int = 12) -> List[Dict[str, Any]]:
    """
    Perform fast hybrid retrieval combining SQL BM25 keyword matching and Chroma vector similarity search.
    If total document chunks <= 25, returns ALL document chunks in sequence order for 100% complete context.
    """
    total_count = get_total_chunks_count(document_id)
    
    # Small to medium contract documents: return full context directly
    if 0 < total_count <= 25:
        with SessionLocal() as db:
            result = db.execute(
                select(Chunk)
                .where(Chunk.document_id == document_id)
                .order_by(Chunk.sequence_number)
            )
            return [c.to_dict() for c in result.scalars().all()]
            
    # Larger contract documents: perform hybrid retrieval
    vector_chunks = search_chunks_vector_db(document_id, query, limit=top_k)
    bm25_chunks = search_chunks_bm25(document_id, query, limit=top_k)
    
    seen_ids = set()
    combined_chunks = []
    
    for chunk in vector_chunks + bm25_chunks:
        cid = chunk.get("chunk_id") or chunk.get("sequence_number")
        if cid and cid not in seen_ids:
            seen_ids.add(cid)
            combined_chunks.append(chunk)
            
    combined_chunks.sort(key=lambda c: c.get("sequence_number") or 0)
    return combined_chunks[:top_k]


def run_fast_grounded_qa(document_id: str, question: str) -> Dict[str, Any]:
    """
    Execute grounded QA using fast hybrid retrieval in a single pass with Ministral 14B.
    Falls back to multi-turn agent if initial retrieval yields no results or fails.
    """
    chunks = hybrid_retrieve_contract_chunks(document_id, question, top_k=15)
    
    if not chunks:
        agent = create_retrieval_agent()
        from langchain_core.messages import HumanMessage
        prompt_msg = f"Please answer the following question about the contract document with ID '{document_id}':\n\n{question}"
        state = agent.invoke({"messages": [HumanMessage(content=prompt_msg)]})
        agent_result = state.get("structured_response") or state.get("response")
        if agent_result and hasattr(agent_result, "model_dump"):
            return agent_result.model_dump()
        elif isinstance(agent_result, dict):
            return agent_result
        return {
            "answer": "Based on the provided contract document, no information or text chunks were found for this query.",
            "citations": [],
            "unresolved_parts": [question]
        }
        
    context_blocks = []
    for c in chunks:
        seq = c.get("sequence_number", "?")
        page_s = c.get("page_start", "?")
        page_e = c.get("page_end", page_s)
        cid = c.get("chunk_id", f"seq_{seq}")
        content = c.get("content", "")
        context_blocks.append(
            f"--- CHUNK (Seq: {seq}, ID: {cid}, Page: {page_s}-{page_e}) ---\n{content}"
        )
        
    formatted_context = "\n\n".join(context_blocks)
    
    prompt = f"""You are a strict, grounded legal document QA assistant.

DOCUMENT ID: {document_id}

QUESTION:
{question}

RETRIEVED CONTRACT CONTEXT:
{formatted_context}

STRICT INSTRUCTIONS:
1. Answer the question based ONLY on the retrieved contract text above.
2. If the text does NOT contain the answer or details requested, state clearly and truthfully: "Based on the provided contract document, no information was found regarding [topic]." Do NOT invent or speculate.
3. Provide citations referencing the Chunk ID and page numbers for all factual assertions in your answer.
"""

    llm = get_ministral_model()
    structured_llm = llm.with_structured_output(RetrievalAgentResult)
    
    try:
        result = structured_llm.invoke(prompt)
        if hasattr(result, "model_dump"):
            return result.model_dump()
        elif isinstance(result, dict):
            return result
        return {"answer": str(result), "citations": [], "unresolved_parts": []}
    except Exception as e:
        logger.error(f"Single-pass QA failed, falling back to multi-turn agent: {e}", exc_info=True)
        agent = create_retrieval_agent()
        from langchain_core.messages import HumanMessage
        prompt_msg = f"Please answer the following question about the contract document with ID '{document_id}':\n\n{question}"
        state = agent.invoke({"messages": [HumanMessage(content=prompt_msg)]})
        agent_result = state.get("structured_response") or state.get("response")
        if agent_result and hasattr(agent_result, "model_dump"):
            return agent_result.model_dump()
        elif isinstance(agent_result, dict):
            return agent_result
        return {"answer": f"QA processing error: {e}", "citations": [], "unresolved_parts": [question]}
