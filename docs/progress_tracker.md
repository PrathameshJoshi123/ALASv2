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


| `backend/agents/jurist_rag_langgraph.py` | **Created** | Autonomous LangGraph Jurist RAG agent with pre-computed analysis grounding, hybrid chunk retrieval, and Indian Kanoon statutory search. |
| `backend/services/contract_revision_service.py` | **Created** | Service for AI-driven clause redrafting, custom prompt revision, and Indian Contract Act 1872 statutory compliance. |
| `backend/routes/contracts.py` | **Modified** | Connected QA endpoint to `run_jurist_rag`; added `POST /{document_id}/redraft-clause` and `POST /{document_id}/apply-revision`. |
| `frontend/services/api.ts` | **Modified** | Added `redraftClause` and `applyClauseRevision` API client functions. |
| `frontend/components/dashboard/ClauseRedlineModal.tsx` | **Created** | Interactive modal for side-by-side redline review, custom user edit prompts, bias selection, and revision application. |
| `frontend/app/dashboard/contracts/[id]/page.tsx` | **Modified** | Integrated "Edit & Redraft Clause" trigger on each analyzed clause card and mounted `ClauseRedlineModal`. |
| `frontend/components/dashboard/JuristChatDrawer.tsx` | **Modified** | Updated header to indicate Autonomous LangGraph RAG and added statutory quick-prompt shortcuts. |

---

## 8. Guidance for Subsequent Developers & Agents

1. **Avoid Unconstrained Agent Loops**:
   Do not use open-ended ReAct coordinators where the LLM decides both the workflow pipeline and termination criteria. Always use LangGraph `StateGraph` with explicit typed state.
2. **Keep Autonomy Bounded**:
   When giving an agent autonomy to invoke tools, place it in a designated node with a conditional edge checking `turn_count < MAX_TURNS` to prevent infinite loops.
3. **Indian Kanoon Scraper Etiquette**:
   Always reuse the cached functions in `backend/tools/indian_kanoon_tools.py`. Do not write raw scrapers that hammer `indiankanoon.org` without User-Agent headers or caching.
4. **Analysis Grounding for RAG & Redlining**:
   Always pass pre-computed `ContractAnalysis` (risk score, flagged clauses, Indian statutory citations) to both `jurist_rag_langgraph.py` and `contract_revision_service.py` so the assistant is context-aware.

---

## 9. Recent Feature Additions (Ask Jurist RAG & Post-Analysis Redlining)

### Ask Jurist Autonomous LangGraph RAG (`backend/agents/jurist_rag_langgraph.py`)
- Replaced the legacy `deepagents.create_deep_agent` in the QA endpoint with a compiled LangGraph `StateGraph`.
- **Pre-computed Analysis Grounding**: Reads parties, overall risk score, critical issues, and flagged clauses into the RAG state at intake.
- **Autonomous Multi-Turn Tool Loop**: The agent can call `hybrid_search_chunks`, `get_surrounding_chunks`, `get_all_document_chunks`, and `search_indian_kanoon` up to `MAX_RETRIEVAL_TURNS = 3`.
- **Strict Grounding**: Emits structured citations (`chunk_id`, page range, section titles, Indian Kanoon URLs) and anti-hallucination guardrails.

### Post-Analysis Contract Revision & Redlining (`ClauseRedlineModal.tsx` & `contract_revision_service.py`)
- **Backend Service**: Intelligently redrafts clauses considering original text, analysis risk flags, custom prompt instructions, and bias (Balanced, Client, Counterparty).
- **Statutory Guardrails**: Automatically remedies non-compete traps under Section 27 ICA and liquidated damage traps under Section 74 ICA.
- **Frontend Interactive UI**: Added an "Edit & Redraft Clause" button on each analyzed clause card opening a side-by-side comparison modal with live diffs and "Apply Revision to Contract" capability.

---

## 10. Contract Drafting & Generation Module Refactoring: Deterministic LangGraph, Dual Kanoon & Yahoo Scraping, and Real-Time SSE Streaming

### 10.1 Background & Root Causes of Prior Failure
The contract drafting and generation module (`backend/agents/contract_drafting_orchestrator.py`) previously suffered from severe non-determinism, vagueness, and opacity:
1. **Unconstrained & Vague ReAct Coordination**: Built on `deepagents.create_deep_agent`, the coordinator LLM decided subagent calls arbitrarily. It often skipped structural analysis, hallucinated legal research, or produced incomplete contracts with placeholder leakage (e.g. `[Insert standard indemnification clause]`).
2. **Brittle File-Based State Coordination**: State was dumped into virtual filesystem markdown files (`/memories/drafting_memory.md`, `/memories/drafted_contract.md`). Dropped tool calls broke downstream context.
3. **Hardcoded Statutory Text (Zero Genuine Research)**: The system previously relied on hardcoded dictionaries (`_CANONICAL_STATUTE_GUIDELINES`) rather than dynamically discovering, searching, and scraping relevant laws.
4. **Frontend Black Box (Fake Timer)**: The frontend (`tenant-files/page.tsx`) submitted a Celery task and spun on a fake 1.8-second timer (`loadingStep`) rotating through 5 static strings, completely disconnected from backend execution.

---

### 10.2 New Architecture: Deterministic LangGraph Drafting Engine

The drafting pipeline was refactored into a compiled **`StateGraph(ContractDraftingGraphState)`** in [`backend/agents/contract_drafting_langgraph.py`](file:///d:/My_Space/MajorProject/backend/agents/contract_drafting_langgraph.py):

```
                                      [START]
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │ node_intake_blueprint │  (Resolves mode: template, reiteration,
                             └───────────────────────┘   or prompt_only; identifies parties)
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │node_structure_extract │  (Constructs comprehensive section
                             └───────────────────────┘   blueprint matching Indian legal practice)
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │node_autonomous_legal_ │  (AUTONOMOUS DUAL SEARCH: Searches Indian
                             │       research        │   Kanoon Direct + Yahoo Legal Index live)
                             └───────────────────────┘
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │  node_section_writer  │  (Iterative drafter: Synthesizes formal
                             └───────────────────────┘   clauses incorporating scraped authorities)
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │node_compliance_review │  (Audits draft against Sec 27, 74, 28 ICA,
                             └───────────────────────┘   Arbitration Act 1996, & empty placeholders)
                                         │
                                         ▼
                               ┌───────────────────┐
                               │  Verdict Approved │
                               │  or Turns >= 2?   │
                               └───────────────────┘
                                  │             │
                          (Revise)│             │(Approved or Max Turns)
                                  ▼             ▼
                       ┌───────────────────┐  ┌───────────────────────┐
                       │node_targeted_revis│  │  node_final_assembly  │
                       └───────────────────┘  └───────────────────────┘
                                  │                         │
                                  └─────────►               ▼
                                                         [END]
```

#### Deterministic Spine & Bounded Loops:
* **Stage 1 (Intake Blueprint)**: Resolves execution mode (`template`, `reiteration`, `prompt_only`), party identities, and contract title.
* **Stage 2 (Structure Mapping)**: Formulates an exhaustive section blueprint with categories (Preamble, Definitions, Commercial, Protective, Boilerplate, Execution).
* **Stage 3 (Autonomous Legal Research)**: Deduces applicable Indian statutes and executes live dual-engine legal research.
* **Stage 4 (Section Writer)**: Sequentially drafts formal legal clauses grounded in the scraped legal findings. Under reiteration mode, it re-drafts only affected sections.
* **Stage 5 (Compliance Reviewer)**: Audits the compiled draft against Indian statutory mandates (Section 27 restraint of trade, Section 74 penalties vs damages, Section 28 limitations, and *Perkins Eastman* sole-arbitrator prohibitions).
* **Stage 6 (Targeted Reviser & Assembly)**: If compliance issues are detected, it enters a targeted revision cycle strictly capped at **2 iterations** before finalizing and formatting the contract.

---

### 10.3 Dual Legal Research Engine: Indian Kanoon Direct + Yahoo (DDGS)

All hardcoded statutory dictionaries were deleted from [`backend/tools/indian_kanoon_tools.py`](file:///d:/My_Space/MajorProject/backend/tools/indian_kanoon_tools.py). The system now conducts **live dual-engine search and web scraping**:

```
                   ┌────────────────────────────────────────────────────────┐
                   │        Targeted Indian Legal Research Query            │
                   └──────────────────┬───────────────────┬─────────────────┘
                                      │                   │
                                      ▼                   ▼
                 ┌─────────────────────────────┐ ┌─────────────────────────────┐
                 │  Method 1: Direct Kanoon    │ │  Method 2: Yahoo (DDGS)     │
                 │  https://indiankanoon.org/  │ │  backend='yahoo'            │
                 │  search/?formInput=...      │ │  site:indiankanoon.org ...  │
                 └──────────────┬──────────────┘ └──────────────┬──────────────┘
                                │                               │
                                └──────────────┬────────────────┘
                                               ▼
                              ┌──────────────────────────────────┐
                              │  Deduplicate by Doc ID & Merge   │
                              │  Tagging Engine Origin           │
                              └────────────────┬─────────────────┘
                                               ▼
                              ┌──────────────────────────────────┐
                              │ Live Scrape Full Statutory Text  │
                              │ & Ratio (indiankanoon.org/doc/X) │
                              └──────────────────────────────────┘
```

1. **Method 1: Direct Indian Kanoon Route (`search_via_kanoon_route`)**:
   - Queries `https://indiankanoon.org/search/?formInput={query}` directly with modern browser headers.
   - Parses `<article class="result">` and extracts case law links and Document IDs.
   - Tagged as `Source Engine: Indian Kanoon Direct`.
2. **Method 2: Yahoo Legal Index via DDGS (`search_via_ddgs`)**:
   - Executes `DDGS(timeout=10).text(..., backend="yahoo")` with concise candidate queries (`site:indiankanoon.org <keywords>` and `indian kanoon <keywords>`).
   - Discovers indexed statutory enactments, section definitions, and legal commentaries.
   - Tagged as `Source Engine: Yahoo Legal Index (DDGS)`.
3. **Doc ID Extraction & Web Scraping**:
   - Extracts numeric document identifiers via regex (`/doc(?:fragment)?/(\d+)`).
   - `fetch_kanoon_document_raw` downloads the canonical `https://indiankanoon.org/doc/{doc_id}/` page, decomposes ads/scripts/menus, and extracts the Court, Bench, Date, and verbatim ratio decidendi.

#### Verified Live Output (Query: `Section 27 Indian Contract Act restraint of trade`):
* **Indian Kanoon Direct**: *Wipro Limited vs Beckman Coulter* (Doc ID `647033`), *199th Law Commission Report on Unfair Terms* (Doc ID `140848451`), *Percept D'Mark vs Zaheer Khan* (Doc ID `571375`).
* **Yahoo Legal Index (DDGS)**: *Section 27 in The Indian Contract Act, 1872* statutory text (Doc ID `1431516`), *Section 26 ICA* (Doc ID `1269245`).

---

### 10.4 Real-Time Event Bus & Server-Sent Events (SSE)

To replace blind waiting and fake timers, an event streaming architecture was deployed:
* **Broadcaster Service (`backend/services/drafting_stream_service.py`)**:
  - Broadcasts structured JSON events to Redis Pub/Sub channel `draft_stream:{doc_id}`.
  - Persists an event history list in Redis `draft_events:{doc_id}` with a 24-hour TTL, ensuring late-joining frontends or refreshed pages instantly replay the entire drafting timeline.
  - Generates standard SSE formatting (`data: {...}\n\n`) with periodic keep-alive comments (`: ping\n\n`).
* **FastAPI Streaming Endpoints (`backend/routes/contracts.py`)**:
  - `GET /api/v1/contracts/{document_id}/draft/stream`: Direct SSE stream via `StreamingResponse(media_type="text/event-stream")`.
  - `GET /api/v1/contracts/{document_id}/draft/events`: REST polling fallback returning the cached event array.
  - `GET /api/v1/contracts/{document_id}/draft/logs`: Execution trace logs.
* **Celery Background Integration (`backend/tasks/drafting_tasks.py`)**:
  - Updated `run_agent_drafting_task` and `run_agent_reiteration_task` to instantiate `ContractDraftingLangGraphRunner`, publishing progress at every node transition.

---

### 10.5 Frontend Real-Time Console (`DraftingStreamConsole.tsx`)

A dedicated streaming component was built and mounted in [`frontend/app/dashboard/tenant-files/page.tsx`](file:///d:/My_Space/MajorProject/frontend/app/dashboard/tenant-files/page.tsx):
* **6-Stage Visual Stepper**:
  1. `Blueprint & Intake` (10% - 18%)
  2. `Structure Mapping` (25% - 35%)
  3. `Kanoon & Yahoo Legal Research` (40% - 52%)
  4. `Autonomous Clause Drafting` (55% - 75%)
  5. `Compliance Review & Audit` (80% - 90%)
  6. `Final Assembly` (95% - 100%)
* **Live Activity Terminal**:
  - Streams real-time legal queries, scraped Kanoon Document IDs, section titles being drafted, and reviewer audit scores.
* **Auto-Transition & Reconnection**:
  - When `is_complete` is received, it automatically triggers `fetchContractData()` and transitions seamlessly into the document editor.
  - Automatically falls back to REST polling if the SSE stream encounters network interruptions.

---

### 10.6 Summary of Created & Modified Files

| File Path | Action | Description |
| :--- | :--- | :--- |
| `backend/tools/indian_kanoon_tools.py` | **Modified** | Purged all hardcoded statutory lookup tables; implemented dual-engine search (`search_via_kanoon_route` + `search_via_ddgs` with `backend='yahoo'`); added live HTML document scraper `fetch_kanoon_document_raw`. |
| `backend/services/drafting_stream_service.py` | **Created** | Redis Pub/Sub event broadcaster (`draft_stream:{doc_id}`) with 24h event history cache (`draft_events:{doc_id}`) and async SSE generator with keep-alive pings. |
| `backend/agents/contract_drafting_langgraph.py` | **Created** | Full 6-stage deterministic LangGraph drafting state machine with bounded legal research and revision loops. |
| `backend/agents/contract_drafting_orchestrator.py` | **Refactored** | Removed legacy DeepAgents boilerplate; cleanly exports `ContractDraftingLangGraphRunner` and backward-compatible factories. |
| `backend/tasks/drafting_tasks.py` | **Modified** | Updated Celery drafting and reiteration tasks to run the LangGraph runner with real-time Redis streaming. |
| `backend/routes/contracts.py` | **Modified** | Added `GET /{document_id}/draft/stream` (SSE), `GET /{document_id}/draft/events`, and `GET /{document_id}/draft/logs`; added markdown code fence sanitization on draft retrieval. |
| `frontend/app/dashboard/tenant-files/page.tsx` | **Modified** | Added `cleanMarkdownForRendering()` to eliminate backtick code blocks; deduplicated `<h1>` titles; supported dynamic `targetId` contract loading. |
| `frontend/components/dashboard/DraftingStreamConsole.tsx` | **Modified** | Added live SSE and polling milestone timeline, terminal stream, and `onComplete(activeDocId)` handover. |
| `frontend/app/globals.css` | **Modified** | Added polished legal contract typography for `.contract-markdown.markdown-body` (headings, lists, spacing, tables). |
| `docs/progress_tracker.md` | **Updated** | Recorded Section 10 documenting the complete contract drafting refactoring, dual legal scraping engine, real-time streaming pipeline, and legal rendering bug fixes. |

---

### 10.7 Bug Fix & Hardening: Prompt-Only Document ID Resolution & Console Rendering

#### Incident & Symptoms:
When submitting a prompt-only contract drafting request from `/dashboard/templates`, the backend terminal showed:
```text
INFO: 127.0.0.1:61002 - "GET /api/v1/contracts/undefined/process/status/ea84bee8-0b8b-411c-a30a-aac777cfb0e7 HTTP/1.1" 404 Not Found
```
Meanwhile, the Celery background worker was actively executing Kanoon and Yahoo scraping:
```text
[KANOON_SEARCH (47%)] Querying Indian Kanoon & Yahoo Legal Index (3/4): 'Specific Relief Act, 1963...'
[KANOON_SCRAPE (49%)] Scraping statutory text & ratio for Kanoon Doc ID: 1028815...
```
However, the user's browser did not display the live streaming console ("working still not shown").

#### Root Cause Analysis:
1. **Schema Field Omission**: In `backend/routes/contracts.py`, `create_draft_contract_endpoint` created the new database document record, queued the Celery task, but returned `TaskSubmitResponse` which omitted `document_id`.
2. **URL Routing `undefined` Propagation**: `frontend/app/dashboard/templates/page.tsx` read `draftRes.document_id`, which was `undefined`, and routed to `/dashboard/tenant-files?generating=true&drafting=true&prompt=...&id=undefined&task_id=...`.
3. **Frontend Guard Blocking**: In `frontend/app/dashboard/tenant-files/page.tsx`, the component checked `if (isGenerating && contractId)`. Because `contractId` evaluated to `null` or the string `"undefined"`, the check blocked `DraftingStreamConsole` from rendering and fell through to the blank document editor while polling `/contracts/undefined/process/status/...` which threw 404s.

#### Solutions Implemented:
1. **Schema & Endpoint Updates**:
   - Added `document_id: Optional[str] = None` to both `TaskSubmitResponse` and `TaskStatusResponse` in `backend/schemas/task_schemas.py`.
   - Updated `create_draft_contract_endpoint`, `draft_contract_endpoint`, and `draft_contract_agent_only_endpoint` in `backend/routes/contracts.py` to always return `document_id=document.id`.
2. **Resilient Status Endpoint (`/process/status`)**:
   - Modified `get_processing_status` in `backend/routes/contracts.py` so that if `document_id in ("undefined", "null", "")`, it does **not** fail with 404; instead, it inspects Celery's `AsyncResult(task_id)` directly, extracts `document_id` from the task metadata, and returns HTTP 200 with the resolved `document_id`.
3. **Frontend Routing & Template Fix**:
   - Updated `frontend/app/dashboard/templates/page.tsx` to safely resolve `draftRes.document_id || draftRes.id` before routing.
4. **Console Rendering & Dynamic ID Resolution**:
   - Updated `frontend/app/dashboard/tenant-files/page.tsx` to sanitize `contractId` (ignoring string `"undefined"` / `"null"`), render `DraftingStreamConsole` whenever `isGenerating` is true, and automatically resolve `contractId` from `taskId`.
   - Updated `frontend/components/dashboard/DraftingStreamConsole.tsx` to maintain `activeDocId` and automatically query task status to obtain the real `document_id` and connect to the SSE stream.

---

### 10.8 Bug Fix & UI Hardening: Contract Markdown Rendering, Typography & Dynamic ID Handover

#### Incident & Symptoms:
When accessing the tenant-files editor with URL:
```text
http://localhost:3000/dashboard/tenant-files?generating=true&drafting=true&prompt=Draft+a+comprehensive+Master+Software+Development+and+Services+Agreement...&id=undefined&task_id=ea84bee8-0b8b-411c-a30a-aac777cfb0e7
```
The generated Master Services Agreement was displayed inside a monospace preformatted code block card (`<pre><code>`) with raw Markdown tokens (`## 1. Preamble and Recitals`, `**1.1. Introduction**`, `- **Apex HealthTech Solutions...**`) instead of formatted legal typography. A blinking text cursor was trapped inside the raw code block and a redundant duplicate title header was shown.

#### Root Cause Analysis:
1. **Code Fence Artifacts from LLM Specialist Writer**:
   - During autonomous section drafting in `backend/agents/contract_drafting_langgraph.py`, the LLM wrapped sections within Markdown code fences (`` ```markdown ... ``` `` or `` ``` ... ``` ``).
   - When assembled via `"\n\n---\n\n".join(sections)`, the document retained opening and closing backtick fences for all 12 sections.
2. **Markdown Parser Code Block Conversion**:
   - In `frontend/app/dashboard/tenant-files/page.tsx`, `marked.parse(content)` processed the code fences as HTML `<pre><code>` blocks.
   - Under `github-markdown-light.css` and `.contract-markdown.markdown-body pre`, the browser rendered each section as a bordered monospace box, preventing headings, bold party names, and lists from rendering.
3. **Duplicate Title Header**:
   - `DocumentEditor` unconditionally rendered `<h1 className="text-[32px] ...">{contract?.original_filename}</h1>`.
   - Because the drafted Markdown already contained `# MASTER SERVICES AGREEMENT...`, a duplicate header was displayed.
4. **Missing Handover of Resolved Document ID**:
   - When `id=undefined` was passed in query params, `DraftingStreamConsole` correctly resolved `activeDocId` via task status, but `onComplete()` did not forward `activeDocId` back to `TenantFilesPage`. As a result, the parent component could experience a delay or closure mismatch in fetching the newly drafted contract.

#### Solutions Implemented:
1. **Backend Agent Hardening (`contract_drafting_langgraph.py`)**:
   - Added `strip_markdown_code_fences()` helper using regex to purge standalone lines containing backtick fences (`^[ \t]*```[a-zA-Z0-9_-]*[ \t]*$`).
   - Updated `node_section_writer`, `node_targeted_reviser`, and `node_final_assembly` to enforce raw Markdown output and clean all sections before persisting to disk and memories.
2. **Route-Level Sanitization (`backend/routes/contracts.py`)**:
   - Hardened the `get_document` endpoint to sanitize `_drafted_contract.md` before returning `analysis_markdown` to API consumers.
3. **Disk & Memory Storage Cleanup**:
   - Sanitized existing draft and memory files for document `cf32d9ba-ec9f-426d-a399-1421e28cfad7` (task `ea84bee8-0b8b-411c-a30a-aac777cfb0e7`), eliminating all code fence lines.
4. **Frontend Markdown Sanitization & Title Deduplication (`tenant-files/page.tsx`)**:
   - Added `cleanMarkdownForRendering()` to remove any residual backtick fences prior to calling `marked.parse()`.
   - Updated `DocumentEditor` with a `hasH1InContent` check (`/^\s*<h1[\s>]/i.test(htmlContent)`), preventing duplicate fallback headers when the Markdown includes a top-level `#` title.
   - Enhanced `fetchContractData(isPolling, targetId)` to accept a target ID and immediately load the resolved document.
5. **Console Document ID Handover (`DraftingStreamConsole.tsx`)**:
   - Updated `onComplete` in `DraftingStreamConsoleProps` to accept `(resolvedDocId?: string) => void`.
   - Both SSE completion and REST polling completion now invoke `onComplete(activeDocId)`.
   - `TenantFilesPage` receives the resolved document ID, sets `contractId`, triggers `fetchContractData(false, finalId)`, and updates the browser URL to `id={finalId}&generated=true`.
6. **Professional Legal Typography (`globals.css`)**:
   - Enhanced `.contract-markdown.markdown-body` styling:
     - `h1`: 26px bold navy (`#0b1437`) with 2px bottom border.
     - `h2`: 18px bold navy with 1px bottom border and 36px top margin.
     - `h3`: 15px bold slate-900 with 24px top margin.
     - `p`: 15px readable text with 1.8 line height and 16px bottom margin.
     - `strong`: 600 weight navy for contracting entities and statutory references.
     - `ul`/`ol`/`li`: Proper padding, indentation, and list spacing.
     - `table`: Full-width bordered legal tables for consideration milestones and payment terms.


