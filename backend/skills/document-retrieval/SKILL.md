---
name: document-retrieval
description: >
  Retrieve relevant contract chunks using vector similarity search, BM25 keyword search,
  or sequential database lookups. Synthesize the retrieved context to answer user queries
  accurately, supporting answers with references to specific pages and chunk IDs.
---

# Document Retrieval & Question Answering Skill

## Goal
To answer user queries about a legal document by retrieving the most relevant chunks using various retrieval tools (Vector Search, BM25 Keyword Search, and Database Sequential/Neighbor Lookups), planning and reasoning over the findings, and citing the exact source of information.

## Strategy and Reasoning Process

1. **Analyze and Plan**:
   - Deconstruct the user query to identify key legal concepts, entities, definitions, obligations, or dates.
   - Formulate search queries for both keyword (BM25) and semantic (Vector) search.

2. **Retrieve Iteratively**:
   - Use **Vector Search** to capture semantic meaning (e.g., finding liability limitations when the query asks about "capped losses").
   - Use **BM25 Search** to search for exact terms, names, section numbers, or acronyms (e.g., searching for "Exhibit A" or "Indemnification").
   - Use **Database Lookups** (sequential or surrounding chunks) to inspect adjacent paragraphs, headings, or context when a candidate chunk has incomplete information or references like "the foregoing" or "this Section 4".

3. **Verify and Resolve**:
   - Verify if the retrieved chunks directly answer the user's question.
   - If they refer to defined terms, use searches to locate the definition of those terms.
   - If there is ambiguity or conflicting information in different parts of the contract, explicitly point it out.

4. **Synthesize and Cite**:
   - Formulate a clear, direct answer to the user's query.
   - Always cite the source for every statement using:
     - The original section/clause numbers if available in the metadata.
     - The page number(s) (`page_start`, `page_end`).
     - The `chunk_id`.
