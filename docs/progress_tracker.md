# Project Progress Tracker & Architectural Refactoring Guide

## 1. Executive Summary & Objective

This document tracks the architectural refactoring of the **Contract Analysis Module** in the system. 
The system was previously built on the experimental `deepagents` library from LangChain, which caused non-deterministic execution, runaway loops, and tool failures. Furthermore, the contract analysis agent completely lacked Indian statutory grounding and Indian Kanoon access.

We transitioned the contract analysis engine to a **deterministic, milestone-driven LangGraph architecture** that provides **structured autonomy** for Indian legal research and live Indian Kanoon scraping. Additionally, we connected the frontend with live streaming logs so users can observe the agent's reasoning steps, tool calls, and scraped statutory citations in real time.

---

## 2. Prior Architecture (DeepAgents) & Root Causes of Failure

### What it Was Earlier
- The contract analysis coordinator was initialized via `deepagents.create_deep_agent` (`backend/agents/orchestrator_agent.py`).
- It attempted to dynamically orchestrate 8 specialist subagents (`STRUCTURE_AGENT`, `CONTEXT_AGENT`, `ENTITY_AGENT`, `CLAUSE_AGENT`, `OBLIGATION_AGENT`, `RISK_AGENT`, `CROSS_REFERENCE_AGENT`, `REVIEW_AGENT`) via a general-purpose ReAct `task` tool.
- All subagents were configured with `inherit_tools=True`, inheriting the database chunk retrieval tools (`get_optimized_chunks_from_db`, `get_total_chunks_count`).

### Why it Failed
1. **Unconstrained ReAct Cognitive Conflict**:
   The prompt instructed the coordinator:
   > *"You are NOT simply executing a predefined pipeline. You must decide dynamically: what needs to be analyzed, which specialist should analyze it..."*
   While simultaneously dictating:
   > *"You MUST continue fetching and analyzing chunks sequentially from start_sequence = 1 in batches up to the total count... Do not stop midway."*
   For models like Mistral/Ministral, this produced runaway loops: the coordinator repeatedly re-queried the same chunk ranges (e.g., sequence 15–20 over and over) without advancing linearly.
2. **Recursive Subagent Spawning & Tool Failures**:
   With `inherit_tools=True`, subagents spawned sub-tasks recursively. Production execution logs (`7750cfec-29fb-45b0-afb8-53ea52432c4d_agent_execution.log`) revealed repeated crashes:
   ```text
   Error invoking tool 'task' with kwargs {'description': "Analyze the overall structure of the contract chunk... starting at sequence 76..."}
   ```
3. **Zero Indian Legal Grounding & Absence of Kanoon Tools**:
   The orchestrator in `orchestrator_agent.py` was given only `[get_optimized_chunks_from_db, get_total_chunks_count]`. It had **no** search tools, **no** access to Indian Contract Act 1872, and **no** access to Indian Kanoon.
4. **Lack of Frontend Streaming & Visibility**:
   The frontend was completely disconnected from agent progress. If an analysis task was running in Celery, the frontend UI remained static without live feedback.

---

## 3. New Architecture: Deterministic LangGraph with Structured Autonomy

### Architectural Philosophy: "Structured Autonomy"
Instead of letting an agent wander freely over the entire analysis pipeline, we split the workflow into:
1. **Deterministic Pipeline Milestones**: Fixed state transitions ensuring 100% chunk coverage, reliable entity resolution, risk calculation, and schema adherence.
2. **Autonomous Legal Research Sub-Loop**: The legal advisor agent is granted autonomy to decide *which* provisions look suspect under Indian law, formulate queries, search Indian Kanoon, and read statutory texts or judgments.
3. **Hard Termination Guardrails**: The autonomous research loop is capped by `MAX_LEGAL_RESEARCH_TURNS = 3`. It cannot loop infinitely.

```
                              [START]
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │    document_intake    │  (Deterministic: Total chunks, preamble,
                     └───────────────────────┘   contract type, contracting parties)
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │   clause_extraction   │  (Deterministic: Batch-reads all chunks
                     └───────────────────────┘   systematically; extracts clauses & obligations)
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │   entity_resolution   │  (Deterministic: Resolves parties; flags
                     └───────────────────────┘   clauses triggering Indian statutory scrutiny)
                                 │
                                 ▼
              ┌─────────► ┌──────────────────────┐
              │           │ autonomous_legal_    │  ◄── (AUTONOMOUS NODE: Scrutinizes clauses,
              │           │       advisor        │       formulates Kanoon queries)
              │           └──────────────────────┘
              │                      │
              │                      ▼
              │            ┌────────────────────┐
              │            │  Needs more Kanoon │
              │            │ research & turns<3?│
              │            └────────────────────┘
              │                 │            │
       (Yes)  │                 │            │ (No or turns >= 3)
              │                 ▼            ▼
     ┌─────────────────┐             ┌───────────────────────┐
     │   legal_tools   │             │   synthesize_risks    │  (Deterministic: Integrates Kanoon
     │ (search/fetch)  │             └───────────────────────┘   statutes, computes risk score)
     └─────────────────┘                         │
                                                 ▼
                                     ┌───────────────────────┐
                                     │   final_validation    │  (Deterministic: Validates Pydantic
                                     └───────────────────────┘   ContractAnalysisResult)
                                                 │
                                                 ▼
                                               [END]
```

---

## 4. Indian Kanoon Route Analysis & Scraping System

Without an official paid API token, we implemented route-pattern analysis combined with DuckDuckGo indexed search.

### Indian Kanoon Route Conventions:
- **Direct Document**: `https://indiankanoon.org/doc/{doc_id}/`
  - E.g., `1431516` = Section 27, The Indian Contract Act 1872
  - E.g., `1941714` = Section 74, The Indian Contract Act 1872
  - E.g., `70828540` = *M/S. Kailash Nath Associates vs DDA* (Supreme Court on liquidated damages)
- **Search Form**: `https://indiankanoon.org/search/?formInput={query}`
- **Doc Fragment**: `https://indiankanoon.org/docfragment/{doc_id}/?formInput={query}`

### Scraper Engineering & Search Engine Optimization:
1. **Direct Indian Kanoon Route Prioritization (`search_via_kanoon_route`)**:
   - In benchmark testing, Indian Kanoon's direct search route (`https://indiankanoon.org/search/?formInput={query}`) consistently responds within 0.5–1.4 seconds with 10 exact case and statutory matches.
   - Parses `<article class="result">`, extracting title from `.result_title a`, doc ID from `/doc/(\d+)` or `/docfragment/(\d+)`, and snippet from `.headline`.
   - Bypasses navigation links like `Entire Act` and `Full Document`.
2. **Selective Metasearch Backend (`search_via_ddgs`)**:
   - Evaluated all 7 backends available in `ddgs` 9.15.0 (`yahoo`, `duckduckgo`, `startpage`, `mojeek`, `brave`, `wikipedia`, `grokipedia`).
   - DuckDuckGo (`html.duckduckgo.com`), Brave, and Startpage return rate-limits (HTTP 429), bot captchas, or empty responses on Indian IP/automated queries.
   - Identified `yahoo` as the only consistently functional search engine backend in DDGS for indexing `site:indiankanoon.org`. Explicitly pinned `backend='yahoo'` with fallback to prevent multi-engine timeout cascading.
3. **Clean Text Scraper (`fetch_kanoon_document`)**:
   - Fetches `/doc/{doc_id}/` using browser-like User-Agent headers.
   - Decomposes scripts, promo banners (`.premium-banner`), ads, navbars, and headers.
   - Extracts from statutory containers (`<div class="akoma-ntoso">`, `<section class="akn-section">`) and judgment containers (`<article class="middle_column">`, `<div class="judgments">`).
   - Cleans boilerplate (`[Cites X, Cited by Y]`, `[Entire Act]`) and yields substantive legal text (up to 3,500 characters).
4. **In-Memory Cache**:
   - Query results and fetched documents are cached in memory (`_SEARCH_CACHE`, `_DOC_CACHE`, `_DOC_META_CACHE`) to eliminate redundant network roundtrips.

---

## 5. Multi-Turn Autonomous Research & Prompt Engineering

The `autonomous_legal_advisor` prompt is structured to guide multi-turn investigation:
- **Turn 1 (Search)**: Uses `search_indian_kanoon` on suspect clauses flagged during extraction.
- **Turn 2 (Fetch & Read)**: Inspects the resulting Doc IDs and calls `fetch_kanoon_document` to read the verbatim statutory section or court ruling.
- **Turn 3 (Synthesize or Follow-up)**: Gathers remaining citations or issues its final legal opinion.

### Critical Indian Statutory Checks Built In:
1. **Section 27, Indian Contract Act 1872**: Restraint of trade / profession is **VOID ab initio**. Post-employment non-compete clauses are invalid in India (*Niranjan Shankar Golikari*, *Percept D'Mark*).
2. **Section 74, Indian Contract Act 1872**: Liquidated damages vs penalty. Sums specified in contracts are only upper ceilings; the aggrieved party must prove actual damage (*Kailash Nath Associates v. DDA*, *ONGC v. Saw Pipes*).
3. **Section 28, Indian Contract Act 1872**: Agreements restricting legal proceedings or shortening limitation periods (3 years) are void.
4. **Arbitration and Conciliation Act 1996**: Unilateral appointment of a sole arbitrator is invalid (*Perkins Eastman*, *TRF Ltd*).
5. **Section 56, Indian Contract Act 1872**: Frustration of contract and force majeure principles (*Energy Watchdog v. CERC*).

---

## 6. Frontend Streaming & Live Log Console

### Backend Endpoint Added:
- **`GET /api/v1/contracts/{document_id}/logs`** in `backend/routes/contracts.py`:
  Reads `backend/storage/logs/{document_id}_agent_execution.log`, classifies events (`tool_call`, `kanoon`, `node`, `finding`, `info`), and returns real-time progress and completion status.

### Frontend Integration Added:
- **API Client**: `apiClient.getContractLogs(contractId)` in `frontend/services/api.ts`.
- **Live Polling**: `ContractDetailsPage` (`frontend/app/dashboard/contracts/[id]/page.tsx`) auto-polls every 3 seconds while analysis is in progress.
- **Run AI Analysis Button**: Allows triggering background analysis on demand.
- **Terminal Console**: Dark terminal widget displaying:
  - Live pulse indicator (`Live Processing` vs `Completed`).
  - Event count badge.
  - Color-coded logs:
    - Amber: Tool calls (`search_indian_kanoon`, `fetch_kanoon_document` with arguments).
    - Cyan: Indian Kanoon search results and document URLs.
    - Indigo: LangGraph node transitions (`[LangGraph Engine] running node: ...`).
    - Emerald: Extracted findings and legal syntheses.

---

## 7. Inventory of Files Created & Modified

| File Path | Status | Description |
| :--- | :--- | :--- |
| `backend/schemas/contract_analysis_models.py` | **Modified** | Added `LegalSourceItem` and `legal_sources: List[LegalSourceItem]` to `ContractAnalysisResult`. |
| `backend/models/contract_analysis.py` | **Modified** | Added `legal_sources: Mapped[list[dict]]` column to PostgreSQL / SQLite table. |
| `backend/services/contract_analysis_service.py` | **Modified** | Updated `get_contract_analysis_from_db` and `save_contract_analysis_to_db` to persist and return `legal_sources`. |
| `backend/database_migrations/create_contract_analysis_tables.py` | **Modified** | Added migration check and column addition for `legal_sources` JSON column. |
| `backend/tools/indian_kanoon_tools.py` | **Modified** | Direct Indian Kanoon route prioritized with `<article class="result">` and `/docfragment/` parsing; DDGS optimized to selectively use responsive `yahoo` backend; fixed `extract_doc_id` pattern. |
| `backend/agents/contract_langgraph_orchestrator.py` | **Modified** | Fixed missing `import re` in node_legal_tools; updated `node_legal_tools` to collect structured `LegalSourceItem` objects into graph state; hardened `node_risk_synthesis` with regex parsing & fallbacks; added `legal_sources` to `node_final_validation`. |
| `backend/agents/orchestrator_agent.py` | **Refactored** | Removed legacy `deepagents` boilerplate and quickjs; cleanly re-exports LangGraph runner and schemas. |
| `backend/tasks/pdf_tasks.py` | **Modified** | Updated `run_stream_analysis` and `run_stream_analysis_only` to log tool calls and extract `final_result` / `structured_response`. |
| `backend/routes/contracts.py` | **Modified** | Added `GET /{document_id}/logs` route; updated `/{document_id}/analyze` to reset document status to `PROCESSING` on re-run. |
| `backend/celery_app.py` & `backend/worker.py` | **Modified** | Added `load_dotenv()` at module import to ensure Celery background workers always receive `MISTRAL_API_KEY`. |
| `backend/utils/llm_utils.py` | **Modified** | Added `load_dotenv()` to guarantee API keys are loaded in resilient model factories. |
| `frontend/services/api.ts` | **Modified** | Added `getContractLogs(contractId)` and added `legal_sources?: any[]` to `AnalysisPayload` normalization. |
| `frontend/app/dashboard/contracts/[id]/page.tsx` | **Modified** | Added "Re-analyze Contract" button, dedicated "Researched Indian Kanoon Precedents & Statutory Authorities" card, and real-time terminal log viewer. |
| `start_backend.ps1` | **Created** | PowerShell startup script with Docker Redis auto-start, FastAPI Uvicorn server, and Celery background worker. |
| `docs/progress_tracker.md` | **Updated** | Recorded Indian Kanoon search route prioritization, DDGS backend evaluation, and `re` runtime resolution. |
| `backend/agents/document_structure_agent.py` | **Deleted** | Obsolete DeepAgents prompt dictionary; superseded by LangGraph `document_intake` node. |
| `backend/agents/chunk_context_specialist.py` | **Deleted** | Obsolete DeepAgents prompt dictionary; superseded by LangGraph `clause_extraction` node. |
| `backend/agents/entity_resolution_agent.py` | **Deleted** | Obsolete DeepAgents prompt dictionary; superseded by LangGraph `entity_resolution` node. |
| `backend/agents/clause_analysis_agent.py` | **Deleted** | Obsolete DeepAgents prompt dictionary; superseded by LangGraph `clause_extraction` node. |
| `backend/agents/obligation_rights_agent.py` | **Deleted** | Obsolete DeepAgents prompt dictionary; superseded by LangGraph `clause_extraction` node. |
| `backend/agents/contract_risk_agent.py` | **Deleted** | Obsolete DeepAgents prompt dictionary; superseded by LangGraph `synthesize_risks` node. |
| `backend/agents/cross_reference_agent.py` | **Deleted** | Obsolete DeepAgents prompt dictionary; superseded by LangGraph `entity_resolution` node. |
| `backend/agents/contract_review_agent.py` | **Deleted** | Obsolete DeepAgents prompt dictionary; superseded by LangGraph `final_validation` node. |
| `backend/skills/{contract-orchestration, document-structure, chunk-context, entity-resolution, clause-analysis, obligation-rights, contract-risk, cross-reference, contract-review}` | **Deleted** | 9 obsolete DeepAgents markdown prompt directories; purged to keep codebase clean. |


---

## 8. Guidance for Subsequent Developers & Agents

1. **Avoid Unconstrained Agent Loops**:
   Do not use open-ended ReAct coordinators where the LLM decides both the workflow pipeline and termination criteria. Always use LangGraph `StateGraph` with explicit typed state.
2. **Keep Autonomy Bounded**:
   When giving an agent autonomy to invoke tools, place it in a designated node with a conditional edge checking `turn_count < MAX_TURNS` to prevent infinite loops.
3. **Indian Kanoon Scraper Etiquette**:
   Always reuse the cached functions in `backend/tools/indian_kanoon_tools.py`. Do not write raw scrapers that hammer `indiankanoon.org` without User-Agent headers or caching.
