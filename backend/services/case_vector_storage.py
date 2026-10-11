import json
import logging
import math
from typing import Any, List, Dict, Optional
from langchain_core.documents import Document as LCDocument
from langchain_chroma import Chroma
from sqlalchemy import select

from backend.config import settings
from backend.database import SessionLocal
from backend.models.cases import CaseDocumentChunk
from backend.services.vector_storage import get_embeddings_model

logger = logging.getLogger(__name__)

def get_case_vector_store() -> Chroma:
    """
    Initialize the Chroma vector store for Case documents.
    Uses the same embedding function, but targeting the 'case_chunks' collection.
    """
    embeddings = get_embeddings_model()
    settings.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    
    return Chroma(
        collection_name="case_chunks",
        embedding_function=embeddings,
        persist_directory=str(settings.CHROMA_DIR),
    )

def store_case_chunks_in_vector_db(chunks: List[CaseDocumentChunk], case_id: str, document_id: str) -> None:
    """
    Embed and store case chunks in Chroma DB.
    
    Args:
        chunks: List of CaseDocumentChunk SQLAlchemy models.
        case_id: The ID of the parent case.
        document_id: The ID of the document.
    """
    if not chunks:
        logger.warning(f"No chunks provided to store for case document {document_id}")
        return

    logger.info(f"Storing {len(chunks)} chunks in Chroma DB for case document {document_id}")
    
    try:
        vectorstore = get_case_vector_store()
        lc_docs = []
        ids = []
        
        for chunk in chunks:
            metadata = {
                "case_id": case_id,
                "document_id": document_id,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "sequence_number": chunk.sequence_number,
            }
            
            if chunk.chunk_metadata:
                for k, v in chunk.chunk_metadata.items():
                    if k not in metadata:
                        metadata[k] = v
                        
            # Clean metadata to primitive values for Chroma
            clean_metadata = {}
            for k, v in metadata.items():
                if isinstance(v, (list, dict)):
                    clean_metadata[k] = json.dumps(v)
                elif v is None:
                    continue
                elif isinstance(v, (str, int, float, bool)):
                    clean_metadata[k] = v
                else:
                    clean_metadata[k] = str(v)
                    
            doc = LCDocument(
                page_content=chunk.content,
                metadata=clean_metadata
            )
            lc_docs.append(doc)
            ids.append(chunk.id)
            
        vectorstore.add_documents(documents=lc_docs, ids=ids)
        logger.info(f"Successfully stored {len(chunks)} chunks in case vector store.")
        
    except Exception as e:
        logger.error(f"Failed to store case chunks in Chroma DB: {e}", exc_info=True)
        raise

def delete_case_chunks_from_vector_db(document_id: str) -> None:
    """Delete all chunks for a document from the case vector store."""
    logger.info(f"Deleting case chunks from Chroma DB for document {document_id}")
    try:
        vectorstore = get_case_vector_store()
        if hasattr(vectorstore, "_collection"):
            vectorstore._collection.delete(where={"document_id": document_id})
        else:
            vectorstore.delete(where={"document_id": document_id})
    except Exception as e:
        logger.error(f"Failed to delete chunks from Chroma DB for document {document_id}: {e}", exc_info=True)
        raise

class SimpleBM25:
    """
    A lightweight BM25 keyword ranker.
    """
    def __init__(self, corpus: List[Dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.corpus_size = len(corpus)
        self.avg_doc_len = 0.0
        self.doc_lens = []
        self.doc_term_freqs = []
        self.df = {}
        self.idf = {}
        self._initialize()

    def _tokenize(self, text: str) -> List[str]:
        return [w.lower() for w in text.split() if w.isalnum()]

    def _initialize(self):
        total_len = 0
        for doc in self.corpus:
            tokens = self._tokenize(doc["content"])
            doc_len = len(tokens)
            self.doc_lens.append(doc_len)
            total_len += doc_len
            
            tf = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self.doc_term_freqs.append(tf)
            
            for t in tf.keys():
                self.df[t] = self.df.get(t, 0) + 1
                
        self.avg_doc_len = total_len / self.corpus_size if self.corpus_size > 0 else 0
        
        # Calculate IDF
        for t, f in self.df.items():
            # BM25 IDF formula
            self.idf[t] = math.log((self.corpus_size - f + 0.5) / (f + 0.5) + 1.0)

    def score(self, query: str) -> List[Dict[str, Any]]:
        query_tokens = self._tokenize(query)
        scores = []
        
        for idx, doc in enumerate(self.corpus):
            score = 0.0
            doc_len = self.doc_lens[idx]
            tf = self.doc_term_freqs[idx]
            
            for t in query_tokens:
                if t in tf:
                    t_freq = tf[t]
                    numerator = self.idf.get(t, 0.0) * t_freq * (self.k1 + 1)
                    denominator = t_freq + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)
                    score += numerator / denominator
            scores.append((doc, score))
            
        # Sort and return
        scores.sort(key=lambda x: x[1], reverse=True)
        return [{"document": item[0], "score": item[1]} for item in scores]

def hybrid_search_case_chunks(case_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Perform a hybrid retrieval combining semantic vector search and keyword search (BM25)
    restricted strictly to the given case_id.
    
    Args:
        case_id: Unique ID of the case.
        query: The search query string.
        limit: Number of results to return.
    """
    logger.info(f"Hybrid search for case {case_id} with query: '{query}'")
    
    # 1. Semantic Search
    semantic_results = []
    try:
        vectorstore = get_case_vector_store()
        docs = vectorstore.similarity_search(query, k=limit * 2, filter={"case_id": case_id})
        for d in docs:
            semantic_results.append({
                "content": d.page_content,
                "metadata": d.metadata
            })
    except Exception as e:
        logger.error(f"Semantic search failed: {e}", exc_info=True)
        
    # 2. Keyword/BM25 Search
    bm25_results = []
    try:
        # Fetch all chunks for this case from DB to build corpus
        with SessionLocal() as db:
            stmt = (
                select(CaseDocumentChunk)
                .join(CaseDocumentChunk.document)
                .where(CaseDocumentChunk.document.has(case_id=case_id))
            )
            chunks = db.execute(stmt).scalars().all()
            
            if chunks:
                corpus = []
                for chunk in chunks:
                    corpus.append({
                        "id": chunk.id,
                        "content": chunk.content,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                        "sequence_number": chunk.sequence_number,
                        "document_id": chunk.document_id,
                        "document_name": chunk.document.name,
                    })
                
                ranker = SimpleBM25(corpus)
                bm25_ranked = ranker.score(query)
                for item in bm25_ranked[:limit * 2]:
                    doc = item["document"]
                    bm25_results.append({
                        "content": doc["content"],
                        "metadata": {
                            "case_id": case_id,
                            "document_id": doc["document_id"],
                            "document_name": doc["document_name"],
                            "page_start": doc["page_start"],
                            "page_end": doc["page_end"],
                            "sequence_number": doc["sequence_number"]
                        }
                    })
    except Exception as e:
        logger.error(f"BM25 keyword search failed: {e}", exc_info=True)
        
    # 3. Reciprocal Rank Fusion (RRF)
    # RRF formula: Score(d) = sum( 1 / (60 + rank(d, r)) )
    rrf_scores = {}
    
    def add_ranks(results):
        for rank, res in enumerate(results):
            # Key by content to deduplicate
            key = (res["content"], res["metadata"]["document_id"])
            if key not in rrf_scores:
                rrf_scores[key] = {"res": res, "score": 0.0}
            rrf_scores[key]["score"] += 1.0 / (60.0 + rank + 1)
            
    add_ranks(semantic_results)
    add_ranks(bm25_results)
    
    # Sort by RRF score
    sorted_rrf = sorted(rrf_scores.values(), key=lambda x: x["score"], reverse=True)
    
    # Return top results up to limit
    top_results = [item["res"] for item in sorted_rrf[:limit]]
    logger.info(f"Hybrid search returned {len(top_results)} results.")
    return top_results
