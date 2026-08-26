"""
Vector Storage Service for embedding and storing chunks in Chroma DB.
"""

import json
import logging
from typing import Any, List, Optional
from langchain_core.documents import Document as LCDocument
from langchain_chroma import Chroma
from langchain_mistralai import MistralAIEmbeddings

from backend.config import settings
from backend.services.chunking.database import Chunk

logger = logging.getLogger(__name__)


def get_embeddings_model() -> Any:
    """
    Initialize the nomic-embed-text embedding model directly using sentence-transformers.
    """
    from langchain_community.embeddings import HuggingFaceEmbeddings
    logger.info("Loading nomic-embed-text via sentence-transformers (HuggingFace)...")
    return HuggingFaceEmbeddings(
        model_name="nomic-ai/nomic-embed-text-v1",
        model_kwargs={"trust_remote_code": True}
    )


def get_vector_store() -> Chroma:
    """
    Initialize the Chroma vector store.
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
                "chunk_id": chunk.chunk_id,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "unit_type": chunk.unit_type,
                "sequence_number": chunk.sequence_number,
            }
            
            # Merge extra chunk metadata if available
            if chunk.chunk_metadata:
                for k, v in chunk.chunk_metadata.items():
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
                page_content=chunk.content,
                metadata=clean_metadata
            )
            lc_docs.append(doc)
            ids.append(chunk.chunk_id)
            
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
