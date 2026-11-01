"""
Vector Storage Service for embedding and storing chunks in Chroma DB.
"""

import json
import uuid
import logging
from typing import Any, List, Optional
from langchain_core.documents import Document as LCDocument
try:
    from langchain_chroma import Chroma
except ImportError:
    class Chroma:
        def __init__(self, collection_name: str, embedding_function: Any = None, persist_directory: str = "./chroma_db"):
            import chromadb
            self.client = chromadb.PersistentClient(path=persist_directory)
            self.collection = self.client.get_or_create_collection(name=collection_name)

        def add_documents(self, documents: List[LCDocument], ids: Optional[List[str]] = None) -> List[str]:
            docs_text = [d.page_content for d in documents]
            metas = [d.metadata for d in documents]
            doc_ids = ids if ids else [str(i) for i in range(len(documents))]
            self.collection.add(documents=docs_text, metadatas=metas, ids=doc_ids)
            return doc_ids

        def similarity_search_with_relevance_scores(
            self, query: str, k: int = 5, filter: Optional[dict] = None
        ) -> List[tuple[LCDocument, float]]:
            res = self.collection.query(query_texts=[query], n_results=k, where=filter)
            results = []
            docs = res.get("documents", [[]])[0] if res.get("documents") else []
            metas = res.get("metadatas", [[]])[0] if res.get("metadatas") else []
            dists = res.get("distances", [[]])[0] if res.get("distances") else []
            for doc_txt, meta, dist in zip(docs, metas, dists):
                score = max(0.0, 1.0 - (dist if dist is not None else 0.5))
                results.append((LCDocument(page_content=doc_txt, metadata=meta or {}), score))
            return results
from langchain_mistralai import MistralAIEmbeddings

from backend.config import settings
from backend.services.chunking.database import Chunk

import functools
logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def get_embeddings_model() -> Any:
    """
    Initialize embeddings model. Uses MistralAIEmbeddings, HuggingFaceEmbeddings, or a deterministic fallback.
    """
    try:
        from langchain_mistralai import MistralAIEmbeddings
        if settings.MISTRAL_API_KEY:
            return MistralAIEmbeddings(
                api_key=settings.MISTRAL_API_KEY,
                model="mistral-embed"
            )
    except Exception as e:
        logger.warning(f"Could not initialize MistralAIEmbeddings: {e}")

    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name="nomic-ai/nomic-embed-text-v1",
            model_kwargs={"trust_remote_code": True}
        )
    except Exception as e:
        logger.warning(f"Could not initialize HuggingFaceEmbeddings: {e}")

    raise RuntimeError(
        "Embeddings initialization failed: MISTRAL_API_KEY is not configured or HuggingFace embeddings are unavailable."
    )


@functools.lru_cache(maxsize=1)
def get_vector_store() -> Chroma:
    """
    Initialize the Chroma vector store. Cached in memory for fast similarity search.
    """
    embeddings = get_embeddings_model()
    # Ensure CHROMA_DIR is created
    settings.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    
    return Chroma(
        collection_name="contract_chunks",
        embedding_function=embeddings,
        persist_directory=str(settings.CHROMA_DIR),
    )


def store_chunks_in_vector_db(chunks: List[Chunk], document_id: str) -> None:
    """
    Embed and store document chunks in Chroma DB.
    Ensures metadata fields are primitive values only.
    
    Args:
        chunks: List of Chunk SQLAlchemy models
        document_id: Unique identifier for the document
    """
    if not chunks:
        logger.warning(f"No chunks provided to store for document {document_id}")
        return

    logger.info(f"Storing {len(chunks)} chunks in Chroma DB for document {document_id}")
    
    try:
        vectorstore = get_vector_store()
        lc_docs = []
        ids = []
        
        for chunk in chunks:
            # Build unified metadata
            metadata = {
                "document_id": document_id,
                "chunk_id": str((getattr(chunk, "chunk_id", None) or (chunk.get("chunk_id") if isinstance(chunk, dict) else None)) or uuid.uuid4()),
                "page_start": getattr(chunk, "page_start", None) or (chunk.get("page_start") if isinstance(chunk, dict) else None),
                "page_end": getattr(chunk, "page_end", None) or (chunk.get("page_end") if isinstance(chunk, dict) else None),
                "unit_type": getattr(chunk, "unit_type", None) or (chunk.get("unit_type") if isinstance(chunk, dict) else "paragraph"),
                "sequence_number": getattr(chunk, "sequence_number", None) or (chunk.get("sequence_number") if isinstance(chunk, dict) else 0),
            }
            
            # Merge extra chunk metadata if available
            extra_meta = getattr(chunk, "chunk_metadata", None) or (chunk.get("metadata") if isinstance(chunk, dict) else None)
            if extra_meta and isinstance(extra_meta, dict):
                for k, v in extra_meta.items():
                    if k not in metadata:
                        metadata[k] = v
            
            # Clean and serialize metadata values to conform to Chroma primitive requirements
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
                page_content=getattr(chunk, "content", None) or (chunk.get("content") or chunk.get("text") if isinstance(chunk, dict) else ""),
                metadata=clean_metadata
            )
            lc_docs.append(doc)
            ids.append(metadata["chunk_id"])
            
        vectorstore.add_documents(documents=lc_docs, ids=ids)
        logger.info(f"Successfully stored {len(chunks)} chunks in Chroma DB for document {document_id}")
        
    except Exception as e:
        logger.error(f"Failed to store chunks in Chroma DB for document {document_id}: {e}", exc_info=True)
        raise


def delete_chunks_from_vector_db(document_id: str) -> int:
    """
    Delete all chunks associated with a document from Chroma DB.
    
    Args:
        document_id: Unique identifier for the document
        
    Returns:
        Number of documents deleted (if info available, otherwise 1 on success)
    """
    logger.info(f"Deleting chunks from Chroma DB for document {document_id}")
    try:
        vectorstore = get_vector_store()
        
        # We can delete chunks matching the document_id
        # Collection delete method is extremely robust
        if hasattr(vectorstore, "_collection"):
            vectorstore._collection.delete(where={"document_id": document_id})
        else:
            vectorstore.delete(where={"document_id": document_id})
            
        logger.info(f"Successfully deleted chunks from Chroma DB for document {document_id}")
        return 1
    except Exception as e:
        logger.error(f"Failed to delete chunks from Chroma DB for document {document_id}: {e}", exc_info=True)
        raise
